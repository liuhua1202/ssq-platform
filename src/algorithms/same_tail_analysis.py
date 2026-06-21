"""
同尾号算法
分析同尾数（如 5,15,25）的出现规律
"""
import random
from typing import List, Dict
from collections import Counter
from src.algorithms.base import BaseAlgorithm


class SameTailAnalysisAlgorithm(BaseAlgorithm):
    """同尾号分析算法"""

    def generate(self, generations: int = 5) -> List[Dict]:
        """生成预测号码"""
        tail_patterns = self._analyze_same_tail_patterns()

        results = []
        for _ in range(generations):
            target_tail = random.randint(0, 9)
            same_tail_count = random.choice(tail_patterns.get('common_counts', [2, 2, 3]))

            tail_numbers = [n for n in range(1, 34) if n % 10 == target_tail]
            red_balls = random.sample(tail_numbers, min(same_tail_count, len(tail_numbers)))

            remaining = 6 - len(red_balls)
            other_pool = [n for n in range(1, 34) if n % 10 != target_tail and n not in red_balls]
            if len(other_pool) >= remaining:
                red_balls.extend(random.sample(other_pool, remaining))

            red_balls = sorted(list(set(red_balls)))[:6]
            # 如果去重后不足 6 个，补充号码
            while len(red_balls) < 6:
                new_ball = random.randint(1, 33)
                if new_ball not in red_balls:
                    red_balls.append(new_ball)
            red_balls = sorted(red_balls)

            blue_ball = random.randint(1, 16)

            tail_info = self._analyze_tails(red_balls)

            result = self._get_common_prediction_info(red_balls, blue_ball, 'same_tail_analysis')
            result['tail_info'] = tail_info['tails']
            result['remark'] = f"尾数{target_tail}出现{tail_info['tail_counts'].get(target_tail, 0)}次"
            results.append(result)

        return results

    def _analyze_same_tail_patterns(self) -> Dict:
        """分析历史数据的同尾号模式"""
        data = self.analyzer.data
        if not data:
            return {'common_counts': [2, 2, 3]}

        tail_counts = []
        for record in data[-50:]:
            red_balls = record.get('red_balls', [])
            tails = [n % 10 for n in red_balls]
            tail_counter = Counter(tails)
            max_same_tail = max(tail_counter.values()) if tail_counter else 1
            tail_counts.append(max_same_tail)

        counter = Counter(tail_counts)
        common = counter.most_common(3)
        return {'common_counts': [c[0] for c in common]}

    def _analyze_tails(self, red_balls: List[int]) -> Dict:
        """分析红球的尾数分布"""
        tails = [n % 10 for n in red_balls]
        tail_counter = Counter(tails)
        return {
            'tails': list(set(tails)),
            'tail_counts': dict(tail_counter),
            'unique_tails': len(set(tails))
        }
