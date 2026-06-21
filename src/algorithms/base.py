"""
双色球预测算法基类
所有预测算法都应继承此类并实现 generate 方法

算法开发指南：
1. 继承 BaseAlgorithm 类
2. 实现 generate() 方法
3. 使用 _calculate_fitness() 评估号码质量
4. 使用 _get_common_prediction_info() 生成标准输出格式
5. 使用 _weighted_sample() 或 _weighted_sample_unique() 进行加权采样

示例：
    class MyAlgorithm(BaseAlgorithm):
        def generate(self, generations=5):
            predictions = []
            for _ in range(generations):
                # 生成号码逻辑
                red_balls = [...]
                blue_ball = ...
                
                predictions.append(
                    self._get_common_prediction_info(
                        red_balls, blue_ball, 'my_algorithm'
                    )
                )
            return predictions
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import random


class BaseAlgorithm(ABC):
    """
    预测算法基类
    
    所有双色球预测算法都必须继承此类并实现 generate() 方法。
    提供了通用的工具方法用于号码评估和采样。
    
    Attributes:
        analyzer: 数据分析器实例，提供统计分析功能
        config: 算法配置参数字典
        name: 算法名称（默认为类名）
    """

    def __init__(self, analyzer, config: Dict = None):
        """
        初始化算法

        Args:
            analyzer: 数据分析器实例，用于获取统计分析结果
            config: 算法配置参数，可包含权重、策略等设置
        """
        self.analyzer = analyzer
        self.config = config or {}
        self.name = self.__class__.__name__

    @abstractmethod
    def generate(self, generations: int = 5) -> List[Dict[str, Any]]:
        """
        生成预测号码

        Args:
            generations: 生成注数

        Returns:
            预测结果列表，每项包含 red_balls, blue_ball, algorithm 等信息
        """
        pass

    def _calculate_fitness(self, red_balls: List[int], blue_ball: int) -> float:
        """
        计算号码组合的适应度评分

        Args:
            red_balls: 红球列表
            blue_ball: 蓝球

        Returns:
            适应度评分
        """
        fitness = 0

        # 热号加分
        hot_numbers = self.analyzer.get_hot_numbers()['overall']
        for ball in red_balls:
            if ball in hot_numbers:
                fitness += 2

        # 蓝球热号加分
        blue_stats = self.analyzer.get_blue_ball_analysis()
        if blue_ball in blue_stats.get('hot_numbers', []):
            fitness += 3

        # 和值接近平均值加分
        sum_val = sum(red_balls)
        sum_stats = self.analyzer.get_sum_analysis()
        if sum_stats:
            mean_sum = sum_stats.get('mean', 102)
            fitness += max(0, 10 - abs(sum_val - mean_sum) / 5)

        # AC 指数适中加分
        ac = self.analyzer.get_ac_index(red_balls)
        if 4 <= ac <= 10:
            fitness += 2

        return fitness

    def _get_common_prediction_info(self, red_balls: List[int], blue_ball: int, algorithm: str) -> Dict:
        """
        获取预测结果的公共信息

        Args:
            red_balls: 红球列表
            blue_ball: 蓝球
            algorithm: 算法名称

        Returns:
            包含公共信息的字典
        """
        return {
            'red_balls': sorted(red_balls),
            'blue_ball': blue_ball,
            'algorithm': algorithm,
            'sum': sum(red_balls),
            'odd_even': f"{sum(1 for r in red_balls if r % 2)}:{sum(1 for r in red_balls if r % 2 == 0)}",
            'ac_index': self.analyzer.get_ac_index(red_balls)
        }

    @staticmethod
    def _weighted_sample(population: List, weights: List, k: int) -> List:
        """加权采样（允许重复）"""
        return random.choices(population, weights=weights, k=k)

    @staticmethod
    def _weighted_sample_unique(population: List, weights: List, k: int) -> List:
        """加权采样（确保不重复）"""
        result = set()
        available = list(population)
        available_weights = list(weights)

        while len(result) < k and available:
            idx = random.choices(range(len(available)), weights=available_weights, k=1)[0]
            result.add(available[idx])
            # 移除已选中的元素
            available.pop(idx)
            available_weights.pop(idx)

        # 如果去重后不足 k 个，补充随机号码
        while len(result) < k:
            result.add(random.randint(1, 33))

        return list(result)
