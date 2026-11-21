"""
综合推荐算法
整合多种算法给出最终推荐
"""
import random
from typing import List, Dict
from src.algorithms.base import BaseAlgorithm
from src.algorithms.weighted_random import WeightedRandomAlgorithm
from src.algorithms.normal_distribution import NormalDistributionAlgorithm
from src.algorithms.genetic import GeneticAlgorithm
from src.algorithms.monte_carlo import MonteCarloAlgorithm


class ComprehensiveAlgorithm(BaseAlgorithm):
    """综合推荐算法"""

    def generate(self, generations: int = 5) -> List[Dict]:
        """生成预测号码"""
        all_predictions = []

        weighted_random = WeightedRandomAlgorithm(self.analyzer, self.config)
        normal_dist = NormalDistributionAlgorithm(self.analyzer, self.config)
        genetic = GeneticAlgorithm(self.analyzer, self.config)
        monte_carlo = MonteCarloAlgorithm(self.analyzer, self.config)

        all_predictions.extend(weighted_random.generate(max(2, generations // 3)))
        all_predictions.extend(normal_dist.generate(max(2, generations // 3)))
        all_predictions.extend(genetic.generate(max(2, generations // 3)))
        all_predictions.extend(monte_carlo.generate(max(2, generations // 3)))

        seen = set()
        unique_predictions = []
        for pred in all_predictions:
            key = (tuple(pred['red_balls']), pred['blue_ball'])
            if key not in seen:
                seen.add(key)
                unique_predictions.append(pred)

        for pred in unique_predictions:
            pred['combined_score'] = self._calculate_fitness(
                pred['red_balls'], pred['blue_ball']
            )

        unique_predictions.sort(key=lambda x: x.get('combined_score', 0), reverse=True)

        return unique_predictions[:generations]
