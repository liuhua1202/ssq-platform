"""
双色球历史数据模块
支持从 500 彩票网获取开奖信息
"""
import json
import os
import shutil
import re
import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 爬虫状态管理 - 防止请求线程被同步爬虫卡死
# ============================================================

import threading
from datetime import datetime, timedelta


class CrawlState:
    """线程安全的爬虫状态管理.

    功能:
      - 单线程执行: 同一时刻只有一个 fetch 在跑 (Lock)
      - 结果缓存: 最近一次成功结果缓存 60s, 重复请求直接返回缓存
      - 防抖: 避免恶意/频繁触发爬虫导致对方站点反爬升级

    使用场景:
      - /api/fetch-latest 和 /api/fetch-history 端点
    """

    DEFAULT_CACHE_TTL = 60  # 秒

    def __init__(self):
        self._lock = threading.Lock()
        self._last_result = None
        self._last_fetched_at = None
        self._cache_ttl = self.DEFAULT_CACHE_TTL

    def try_acquire(self) -> bool:
        """非阻塞获取锁. 成功返回 True, 失败 (锁被占用) 返回 False."""
        return self._lock.acquire(blocking=False)

    def release(self) -> None:
        """释放锁. 调用方必须先成功 try_acquire."""
        try:
            self._lock.release()
        except RuntimeError:
            # 锁已经被释放过 (try_acquire 返回 False 时不能 release)
            pass

    def get_cached(self):
        """获取缓存结果. 如果没缓存或已过期, 返回 None."""
        if self._last_result is None or self._last_fetched_at is None:
            return None
        age = (datetime.now() - self._last_fetched_at).total_seconds()
        if age > self._cache_ttl:
            return None
        return self._last_result

    def cache_result(self, result) -> None:
        """缓存成功的结果."""
        self._last_result = result
        self._last_fetched_at = datetime.now()

    def invalidate(self) -> None:
        """清空缓存."""
        self._last_result = None
        self._last_fetched_at = None

    def get_status(self) -> dict:
        """获取当前状态 (用于 /health 等监控端点).

        使用非阻塞 acquire 测试, 避免与持有锁的线程死锁.
        """
        # 非阻塞 acquire: 如果当前没人持有, 我们能拿到, 则不 busy
        # 如果已经有人持有, 非阻塞 acquire 失败, 则 busy
        got_lock = self._lock.acquire(blocking=False)
        if got_lock:
            self._lock.release()
            is_busy = False
        else:
            is_busy = True
        age = None
        if self._last_fetched_at:
            age = (datetime.now() - self._last_fetched_at).total_seconds()
        return {
            'is_busy': is_busy,
            'last_fetched_at': self._last_fetched_at.isoformat() if self._last_fetched_at else None,
            'last_result_age_seconds': age,
            'cache_ttl': self._cache_ttl,
            'has_cached_result': self._last_result is not None
        }


# 全局单例
_crawl_state = CrawlState()


def get_crawl_state() -> CrawlState:
    """获取全局爬虫状态单例."""
    return _crawl_state


# 可选依赖导入
try:
    from fake_useragent import UserAgent
    HAS_FAKE_UA = True
except ImportError:
    HAS_FAKE_UA = False
    UserAgent = None

try:
    from curl_cffi import requests as curl_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False
    curl_requests = None

try:
    from playwright.sync_api import sync_playwright
    from playwright_stealth import stealth_sync
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    sync_playwright = None
    stealth_sync = None

# 初始化 UserAgent
if HAS_FAKE_UA:
    ua = UserAgent()
else:
    ua = None


class Crawler:
    """双色球历史数据管理器"""

    def __init__(self, data_dir: str = None):
        # 使用统一的路径处理函数
        from config import get_base_path
        
        if data_dir is None:
            data_dir = os.path.join(get_base_path(), 'data')

        self.data_dir = os.path.abspath(data_dir)
        self.history_file = os.path.join(self.data_dir, "history.json")
        self.backup_dir = os.path.join(self.data_dir, "backup")
        # 确保目录存在
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)

    # ============================================================
    # Public API - 暴露给 api.py 调用的方法
    # 内部仍保留 _ 前缀方法作为私有实现
    # ============================================================

    def create_backup(self) -> None:
        """Public wrapper for _create_backup. 创建当前数据的备份."""
        self._create_backup()

    def parse_record(self, record):
        """Public wrapper for _parse_record. 解析单条 JSON/CSV 导入记录."""
        return self._parse_record(record)

    def parse_web_copy(self, data):
        """Public wrapper for _parse_web_copy. 解析从网页直接复制的数据."""
        return self._parse_web_copy(data)


    def fetch_latest_lottery(self) -> Dict:
        """从多个来源获取最新一期开奖信息（支持备用数据源）"""
        # 尝试多个数据源，按优先级排序
        sources = [
            # 来源 1: 500彩票网开奖页面 - 主数据源
            {
                'name': '500彩票网开奖页面',
                'url': 'https://kaijiang.500.com/ssq.shtml',
                'encoding': 'utf-8',
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9',
                }
            },
            # 来源 2: 中彩网 - 备用数据源
            {
                'name': '中彩网',
                'url': 'http://www.zhcw.com/ssq/',
                'encoding': 'utf-8',
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9',
                }
            },
            # 来源 3: 福彩官网 - 备用数据源
            {
                'name': '福彩官网',
                'url': 'https://www.cwl.gov.cn/ygkj/kjgg/ssq/',
                'encoding': 'utf-8',
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9',
                }
            },
        ]

        last_error = None
        failed_sources = []

        for source in sources:
            try:
                logger.info(f"尝试从 {source['name']} 获取数据...")
                result = self._fetch_latest_from_source(source['url'], source['encoding'], source['headers'])
                if result['success']:
                    logger.info(f"成功从 {source['name']} 获取数据")
                    return result
                else:
                    failed_sources.append(source['name'])
                    last_error = result.get('message', '未知错误')
                    logger.warning(f"{source['name']} 获取失败：{last_error}")
            except Exception as e:
                failed_sources.append(source['name'])
                last_error = repr(e)
                logger.error(f"{source['name']} 异常：{repr(e)}")
                continue

        error_detail = f"所有数据源均获取失败。失败源：{', '.join(failed_sources)}。最后错误：{last_error}"
        logger.error(error_detail)

        return {
            'success': False,
            'message': error_detail
        }

    def _convert_issue(self, issue: str) -> str:
        """将简写期号转换为 7 位标准格式"""
        if len(issue) == 5:
            return '20' + issue
        if len(issue) == 6 and not issue.startswith('202'):
            return '20' + issue
        return issue

    def _extract_issue(self, soup) -> Optional[str]:
        """从 HTML 中提取期号，按可靠性排序的多种策略"""
        import re

        def _find_and_convert(text: str) -> Optional[str]:
            """从文本中提取期号并转换"""
            match = re.search(r'(\d{5,7})', text)
            if match:
                return self._convert_issue(match.group(1))
            return None

        # 策略 1: table-title class（500 网最可靠）
        for tag in soup.find_all(class_='table-title'):
            text = tag.get_text(strip=True)
            if '期' in text:
                result = _find_and_convert(text)
                if result:
                    return result

        # 策略 2: 查找包含"期"字的关键元素
        for tag in soup.find_all(['td', 'th', 'em', 'strong']):
            text = tag.get_text(strip=True)
            if '期' in text:
                result = _find_and_convert(text)
                if result:
                    return result

        # 策略 3: 查找特定 class 元素
        for class_name in ['lottery', 'issue', 'period', 'title', 'header', 'cont', 'main']:
            el = soup.find(class_=lambda x: x and class_name in x.lower())
            if el:
                text = el.get_text(strip=True)
                result = _find_and_convert(text)
                if result:
                    return result

        # 策略 4: 从页面标题中提取
        title = soup.find('title')
        if title:
            text = title.get_text(strip=True)
            result = _find_and_convert(text)
            if result:
                return result

        # 策略 5: 从 meta 标签中查找
        for meta in soup.find_all('meta'):
            content = meta.get('content', '')
            if content and '期' in content:
                result = _find_and_convert(content)
                if result:
                    return result

        # 策略 6: 查找紧邻"开奖"二字的数字
        for tag in soup.find_all(['span', 'div', 'p']):
            text = tag.get_text(strip=True)
            if '开奖' in text:
                result = _find_and_convert(text)
                if result:
                    return result

        return None

    def _fetch_latest_from_source(self, url: str, encoding: str, headers: dict) -> Dict:
        """从指定 URL 获取最新开奖信息"""
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            # 处理编码问题
            if encoding == 'gbk':
                try:
                    html = response.content.decode('gbk')
                except UnicodeDecodeError:
                    try:
                        html = response.content.decode('gb18030')
                    except UnicodeDecodeError:
                        html = response.content.decode('utf-8', errors='ignore')
            else:
                html = response.text

            soup = BeautifulSoup(html, 'html.parser')

            # 查找期号和号码 - 针对 kaijiang.500.com 结构优化
            issue = None
            red_balls = []
            blue_ball = None
            date = None

            # 方法 1: 查找 draw-table 表格
            table = soup.find('table', class_='draw-table')
            if table:
                rows = table.find_all('tr')
                if len(rows) > 1:
                    # 第一行是表头，第二行是最新数据
                    cells = rows[1].find_all(['td', 'th'])
                    if len(cells) >= 3:
                        issue_text = cells[0].get_text(strip=True)
                        balls_text = cells[1].get_text(strip=True)
                        date_text = cells[2].get_text(strip=True)
                        
                        # 提取期号
                        issue_match = re.search(r'(\d+)期', issue_text)
                        if issue_match:
                            issue = self._convert_issue(issue_match.group(1))
                        
                        # 提取号码（7位数字连在一起）
                        if balls_text != '待开奖':
                            balls_match = re.findall(r'\d', balls_text)
                            if len(balls_match) == 7:
                                red_balls = sorted([int(x) for x in balls_match[:6]])
                                blue_ball = int(balls_match[6])
                        
                        # 提取日期
                        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', date_text)
                        if date_match:
                            date = date_match.group(1)

            # 方法 2: 如果表格没找到，使用原有逻辑
            if not issue or len(red_balls) < 6 or blue_ball is None:
                issue = self._extract_issue(soup)
                
                if len(red_balls) < 6 or blue_ball is None:
                    all_numbers = []
                    for tag in soup.find_all(['td', 'span', 'div', 'em', 'strong', 'li']):
                        text = tag.get_text(strip=True)
                        if text.isdigit():
                            num = int(text)
                            all_numbers.append(num)

                    seen = set()
                    unique_nums = []
                    for n in all_numbers:
                        if n not in seen:
                            seen.add(n)
                            unique_nums.append(n)

                    if len(red_balls) < 6:
                        red_balls = []
                        for n in unique_nums:
                            if 1 <= n <= 33 and n not in red_balls:
                                red_balls.append(n)
                                if len(red_balls) == 6:
                                    break

                    if blue_ball is None:
                        for n in unique_nums:
                            if 1 <= n <= 16 and n not in red_balls:
                                blue_ball = n
                                break

            if not date:
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', html)
                date = date_match.group(1) if date_match else datetime.now().strftime('%Y-%m-%d')

            valid_issue = bool(issue) and re.match(r'^\d{5,7}$', issue)

            if len(red_balls) == 6 and blue_ball and valid_issue:
                return {
                    'success': True,
                    'issue': issue,
                    'date': date,
                    'red_balls': sorted(red_balls),
                    'blue_ball': blue_ball
                }

            return {
                'success': False,
                'message': f'解析失败：期号={issue}, 红球数={len(red_balls)}, 蓝球={blue_ball}'
            }
        except requests.RequestException as e:
            return {
                'success': False,
                'message': f'网络请求失败：{str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'获取失败：{str(e)}'
            }

    def fetch_lottery_history(self, page: int = 1, page_size: int = 20) -> Dict:
        """从多个来源获取历史开奖记录"""
        sources = [
            # 来源 1: 500彩票网主页面（包含最近10期历史）
            {
                'url': "https://kaijiang.500.com/ssq.shtml",
                'encoding': 'utf-8',
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9',
                    'Referer': 'https://www.500.com/',
                    'Connection': 'keep-alive',
                }
            },
        ]

        last_error = None
        for source in sources:
            try:
                result = self._fetch_history_from_source(source['url'], source['encoding'], source['headers'], page_size)
                if result['success']:
                    return result
                last_error = result.get('message', '未知错误')
            except Exception as e:
                last_error = str(e)
                logger.warning(f"来源 {source['url']} 获取失败：{e}")
                continue

        return {
            'success': False,
            'message': f'所有数据源均获取失败：{last_error}'
        }

    def _fetch_history_from_source(self, url: str, encoding: str, headers: dict, page_size: int) -> Dict:
        """从指定 URL 获取历史开奖记录"""
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # 处理编码
        if encoding == 'gbk':
            html = response.content.decode('gbk', errors='ignore')
        else:
            html = response.text

        soup = BeautifulSoup(html, 'html.parser')
        lottery_data = []

        # 方法 1: 从 lottery-page-bottom 区域提取（主页面）
        history_section = soup.find(class_='lottery-page-bottom')
        if history_section:
            logger.info("找到 lottery-page-bottom 区域")
            issue_links = history_section.find_all('a', href=True)
            
            for link in issue_links:
                href = link['href']
                text = link.get_text(strip=True)
                
                # 从href中提取期号
                issue_match = re.search(r'kaijiang/ssq/(\d{5,6})\.html', href)
                if issue_match:
                    issue = self._convert_issue(issue_match.group(1))  # 转换为7位标准格式
                    
                    # 从文本中提取日期和号码
                    numbers_in_text = re.findall(r'\d+', text)
                    
                    # 提取日期（格式：2026-04-28）
                    date = None
                    for num_str in numbers_in_text:
                        if len(num_str) == 4 and num_str.startswith('20'):  # 年份
                            # 查找后续的月份和日期
                            year_idx = numbers_in_text.index(num_str)
                            if year_idx + 3 <= len(numbers_in_text):
                                year = num_str
                                month = numbers_in_text[year_idx + 1]
                                day = numbers_in_text[year_idx + 2]
                                if len(month) == 2 and len(day) == 2:
                                    date = f"{year}-{month}-{day}"
                                    break
                    
                    # 提取14位号码字符串
                    for num_str in numbers_in_text:
                        if len(num_str) == 14:
                            red_balls = sorted([int(num_str[i:i+2]) for i in range(0, 12, 2)])
                            blue_ball = int(num_str[12:14])
                            
                            # 验证号码范围
                            if all(1 <= r <= 33 for r in red_balls) and 1 <= blue_ball <= 16:
                                lottery_data.append({
                                    'issue': issue,
                                    'date': date or datetime.now().strftime('%Y-%m-%d'),
                                    'red_balls': red_balls,
                                    'blue_ball': blue_ball
                                })
                                logger.debug(f"解析成功: {issue}")
                            break
            
            logger.info(f"从 lottery-page-bottom 解析到 {len(lottery_data)} 条记录")
        
        # 方法 2: 查找 custom-table 表格（历史页面）
        if not lottery_data:
            table = soup.find('table', class_='custom-table')
            if table:
                rows = table.find_all('tr')
                logger.info(f"找到 custom-table，共 {len(rows)} 行")
                # 跳过前两行表头，从第3行开始是数据
                for row in rows[2:]:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        try:
                            issue = cells[0].get_text(strip=True)
                            date_time = cells[1].get_text(strip=True)
                            balls_text = cells[2].get_text(strip=True)
                            
                            # 验证期号（可能是5位或6位数字）
                            if not issue or not re.match(r'^\d{5,6}$', issue):
                                logger.debug(f"期号格式不符: {issue}")
                                continue
                            
                            # 转换为7位标准格式
                            issue = self._convert_issue(issue)
                            
                            # 提取日期
                            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', date_time)
                            date = date_match.group(1) if date_match else datetime.now().strftime('%Y-%m-%d')
                            
                            # 提取号码（14位数字连在一起，每2位是一个号码）
                            if balls_text and len(balls_text) == 14:
                                # 每2位数字组成一个号码
                                balls = [int(balls_text[i:i+2]) for i in range(0, 14, 2)]
                                if len(balls) == 7:
                                    red_balls = sorted(balls[:6])
                                    blue_ball = balls[6]
                                    
                                    # 验证号码范围
                                    if all(1 <= r <= 33 for r in red_balls) and 1 <= blue_ball <= 16:
                                        lottery_data.append({
                                            'issue': issue,
                                            'date': date,
                                            'red_balls': red_balls,
                                            'blue_ball': blue_ball
                                        })
                                        logger.debug(f"解析成功: {issue}")
                                    else:
                                        logger.debug(f"号码范围验证失败: red={red_balls}, blue={blue_ball}")
                                else:
                                    logger.debug(f"号码数量不符: {len(balls)}, balls_text={balls_text}")
                        except Exception as e:
                            logger.debug(f"解析行失败: {e}")
                            continue
                
                logger.info(f"从 custom-table 解析到 {len(lottery_data)} 条记录")
        
        # 如果没找到 custom-table，尝试其他表格
        if not lottery_data:
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 8:
                        cell_texts = [c.get_text(strip=True) for c in cells]

                        # 查找期号（通常是 6 位数字）
                        issue = None
                        for text in cell_texts:
                            if re.match(r'^\d{6,}$', text):
                                issue = text
                                break

                        # 查找红球
                        red_balls = []
                        for text in cell_texts:
                            if text.isdigit() and 1 <= int(text) <= 33:
                                num = int(text)
                                if num not in red_balls and len(red_balls) < 6:
                                    red_balls.append(num)

                        # 查找蓝球
                        blue_ball = None
                        for text in cell_texts:
                            if text.isdigit():
                                num = int(text)
                                if 1 <= num <= 16 and num not in red_balls:
                                    blue_ball = num
                                    break

                        # 查找日期
                        date = None
                        for text in cell_texts:
                            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
                            if date_match:
                                date = date_match.group(1)
                                break

                        if issue and len(red_balls) == 6 and blue_ball:
                            lottery_data.append({
                                'issue': issue,
                                'date': date or datetime.now().strftime('%Y-%m-%d'),
                                'red_balls': sorted(red_balls),
                                'blue_ball': blue_ball
                            })

        # 方法 2: 遍历所有 tr 查找
        if not lottery_data:
            all_trs = soup.find_all('tr')
            for tr in all_trs:
                tds = tr.find_all('td')
                if len(tds) >= 5:
                    cell_texts = [td.get_text(strip=True) for td in tds]

                    issue = None
                    for text in cell_texts:
                        if re.match(r'^\d{6,}$', text):
                            issue = text
                            break

                    if issue:
                        red_balls = []
                        for text in cell_texts:
                            if text.isdigit() and 1 <= int(text) <= 33:
                                num = int(text)
                                if num not in red_balls and len(red_balls) < 6:
                                    red_balls.append(num)

                        blue_ball = None
                        for text in cell_texts:
                            if text.isdigit():
                                num = int(text)
                                if 1 <= num <= 16 and num not in red_balls:
                                    blue_ball = num
                                    break

                        date = None
                        for text in cell_texts:
                            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
                            if date_match:
                                date = date_match.group(1)
                                break

                        if issue and len(red_balls) == 6 and blue_ball:
                            exists = any(d['issue'] == issue for d in lottery_data)
                            if not exists:
                                lottery_data.append({
                                    'issue': issue,
                                    'date': date or datetime.now().strftime('%Y-%m-%d'),
                                    'red_balls': sorted(red_balls),
                                    'blue_ball': blue_ball
                                })

        if lottery_data:
            seen = set()
            unique_data = []
            for item in lottery_data:
                if item['issue'] not in seen:
                    seen.add(item['issue'])
                    unique_data.append(item)

            return {
                'success': True,
                'data': unique_data[:page_size],
                'page': 1,
                'total': len(unique_data)
            }

        return {
            'success': False,
            'message': '未找到开奖数据，请检查网页结构是否变化'
        }

    def load_history(self) -> List[Dict]:
        """加载本地历史数据"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"已加载 {len(data)} 条历史数据")
                    return data
            except Exception as e:
                logger.warning(f"加载历史数据失败：{e}")
                return self._restore_from_backup()
        else:
            logger.info("历史数据文件不存在，将创建新文件")
            return []

    def _restore_from_backup(self) -> List[Dict]:
        """从备份文件恢复数据"""
        if not os.path.exists(self.backup_dir):
            return []

        backup_files = [f for f in os.listdir(self.backup_dir) if f.endswith('.json')]
        if not backup_files:
            return []

        latest_backup = max(backup_files)
        backup_path = os.path.join(self.backup_dir, latest_backup)

        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"从备份文件恢复 {len(data)} 条历史数据")
                return data
        except Exception as e:
            logger.warning(f"从备份恢复失败：{e}")
            return []

    def save_history(self, data: List[Dict], backup: bool = True) -> None:
        """保存历史数据到本地，并创建备份"""
        os.makedirs(self.data_dir, exist_ok=True)

        # 只有在 backup=True 且文件已存在时才创建备份
        if backup and os.path.exists(self.history_file):
            self._create_backup()

        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"历史数据已保存：{len(data)} 条记录")

    def _create_backup(self) -> None:
        """创建当前数据的备份"""
        if not os.path.exists(self.history_file):
            return

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(self.backup_dir, f'history_{timestamp}.json')

        try:
            shutil.copy2(self.history_file, backup_file)
            logger.info(f"已创建备份：{backup_file}")
            self._cleanup_old_backups()
        except Exception as e:
            logger.warning(f"创建备份失败：{e}")

    def _cleanup_old_backups(self, keep_count: int = 5) -> None:
        """清理旧备份文件"""
        if not os.path.exists(self.backup_dir):
            return

        backup_files = sorted([f for f in os.listdir(self.backup_dir) if f.endswith('.json')])

        while len(backup_files) > keep_count:
            oldest = backup_files.pop(0)
            os.remove(os.path.join(self.backup_dir, oldest))
            logger.info(f"已删除旧备份：{oldest}")

    def _parse_web_copy(self, data: Dict) -> Optional[Dict]:
        """
        解析从网页直接复制的数据

        支持格式：
        1. 开奖号码连在一起：如 "36132128296" -> 红球 [3,6,13,21,28,29] + 蓝球 6
        2. 开奖号码连在一起：如 "13111831332" -> 红球 [13,11,18,31,33] + 蓝球 2
        """
        try:
            issue = data.get('issue', '').strip()
            date = data.get('date', '').strip() if data.get('date') else None
            balls_str = data.get('balls', '').strip() if data.get('balls') else None

            if not issue or not balls_str:
                return None

            if not issue.isdigit():
                return None

            parsed_date = None
            if date:
                date_match = re.match(r'(\d{4}-\d{2}-\d{2})', date)
                if date_match:
                    parsed_date = date_match.group(1)

            balls_str = balls_str.replace(' ', '')

            result = self._parse_seven_numbers(balls_str)

            if not result or len(result) != 7:
                return None

            red_balls = result[:6]
            blue_ball = result[6]

            if not all(1 <= r <= 33 for r in red_balls):
                return None
            if not 1 <= blue_ball <= 16:
                return None

            return {
                'issue': issue,
                'date': parsed_date,
                'red_balls': sorted(red_balls),
                'blue_ball': blue_ball,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.warning(f"解析网页复制数据失败：{e}")
            return None

    def _parse_seven_numbers(self, s: str) -> Optional[List[int]]:
        """
        解析字符串为 7 个数字（6 红球 +1 蓝球）

        策略：从后往前解析，先确定蓝球，再解析红球
        """
        if not s or not s.isdigit():
            return None

        blue_candidates = []

        if len(s) >= 2:
            blue_2 = int(s[-2:])
            if 10 <= blue_2 <= 16:
                blue_candidates.append((blue_2, s[:-2]))

        blue_1 = int(s[-1:])
        if 1 <= blue_1 <= 16:
            blue_candidates.append((blue_1, s[:-1]))

        for blue_ball, red_str in blue_candidates:
            red_balls = self._parse_six_red_balls(red_str)
            if red_balls and len(red_balls) == 6:
                return red_balls + [blue_ball]

        return None

    def _parse_six_red_balls(self, s: str) -> Optional[List[int]]:
        """
        解析 6 个红球（每个 1-33）
        优化策略：从后往前匹配，优先匹配末尾的号码，自动忽略开头的期号/日期
        """
        if not s:
            return None

        result = []
        idx = len(s)
        
        # 从后往前扫描，尝试提取 6 个红球
        while len(result) < 6 and idx > 0:
            matched = False
            
            # 策略 1: 优先尝试匹配 2 位数 (10-33)
            if idx >= 2:
                num = int(s[idx-2:idx])
                if 10 <= num <= 33:
                    result.append(num)
                    idx -= 2
                    matched = True
                    continue
            
            # 策略 2: 尝试匹配 1 位数 (1-9)
            # 注意：只有当不是 2 位数的一部分时才匹配 1 位数
            # 例如 "12"，如果 12 是有效红球，就不应该拆成 1 和 2
            if not matched and idx >= 1:
                num = int(s[idx-1:idx])
                if 1 <= num <= 33:
                    result.append(num)
                    idx -= 1
                    matched = True
                    continue
            
            # 如果当前字符无法匹配任何有效红球（可能是期号残留），则跳过
            if not matched:
                idx -= 1

        # 如果成功找到 6 个红球，反转回正序
        if len(result) == 6:
            return result[::-1]
        
        return None

    def _parse_record(self, record: Dict) -> Optional[Dict]:
        """解析单条记录（用于 JSON/CSV 导入）"""
        try:
            issue = record.get('issue', record.get('expectNum', record.get('lotteryIssue')))
            date = record.get('date', record.get('lotteryDrawTime', record.get('openTime')))
            red_balls = record.get('red', record.get('redBall', record.get('redBalls', record.get('red_balls', []))))
            blue_ball = record.get('blue', record.get('blueBall', record.get('blue_ball', None)))

            if isinstance(red_balls, str):
                red_balls = [int(x) for x in red_balls.replace(',', ' ').split()]

            if not red_balls or not blue_ball:
                return None

            red_balls = sorted([int(x) for x in red_balls])
            blue_ball = int(blue_ball)

            if len(red_balls) != 6:
                return None
            if not all(1 <= r <= 33 for r in red_balls):
                return None
            if not 1 <= blue_ball <= 16:
                return None

            return {
                'issue': str(issue),
                'date': str(date)[:10] if date else None,
                'red_balls': red_balls,
                'blue_ball': blue_ball,
                'timestamp': datetime.now().isoformat()
            }
        except Exception:
            return None

    def fetch_cwl_lottery(self, max_pages: int = 100) -> Dict:
        """
        从福彩网批量获取历史开奖信息（带完整反爬应对）
        :param max_pages: 最大抓取页数（默认100页，覆盖全部历史数据）
        :return: 标准格式字典
        """
        base_url = "https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/"
        all_records = []
        
        # 福彩网分页规律通常是 index_1.html, index_2.html... 首页是 index.html 或 index_1.html
        # 我们尝试通用模式
        
        for p in range(1, max_pages + 1):
            # 构造 URL
            if p == 1:
                url = base_url
            else:
                url = f"{base_url}index_{p}.html"
            
            logger.info(f"正在抓取福彩网第 {p} 页: {url}")
            
            # 随机延迟，避免触发频率限制
            time.sleep(random.uniform(1.0, 2.5))
            
            html = self._fetch_cwl_html(url)
            if not html:
                logger.warning(f"福彩网第 {p} 页获取失败或内容为空，停止抓取")
                break
                
            records = self._parse_cwl_html_robust(html)
            
            if not records:
                logger.info(f"福彩网第 {p} 页未解析到数据，可能已到末页")
                break
            
            all_records.extend(records)
            logger.info(f"福彩网第 {p} 页成功解析 {len(records)} 条")
            
            # 如果某一页数据很少（比如少于 20 条），可能是最后一页
            if len(records) < 20:
                logger.info("检测到最后一页数据，停止抓取")
                break

        if all_records:
            # 去重
            seen = set()
            unique_records = []
            for r in all_records:
                if r['issue'] not in seen:
                    seen.add(r['issue'])
                    unique_records.append(r)
            
            # 按期号排序（最新的在前）
            unique_records.sort(key=lambda x: x['issue'], reverse=True)
            
            return {
                'success': True,
                'data': unique_records,
                'source': 'cwl.gov.cn',
                'total': len(unique_records)
            }
        return {'success': False, 'message': '福彩网数据获取失败，请检查网络'}

    def _fetch_cwl_html(self, url: str) -> Optional[str]:
        """三层抓取策略：Requests -> Playwright -> 降级"""
        # Layer 1: requests 直接请求（最快）
        try:
            html = self._fetch_with_requests(url)
            if html and len(html) > 2000:  # 基础完整性校验
                return html
        except Exception as e:
            logger.debug(f"福彩网 requests 失败: {e}")

        # Layer 2: Playwright 兜底（最稳）
        try:
            html = self._fetch_with_playwright(url)
            if html and len(html) > 2000:
                return html
        except Exception as e:
            logger.error(f"福彩网 Playwright 失败: {e}")

        return None

    def _fetch_with_requests(self, url: str) -> str:
        """Layer 1: 模拟真实浏览器会话（优化版 - 优先使用 curl_cffi 伪造 TLS 指纹）"""
        headers = {
            'User-Agent': ua.random if ua else 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.cwl.gov.cn/',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # 优先尝试 curl_cffi (TLS 指纹伪造，对抗反爬最有效)
        if HAS_CURL_CFFI:
            try:
                logger.info(f"使用 curl_cffi 抓取: {url}")
                # impersonate="chrome120" 会模拟 Chrome 120 的 TLS 指纹
                resp = curl_requests.get(url, headers=headers, impersonate="chrome120", timeout=15)
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                logger.warning(f"curl_cffi 抓取失败，回退到 requests: {e}")

        # 回退到标准 requests
        logger.info(f"使用标准 requests 抓取: {url}")
        session = requests.Session()
        
        # 先访问首页获取基础 Cookie
        try:
            session.get('https://www.cwl.gov.cn/', headers=headers, timeout=10)
            time.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            logger.debug(f"访问福彩网首页失败: {e}")
        
        # 访问目标页
        resp = session.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.text

    def _fetch_with_playwright(self, url: str) -> Optional[str]:
        """Layer 2: 无头浏览器渲染（应对 JS 反爬）"""
        try:
            from playwright.sync_api import sync_playwright
            from playwright_stealth import stealth_sync
        except ImportError:
            logger.error("Playwright 未安装，请运行: pip install playwright playwright-stealth && playwright install chromium")
            return None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=ua.random,
                    viewport={'width': 1920, 'height': 1080},
                    locale='zh-CN'
                )
                page = context.new_page()
                
                # 应用 stealth 插件，隐藏自动化特征
                stealth_sync(page)
                
                page.goto(url, wait_until='networkidle', timeout=20000)
                
                # 等待表格或关键元素加载
                try:
                    page.wait_for_selector('table, .list-table, .data-table', timeout=8000)
                except:
                    pass
                
                time.sleep(1)
                html = page.content()
                browser.close()
                return html
        except Exception as e:
            logger.error(f"Playwright 抓取异常: {e}")
            return None

    def _parse_cwl_html_robust(self, html: str) -> List[Dict]:
        """
        增强版解析器：针对福彩网结构优化，提取所有数字组合
        """
        soup = BeautifulSoup(html, 'html.parser')
        records = []
        
        # 策略 1: 查找所有行 (tr)
        rows = soup.find_all('tr')
        
        for row in rows:
            # 获取所有单元格的文本
            cells = row.find_all(['td', 'th'])
            if len(cells) < 3:
                continue
                
            # 提取每个单元格的文本
            cell_texts = [c.get_text(strip=True) for c in cells]
            full_text = ' '.join(cell_texts)
            
            # 跳过表头或统计行
            if '期号' in full_text or '开奖日期' in full_text or '销售额' in full_text:
                continue
                
            # 提取所有连续的数字块
            nums = re.findall(r'\d+', full_text)
            
            # 过滤掉太短的数字（如页码、统计数字）
            # 我们需要：期号(7位) + 日期(8位) + 7个球号(1-2位)
            if len(nums) < 8:
                continue
                
            issue = None
            date = None
            
            # 1. 找期号 (通常是 7 位数字，如 2024001)
            potential_issue = [n for n in nums if len(n) == 7 and n.startswith('20')]
            if not potential_issue:
                continue
            issue = potential_issue[0]
            
            # 2. 找日期 (通常是 8 位数字 20240101)
            potential_date = [n for n in nums if len(n) == 8 and n.startswith('20')]
            if potential_date:
                date = potential_date[0]
                # 格式化日期
                if len(date) == 8:
                    date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
            
            # 3. 找球号 (剩下的数字中，筛选 1-33 和 1-16)
            # 逻辑：跳过期号，跳过日期，剩下的如果是 1-2 位数字，且范围符合，就是球号
            # 3. 找球号 - 基于位置过滤 (跳过已知的 issue/date 成员)
            # 注意: 不再按值范围过滤, 因为 1-12 也是合法的球号
            skip_set = set()
            if issue:
                skip_set.add(issue)
            if date:
                for part in date.split('-'):
                    skip_set.add(part)
                    skip_set.add(part.lstrip('0') or '0')

            temp_balls = []
            for n in nums:
                if n in skip_set:
                    continue
                val = int(n)
                if 1 <= val <= 33:
                    temp_balls.append(val)
            
            # 如果找到了 7 个球号 (6红 + 1蓝)
            if len(temp_balls) >= 7:
                red_balls = temp_balls[:6]
                blue_ball = temp_balls[6]
                
                # 校验
                if all(1 <= r <= 33 for r in red_balls) and 1 <= blue_ball <= 16:
                    records.append({
                        'issue': issue,
                        'date': date,
                        'red_balls': red_balls,
                        'blue_ball': blue_ball
                    })

        return records

    # 注意: 以下方法已被移除以避免重复定义:
    # - _fetch_cwl_html (L889 版本保留, 含 curl_cffi 优化)
    # - _fetch_with_requests (L909 版本保留, 含 curl_cffi 优化)
    # - _fetch_with_playwright (L948 版本保留, 含 stealth_sync 优化)
    # - _parse_cwl_html / _extract_record_from_cells / _extract_record_from_text (未使用, 已删除)
