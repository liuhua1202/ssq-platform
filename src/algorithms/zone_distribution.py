"""
区间分布算法
将 33 个红球分为 3 个区间，根据历史区间比例生成号码
一区：1-11, 二区：12-22, 三区：23-33
"""
import random
from typing import List, Dict
from collections import Counter
from src.algorithms.base import BaseAlgorithm


class ZoneDistributionAlgorithm(BaseAlgorithm):
    """区间分布算法"""

    def generate(self, generations: int = 5) -> List[Dict]:
        """生成预测号码"""
        zone_ratio = self._analyze_zone_distribution()

        results = []
        for _ in range(generations):
            red_balls = []

            for zone_idx, zone_count in enumerate(zone_ratio):
                zone_start = zone_idx * 11 + 1
                zone_end = min(33, (zone_idx + 1) * 11)
                zone_numbers = list(range(zone_start, zone_end + 1))
                selected = random.sample(zone_numbers, min(zone_count, len(zone_numbers)))
                red_balls.extend(selected)

            # 确保号码不重复且数量为 6 个
            red_balls = sorted(list(set(red_balls)))
            while len(red_balls) < 6:
                remaining = [n for n in range(1, 34) if n not in red_balls]
                if remaining:
                    red_balls.append(random.choice(remaining))
                else:
                    break
            red_balls = sorted(red_balls[:6])

            blue_ball = random.randint(1, 16)

            zone_info = self._get_zone_info(red_balls)

            result = self._get_common_prediction_info(red_balls, blue_ball, 'zone_distribution')
            result['zone_ratio'] = zone_info['ratio']
            result['remark'] = f"区间比{zone_info['ratio']}"
            results.append(result)

        return results

    def _analyze_zone_distribution(self) -> List[int]:
        """分析历史数据的区间分布"""
        data = self.analyzer.data
        if not data:
            return [2, 2, 2]

        zone_counts = []
        for record in data[-50:]:
            red_balls = record.get('red_balls', [])
            zone1 = sum(1 for r in red_balls if 1 <= r <= 11)
            zone2 = sum(1 for r in red_balls if 12 <= r <= 22)
            zone3 = sum(1 for r in red_balls if 23 <= r <= 33)
            zone_counts.append((zone1, zone2, zone3))

        counter = Counter(zone_counts)
        most_common = counter.most_common(1)
        if most_common:
            return list(most_common[0][0])
        return [2, 2, 2]

    def _get_zone_info(self, red_balls: List[int]) -> Dict:
        """获取红球的区间信息"""
        zone1 = sum(1 for r in red_balls if 1 <= r <= 11)
        zone2 = sum(1 for r in red_balls if 12 <= r <= 22)
        zone3 = sum(1 for r in red_balls if 23 <= r <= 33)
        return {'ratio': f"{zone1}:{zone2}:{zone3}", 'counts': [zone1, zone2, zone3]}
