"""
网络抓取层 - 福彩网 (cwl.gov.cn) + 多源 HTML 数据抓取.

底层从 curl_cffi + playwright 切换为 Scrapling:
  Layer 1: Fetcher.get               (HTTP + TLS 指纹, 最快, 默认)
  Layer 2: StealthyFetcher.fetch     (无头 Firefox + Cloudflare Turnstile 绕过)
  Layer 3: DynamicFetcher.fetch      (Playwright Chromium, 应对 SPA / 复杂 JS)

新增能力:
  - adaptive=True  (Scrapling 自适应选择器, 网站改版后自动重新定位元素)
  - solve_cloudflare=True  (StealthyFetcher 自带, 应对 cwl.gov.cn 的 CF 墙)
  - capture_xhr=True  (DynamicFetcher 可抓取页面的 XHR/fetch 响应, 备用)

设计: 每次 fetch 调用都是独立的 (不共享 FetcherSession),
      避免 gunicorn 多 worker / 多线程下的连接冲突.
"""
import logging
import random
import time
from typing import Optional, Dict, List, Any

from .parser import IssueParser

logger = logging.getLogger(__name__)

# ============================================================
# Scrapling 可选依赖导入
# ============================================================

try:
    from scrapling.fetchers import Fetcher, StealthyFetcher, DynamicFetcher
    from scrapling.parser import Adaptor
    _HAS_SCRAPLING = True
except ImportError:
    _HAS_SCRAPLING = False
    Fetcher = None  # type: ignore
    StealthyFetcher = None  # type: ignore
    DynamicFetcher = None  # type: ignore
    Adaptor = None  # type: ignore


# 反爬触发标志 (用于判断是否需要升级到 StealthyFetcher / DynamicFetcher)
_BLOCK_MARKERS = (
    'cloudflare',
    'attention required! | cloudflare',
    'checking your browser before accessing',
    'access denied',
    '禁止访问',
    '访问被拒绝',
    '访问频率过高',
    '请稍后再试',
    '验证码',
    'access forbidden',
    '403 forbidden',
    'service unavailable',
    '您的请求被拦截',
)


def _looks_blocked(html: str) -> bool:
    """检查 HTML 是否像是被反爬墙拦截 (而非真实数据缺失)."""
    if not html or len(html) < 500:
        return True
    lower = html.lower()
    return any(marker in lower for marker in _BLOCK_MARKERS)


def _decode_html_bytes(raw: bytes) -> str:
    """从 raw HTML bytes 解码出可读字符串 (处理 GBK / UTF-8 / GB18030).

    优先级:
      1. UTF-8 (含 BOM)
      2. GBK (国内彩票站常用, cwl.gov.cn 即是, meta 虽写 UTF-8 实际 GBK)
      3. GB18030 (GBK 超集, 兜底生僻字)
      4. UTF-8 with errors='replace' (最后兜底)
    """
    if not raw:
        return ''
    # BOM 检测
    if raw[:3] == b'\xef\xbb\xbf':
        return raw[3:].decode('utf-8', errors='replace')
    # GBK/GB18030 优先 (国内站点)
    for enc in ('gb18030', 'gbk', 'utf-8'):
        try:
            decoded = raw.decode(enc)
            # 简单启发式: 解码后含 ASCII 乱码比例 < 5% 视为成功
            if _looks_sane(decoded):
                return decoded
        except UnicodeDecodeError:
            continue
    # 最后兜底
    return raw.decode('utf-8', errors='replace')


def _looks_sane(s: str, max_replacement_ratio: float = 0.02) -> bool:
    """简单启发式: 字符串里含 U+FFFD (替换符) 比例是否过高."""
    if not s:
        return False
    bad = s.count('\ufffd')
    return (bad / len(s)) <= max_replacement_ratio


class CWLFetcher:
    """福彩网 + 多源 HTML 数据抓取器 (基于 Scrapling).

    公开方法 (与旧版兼容, 但实现换为 Scrapling 三层链):
      - fetch_html(url) -> Optional[str]   返回 HTML 字符串 (供 IssueParser.parse_cwl_html 使用)
      - fetch(url)      -> Response|None   返回 Scrapling Response (含 css/xpath 能力)
      - fetch_multi_page(max_pages)        批量抓取 cwl.gov.cn 历史数据
    """

    DEFAULT_BASE_URL = "https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/"
    DEFAULT_TIMEOUT = 15
    DEFAULT_DELAY_RANGE = (1.0, 2.5)

    # 反爬升级阈值: 连续 N 次被拦后跳到 StealthyFetcher
    BLOCKED_RETRY_THRESHOLD = 2

    def __init__(self, base_url: str = DEFAULT_BASE_URL,
                 timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout

        if not _HAS_SCRAPLING:
            logger.warning(
                "Scrapling 未安装, 抓取功能将受限. "
                "请运行: pip install \"scrapling[fetchers]>=0.4.15\" && scrapling install"
            )

    # ============================================================
    # 公共 API
    # ============================================================

    def fetch(self, url: str, allow_stealth: bool = True,
              allow_dynamic: bool = True):
        """抓取 URL, 三层 fallback, 返回 Scrapling Response 或 None.

        Args:
            url: 目标 URL
            allow_stealth: 失败时是否升级到 StealthyFetcher (反 Cloudflare)
            allow_dynamic: 失败时是否升级到 DynamicFetcher (Playwright JS 渲染)

        Returns:
            scrapling Response 对象 (有 .text, .css, .xpath 等)
            或 None (所有层都失败)
        """
        if not _HAS_SCRAPLING:
            logger.error("Scrapling 未安装, 无法抓取")
            return None

        # Layer 1: Fetcher (HTTP + TLS 指纹, 最快)
        resp = self._fetch_fast(url)
        if resp is not None and not _looks_blocked(self._get_content(resp)):
            return resp

        # Layer 2: StealthyFetcher (Firefox + 反 Cloudflare)
        if allow_stealth:
            logger.info(f"Layer 1 被拦, 升级到 StealthyFetcher: {url}")
            resp = self._fetch_stealthy(url)
            if resp is not None and not _looks_blocked(self._get_content(resp)):
                return resp

        # Layer 3: DynamicFetcher (Playwright Chromium, JS 渲染)
        if allow_dynamic:
            logger.info(f"Layer 2 被拦, 升级到 DynamicFetcher: {url}")
            resp = self._fetch_dynamic(url)
            if resp is not None:
                return resp

        logger.error(f"所有层都失败: {url}")
        return None

    @staticmethod
    def _get_content(resp) -> str:
        """从 Scrapling Response 安全获取 HTML 文本 (处理 gzip 响应 + 编码坑).

        Scrapling 0.4.x 的两个坑:
          1. .text 在 gzip 响应下返回空字符串
          2. .html_content 按 meta 声明的 charset 解码 (不准确, 遇到 cwl.gov.cn
             这种 meta 写 UTF-8 实际是 GBK 的页面会乱码)

        修法: 优先用 .body 原始字节, 用 BS4 自动检测编码 (from_encoding='chardet'
        在 html.parser 下效果跟 chardet 接近).
        """
        if resp is None:
            return ''
        # 优先用 raw bytes (Scrapling 自动解压 gzip)
        raw = getattr(resp, 'body', None)
        if isinstance(raw, (bytes, bytearray)) and raw:
            return _decode_html_bytes(raw)
        # 兜底: html_content (已解码字符串, 可能有编码错误)
        if hasattr(resp, 'html_content') and resp.html_content:
            hc = resp.html_content
            if isinstance(hc, str):
                return hc
        if hasattr(resp, 'text') and resp.text:
            t = resp.text
            if isinstance(t, str):
                return t
        return ''

    def fetch_html(self, url: str, **kwargs) -> Optional[str]:
        """抓取 URL, 返回 HTML 字符串 (与旧版签名兼容).

        供 IssueParser.parse_cwl_html(html) 等纯字符串解析使用.
        """
        resp = self.fetch(url, **kwargs)
        if resp is None:
            return None
        return self._get_content(resp)

    def fetch_page_response(self, url: str, adaptive: bool = True, **kwargs):
        """抓取 URL 并返回 Scrapling Response (启用 adaptive 选择器).

        供 IssueParser.parse_cwl_html_with_selector 等需要 CSS 选择器的解析使用.
        adaptive=True 时, 网站改版后选择器会自动重新定位.
        """
        resp = self.fetch(url, **kwargs)
        if resp is None:
            return None

        # 在 Response 上启用 adaptive (Scrapling 配置, 后续 css() 自动生效)
        if adaptive and Adaptor is not None:
            try:
                # 启用全局 adaptive 配置 (影响后续 .css() 调用)
                from scrapling.fetchers import Fetcher as _Fetcher
                _Fetcher.adaptive = True
                _Fetcher.adaptive_domain = url.split('/')[2] if '://' in url else url
            except Exception as e:
                logger.debug(f"启用 adaptive 失败 (非致命): {e}")

        return resp

    # ============================================================
    # Layer 1: Fetcher (HTTP + TLS 指纹, 最快)
    # ============================================================

    def _fetch_fast(self, url: str):
        """Scrapling Fetcher - HTTP 请求 + Chrome TLS 指纹 + 真实 headers."""
        try:
            return Fetcher.get(
                url,
                impersonate='chrome',
                stealthy_headers=True,   # 真实浏览器 headers 顺序
                timeout=self.timeout,
                follow_redirects=True,
                retries=2,               # 内置 2 次重试
            )
        except Exception as e:
            logger.debug(f"Fetcher 失败: {e}")
            return None

    # ============================================================
    # Layer 2: StealthyFetcher (Firefox 隐身 + Cloudflare 绕过)
    # ============================================================

    def _fetch_stealthy(self, url: str):
        """Scrapling StealthyFetcher - 改版 Firefox + 反 bot 检测 + Cloudflare Turnstile 自动解.

        应对 cwl.gov.cn 偶发的 Cloudflare 墙.
        """
        try:
            return StealthyFetcher.fetch(
                url,
                headless=True,
                solve_cloudflare=True,   # 自动解 Cloudflare Turnstile
                network_idle=True,       # 等网络空闲
                timeout=self.timeout * 2,  # 浏览器启动慢, 给更多时间
            )
        except Exception as e:
            logger.debug(f"StealthyFetcher 失败: {e}")
            return None

    # ============================================================
    # Layer 3: DynamicFetcher (Playwright Chromium, JS 渲染)
    # ============================================================

    def _fetch_dynamic(self, url: str):
        """Scrapling DynamicFetcher - 复用 Playwright Chromium 完整浏览器渲染.

        应对 500 彩票网 / 中彩网 偶尔上 JS 反爬 (SPA 骨架 HTML).
        """
        try:
            return DynamicFetcher.fetch(
                url,
                headless=True,
                network_idle=True,
                timeout=self.timeout * 2,
            )
        except Exception as e:
            logger.debug(f"DynamicFetcher 失败: {e}")
            return None

    # ============================================================
    # 批量抓取 - 多页
    # ============================================================

    # 福彩网官方 JSON API (从 lottery.js 反解, 比 HTML 稳定 10x)
    CWL_API_URL = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"

    def fetch_cwl_api(self, page_no: int = 1, page_size: int = 20) -> Dict:
        """从 cwl.gov.cn 官方 JSON API 抓取历史开奖数据.

        比 HTML 解析稳的原因:
          - 不依赖 DOM 结构 (前端改版不影响)
          - 字段结构化 (code/red/blue/date 直接对应)
          - 官方支持分页 (pageNo / pageSize / total 都在返回里)

        真实接口路径 (从 https://www.cwl.gov.cn/js/lottery.js 反解):
          https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice
            ?name=ssq
            &pageNo=1
            &pageSize=20
            &systemType=PC

        Returns:
            dict: {'success': bool, 'data': [...], 'source': 'cwl.gov.cn API', 'total': int}
        """
        params = {
            'name': 'ssq',
            'issueCount': '',
            'issueStart': '',
            'issueEnd': '',
            'dayStart': '',
            'dayEnd': '',
            'pageNo': str(page_no),
            'pageSize': str(page_size),
            'week': '',
            'systemType': 'PC',
        }
        from urllib.parse import urlencode
        url = f"{self.CWL_API_URL}?{urlencode(params)}"

        resp = self._fetch_fast(url)
        if resp is None:
            return {'success': False, 'message': f'API 请求失败: {url}'}

        body = self._get_content(resp)
        if not body:
            return {'success': False, 'message': 'API 响应为空'}

        # 解析 JSON
        import json as _json
        try:
            payload = _json.loads(body)
        except _json.JSONDecodeError as e:
            return {'success': False, 'message': f'JSON 解析失败: {e}', 'raw': body[:200]}

        if payload.get('state') != 0:
            return {
                'success': False,
                'message': f"API 报错: state={payload.get('state')}, msg={payload.get('message')}",
                'raw': payload,
            }

        records = IssueParser.parse_cwl_api_json(payload)
        return {
            'success': True,
            'data': records,
            'source': 'cwl.gov.cn API',
            'total': payload.get('total', len(records)),
            'page_num': payload.get('pageNum'),
            'page_no': payload.get('pageNo'),
        }

    def fetch_multi_page(self, max_pages: int = 100,
                         delay_range: tuple = DEFAULT_DELAY_RANGE,
                         prefer_api: bool = True) -> Dict:
        """从福彩网批量获取历史开奖信息.

        优先走官方 JSON API (prefer_api=True, 推荐), HTML 解析作为兜底.

        :param max_pages: 最大抓取页数 (默认 100 页)
        :param delay_range: 每页之间随机延迟 (秒)
        :param prefer_api: True=先试 JSON API; False=直接走 HTML (旧逻辑)
        :return: 标准格式字典 {'success': bool, 'data': [...], 'source': str, 'total': int}
        """
        all_records: List[Dict] = []

        # === 优先: JSON API 路径 ===
        if prefer_api:
            logger.info("优先走 cwl.gov.cn 官方 JSON API")
            api_result = self._fetch_multi_page_via_api(max_pages, delay_range)
            if api_result.get('success'):
                return api_result
            logger.warning("JSON API 路径失败, 降级到 HTML 解析路径")

        # === 兜底: HTML 解析路径 ===
        for p in range(1, max_pages + 1):
            url = self.base_url if p == 1 else f"{self.base_url}index_{p}.html"
            logger.info(f"正在抓取福彩网第 {p} 页: {url}")

            time.sleep(random.uniform(*delay_range))

            html = self.fetch_html(url)
            if not html:
                logger.warning(f"福彩网第 {p} 页获取失败或内容为空, 停止抓取")
                break

            records = IssueParser.parse_cwl_html(html)
            if not records:
                logger.info(f"福彩网第 {p} 页未解析到数据, 可能已到末页")
                break

            all_records.extend(records)
            logger.info(f"福彩网第 {p} 页成功解析 {len(records)} 条")
            if len(records) < 20:
                logger.info("检测到最后一页数据, 停止抓取")
                break

        if all_records:
            # 去重 + 按期号排序 (最新的在前)
            seen = set()
            unique_records = []
            for r in all_records:
                if r['issue'] not in seen:
                    seen.add(r['issue'])
                    unique_records.append(r)
            unique_records.sort(key=lambda x: x['issue'], reverse=True)

            return {
                'success': True,
                'data': unique_records,
                'source': 'cwl.gov.cn (HTML)',
                'total': len(unique_records)
            }

        return {'success': False, 'message': '福彩网数据获取失败, 请检查网络'}

    def _fetch_multi_page_via_api(self, max_pages: int, delay_range: tuple) -> Dict:
        """JSON API 多页抓取 (内部方法, 供 fetch_multi_page 调用)."""
        all_records: List[Dict] = []
        page_size = 30  # API 一次最多支持 30 条

        for p in range(1, max_pages + 1):
            time.sleep(random.uniform(*delay_range))
            result = self.fetch_cwl_api(page_no=p, page_size=page_size)
            if not result.get('success'):
                logger.warning(f"API 第 {p} 页失败: {result.get('message')}")
                break

            records = result.get('data', [])
            if not records:
                logger.info(f"API 第 {p} 页无数据, 已到末页")
                break

            all_records.extend(records)
            logger.info(f"API 第 {p} 页成功获取 {len(records)} 条 (累计 {len(all_records)})")

            # 末页检测
            total = result.get('total', 0)
            if total and len(all_records) >= total:
                logger.info(f"已获取全部 {total} 条记录")
                break
            if len(records) < page_size:
                logger.info("单页数据 < pageSize, 已到末页")
                break

        if all_records:
            # 去重 + 排序
            seen = set()
            unique = []
            for r in all_records:
                if r['issue'] not in seen:
                    seen.add(r['issue'])
                    unique.append(r)
            unique.sort(key=lambda x: x['issue'], reverse=True)
            return {
                'success': True,
                'data': unique,
                'source': 'cwl.gov.cn API',
                'total': len(unique),
            }
        return {'success': False, 'message': 'API 多页抓取全部失败'}
