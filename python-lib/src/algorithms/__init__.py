"""
双色球预测算法包
"""
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

__all__ = [
    'BaseAlgorithm',
    'WeightedRandomAlgorithm',
    'NormalDistributionAlgorithm',
    'GeneticAlgorithm',
    'MonteCarloAlgorithm',
    'ComprehensiveAlgorithm',
    'SmartRecommendationAlgorithm',
    'ZoneDistributionAlgorithm',
    'ConsecutiveAnalysisAlgorithm',
    'SameTailAnalysisAlgorithm',
    'PrimeCompositeAlgorithm',
    'BigSmallAnalysisAlgorithm',
    'MarkovChainAlgorithm',
    'KMeansClusteringAlgorithm',
]
