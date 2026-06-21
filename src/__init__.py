"""
双色球数据模块
"""
from .crawler import Crawler
from .analyzer import Analyzer
from .cache import DataCache, analysis_cache, prediction_cache, cached_analysis, cached_prediction

# 算法模块
from .algorithms import (
    BaseAlgorithm,
    WeightedRandomAlgorithm,
    NormalDistributionAlgorithm,
    GeneticAlgorithm,
    MonteCarloAlgorithm,
    ComprehensiveAlgorithm,
    SmartRecommendationAlgorithm,
    ZoneDistributionAlgorithm,
    ConsecutiveAnalysisAlgorithm,
    SameTailAnalysisAlgorithm,
    PrimeCompositeAlgorithm,
    BigSmallAnalysisAlgorithm,
    MarkovChainAlgorithm,
    KMeansClusteringAlgorithm,
)

__all__ = [
    'Crawler',
    'Analyzer',
    'DataCache',
    'analysis_cache',
    'prediction_cache',
    'cached_analysis',
    'cached_prediction',
    # 算法类
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
