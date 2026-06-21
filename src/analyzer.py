"""
双色球数据分析模块
优化版本：使用内置函数替代 numpy，优化预处理性能
"""
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Any
from datetime import datetime, timedelta
from src.cache import cached_analysis


def _mean(data: List[float]) -> float:
    """计算平均值"""
    return sum(data) / len(data) if data else 0.0


def _median(data: List[float]) -> float:
    """计算中位数"""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    mid = n // 2
    return (sorted_data[mid - 1] + sorted_data[mid]) / 2 if n % 2 == 0 else sorted_data[mid]


def _std(data: List[float]) -> float:
    """计算标准差"""
    if len(data) < 2:
        return 0.0
    m = _mean(data)
    variance = sum((x - m) ** 2 for x in data) / len(data)
    return variance ** 0.5


class Analyzer:
    """双色球数据分析器"""

    def __init__(self, history_data: List[Dict]):
        self.data = history_data
        self.red_balls_all = []
        self.blue_balls_all = []
        self._preprocess()

    def _preprocess(self):
        """预处理数据（优化版本）"""
        # 使用列表推导式提升性能
        self.red_balls_all = [
            ball for record in self.data
            for ball in record.get('red_balls', [])
        ]
        self.blue_balls_all = [
            record.get('blue_ball') for record in self.data
            if record.get('blue_ball') is not None
        ]

    def get_frequency_stats(self, balls: List[int], min_val: int, max_val: int) -> Dict:
        """获取频率统计"""
        counter = Counter(balls)
        stats = {}
        for num in range(min_val, max_val + 1):
            count = counter.get(num, 0)
            stats[num] = {
                'number': num,
                'count': count,
                'frequency': count / len(self.data) if self.data else 0,
                'percentage': count / len(self.data) * 100 if self.data else 0
            }
        return stats

    @cached_analysis
    def get_hot_numbers(self, top_n: int = 10, recent_ratio: float = 0.3) -> Dict[str, List]:
        """
        获取热号（出现频率高的号码）
        :param top_n: 返回前 N 个热号
        :param recent_ratio: 近期数据比例（最近 30% 的数据）
        """
        # 近期数据
        recent_count = max(int(len(self.data) * recent_ratio), 10)
        recent_data = self.data[:recent_count]
        recent_reds = []
        for record in recent_data:
            recent_reds.extend(record.get('red_balls', []))

        # 全部数据
        all_red_stats = self.get_frequency_stats(
            self.red_balls_all, 1, 33
        )

        # 近期数据
        recent_counter = Counter(recent_reds)
        recent_stats = {}
        for num in range(1, 34):
            count = recent_counter.get(num, 0)
            recent_stats[num] = {
                'number': num,
                'count': count,
                'recent_frequency': count / recent_count if recent_count else 0
            }

        # 按频率排序
        hot_all = sorted(all_red_stats.items(), key=lambda x: x[1]['count'], reverse=True)[:top_n]
        hot_recent = sorted(recent_stats.items(), key=lambda x: x[1]['count'], reverse=True)[:top_n]

        return {
            'overall': [x[0] for x in hot_all],
            'recent': [x[0] for x in hot_recent],
            'stats': all_red_stats,
            'recent_stats': recent_stats
        }

    @cached_analysis
    def get_cold_numbers(self, top_n: int = 10) -> Dict:
        """获取冷号（出现频率低的号码）"""
        stats = self.get_frequency_stats(self.red_balls_all, 1, 33)
        cold = sorted(stats.items(), key=lambda x: x[1]['count'])[:top_n]

        return {
            'numbers': [x[0] for x in cold],
            'stats': {x[0]: x[1] for x in cold}
        }

    @cached_analysis
    def get_missing_stats(self) -> Dict[int, Dict]:
        """
        获取遗漏值统计
        遗漏值：某个号码连续未出现的期数
        """
        missing = defaultdict(int)
        max_missing = defaultdict(int)

        # 从最新数据开始往前找
        for record in self.data:
            current_reds = set(record.get('red_balls', []))
            for num in range(1, 34):
                if num in current_reds:
                    # 更新最大遗漏值
                    if missing[num] > max_missing[num]:
                        max_missing[num] = missing[num]
                    missing[num] = 0  # 重置遗漏计数
                else:
                    missing[num] += 1

        # 计算平均遗漏值
        total_periods = len(self.data)
        avg_missing = {}
        for num in range(1, 34):
            count = sum(1 for r in self.data if num in r.get('red_balls', []))
            if count > 0:
                avg_missing[num] = total_periods / count
            else:
                avg_missing[num] = total_periods

        result = {}
        for num in range(1, 34):
            result[num] = {
                'current_missing': missing[num],
                'max_missing': max_missing[num],
                'avg_missing': avg_missing[num],
                'is_cold': missing[num] > avg_missing[num]
            }

        return result

    @cached_analysis
    def get_odd_even_ratio(self) -> Dict:
        """获取奇偶比分析"""
        odd_counts = []
        even_counts = []

        for record in self.data:
            reds = record.get('red_balls', [])
            odd = sum(1 for r in reds if r % 2 == 1)
            even = 6 - odd
            odd_counts.append(odd)
            even_counts.append(even)

        odd_counter = Counter(odd_counts)
        ratio_dist = {
            f"{odd}:{6-odd}": {
                'count': odd_counter.get(odd, 0),
                'percentage': odd_counter.get(odd, 0) / len(self.data) * 100 if self.data else 0
            }
            for odd in range(7)
        }

        return {
            'distribution': ratio_dist,
            'avg_odd': _mean(odd_counts) if odd_counts else 0,
            'avg_even': _mean(even_counts) if even_counts else 0,
            'most_common': max(ratio_dist.items(), key=lambda x: x[1]['count'])[0] if ratio_dist else "N/A"
        }

    @cached_analysis
    def get_sum_analysis(self) -> Dict:
        """获取和值分析（红球总和）"""
        sums = []
        for record in self.data:
            reds = record.get('red_balls', [])
            sums.append(sum(reds))

        if not sums:
            return {}

        sum_counter = Counter(sums)

        # 按区间统计
        sum_ranges = {
            '21-50': sum(1 for s in sums if 21 <= s <= 50),
            '51-80': sum(1 for s in sums if 51 <= s <= 80),
            '81-100': sum(1 for s in sums if 81 <= s <= 100),
            '101-120': sum(1 for s in sums if 101 <= s <= 120),
            '121-150': sum(1 for s in sums if 121 <= s <= 150),
            '151-180': sum(1 for s in sums if 151 <= s <= 180),
        }

        return {
            'min': min(sums),
            'max': max(sums),
            'mean': _mean(sums),
            'median': _median(sums),
            'std': _std(sums),
            'distribution': dict(sum_counter.most_common(20)),
            'range_distribution': sum_ranges,
            'most_common_sum': sum_counter.most_common(1)[0] if sum_counter else None
        }

    @cached_analysis
    def get_consecutive_numbers_analysis(self) -> Dict:
        """获取连号分析"""
        consecutive_counts = []
        consecutive_patterns = Counter()

        for record in self.data:
            reds = sorted(record.get('red_balls', []))
            consecutive = 0
            patterns = []

            for i in range(len(reds) - 1):
                if reds[i + 1] - reds[i] == 1:
                    consecutive += 1
                    patterns.append((reds[i], reds[i + 1]))

            consecutive_counts.append(consecutive)
            for p in patterns:
                consecutive_patterns[p] += 1

        return {
            'avg_consecutive': _mean(consecutive_counts) if consecutive_counts else 0,
            'distribution': dict(Counter(consecutive_counts)),
            'most_common_pairs': consecutive_patterns.most_common(10)
        }

    @cached_analysis
    def get_blue_ball_analysis(self) -> Dict:
        """获取蓝球分析"""
        if not self.blue_balls_all:
            return {}

        counter = Counter(self.blue_balls_all)
        stats = {}
        for num in range(1, 17):
            count = counter.get(num, 0)
            stats[num] = {
                'number': num,
                'count': count,
                'frequency': count / len(self.data) if self.data else 0,
                'percentage': count / len(self.data) * 100 if self.data else 0
            }

        # 奇偶分析
        odd = sum(1 for b in self.blue_balls_all if b % 2 == 1)
        even = len(self.blue_balls_all) - odd

        # 大小分析（1-8 为小，9-16 为大）
        small = sum(1 for b in self.blue_balls_all if b <= 8)
        big = len(self.blue_balls_all) - small

        return {
            'stats': stats,
            'hot_numbers': [k for k, v in sorted(stats.items(), key=lambda x: x[1]['count'], reverse=True)[:5]],
            'cold_numbers': [k for k, v in sorted(stats.items(), key=lambda x: x[1]['count'])[:5]],
            'odd_even': {'odd': odd, 'even': even, 'ratio': f"{odd}:{even}"},
            'big_small': {'big': big, 'small': small, 'ratio': f"{big}:{small}"}
        }

    def get_ac_index(self, red_balls: List[int]) -> float:
        """
        计算 AC 指数（Arbitrary Complexity）
        用于衡量号码组合的复杂度
        AC = D - (N - 1), 其中 D 是不同差值的数量，N 是号码数量
        """
        if len(red_balls) != 6:
            return 0

        diffs = set()
        for i in range(len(red_balls)):
            for j in range(i + 1, len(red_balls)):
                diffs.add(abs(red_balls[i] - red_balls[j]))

        return len(diffs) - 5  # N-1 = 5

    def get_comprehensive_analysis(self) -> Dict[str, Any]:
        """获取综合分析结果"""
        hot = self.get_hot_numbers()
        cold = self.get_cold_numbers()
        missing = self.get_missing_stats()
        odd_even = self.get_odd_even_ratio()
        sum_analysis = self.get_sum_analysis()
        blue = self.get_blue_ball_analysis()

        return {
            'total_records': len(self.data),
            'hot_numbers': hot,
            'cold_numbers': cold,
            'missing_stats': missing,
            'odd_even': odd_even,
            'sum_analysis': sum_analysis,
            'blue_ball': blue,
            'analysis_time': datetime.now().isoformat()
        }
