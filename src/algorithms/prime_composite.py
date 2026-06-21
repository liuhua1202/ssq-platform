"""
质合数算法
基于质数和合数的比例生成号码
质数：2,3,5,7,11,13,17,19,23,29,31 (共 11 个)
合数：其余号码 (共 22 个)
"""
import random
from typing import List, Dict
from src.algorithms.base import BaseAlgorithm


class PrimeCompositeAlgorithm(BaseAlgorithm):
    """质合数分析算法"""

    def __init__(self, analyzer, config=None):
        super().__init__(analyzer, config)
        self.primes = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}

    def generate(self, generations: int = 5) -> List[Dict]:
        """生成预测号码"""
        prime_ratio = self._analyze_prime_ratio()

        results = []
        for _ in range(generations):
            if random.random() < prime_ratio:
                prime_count = random.choice([3, 4])
            else:
                prime_count = random.choice([2, 3])

            composite_count = 6 - prime_count

            prime_list = sorted(list(self.primes))
            selected_primes = random.sample(prime_list, min(prime_count, len(prime_list)))

            composite_list = [n for n in range(1, 34) if n not in self.primes]
            selected_composites = random.sample(composite_list, min(composite_count, len(composite_list)))

            red_balls = sorted(selected_primes + selected_composites)
            blue_ball = random.randint(1, 16)

            actual_prime_count = sum(1 for r in red_balls if r in self.primes)
            actual_composite_count = 6 - actual_prime_count

            result = self._get_common_prediction_info(red_balls, blue_ball, 'prime_composite')
            result['prime_count'] = actual_prime_count
            result['composite_count'] = actual_composite_count
            result['remark'] = f"质合比{actual_prime_count}:{actual_composite_count}"
            results.append(result)

        return results

    def _analyze_prime_ratio(self) -> float:
        """分析历史数据中质数出现的平均比例"""
        data = self.analyzer.data
        if not data:
            return 0.5

        total_prime_count = 0
        for record in data[-50:]:
            red_balls = record.get('red_balls', [])
            total_prime_count += sum(1 for r in red_balls if r in self.primes)

        return total_prime_count / (min(50, len(data)) * 6)
