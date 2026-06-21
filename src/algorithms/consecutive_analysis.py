"""
连号分析算法
分析历史数据中连号出现的规律，生成包含连号的组合
"""
import random
from typing import List, Dict
from collections import Counter
from src.algorithms.base import BaseAlgorithm


class ConsecutiveAnalysisAlgorithm(BaseAlgorithm):
    """连号分析算法"""

    def generate(self, generations: int = 5) -> List[Dict]:
        """生成预测号码"""
        consecutive_prob = self._analyze_consecutive_probability()

        results = []
        for _ in range(generations):
            red_balls = []

            if random.random() < consecutive_prob:
                consecutive_count = random.randint(2, 3)
                start = random.randint(1, 33 - consecutive_count + 1)
                red_balls = list(range(start, start + consecutive_count))

                remaining = 6 - len(red_balls)
                other_pool = [n for n in range(1, 34) if n not in red_balls]
                red_balls.extend(random.sample(other_pool, remaining))
            else:
                red_balls = random.sample(range(1, 34), 6)

            red_balls = sorted(list(set(red_balls)))[:6]
            # 如果去重后不足 6 个，补充号码
            while len(red_balls) < 6:
                new_ball = random.randint(1, 33)
                if new_ball not in red_balls:
                    red_balls.append(new_ball)
            red_balls = sorted(red_balls)

            blue_ball = random.randint(1, 16)

            consecutive_info = self._check_consecutive(red_balls)

            result = self._get_common_prediction_info(red_balls, blue_ball, 'consecutive_analysis')
            result['consecutive'] = consecutive_info['has_consecutive']
            result['remark'] = f"{'含' if consecutive_info['has_consecutive'] else '无'}连号"
            results.append(result)

        return results

    def _analyze_consecutive_probability(self) -> float:
        """分析历史数据中连号出现的概率"""
        data = self.analyzer.data
        if not data:
            return 0.6

        consecutive_count = 0
        for record in data[-50:]:
            red_balls = sorted(record.get('red_balls', []))
            for i in range(len(red_balls) - 1):
                if red_balls[i+1] - red_balls[i] == 1:
                    consecutive_count += 1
                    break

        return consecutive_count / min(50, len(data))

    def _check_consecutive(self, red_balls: List[int]) -> Dict:
        """检查红球是否包含连号"""
        sorted_balls = sorted(red_balls)
        consecutive_pairs = []
        for i in range(len(sorted_balls) - 1):
            if sorted_balls[i+1] - sorted_balls[i] == 1:
                consecutive_pairs.append((sorted_balls[i], sorted_balls[i+1]))

        return {
            'has_consecutive': len(consecutive_pairs) > 0,
            'pairs': consecutive_pairs,
            'count': len(consecutive_pairs)
        }
