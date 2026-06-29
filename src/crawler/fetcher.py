"""
网络抓取层 - 福彩网 HTML 数据抓取.

三层策略:
  - Layer 1: requests 直接请求 (最快, 默认)
  - Layer 1+ (优先): curl_cffi 伪造 TLS 指纹 (对抗反爬最有效, 模拟 Chrome 120)
  - Layer 2: Playwright + stealth_sync 无头浏览器 (兜底, 应对 JS 反爬)
"""
import logging
import random
import time
from typing import Optional, Dict, List, Any

import requests

from .parser import IssueParser

logger = logging.getLogger(__name__)

# 可选依赖导入
try:
    from fake_useragent import UserAgent
    _HAS_FAKE_UA = True
except ImportError:
    _HAS_FAKE_UA = False
    UserAgent = None  # type: ignore

try:
    from curl_cffi import requests as curl_requests
    _HAS_CURL_CFFI = True
except ImportError:
    _HAS_CURL_CFFI = False
    curl_requests = None  # type: ignore

try:
    from playwright.sync_api import sync_playwright
    from playwright_stealth import stealth_sync
    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False
    sync_playwright = None  # type: ignore
    stealth_sync = None  # type: ignore


class CWLFetcher:
    """福彩网 (cwl.gov.cn) 数据抓取器.

    设计: 每个 fetch 调用都是线程局部 (不共享 requests.Session),
    避免 gunicorn 多 worker / 多线程下的连接冲突.
    """

    DEFAULT_BASE_URL = "https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/"
    DEFAULT_TIMEOUT = 15
    DEFAULT_DELAY_RANGE = (1.0, 2.5)

    def __init__(self, base_url: str = DEFAULT_BASE_URL,
                 timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout

        if _HAS_FAKE_UA:
            self.ua = UserAgent()
        else:
            self.ua = None

    # ============================================================
    # 三层抓取调度
    # ============================================================

    def fetch_html(self, url: str) -> Optional[str]:
        """三层抓取: requests (含 curl_cffi 优先) -> Playwright -> 失败.

        Returns HTML string 或 None (所有层都失败).
        """
        # Layer 1: requests (含 curl_cffi 优先)
        try:
            html = self._fetch_with_requests(url)
            if html and len(html) > 2000:
                return html
        except Exception as e:
            logger.debug(f"Fetcher requests 失败: {e}")

        # Layer 2: Playwright
        try:
            html = self._fetch_with_playwright(url)
            if html and len(html) > 2000:
                return html
        except Exception as e:
            logger.error(f"Fetcher Playwright 失败: {e}")

        return None

    # ============================================================
    # Layer 1: requests / curl_cffi
    # ============================================================

    def _fetch_with_requests(self, url: str) -> str:
        """模拟真实浏览器会话 (curl_cffi 优先, 回退到标准 requests).

        每次调用新建 Session, 不在实例间共享 (线程安全).
        """
        # 生成随机的 headers (包括 UA)
        ua_str = self.ua.random if self.ua else (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        )
        headers = {
            'User-Agent': ua_str,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
                      'image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.cwl.gov.cn/',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        # 优先尝试 curl_cffi (TLS 指纹伪造)
        if _HAS_CURL_CFFI:
            try:
                logger.info(f"CWL 使用 curl_cffi 抓取: {url}")
                resp = curl_requests.get(
                    url, headers=headers, impersonate="chrome120",
                    timeout=self.timeout
                )
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                logger.warning(f"curl_cffi 抓取失败, 回退到 requests: {e}")

        # 回退到标准 requests (每次新建 Session)
        logger.info(f"CWL 使用标准 requests 抓取: {url}")
        session = requests.Session()

        # 先访问首页获取基础 Cookie
        try:
            session.get('https://www.cwl.gov.cn/', headers=headers, timeout=10)
            time.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            logger.debug(f"访问福彩网首页失败: {e}")

        # 访问目标页
        resp = session.get(url, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        return resp.text

    # ============================================================
    # Layer 2: Playwright + stealth
    # ============================================================

    def _fetch_with_playwright(self, url: str) -> Optional[str]:
        """无头浏览器渲染 (应对 JS 反爬)."""
        if not _HAS_PLAYWRIGHT:
            logger.error("Playwright 未安装, 请运行: pip install playwright playwright-stealth && playwright install chromium")
            return None

        try:
            ua_str = self.ua.random if self.ua else 'Mozilla/5.0 (X11; Linux x86_64)'

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=ua_str,
                    viewport={'width': 1920, 'height': 1080},
                    locale='zh-CN'
                )
                page = context.new_page()
                stealth_sync(page)

                page.goto(url, wait_until='networkidle', timeout=20000)

                # 等待表格或关键元素加载
                try:
                    page.wait_for_selector('table, .list-table, .data-table', timeout=8000)
                except Exception:
                    pass  # 不阻塞, 后续再做兜底

                time.sleep(1)
                html = page.content()
                browser.close()
                return html
        except Exception as e:
            logger.error(f"Playwright 抓取异常: {e}")
            return None

    # ============================================================
    # 批量抓取 - 多页
    # ============================================================

    def fetch_multi_page(self, max_pages: int = 100,
                         delay_range: tuple = DEFAULT_DELAY_RANGE) -> Dict:
        """从福彩网批量获取历史开奖信息.

        :param max_pages: 最大抓取页数 (默认 100 页, 覆盖全部历史数据)
        :param delay_range: 每页之间随机延迟 (秒)
        :return: 标准格式字典 {'success': bool, 'data': [...], 'source': 'cwl.gov.cn', 'total': int}
        """
        all_records: List[Dict] = []

        for p in range(1, max_pages + 1):
            url = self.base_url if p == 1 else f"{self.base_url}index_{p}.html"

            logger.info(f"正在抓取福彩网第 {p} 页: {url}")

            # 随机延迟, 避免触发频率限制
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

            # 单页数据少可能是末页
            if len(records) < 20:
                logger.info("检测到最后一页数据, 停止抓取")
                break

        if all_records:
            # 去重
            seen = set()
            unique_records = []
            for r in all_records:
                if r['issue'] not in seen:
                    seen.add(r['issue'])
                    unique_records.append(r)

            # 按期号排序 (最新的在前)
            unique_records.sort(key=lambda x: x['issue'], reverse=True)

            return {
                'success': True,
                'data': unique_records,
                'source': 'cwl.gov.cn',
                'total': len(unique_records)
            }

        return {'success': False, 'message': '福彩网数据获取失败, 请检查网络'}
