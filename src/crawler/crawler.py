"""
Crawler - 顶层协调器.

组合 BackupManager / IssueParser / CWLFetcher, 提供向后兼容的 API:
  - load_history / save_history (本地 JSON 存储)
  - fetch_latest_lottery / fetch_lottery_history (网络抓取多源)
  - parse_record / parse_web_copy (数据导入解析)
  - create_backup (备份管理)
  - fetch_cwl_lottery (批量抓取)
"""
import json
import logging
import os
import random
import re
import time
from datetime import datetime
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from .backup import BackupManager
from .parser import IssueParser
from .fetcher import CWLFetcher

logger = logging.getLogger(__name__)


class Crawler:
    """双色球历史数据管理器 - 协调 BackupManager / IssueParser / CWLFetcher."""

    def __init__(self, data_dir: Optional[str] = None):
        from config import get_base_path
        if data_dir is None:
            data_dir = os.path.join(get_base_path(), 'data')

        self.data_dir = os.path.abspath(data_dir)
        self.history_file = os.path.join(self.data_dir, "history.json")

        # 子组件
        self.backup_manager = BackupManager(self.data_dir)
        self.fetcher = CWLFetcher()

        # 确保目录存在 (BackupManager 已建, 但 data_dir 可能不存在)
        os.makedirs(self.data_dir, exist_ok=True)

    # ============================================================
    # 向后兼容的访问器属性 (旧代码可能用 crawler.backup_dir / history_file)
    # ============================================================

    @property
    def backup_dir(self) -> str:
        """向后兼容: 直接访问 .backup_dir."""
        return self.backup_manager.backup_dir

    @property
    def history_file_path(self) -> str:
        """向后兼容: 直接访问 .history_file."""
        return self.backup_manager.history_file

    # ============================================================
    # 历史数据读写
    # ============================================================

    def load_history(self) -> List[Dict]:
        """加载本地历史数据."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"已加载 {len(data)} 条历史数据")
                    return data
            except Exception as e:
                logger.warning(f"加载历史数据失败: {e}")
                return self._restore_from_backup()
        logger.info("历史数据文件不存在, 将创建新文件")
        return []

    def _restore_from_backup(self) -> List[Dict]:
        """从备份恢复 (委托给 BackupManager)."""
        data = self.backup_manager.restore_from_latest()
        if data:
            logger.info(f"从备份文件恢复 {len(data)} 条历史数据")
        return data or []

    def save_history(self, data: List[Dict], backup: bool = True) -> None:
        """保存历史数据到本地, 可选创建备份."""
        os.makedirs(self.data_dir, exist_ok=True)

        if backup and os.path.exists(self.history_file):
            self.create_backup()

        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"历史数据已保存: {len(data)} 条记录")

    # ============================================================
    # 公共 wrapper 方法 (旧代码可能通过 _ 前缀方法调用, 这里提供 public API)
    # ============================================================

    def create_backup(self) -> None:
        """Public wrapper for _create_backup. 创建当前数据的备份."""
        self.backup_manager.create_backup()

    def parse_record(self, record: Dict) -> Optional[Dict]:
        """Public wrapper for _parse_record."""
        return IssueParser.parse_record(record)

    def parse_web_copy(self, data: Dict) -> Optional[Dict]:
        """Public wrapper for _parse_web_copy."""
        return IssueParser.parse_web_copy(data)

    # ============================================================
    # 向后兼容的 _xxx 私有方法别名 (供测试 / 历史代码)
    # 新代码请使用 IssueParser.normalize_issue 等公开 API
    # ============================================================

    def _convert_issue(self, issue: str) -> str:
        """向后兼容的私有方法别名 -> IssueParser.normalize_issue."""
        return IssueParser.normalize_issue(issue)

    def _extract_issue(self, soup) -> Optional[str]:
        """向后兼容的私有方法别名 -> IssueParser.extract_issue_from_soup."""
        return IssueParser.extract_issue_from_soup(soup)

    def _parse_seven_numbers(self, s: str) -> Optional[List[int]]:
        """向后兼容的私有方法别名 -> IssueParser.parse_seven_numbers."""
        return IssueParser.parse_seven_numbers(s)

    def _parse_six_red_balls(self, s: str) -> Optional[List[int]]:
        """向后兼容的私有方法别名 -> IssueParser._parse_six_red_balls."""
        return IssueParser._parse_six_red_balls(s)

    def _create_backup(self) -> None:
        """向后兼容: 委托给 BackupManager."""
        self.backup_manager.create_backup()

    # ============================================================
    # 网络抓取 - 最新一期 (多源 fallback)
    # ============================================================

    def fetch_latest_lottery(self) -> Dict:
        """从多个来源获取最新一期开奖信息 (支持备用数据源)."""
        sources = [
            {
                'name': '500彩票网开奖页面',
                'url': 'https://kaijiang.500.com/ssq.shtml',
                'encoding': 'utf-8',
                'headers': self._default_headers()
            },
            {
                'name': '中彩网',
                'url': 'http://www.zhcw.com/ssq/',
                'encoding': 'utf-8',
                'headers': self._default_headers()
            },
            {
                'name': '福彩官网',
                'url': 'https://www.cwl.gov.cn/ygkj/kjgg/ssq/',
                'encoding': 'utf-8',
                'headers': self._default_headers()
            },
        ]

        last_error = None
        failed_sources: List[str] = []

        for source in sources:
            try:
                logger.info(f"尝试从 {source['name']} 获取数据...")
                result = self._fetch_latest_from_source(
                    source['url'], source['encoding'], source['headers']
                )
                if result['success']:
                    logger.info(f"成功从 {source['name']} 获取数据")
                    return result

                failed_sources.append(source['name'])
                last_error = result.get('message', '未知错误')
                logger.warning(f"{source['name']} 获取失败: {last_error}")
            except Exception as e:
                failed_sources.append(source['name'])
                last_error = repr(e)
                logger.error(f"{source['name']} 异常: {repr(e)}")
                continue

        error_detail = (
            f"所有数据源均获取失败. 失败源: {', '.join(failed_sources)}. "
            f"最后错误: {last_error}"
        )
        logger.error(error_detail)
        return {'success': False, 'message': error_detail}

    @staticmethod
    def _default_headers() -> Dict[str, str]:
        """生成默认浏览器 headers."""
        return {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }

    def _fetch_latest_from_source(self, url: str, encoding: str, headers: dict) -> Dict:
        """从指定 URL 获取最新开奖信息 (requests 单次调用)."""
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

            issue = None
            red_balls: List[int] = []
            blue_ball: Optional[int] = None
            date: Optional[str] = None

            # 方法 1: draw-table 表格
            table = soup.find('table', class_='draw-table')
            if table:
                rows = table.find_all('tr')
                if len(rows) > 1:
                    cells = rows[1].find_all(['td', 'th'])
                    if len(cells) >= 3:
                        issue_text = cells[0].get_text(strip=True)
                        balls_text = cells[1].get_text(strip=True)
                        date_text = cells[2].get_text(strip=True)

                        issue_match = re.search(r'(\d+)期', issue_text)
                        if issue_match:
                            issue = IssueParser.normalize_issue(issue_match.group(1))

                        if balls_text != '待开奖':
                            balls_match = re.findall(r'\d', balls_text)
                            if len(balls_match) == 7:
                                red_balls = sorted([int(x) for x in balls_match[:6]])
                                blue_ball = int(balls_match[6])

                        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', date_text)
                        if date_match:
                            date = date_match.group(1)

            # 方法 2: fallback - 全文档搜索
            if not issue or len(red_balls) < 6 or blue_ball is None:
                issue = IssueParser.extract_issue_from_soup(soup)

                if len(red_balls) < 6 or blue_ball is None:
                    all_numbers = []
                    for tag in soup.find_all(['td', 'span', 'div', 'em', 'strong', 'li']):
                        text = tag.get_text(strip=True)
                        if text.isdigit():
                            all_numbers.append(int(text))

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
                'message': f'解析失败: 期号={issue}, 红球数={len(red_balls)}, 蓝球={blue_ball}'
            }
        except requests.RequestException as e:
            return {'success': False, 'message': f'网络请求失败: {str(e)}'}
        except Exception as e:
            return {'success': False, 'message': f'获取失败: {str(e)}'}

    # ============================================================
    # 网络抓取 - 历史开奖
    # ============================================================

    def fetch_lottery_history(self, page: int = 1, page_size: int = 20) -> Dict:
        """从 500 彩票网主页面获取最近 10 期历史开奖记录."""
        source = {
            'url': "https://kaijiang.500.com/ssq.shtml",
            'encoding': 'utf-8',
            'headers': {
                **self._default_headers(),
                'Referer': 'https://www.500.com/',
                'Connection': 'keep-alive',
            }
        }

        try:
            result = self._fetch_history_from_source(
                source['url'], source['encoding'], source['headers'], page_size
            )
            return result
        except Exception as e:
            logger.warning(f"历史抓取异常: {e}")
            return {'success': False, 'message': f'所有数据源均获取失败: {e}'}

    def _fetch_history_from_source(self, url: str, encoding: str,
                                   headers: dict, page_size: int) -> Dict:
        """从指定 URL 获取历史开奖记录 (500 彩票网专用解析)."""
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        html = response.content.decode(encoding, errors='ignore') if encoding == 'gbk' else response.text
        soup = BeautifulSoup(html, 'html.parser')
        lottery_data: List[Dict] = []

        # 方法 1: lottery-page-bottom 区域
        history_section = soup.find(class_='lottery-page-bottom')
        if history_section:
            logger.info("找到 lottery-page-bottom 区域")
            issue_links = history_section.find_all('a', href=True)

            for link in issue_links:
                href = link['href']
                text = link.get_text(strip=True)

                issue_match = re.search(r'kaijiang/ssq/(\d{5,6})\.html', href)
                if issue_match:
                    issue = IssueParser.normalize_issue(issue_match.group(1))
                    numbers_in_text = re.findall(r'\d+', text)

                    # 提取日期
                    date: Optional[str] = None
                    for num_str in numbers_in_text:
                        if len(num_str) == 4 and num_str.startswith('20'):
                            year_idx = numbers_in_text.index(num_str)
                            if year_idx + 3 <= len(numbers_in_text):
                                year = num_str
                                month = numbers_in_text[year_idx + 1]
                                day = numbers_in_text[year_idx + 2]
                                if len(month) == 2 and len(day) == 2:
                                    date = f"{year}-{month}-{day}"
                                    break

                    # 提取 14 位号码字符串
                    for num_str in numbers_in_text:
                        if len(num_str) == 14:
                            red_balls = sorted([int(num_str[i:i+2]) for i in range(0, 12, 2)])
                            blue_ball = int(num_str[12:14])
                            if all(1 <= r <= 33 for r in red_balls) and 1 <= blue_ball <= 16:
                                lottery_data.append({
                                    'issue': issue,
                                    'date': date or datetime.now().strftime('%Y-%m-%d'),
                                    'red_balls': red_balls,
                                    'blue_ball': blue_ball
                                })
                            break

        # 方法 2: custom-table 表格
        if not lottery_data:
            table = soup.find('table', class_='custom-table')
            if table:
                rows = table.find_all('tr')
                logger.info(f"找到 custom-table, 共 {len(rows)} 行")
                for row in rows[2:]:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        try:
                            issue = cells[0].get_text(strip=True)
                            date_time = cells[1].get_text(strip=True)
                            balls_text = cells[2].get_text(strip=True)

                            if not issue or not re.match(r'^\d{5,6}$', issue):
                                continue

                            issue = IssueParser.normalize_issue(issue)

                            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', date_time)
                            date = date_match.group(1) if date_match else datetime.now().strftime('%Y-%m-%d')

                            if balls_text and len(balls_text) == 14:
                                balls = [int(balls_text[i:i+2]) for i in range(0, 14, 2)]
                                if len(balls) == 7:
                                    red_balls = sorted(balls[:6])
                                    blue_ball = balls[6]
                                    if all(1 <= r <= 33 for r in red_balls) and 1 <= blue_ball <= 16:
                                        lottery_data.append({
                                            'issue': issue,
                                            'date': date,
                                            'red_balls': red_balls,
                                            'blue_ball': blue_ball
                                        })
                        except Exception:
                            continue

        # 方法 3: 兜底 - 任何含 6+ 数字列的表格
        if not lottery_data:
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) < 8:
                        continue
                    cell_texts = [c.get_text(strip=True) for c in cells]

                    issue = None
                    for text in cell_texts:
                        if re.match(r'^\d{6,}$', text):
                            issue = text
                            break

                    red_balls: List[int] = []
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

                    date: Optional[str] = None
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

        # 方法 4: 遍历所有 tr - 兜底策略
        if not lottery_data:
            all_trs = soup.find_all('tr')
            for tr in all_trs:
                tds = tr.find_all('td')
                if len(tds) < 5:
                    continue
                cell_texts = [td.get_text(strip=True) for td in tds]

                issue = None
                for text in cell_texts:
                    if re.match(r'^\d{6,}$', text):
                        issue = text
                        break

                if not issue:
                    continue

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

        return {'success': False, 'message': '未找到开奖数据, 请检查网页结构是否变化'}

    # ============================================================
    # 批量抓取 - 福彩网 (委托给 CWLFetcher)
    # ============================================================

    def fetch_cwl_lottery(self, max_pages: int = 100) -> Dict:
        """从福彩网批量获取历史开奖信息 (完整反爬应对).

        委托给 CWLFetcher.fetch_multi_page. 保留此方法向后兼容.
        """
        return self.fetcher.fetch_multi_page(max_pages=max_pages)
