"""
K 均值聚类算法
将历史数据聚类，找出相似模式

实现说明: 用内置统计函数替代 numpy, 无 numpy 依赖.
"""
import random
import statistics
from typing import List, Dict
from collections import Counter
from src.algorithms.base import BaseAlgorithm


class KMeansClusteringAlgorithm(BaseAlgorithm):
    """K 均值聚类算法"""

    def generate(self, generations: int = 5) -> List[Dict]:
        """生成预测号码"""
        clusters = self._cluster_historical_data()

        results = []
        for _ in range(generations):
            red_balls = []

            if clusters:
                selected_cluster = random.choice(clusters)
                center = selected_cluster.get('center', [])

                for c in center[:4]:
                    for offset in [-1, 0, 1]:
                        candidate = c + offset
                        if 1 <= candidate <= 33 and candidate not in red_balls:
                            red_balls.append(candidate)
                            if len(red_balls) >= 6:
                                break
                    if len(red_balls) >= 6:
                        break

            # 确保号码不重复且数量为 6 个
            red_balls = sorted(list(set(red_balls)))
            while len(red_balls) < 6:
                new_ball = random.randint(1, 33)
                if new_ball not in red_balls:
                    red_balls.append(new_ball)
            red_balls = sorted(red_balls[:6])

            blue_ball = self._predict_blue_ball_clustering(clusters)

            result = self._get_common_prediction_info(red_balls, blue_ball, 'kmeans_clustering')
            result['remark'] = '基于历史数据聚类'
            results.append(result)

        return results

    def _cluster_historical_data(self, k: int = 5) -> List[Dict]:
        """简单的聚类分析"""
        data = self.analyzer.data
        if not data:
            return []

        features = []
        for record in data[:100]:
            red_balls = record.get('red_balls', [])
            if len(red_balls) == 6:
                # 标准差: statistics.stdev 需要至少 2 个点, 0/1 个点时退化为 0
                std_val = statistics.stdev(red_balls) if len(red_balls) > 1 else 0
                features.append({
                    'red_balls': red_balls,
                    'sum': sum(red_balls),
                    'mean': sum(red_balls) / 6,
                    'std': std_val
                })

        if not features:
            return []

        sum_groups = {}
        for f in features:
            sum_range = (f['sum'] // 20) * 20
            if sum_range not in sum_groups:
                sum_groups[sum_range] = []
            sum_groups[sum_range].append(f)

        clusters = []
        for sum_range, group in sum_groups.items():
            if group:
                centers = sorted(group[0]['red_balls'])
                clusters.append({
                    'center': centers,
                    'sum_range': sum_range,
                    'count': len(group)
                })

        return clusters

    def _predict_blue_ball_clustering(self, clusters: List[Dict]) -> int:
        """基于聚类结果预测蓝球"""
        if not clusters:
            return random.randint(1, 16)

        blue_counts = Counter()
        for cluster in clusters:
            blue_counts[random.randint(1, 16)] += cluster.get('count', 0)

        if blue_counts:
            return blue_counts.most_common(1)[0][0]
        return random.randint(1, 16)
