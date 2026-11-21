"""
Sanity check for parsed lottery data - 防 SPA loader / demo 数据 / maxlength 属性误判.

核心思路: 真实开奖数据必须满足多个强条件同时成立,
光"数字在范围"不足以判定.
"""
import re
from typing import Optional


def is_valid_lottery_data(issue, red_balls, blue_ball, source_html: str) -> bool:
    """校验解析出的数据是否像是真实开奖数据, 而不是 demo / loader 噪声.

    Args:
        issue: 期号字符串 (e.g. "2024001")
        red_balls: 6 个红球 list
        blue_ball: 蓝球 int
        source_html: 来源 HTML, 用于 sanity check

    Returns:
        True 如果看起来像真实数据, False 拒绝
    """
    # 基本完整性 (None / 长度错误直接拒绝)
    if not issue:
        return False
    if red_balls is None or len(red_balls) != 6:
        return False
    if blue_ball is None:
        return False

    # 1) 期号格式: 必须 7 位数字, 以 "20" 开头, 年份合理 [2010, 当前+1]
    if not isinstance(issue, str) or not re.fullmatch(r'20\d{5}', issue):
        return False
    try:
        year = int(issue[:4])
        import datetime
        current_year = datetime.datetime.now().year
        if not (2010 <= year <= current_year + 1):
            return False
    except (ValueError, TypeError):
        return False

    # 2) 红球范围 1-33, 蓝球 1-16
    for r in red_balls:
        if not (1 <= int(r) <= 33):
            return False
    if not (1 <= int(blue_ball) <= 16):
        return False

    # 3) 红球必须互不重复
    if len(set(red_balls)) != 6:
        return False

    # 4) 蓝球不能在红球里 (规则约束: 红蓝球各自独立)
    # 实际规则允许, 不强制. skip

    # 5) 反 "demo 数据" 模式: 数字是连续递增的
    #    真实 lottery: 6 个独立采样, 连续递增概率极低
    sorted_red = sorted(int(r) for r in red_balls)
    is_consecutive = all(
        sorted_red[i+1] - sorted_red[i] == 1
        for i in range(len(sorted_red) - 1)
    )
    if is_consecutive and sorted_red[0] == 1 and sorted_red[5] == 6:
        # [1, 2, 3, 4, 5, 6] 是典型 demo 数据
        return False

    # 6) 拒绝明显 dummy 期号: 0123456, 1234567 等
    if issue in {'0123456', '1234567', '2345678', '0000000'}:
        return False

    # 7) source_html 不能为空或太小 (loader 截断标志)
    #    注意: JSON API 路径会传 source_html='', 此处跳过 HTML 相关检查
    if source_html:
        if len(source_html) < 5000:
            return False

        # 8) source_html 必须包含 lottery 关键词 (双色 / 开奖 / 等)
        lottery_keywords = ['双色球', '开奖', '红球', '蓝球', 'SSQ', 'ssq']
        keyword_found = any(kw in source_html for kw in lottery_keywords)
        if not keyword_found:
            return False
    # else: JSON API 路径, 1-6 项已校验数据本身, 信任即可

    return True
