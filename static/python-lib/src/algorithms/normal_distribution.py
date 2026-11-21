"""
正态分布模型
基于和值的正态分布生成组合

实现说明: 使用 random.gauss() 替代 numpy.random.normal(),
无需 numpy 依赖.
"""
import random
from typing import List, Dict
from src.algorithms.base import BaseAlgorithm


class NormalDistributionAlgorithm(BaseAlgorithm):
    """正态分布算法"""

    def generate(self, generations: int = 5) -> List[Dict]:
        """生成预测号码"""
        sum_stats = self.analyzer.get_sum_analysis()

        if not sum_stats:
            mean_sum, std_sum = 102, 15
        else:
            mean_sum = sum_stats.get('mean', 102)
            std_sum = sum_stats.get('std', 15)

        results = []
        for _ in range(generations):
            # random.gauss(mu, sigma) 等价于 numpy.random.normal(mu, sigma)
            target_sum = int(random.gauss(mean_sum, std_sum))
            target_sum = max(21, min(180, target_sum))

            red_balls = self._generate_balls_with_sum(target_sum)
            blue_ball = self._generate_blue_ball_normal()

            result = self._get_common_prediction_info(red_balls, blue_ball, 'normal_distribution')
            result['target_sum'] = target_sum
            results.append(result)

        return results

    def _generate_balls_with_sum(self, target_sum: int) -> List[int]:
        """生成指定和值的红球组合"""
        max_attempts = 1000

        for _ in range(max_attempts):
            balls = sorted(random.sample(range(1, 34), 6))
            current_sum = sum(balls)

            if abs(current_sum - target_sum) <= 3:
                return balls

            balls = self._adjust_balls_to_sum(balls, target_sum)
            if balls and sum(balls) == target_sum:
                return balls

        return sorted(random.sample(range(1, 34), 6))

    def _adjust_balls_to_sum(self, balls: List[int], target_sum: int) -> List[int]:
        """调整球使其接近目标和值"""
        balls = balls.copy()
        current_sum = sum(balls)
        diff = target_sum - current_sum

        if diff == 0:
            return balls

        for i in range(len(balls)):
            new_val = balls[i] + diff
            if 1 <= new_val <= 33 and new_val not in balls:
                balls[i] = new_val
                return sorted(balls)

        return sorted(balls)

    def _generate_blue_ball_normal(self) -> int:
        """基于正态分布生成蓝球"""
        # random.gauss(mu=8.5, sigma=4.5) 等价于 numpy.random.normal(8.5, 4.5)
        blue = int(random.gauss(8.5, 4.5))
        return max(1, min(16, blue))
