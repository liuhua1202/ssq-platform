"""
双色球预测器 - 统一接口
优化版本：缓存算法实例，添加内存清理机制
"""
import logging
from typing import List, Dict
from src.algorithms.base import BaseAlgorithm
from src.algorithms.weighted_random import WeightedRandomAlgorithm
from src.algorithms.normal_distribution import NormalDistributionAlgorithm
from src.algorithms.genetic import GeneticAlgorithm
from src.algorithms.monte_carlo import MonteCarloAlgorithm
from src.algorithms.comprehensive import ComprehensiveAlgorithm
from src.algorithms.smart_recommendation import SmartRecommendationAlgorithm
from src.algorithms.zone_distribution import ZoneDistributionAlgorithm
from src.algorithms.consecutive_analysis import ConsecutiveAnalysisAlgorithm
from src.algorithms.same_tail_analysis import SameTailAnalysisAlgorithm
from src.algorithms.prime_composite import PrimeCompositeAlgorithm
from src.algorithms.big_small_analysis import BigSmallAnalysisAlgorithm
from src.algorithms.markov_chain import MarkovChainAlgorithm
from src.algorithms.kmeans_clustering import KMeansClusteringAlgorithm

logger = logging.getLogger(__name__)


class Predictor:
    """双色球预测器 - 统一接口"""

    # 算法类映射
    ALGORITHM_CLASSES = {
        'weighted_random': WeightedRandomAlgorithm,
        'normal_distribution': NormalDistributionAlgorithm,
        'genetic_algorithm': GeneticAlgorithm,
        'monte_carlo': MonteCarloAlgorithm,
        'comprehensive': ComprehensiveAlgorithm,
        'smart_recommendation': SmartRecommendationAlgorithm,
        'zone_distribution': ZoneDistributionAlgorithm,
        'consecutive_analysis': ConsecutiveAnalysisAlgorithm,
        'same_tail_analysis': SameTailAnalysisAlgorithm,
        'prime_composite': PrimeCompositeAlgorithm,
        'big_small_analysis': BigSmallAnalysisAlgorithm,
        'markov_chain': MarkovChainAlgorithm,
        'kmeans_clustering': KMeansClusteringAlgorithm,
    }

    # 最大缓存实例数，防止内存泄漏
    MAX_CACHED_INSTANCES = 20

    def __init__(self, analyzer, config: Dict = None):
        """
        初始化预测器

        Args:
            analyzer: 数据分析器实例
            config: 全局配置参数
        """
        self.analyzer = analyzer
        self.config = config or {}
        self._algorithm_instances: Dict[str, BaseAlgorithm] = {}
        self._instance_access_order: List[str] = []  # 记录访问顺序用于 LRU 淘汰

    def _get_algorithm(self, name: str) -> BaseAlgorithm:
        """获取或创建算法实例（带缓存和 LRU 淘汰）"""
        if name not in self.ALGORITHM_CLASSES:
            raise ValueError(f'未知的算法：{name}')

        # 如果已存在，更新访问顺序
        if name in self._algorithm_instances:
            self._update_access_order(name)
            return self._algorithm_instances[name]

        # 检查是否需要淘汰旧实例
        if len(self._algorithm_instances) >= self.MAX_CACHED_INSTANCES:
            self._evict_lru_instance()

        # 创建新实例
        algo_class = self.ALGORITHM_CLASSES[name]
        self._algorithm_instances[name] = algo_class(self.analyzer, self.config)
        self._instance_access_order.append(name)
        logger.debug(f"创建算法实例：{name}，当前缓存数：{len(self._algorithm_instances)}")

        return self._algorithm_instances[name]

    def _update_access_order(self, name: str):
        """更新访问顺序（移到末尾表示最近访问）"""
        if name in self._instance_access_order:
            self._instance_access_order.remove(name)
        self._instance_access_order.append(name)

    def _evict_lru_instance(self):
        """淘汰最久未使用的算法实例"""
        if self._instance_access_order:
            lru_name = self._instance_access_order.pop(0)
            if lru_name in self._algorithm_instances:
                del self._algorithm_instances[lru_name]
                logger.debug(f"淘汰算法实例：{lru_name}")

    def clear_cache(self):
        """清空所有算法实例缓存"""
        count = len(self._algorithm_instances)
        self._algorithm_instances.clear()
        self._instance_access_order.clear()
        logger.info(f"已清空 {count} 个算法实例缓存")

    def predict(self, algorithm: str, generations: int = 5) -> List[Dict]:
        """
        使用指定算法生成预测

        Args:
            algorithm: 算法名称
            generations: 生成注数

        Returns:
            预测结果列表

        Raises:
            ValueError: 算法不存在
        """
        algo = self._get_algorithm(algorithm)
        return algo.generate(generations)

    def get_available_algorithms(self) -> List[str]:
        """获取所有可用算法名称"""
        return list(self.ALGORITHM_CLASSES.keys())

    # 保持向后兼容的方法（已废弃，建议使用 predict）
    def generate_weighted_random(self, generations: int = 5) -> List[Dict]:
        return self.predict('weighted_random', generations)

    def generate_normal_distribution(self, generations: int = 5) -> List[Dict]:
        return self.predict('normal_distribution', generations)

    def generate_genetic_algorithm(self, generations: int = 5) -> List[Dict]:
        return self.predict('genetic_algorithm', generations)

    def generate_monte_carlo(self, generations: int = 5) -> List[Dict]:
        return self.predict('monte_carlo', generations)

    def generate_comprehensive(self, generations: int = 5) -> List[Dict]:
        return self.predict('comprehensive', generations)

    def generate_smart_recommendation(self, generations: int = 5) -> List[Dict]:
        return self.predict('smart_recommendation', generations)

    def generate_zone_distribution(self, generations: int = 5) -> List[Dict]:
        return self.predict('zone_distribution', generations)

    def generate_consecutive_analysis(self, generations: int = 5) -> List[Dict]:
        return self.predict('consecutive_analysis', generations)

    def generate_same_tail_analysis(self, generations: int = 5) -> List[Dict]:
        return self.predict('same_tail_analysis', generations)

    def generate_prime_composite(self, generations: int = 5) -> List[Dict]:
        return self.predict('prime_composite', generations)

    def generate_big_small_analysis(self, generations: int = 5) -> List[Dict]:
        return self.predict('big_small_analysis', generations)

    def generate_markov_chain(self, generations: int = 5) -> List[Dict]:
        return self.predict('markov_chain', generations)

    def generate_kmeans_clustering(self, generations: int = 5) -> List[Dict]:
        return self.predict('kmeans_clustering', generations)
