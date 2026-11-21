"""
遗传算法
通过进化优化生成最优组合
优化版本：修复潜在死循环，提升效率
"""
import random
from typing import List, Dict, Set
from src.algorithms.base import BaseAlgorithm


class GeneticAlgorithm(BaseAlgorithm):
    """遗传算法"""

    def generate(self, generations: int = 5, population_size: int = 50) -> List[Dict]:
        """生成预测号码"""
        population = self._init_population(population_size)

        for _ in range(20):
            population = self._evolve(population)

        results = []
        for i in range(min(generations, len(population))):
            individual = population[i]
            red_balls = sorted(individual['red_balls'])

            result = self._get_common_prediction_info(red_balls, individual['blue_ball'], 'genetic_algorithm')
            result['fitness'] = individual['fitness']
            results.append(result)

        return results

    def _init_population(self, size: int) -> List[Dict]:
        """初始化种群"""
        population = []
        for _ in range(size):
            red_balls = sorted(random.sample(range(1, 34), 6))
            blue_ball = random.randint(1, 16)
            population.append({
                'red_balls': red_balls,
                'blue_ball': blue_ball,
                'fitness': self._calculate_fitness(red_balls, blue_ball)
            })
        return population

    def _evolve(self, population: List[Dict]) -> List[Dict]:
        """进化一代"""
        population.sort(key=lambda x: x['fitness'], reverse=True)
        new_population = population[:10].copy()

        while len(new_population) < len(population):
            parent1 = self._tournament_selection(population)
            parent2 = self._tournament_selection(population)
            child = self._crossover(parent1, parent2)
            child = self._mutate(child)
            new_population.append(child)

        return new_population

    def _tournament_selection(self, population: List[Dict], k: int = 5) -> Dict:
        """锦标赛选择"""
        candidates = random.sample(population, k)
        return max(candidates, key=lambda x: x['fitness'])

    def _crossover(self, parent1: Dict, parent2: Dict) -> Dict:
        """交叉（优化版本）"""
        # 随机选择一个父本的红球作为基础
        base_parent = parent1 if random.random() < 0.5 else parent2
        other_parent = parent2 if base_parent == parent1 else parent1
        
        red_balls = set(base_parent['red_balls'])
        
        # 从另一个父本交换 1-2 个球
        exchange_count = random.randint(1, 2)
        for ball in other_parent['red_balls']:
            if exchange_count <= 0:
                break
            if ball not in red_balls:
                # 随机替换一个现有球
                to_remove = random.choice(list(red_balls))
                red_balls.discard(to_remove)
                red_balls.add(ball)
                exchange_count -= 1

        blue_ball = random.choice([parent1['blue_ball'], parent2['blue_ball']])

        return {
            'red_balls': sorted(list(red_balls))[:6],
            'blue_ball': blue_ball,
            'fitness': 0
        }

    def _mutate(self, individual: Dict, rate: float = 0.1) -> Dict:
        """变异（优化版本，避免死循环）"""
        red_balls = set(individual['red_balls'])
        all_numbers = set(range(1, 34))
        
        for ball in list(red_balls):
            if random.random() < rate:
                red_balls.discard(ball)
                # 从剩余号码中选择
                available = list(all_numbers - red_balls)
                if available:
                    red_balls.add(random.choice(available))

        # 蓝球变异
        if random.random() < rate:
            individual['blue_ball'] = random.randint(1, 16)

        # 确保数量为 6（使用集合操作，避免死循环）
        while len(red_balls) < 6:
            available = list(all_numbers - red_balls)
            if not available:
                break
            red_balls.add(random.choice(available))

        return {
            'red_balls': sorted(list(red_balls))[:6],
            'blue_ball': individual['blue_ball'],
            'fitness': 0
        }
