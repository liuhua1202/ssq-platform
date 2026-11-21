"""
加权随机算法
基于热号、冷号、遗漏值等权重生成组合
"""
import random
from typing import List, Dict
from src.algorithms.base import BaseAlgorithm


class WeightedRandomAlgorithm(BaseAlgorithm):
    """加权随机算法"""

    def __init__(self, analyzer, config: Dict = None):
        super().__init__(analyzer, config)
        self.config = config or {
            'hot_weight': 0.4,
            'cold_weight': 0.2,
            'missing_weight': 0.3,
            'trend_weight': 0.1,
        }

    def generate(self, generations: int = 5) -> List[Dict]:
        """生成预测号码"""
        hot_stats = self.analyzer.get_hot_numbers()
        cold_stats = self.analyzer.get_cold_numbers()
        missing_stats = self.analyzer.get_missing_stats()

        # 计算每个号码的权重
        weights = {}
        for num in range(1, 34):
            hot_score = 1 / (hot_stats['stats'].get(num, {}).get('count', 1) + 1)
            cold_score = cold_stats['stats'].get(num, {}).get('count', 1) + 1
            missing_score = missing_stats.get(num, {}).get('current_missing', 0) + 1

            weight = (
                self.config['hot_weight'] * (1 / hot_score) +
                self.config['cold_weight'] * cold_score +
                self.config['missing_weight'] * missing_score +
                self.config['trend_weight'] * random.uniform(0.5, 1.5)
            )
            weights[num] = weight

        results = []
        for _ in range(generations):
            numbers = list(range(1, 34))
            number_weights = [weights[n] for n in numbers]
            red_balls = self._weighted_sample_unique(numbers, number_weights, 6)
            red_balls = sorted(red_balls)
            blue_ball = random.randint(1, 16)

            result = self._get_common_prediction_info(red_balls, blue_ball, 'weighted_random')
            results.append(result)

        return results
