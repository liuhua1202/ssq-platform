"""
数据解析器 - 期号、记录、数字提取.

三种入口:
  - IssueParser.normalize_issue(issue)              : '24001' -> '2024001'
  - IssueParser.extract_issue_from_soup(soup)       : 从 HTML 抽取期号
  - IssueParser.parse_record(record)                : 从 dict 解析单条 JSON/CSV 记录
  - IssueParser.parse_web_copy(data)                : 从网页复制粘贴数据解析
  - IssueParser.parse_seven_numbers(s)              : 解析 7 号码字符串
  - IssueParser.parse_cwl_html(html)                : 从福彩网 HTML 抽取多条记录
"""
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None  # type: ignore


class IssueParser:
    """双色球数据解析器 - 纯函数风格, 无状态."""

    # 红球/蓝球范围常量
    RED_MIN, RED_MAX, RED_COUNT = 1, 33, 6
    BLUE_MIN, BLUE_MAX = 1, 16

    # ============================================================
    # 期号归一化
    # ============================================================

    @staticmethod
    def normalize_issue(issue: str) -> str:
        """将简写期号转换为 7 位标准格式.

        '24001' -> '2024001'
        '2024001' -> '2024001'
        """
        if not issue:
            return issue
        if len(issue) == 5:
            return '20' + issue
        if len(issue) == 6 and not issue.startswith('202'):
            return '20' + issue
        return issue

    # ============================================================
    # HTML 期号提取 (多种策略)
    # ============================================================

    @staticmethod
    def extract_issue_from_soup(soup) -> Optional[str]:
        """从 BeautifulSoup 对象抽取期号, 按可靠性排序的多种策略."""
        if soup is None:
            return None

        # 复用闭包逻辑: 需要访问 normalize_issue
        def _find_and_convert(text: str) -> Optional[str]:
            match = re.search(r'(\d{5,7})', text)
            if match:
                return IssueParser.normalize_issue(match.group(1))
            return None

        # 策略 1: table-title class
        for tag in soup.find_all(class_='table-title'):
            text = tag.get_text(strip=True)
            if '期' in text:
                result = _find_and_convert(text)
                if result:
                    return result

        # 策略 2: 包含"期"字的关键元素
        for tag in soup.find_all(['td', 'th', 'em', 'strong']):
            text = tag.get_text(strip=True)
            if '期' in text:
                result = _find_and_convert(text)
                if result:
                    return result

        # 策略 3: 特定 class 元素
        for class_name in ['lottery', 'issue', 'period', 'title', 'header', 'cont', 'main']:
            el = soup.find(class_=lambda x: x and class_name in x.lower())
            if el:
                text = el.get_text(strip=True)
                result = _find_and_convert(text)
                if result:
                    return result

        # 策略 4: 页面标题
        title = soup.find('title')
        if title:
            text = title.get_text(strip=True)
            result = _find_and_convert(text)
            if result:
                return result

        # 策略 5: meta 标签
        for meta in soup.find_all('meta'):
            content = meta.get('content', '')
            if content and '期' in content:
                result = _find_and_convert(content)
                if result:
                    return result

        # 策略 6: 紧邻"开奖"二字
        for tag in soup.find_all(['span', 'div', 'p']):
            text = tag.get_text(strip=True)
            if '开奖' in text:
                result = _find_and_convert(text)
                if result:
                    return result

        return None

    # ============================================================
    # 记录解析 (JSON/CSV dict -> 标准格式)
    # ============================================================

    @staticmethod
    def parse_record(record: Dict) -> Optional[Dict]:
        """解析单条记录 (用于 JSON/CSV 导入).

        支持多种字段别名:
          - issue / expectNum / lotteryIssue
          - date / lotteryDrawTime / openTime
          - red_balls / red / redBall / redBalls
          - blue_ball / blue / blueBall
        """
        try:
            issue = record.get('issue', record.get('expectNum', record.get('lotteryIssue')))
            date = record.get('date', record.get('lotteryDrawTime', record.get('openTime')))
            red_balls = record.get('red', record.get(
                'redBall', record.get('redBalls', record.get('red_balls', []))))
            blue_ball = record.get('blue', record.get(
                'blueBall', record.get('blue_ball', None)))

            if isinstance(red_balls, str):
                red_balls = [int(x) for x in red_balls.replace(',', ' ').split()]

            if not red_balls or not blue_ball:
                return None

            red_balls_sorted = sorted([int(x) for x in red_balls])
            blue_ball_int = int(blue_ball)

            if len(red_balls_sorted) != IssueParser.RED_COUNT:
                return None
            if not all(IssueParser.RED_MIN <= r <= IssueParser.RED_MAX for r in red_balls_sorted):
                return None
            if not IssueParser.BLUE_MIN <= blue_ball_int <= IssueParser.BLUE_MAX:
                return None

            return {
                'issue': str(issue),
                'date': str(date)[:10] if date else None,
                'red_balls': red_balls_sorted,
                'blue_ball': blue_ball_int,
                'timestamp': datetime.now().isoformat()
            }
        except Exception:
            return None

    # ============================================================
    # 网页复制粘贴数据解析
    # ============================================================

    @staticmethod
    def parse_web_copy(data: Dict) -> Optional[Dict]:
        """解析从网页直接复制的数据.

        支持格式:
          "36132128296" -> 红球 [3,6,13,21,28,29] + 蓝球 6
          "13111831332" -> 红球 [13,11,18,31,33] + 蓝球 2
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
            result = IssueParser.parse_seven_numbers(balls_str)

            if not result or len(result) != 7:
                return None

            red_balls = result[:6]
            blue_ball = result[6]

            if not all(IssueParser.RED_MIN <= r <= IssueParser.RED_MAX for r in red_balls):
                return None
            if not IssueParser.BLUE_MIN <= blue_ball <= IssueParser.BLUE_MAX:
                return None

            return {
                'issue': issue,
                'date': parsed_date,
                'red_balls': sorted(red_balls),
                'blue_ball': blue_ball,
                'timestamp': datetime.now().isoformat()
            }
        except Exception:
            return None

    @staticmethod
    def parse_seven_numbers(s: str) -> Optional[List[int]]:
        """解析字符串为 7 个数字 (6 红球 + 1 蓝球).

        策略: 从后往前, 先确定蓝球, 再解析红球.
        """
        if not s or not s.isdigit():
            return None

        blue_candidates = []

        # 蓝球可以是 2 位或 1 位
        if len(s) >= 2:
            blue_2 = int(s[-2:])
            if 10 <= blue_2 <= 16:
                blue_candidates.append((blue_2, s[:-2]))

        blue_1 = int(s[-1:])
        if 1 <= blue_1 <= 16:
            blue_candidates.append((blue_1, s[:-1]))

        for blue_ball, red_str in blue_candidates:
            red_balls = IssueParser._parse_six_red_balls(red_str)
            if red_balls and len(red_balls) == 6:
                return red_balls + [blue_ball]
        return None

    @staticmethod
    def _parse_six_red_balls(s: str) -> Optional[List[int]]:
        """解析 6 个红球, 范围 1-33.

        优化策略: 从后往前匹配, 优先匹配末尾号码, 自动忽略开头残留.
        """
        if not s:
            return None

        result = []
        idx = len(s)

        while len(result) < 6 and idx > 0:
            matched = False

            # 策略 1: 优先匹配 2 位数 (10-33)
            if idx >= 2:
                num = int(s[idx-2:idx])
                if 10 <= num <= 33:
                    result.append(num)
                    idx -= 2
                    matched = True
                    continue

            # 策略 2: 匹配 1 位数 (1-9)
            if not matched and idx >= 1:
                num = int(s[idx-1:idx])
                if 1 <= num <= 33:
                    result.append(num)
                    idx -= 1
                    matched = True
                    continue

            # 跳过无法匹配的字符 (可能是期号残留)
            if not matched:
                idx -= 1

        if len(result) == 6:
            return result[::-1]
        return None

    # ============================================================
    # 福彩网 HTML 解析 (批量)
    # ============================================================

    @staticmethod
    def parse_cwl_html(html: str) -> List[Dict]:
        """从福彩网 HTML 解析多条历史记录.

        增强版解析器: 针对福彩网结构优化, 提取所有数字组合.
        """
        if not html or BeautifulSoup is None:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        records = []

        rows = soup.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 3:
                continue

            cell_texts = [c.get_text(strip=True) for c in cells]
            full_text = ' '.join(cell_texts)

            # 跳过表头或统计行
            if '期号' in full_text or '开奖日期' in full_text or '销售额' in full_text:
                continue

            # 提取所有数字块
            nums = re.findall(r'\d+', full_text)
            if len(nums) < 8:
                continue

            # 1. 找期号 (7 位数字, 20 开头)
            potential_issue = [n for n in nums if len(n) == 7 and n.startswith('20')]
            if not potential_issue:
                continue
            issue = potential_issue[0]

            # 2. 找日期 (8 位数字, 20 开头)
            date = None
            potential_date = [n for n in nums if len(n) == 8 and n.startswith('20')]
            if potential_date:
                date = potential_date[0]
                if len(date) == 8:
                    date = f"{date[:4]}-{date[4:6]}-{date[6:]}"

            # 3. 找球号 (剩下的数字中, 筛选 1-33)
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

            # 找到 7 个球号 (6 红 + 1 蓝)
            if len(temp_balls) >= 7:
                red_balls = temp_balls[:6]
                blue_ball = temp_balls[6]

                if all(1 <= r <= 33 for r in red_balls) and 1 <= blue_ball <= 16:
                    records.append({
                        'issue': issue,
                        'date': date,
                        'red_balls': red_balls,
                        'blue_ball': blue_ball
                    })

        return records

    # ============================================================
    # Scrapling 自适应解析 (新增, 建议网站改版后切换)
    # ============================================================

    @staticmethod
    def parse_cwl_api_json(payload: Dict) -> List[Dict]:
        """从 cwl.gov.cn 官方 JSON API 响应解析多条历史记录.

        字段映射:
          payload['result']: list of
            {
              'code': '2026104',                 # 期号
              'date': '2026-09-08(周二)',
              'red': '11,12,13,19,20,31',         # 6 个红球, 逗号分隔
              'blue': '03',                       # 1 个蓝球
              'sales': '333116798',
              'poolmoney': '798557035',
              ...
            }

        Returns:
            list of {issue, date, red_balls, blue_ball} (与 parse_cwl_html 输出一致)
        """
        results = payload.get('result', []) if isinstance(payload, dict) else []
        if not results:  # None / [] / 缺失都按空处理
            return []
        records = []

        for r in results:
            try:
                code = r.get('code', '').strip()
                if not code:
                    continue

                # 红球 (逗号分隔的 6 个 1-33 数字)
                red_str = r.get('red', '')
                red_balls = []
                for part in red_str.split(','):
                    part = part.strip()
                    if part.isdigit():
                        v = int(part)
                        if 1 <= v <= 33:
                            red_balls.append(v)

                # 蓝球 (1 个 1-16 数字)
                blue_str = r.get('blue', '').strip()
                blue_ball = int(blue_str) if blue_str.isdigit() else None

                # 校验
                if len(red_balls) != 6 or blue_ball is None:
                    continue
                if not (1 <= blue_ball <= 16):
                    continue

                # 日期: '2026-09-08(周二)' → '2026-09-08'
                date_raw = r.get('date', '')
                date = date_raw.split('(')[0].strip() if date_raw else None

                records.append({
                    'issue': code,
                    'date': date,
                    'red_balls': red_balls,
                    'blue_ball': blue_ball,
                })
            except Exception as e:
                logger.debug(f"解析单条 API 记录失败: {e}, record={r}")
                continue

        return records

    @staticmethod
    def parse_cwl_html_with_selector(response, adaptive: bool = True,
                                    auto_save: bool = False) -> List[Dict]:
        """用 Scrapling Selector 解析福彩网历史数据 (支持 adaptive 自适应).

        与 parse_cwl_html 区别:
          - 接收 Scrapling Response (不是纯字符串)
          - 使用 CSS selector 替代 BS4 字符串扫描
          - adaptive=True 时, 网站改版后选择器自动重新定位
          - 速度比 BS4+html5lib 快 ~1700x (Scrapling benchmark)

        Args:
            response: Scrapling Fetcher/StealthyFetcher/DynamicFetcher 返回的 Response 对象
            adaptive: 是否启用自适应选择器 (网站改版后自动找元素)
            auto_save: 首次调用时设为 True, 之后改为 False (Scrapling 会把元素特征存盘)

        Returns:
            list of {issue, date, red_balls, blue_ball} 字典

        用法:
            from src.crawler.fetcher import CWLFetcher
            fetcher = CWLFetcher()
            resp = fetcher.fetch('https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/')
            records = IssueParser.parse_cwl_html_with_selector(
                resp, adaptive=True, auto_save=True   # 首次
            )
            # 后续调用只传 adaptive=True
        """
        if response is None:
            return []

        records = []

        try:
            # 主选择器: 表格的每一行 (历史开奖记录)
            rows = response.css('table tr', adaptive=adaptive, auto_save=auto_save)
        except Exception as e:
            logger.debug(f"CSS selector 失败, 降级到 BS4 解析: {e}")
            # 降级: 转字符串 + 老 parser (注意 Scrapling Response 的 text 在 gzip 下可能为空, 用 html_content)
            html_str = str(response.html_content) if hasattr(response, 'html_content') and response.html_content \
                else (response.text if hasattr(response, 'text') else str(response))
            return IssueParser.parse_cwl_html(html_str)

        for row in rows:
            try:
                cells = row.css('td, th')
                if len(cells) < 3:
                    continue

                cell_texts = [c.text.strip() for c in cells if c.text]
                full_text = ' '.join(cell_texts)

                # 跳过表头或统计行
                if '期号' in full_text or '开奖日期' in full_text or '销售额' in full_text:
                    continue

                nums = re.findall(r'\d+', full_text)
                if len(nums) < 8:
                    continue

                # 1. 期号
                potential_issue = [n for n in nums if len(n) == 7 and n.startswith('20')]
                if not potential_issue:
                    continue
                issue = potential_issue[0]

                # 2. 日期
                date = None
                potential_date = [n for n in nums if len(n) == 8 and n.startswith('20')]
                if potential_date:
                    date = potential_date[0]
                    if len(date) == 8:
                        date = f"{date[:4]}-{date[4:6]}-{date[6:]}"

                # 3. 球号
                skip_set = {issue}
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

                if len(temp_balls) >= 7:
                    red_balls = temp_balls[:6]
                    blue_ball = temp_balls[6]

                    if all(1 <= r <= 33 for r in red_balls) and 1 <= blue_ball <= 16:
                        records.append({
                            'issue': issue,
                            'date': date,
                            'red_balls': red_balls,
                            'blue_ball': blue_ball
                        })
            except Exception:
                continue

        return records
