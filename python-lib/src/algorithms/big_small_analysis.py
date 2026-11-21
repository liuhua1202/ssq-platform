"""
大中小号算法
小号：1-11, 中号：12-22, 大号：23-33
根据历史大小比生成号码
"""
import random
from typing import List, Dict, Tuple
from collections import Counter
from src.algorithms.base import BaseAlgorithm


class BigSmallAnalysisAlgorithm(BaseAlgorithm):
    """大中小号分析算法"""

    def generate(self, generations: int = 5) -> List[Dict]:
        """生成预测号码"""
        big_small_ratio = self._analyze_big_small_ratio()

        results = []
        for _ in range(generations):
            small_count, big_count = random.choice(big_small_ratio)
            mid_count = 6 - small_count - big_count

            small_pool = list(range(1, 12))
            selected_small = random.sample(small_pool, min(small_count, len(small_pool)))

            mid_pool = list(range(12, 23))
            selected_mid = random.sample(mid_pool, min(mid_count, len(mid_pool)))

            big_pool = list(range(23, 34))
            selected_big = random.sample(big_pool, min(big_count, len(big_pool)))

            red_balls = sorted(selected_small + selected_mid + selected_big)
            blue_ball = random.randint(1, 16)

            actual_small = sum(1 for r in red_balls if r <= 11)
            actual_mid = sum(1 for r in red_balls if 12 <= r <= 22)
            actual_big = sum(1 for r in red_balls if r >= 23)

            result = self._get_common_prediction_info(red_balls, blue_ball, 'big_small_analysis')
            result['size_ratio'] = f"{actual_small}:{actual_mid}:{actual_big}"
            result['remark'] = f"大中小比{actual_small}:{actual_mid}:{actual_big}"
            results.append(result)

        return results

    def _analyze_big_small_ratio(self) -> List[Tuple[int, int]]:
        """分析历史数据的大小比"""
        data = self.analyzer.data
        if not data:
            return [(2, 2)]

        ratios = []
        for record in data[-50:]:
            red_balls = record.get('red_balls', [])
            small = sum(1 for r in red_balls if r <= 11)
            big = sum(1 for r in red_balls if r >= 23)
            ratios.append((small, big))

        counter = Counter(ratios)
        common = counter.most_common(5)
        return [r[0] for r in common]
