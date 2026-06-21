"""
智能推荐算法
考虑历史数据趋势，排除近期已出号码
"""
import random
from typing import List, Dict
from src.algorithms.base import BaseAlgorithm


class SmartRecommendationAlgorithm(BaseAlgorithm):
    """智能推荐算法"""

    def generate(self, generations: int = 5, exclude_last: List[Dict] = None) -> List[Dict]:
        """生成预测号码"""
        missing_stats = self.analyzer.get_missing_stats()
        cold_numbers = self.analyzer.get_cold_numbers()['numbers']
        hot_numbers = self.analyzer.get_hot_numbers()['overall']

        recommendations = []
        for num in range(1, 34):
            miss = missing_stats.get(num, {}).get('current_missing', 0)
            is_hot = num in hot_numbers
            is_cold = num in cold_numbers

            score = miss
            if is_hot:
                score += 5
            if is_cold and miss > 10:
                score += 3

            recommendations.append((num, score))

        recommendations.sort(key=lambda x: x[1], reverse=True)

        results = []
        for _ in range(generations):
            top_pool = [r[0] for r in recommendations[:15]]
            red_balls = sorted(random.sample(top_pool, 6))

            blue_stats = self.analyzer.get_blue_ball_analysis()
            blue_hot = blue_stats.get('hot_numbers', [])
            blue_pool = list(set(blue_hot + [random.randint(1, 16)]))
            blue_ball = random.choice(blue_pool)

            result = self._get_common_prediction_info(red_balls, blue_ball, 'smart_recommendation')
            result['recommendation_basis'] = 'based on missing value and hot/cold analysis'
            results.append(result)

        return results
