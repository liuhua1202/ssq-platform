"""
在线数据获取模块 - 500彩票网专用
针对反爬虫机制的多层防护设计
"""
import json
import os
import re
import time
import random
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# 可选依赖导入
try:
    from fake_useragent import UserAgent
    HAS_FAKE_UA = True
except ImportError:
    HAS_FAKE_UA = False
    UserAgent = None

try:
    from playwright.sync_api import sync_playwright
    from playwright_stealth import stealth_sync
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    sync_playwright = None
    stealth_sync = None


class OnlineFetcher:
    """在线数据获取器 - 针对500彩票网反爬虫优化"""

    # 500彩票网 API 端点
    CWL_API_URL = "https://kaijiang.500.com/ssq.shtml"
    CWL_HISTORY_URL = "https://www.500.com/kaijiang/ssq/lskj/"

    def __init__(self):
        self.session = None
        self.user_agents = []
        if HAS_FAKE_UA:
            self.ua = UserAgent()
        else:
            self.ua = None
            # 备用 UA 列表
            self.user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            ]

    def _get_random_headers(self) -> Dict[str, str]:
        """生成随机请求头，模拟真实浏览器"""
        if self.ua:
            user_agent = self.ua.chrome
        else:
            user_agent = random.choice(self.user_agents)

        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://kaijiang.500.com/',
            'Origin': 'https://kaijiang.500.com',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        }
        return headers

    def _random_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """随机延迟，模拟人类行为"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)

    def fetch_from_cwl_api(self, page: int = 1, page_size: int = 50) -> Dict:
        """
        从 500彩票网获取历史开奖数据（推荐方式）

        Args:
            page: 页码（从 1 开始）
            page_size: 每页数量（最大 50）

        Returns:
            包含成功状态和数据字典
        """
        try:
            import requests
        except ImportError:
            return {'success': False, 'message': 'requests 库未安装'}

        # 构造 URL
        if page == 1:
            url = "https://www.500.com/kaijiang/ssq/lskj/"
        else:
            url = f"https://www.500.com/kaijiang/ssq/lskj/{page}.html"

        headers = self._get_random_headers()

        try:
            logger.info(f"尝试从 500彩票网获取数据 (第 {page} 页)...")
            self._random_delay(1.5, 3.0)

            response = requests.get(
                url,
                headers=headers,
                timeout=15,
                verify=True
            )
            response.raise_for_status()
            
            # 处理 GBK 编码
            html = response.content.decode('gbk', errors='ignore')

            # 解析 HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            parsed_data = self._parse_500_html(soup)

            if parsed_data:
                logger.info(f"成功获取 {len(parsed_data)} 条记录")
                return {
                    'success': True,
                    'data': parsed_data,
                    'total': len(parsed_data),
                    'page': page,
                    'page_size': page_size,
                    'source': '500彩票网'
                }
            else:
                return {
                    'success': False,
                    'message': '未能解析到数据',
                }

        except requests.exceptions.RequestException as e:
            error_msg = f"网络请求失败：{str(e)}"
            logger.error(error_msg)
            return {'success': False, 'message': error_msg}
        except Exception as e:
            error_msg = f"解析数据失败：{str(e)}"
            logger.error(error_msg)
            return {'success': False, 'message': error_msg}

    def fetch_from_cwl_page(self, page: int = 1) -> Dict:
        """
        从 500彩票网页面抓取历史数据（备用方式）
        使用 Playwright 绕过 JavaScript 渲染和反爬虫

        Args:
            page: 页码

        Returns:
            包含成功状态和数据字典
        """
        if not HAS_PLAYWRIGHT:
            return {
                'success': False,
                'message': 'Playwright 未安装，请使用 API 方式或安装 playwright'
            }

        try:
            logger.info(f"使用 Playwright 从 500彩票网页面获取数据 (第 {page} 页)...")

            with sync_playwright() as p:
                # 启动浏览器（隐藏自动化特征）
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                    ]
                )

                context = browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent=self._get_random_headers()['User-Agent'],
                    locale='zh-CN',
                    timezone_id='Asia/Shanghai',
                )

                # 添加额外的初始化脚本以隐藏自动化特征
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)

                page_obj = context.new_page()

                # 设置超时
                page_obj.set_default_timeout(30000)

                try:
                    # 访问页面
                    url = "https://www.500.com/kaijiang/ssq/lskj/" if page == 1 else f"https://www.500.com/kaijiang/ssq/lskj/{page}.html"
                    page_obj.goto(url, wait_until='networkidle')
                    self._random_delay(2.0, 4.0)

                    # 尝试点击分页或等待表格加载
                    page_obj.wait_for_selector('table', timeout=10000)
                    self._random_delay(1.0, 2.0)

                    # 获取页面内容
                    content = page_obj.content()

                    # 解析数据
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(content, 'html.parser')
                    parsed_data = self._parse_500_html(soup)

                    browser.close()

                    if parsed_data:
                        logger.info(f"成功解析 {len(parsed_data)} 条记录")
                        return {
                            'success': True,
                            'data': parsed_data,
                            'source': '500彩票网页面'
                        }
                    else:
                        return {
                            'success': False,
                            'message': '未能解析到数据'
                        }

                except Exception as e:
                    browser.close()
                    raise e

        except Exception as e:
            error_msg = f"Playwright 抓取失败：{str(e)}"
            logger.error(error_msg)
            return {'success': False, 'message': error_msg}

    def _parse_500_html(self, soup) -> List[Dict]:
        """解析 500彩票网 HTML 页面数据"""
        parsed = []
        
        # 查找表格
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:
                    try:
                        # 提取期号、日期、号码等信息
                        issue_text = cells[0].get_text(strip=True)
                        date_text = cells[1].get_text(strip=True) if len(cells) > 1 else ''
                        balls_text = cells[2].get_text(strip=True) if len(cells) > 2 else ''
                        
                        # 提取期号
                        issue_match = re.search(r'(\d+)期', issue_text)
                        if not issue_match:
                            continue
                        issue = self._convert_issue(issue_match.group(1))
                        
                        # 提取日期
                        date_formatted = self._format_date(date_text)
                        
                        # 提取号码（7位数字连在一起）
                        if balls_text and balls_text != '待开奖':
                            balls_match = re.findall(r'\d', balls_text)
                            if len(balls_match) == 7:
                                red_balls = sorted([int(x) for x in balls_match[:6]])
                                blue_ball = int(balls_match[6])
                                
                                parsed.append({
                                    'issue': issue,
                                    'date': date_formatted,
                                    'red_balls': red_balls,
                                    'blue_ball': blue_ball
                                })
                    except Exception as e:
                        logger.warning(f"解析单条记录失败：{str(e)}")
                        continue
        
        return parsed
    
    def _convert_issue(self, issue: str) -> str:
        """将简写期号转换为 7 位标准格式"""
        if len(issue) == 5:
            return '20' + issue
        if len(issue) == 6 and not issue.startswith('202'):
            return '20' + issue
        return issue

    def _parse_cwl_api_response(self, records: List[Dict]) -> List[Dict]:
        """解析福彩官网 API 响应数据"""
        parsed = []

        for record in records:
            try:
                issue = record.get('code', '')
                date_str = record.get('date', '')
                red_balls_str = record.get('redBallNumbers', '')
                blue_ball_str = record.get('blueBallNumber', '')

                if not issue or not red_balls_str:
                    continue

                # 解析红球
                red_balls = []
                for num in red_balls_str.split(','):
                    num = num.strip()
                    if num.isdigit():
                        red_balls.append(int(num))

                # 解析蓝球
                blue_ball = 0
                if blue_ball_str and blue_ball_str.strip().isdigit():
                    blue_ball = int(blue_ball_str.strip())

                # 格式化日期
                date_formatted = self._format_date(date_str)

                if len(red_balls) == 6 and blue_ball > 0:
                    parsed.append({
                        'issue': issue,
                        'date': date_formatted,
                        'red_balls': sorted(red_balls),
                        'blue_ball': blue_ball
                    })

            except Exception as e:
                logger.warning(f"解析单条记录失败：{str(e)}")
                continue

        return parsed

    def _parse_cwl_html(self, html_content: str) -> List[Dict]:
        """解析福彩官网 HTML 页面数据"""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("BeautifulSoup 未安装")
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        parsed = []

        # 查找表格行（根据实际 HTML 结构调整选择器）
        rows = soup.find_all('tr')

        for row in rows:
            try:
                cells = row.find_all('td')
                if len(cells) < 8:
                    continue

                # 提取期号、日期、号码等信息
                # 注意：以下选择器需要根据实际页面结构调整
                issue_cell = cells[0].get_text(strip=True)
                date_cell = cells[1].get_text(strip=True)
                balls_cell = cells[2].get_text(strip=True)

                # 解析期号
                issue_match = re.search(r'(\d{7})', issue_cell)
                if not issue_match:
                    continue
                issue = issue_match.group(1)

                # 解析日期
                date_formatted = self._format_date(date_cell)

                # 解析号码（格式如：01 02 03 04 05 06 + 07）
                balls_match = re.findall(r'(\d{2})', balls_cell)
                if len(balls_match) >= 7:
                    red_balls = [int(x) for x in balls_match[:6]]
                    blue_ball = int(balls_match[6])

                    parsed.append({
                        'issue': issue,
                        'date': date_formatted,
                        'red_balls': sorted(red_balls),
                        'blue_ball': blue_ball
                    })

            except Exception as e:
                continue

        return parsed

    def _format_date(self, date_str: str) -> str:
        """格式化日期字符串为 YYYY-MM-DD"""
        if not date_str:
            return datetime.now().strftime('%Y-%m-%d')

        # 尝试多种日期格式
        formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%Y年%m月%d日',
            '%Y-%m-%d %H:%M:%S',
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue

        # 如果都失败，返回原始字符串或当前日期
        return date_str.strip() if date_str else datetime.now().strftime('%Y-%m-%d')

    def fetch_multiple_pages(self, start_page: int = 1, end_page: int = 10,
                             use_api: bool = True) -> Dict:
        """
        批量获取多页数据

        Args:
            start_page: 起始页码
            end_page: 结束页码
            use_api: 是否使用 API 方式（否则使用页面抓取）

        Returns:
            包含所有数据的字典
        """
        all_data = []
        failed_pages = []

        for page in range(start_page, end_page + 1):
            logger.info(f"正在获取第 {page}/{end_page} 页...")

            if use_api:
                result = self.fetch_from_cwl_api(page=page, page_size=50)
            else:
                result = self.fetch_from_cwl_page(page=page)

            if result['success']:
                all_data.extend(result['data'])
                logger.info(f"第 {page} 页成功，累计 {len(all_data)} 条记录")
            else:
                failed_pages.append(page)
                logger.warning(f"第 {page} 页失败：{result.get('message')}")

            # 页面间延迟，避免被封
            self._random_delay(2.0, 4.0)

        return {
            'success': len(all_data) > 0,
            'data': all_data,
            'total_records': len(all_data),
            'failed_pages': failed_pages,
            'total_pages': end_page - start_page + 1
        }


# 便捷函数
def fetch_latest_from_cwl() -> Dict:
    """获取最新一期开奖数据（便捷函数）"""
    fetcher = OnlineFetcher()
    return fetcher.fetch_from_cwl_api(page=1, page_size=1)


def fetch_history_from_cwl(pages: int = 5) -> Dict:
    """获取历史数据（便捷函数）"""
    fetcher = OnlineFetcher()
    return fetcher.fetch_multiple_pages(1, pages, use_api=True)
