"""
蒙特卡洛模拟
大量模拟找出高概率组合
"""
import random
from typing import List, Dict
from src.algorithms.base import BaseAlgorithm


class MonteCarloAlgorithm(BaseAlgorithm):
    """蒙特卡洛算法"""

    def generate(self, generations: int = 5, simulations: int = 10000) -> List[Dict]:
        """生成预测号码"""
        simulation_results = []

        for _ in range(simulations):
            red_balls = sorted(random.sample(range(1, 34), 6))
            blue_ball = random.randint(1, 16)
            fitness = self._calculate_fitness(red_balls, blue_ball)
            simulation_results.append({
                'red_balls': red_balls,
                'blue_ball': blue_ball,
                'fitness': fitness
            })

        simulation_results.sort(key=lambda x: x['fitness'], reverse=True)

        results = []
        for i in range(generations):
            idx = i * len(simulation_results) // generations
            individual = simulation_results[idx]
            red_balls = individual['red_balls']

            result = self._get_common_prediction_info(red_balls, individual['blue_ball'], 'monte_carlo')
            result['fitness'] = individual['fitness']
            results.append(result)

        return results
