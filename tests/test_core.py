"""
双色球预测平台 - 单元测试
测试核心功能：数据分析、预测算法、API 端点
"""
import unittest
import json
import os
import sys
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.analyzer import Analyzer
from src.predictor import Predictor
from src.cache import DataCache, analysis_cache, prediction_cache


class TestAnalyzer(unittest.TestCase):
    """数据分析器测试"""
    
    def setUp(self):
        """测试数据"""
        self.test_data = [
            {
                'issue': '2024001',
                'date': '2024-01-02',
                'red_balls': [5, 10, 15, 20, 25, 30],
                'blue_ball': 8
            },
            {
                'issue': '2024002',
                'date': '2024-01-04',
                'red_balls': [3, 8, 17, 22, 28, 31],
                'blue_ball': 12
            },
            {
                'issue': '2024003',
                'date': '2024-01-07',
                'red_balls': [1, 6, 11, 16, 21, 26],
                'blue_ball': 5
            }
        ]
        self.analyzer = Analyzer(self.test_data)
    
    def test_frequency_stats(self):
        """测试频率统计"""
        stats = self.analyzer.get_frequency_stats([1, 2, 3, 1, 2, 1], 1, 33)
        self.assertEqual(stats[1]['count'], 3)
        self.assertEqual(stats[2]['count'], 2)
        self.assertEqual(stats[3]['count'], 1)
    
    def test_hot_numbers(self):
        """测试热号计算"""
        hot = self.analyzer.get_hot_numbers(top_n=5)
        self.assertIn('overall', hot)
        self.assertIn('recent', hot)
        self.assertLessEqual(len(hot['overall']), 5)
    
    def test_cold_numbers(self):
        """测试冷号计算"""
        cold = self.analyzer.get_cold_numbers(top_n=5)
        self.assertIn('numbers', cold)
        self.assertLessEqual(len(cold['numbers']), 5)
    
    def test_missing_stats(self):
        """测试遗漏值统计"""
        missing = self.analyzer.get_missing_stats()
        self.assertEqual(len(missing), 33)  # 33个红球
        for num in range(1, 34):
            self.assertIn(num, missing)
            self.assertIn('current_missing', missing[num])
    
    def test_odd_even_ratio(self):
        """测试奇偶比分析"""
        ratio = self.analyzer.get_odd_even_ratio()
        self.assertIn('distribution', ratio)
        self.assertIn('avg_odd', ratio)
        self.assertIn('avg_even', ratio)
    
    def test_sum_analysis(self):
        """测试和值分析"""
        sum_analysis = self.analyzer.get_sum_analysis()
        self.assertIn('min', sum_analysis)
        self.assertIn('max', sum_analysis)
        self.assertIn('mean', sum_analysis)
    
    def test_blue_ball_analysis(self):
        """测试蓝球分析"""
        blue = self.analyzer.get_blue_ball_analysis()
        self.assertIn('stats', blue)
        self.assertIn('hot_numbers', blue)
        self.assertIn('cold_numbers', blue)
    
    def test_ac_index(self):
        """测试 AC 指数计算"""
        ac = self.analyzer.get_ac_index([1, 5, 10, 15, 20, 25])
        self.assertIsInstance(ac, (int, float))  # AC指数可能是整数
        self.assertGreater(ac, 0)
    
    def test_comprehensive_analysis(self):
        """测试综合分析"""
        analysis = self.analyzer.get_comprehensive_analysis()
        self.assertIn('total_records', analysis)
        self.assertEqual(analysis['total_records'], 3)
        self.assertIn('hot_numbers', analysis)
        self.assertIn('cold_numbers', analysis)


class TestCache(unittest.TestCase):
    """缓存系统测试"""
    
    def setUp(self):
        self.cache = DataCache(max_size=10, ttl=2)  # 2秒TTL用于测试过期
    
    def test_cache_set_get(self):
        """测试缓存读写"""
        self.cache.set('test_key', 'test_value')
        value = self.cache.get('test_key')
        self.assertEqual(value, 'test_value')
    
    def test_cache_miss(self):
        """测试缓存未命中"""
        value = self.cache.get('nonexistent')
        self.assertIsNone(value)
    
    def test_cache_expiry(self):
        """测试缓存过期"""
        import time
        self.cache.set('temp', 'value')
        self.assertEqual(self.cache.get('temp'), 'value')
        
        # 等待过期
        time.sleep(2.1)
        self.assertIsNone(self.cache.get('temp'))
    
    def test_cache_max_size(self):
        """测试缓存容量限制"""
        for i in range(15):
            self.cache.set(f'key_{i}', f'value_{i}')
        
        # 缓存大小不应超过 max_size
        self.assertLessEqual(len(self.cache._cache), 10)
    
    def test_cache_clear(self):
        """测试清空缓存"""
        self.cache.set('key1', 'value1')
        self.cache.set('key2', 'value2')
        self.cache.clear()
        
        self.assertIsNone(self.cache.get('key1'))
        self.assertIsNone(self.cache.get('key2'))
    
    def test_cache_stats(self):
        """测试缓存统计"""
        self.cache.set('key', 'value')
        self.cache.get('key')  # hit
        self.cache.get('missing')  # miss
        
        stats = self.cache.stats()
        self.assertIn('hits', stats)
        self.assertIn('misses', stats)
        self.assertIn('hit_rate', stats)
        self.assertGreater(stats['hits'], 0)


class TestPredictor(unittest.TestCase):
    """预测器测试"""
    
    def setUp(self):
        """测试数据"""
        self.test_data = [
            {
                'issue': f'2024{i:03d}',
                'date': f'2024-01-{(i*2):02d}',
                'red_balls': [i, i+5, i+10, i+15, i+20, i+25],
                'blue_ball': (i % 16) + 1
            }
            for i in range(1, 21)
        ]
        self.analyzer = Analyzer(self.test_data)
        self.predictor = Predictor(self.analyzer)
    
    def test_predict_comprehensive(self):
        """测试综合推荐算法"""
        predictions = self.predictor.predict('comprehensive', generations=5)
        self.assertEqual(len(predictions), 5)
        
        for pred in predictions:
            self.assertIn('red_balls', pred)
            self.assertIn('blue_ball', pred)
            self.assertEqual(len(pred['red_balls']), 6)
            self.assertIsInstance(pred['blue_ball'], int)
    
    def test_predict_weighted_random(self):
        """测试加权随机算法"""
        predictions = self.predictor.predict('weighted_random', generations=3)
        self.assertEqual(len(predictions), 3)
    
    def test_predict_invalid_algorithm(self):
        """测试无效算法"""
        with self.assertRaises(ValueError):
            self.predictor.predict('invalid_algorithm')
    
    def test_predict_ball_range(self):
        """测试号码范围"""
        predictions = self.predictor.predict('comprehensive', generations=10)
        
        for pred in predictions:
            for red in pred['red_balls']:
                self.assertGreaterEqual(red, 1)
                self.assertLessEqual(red, 33)
            
            self.assertGreaterEqual(pred['blue_ball'], 1)
            self.assertLessEqual(pred['blue_ball'], 16)
    
    def test_get_available_algorithms(self):
        """测试获取可用算法列表"""
        algorithms = self.predictor.get_available_algorithms()
        self.assertIn('comprehensive', algorithms)
        self.assertIn('weighted_random', algorithms)
        self.assertGreater(len(algorithms), 10)
    
    def test_predictor_cache_cleanup(self):
        """测试预测器缓存清理功能"""
        # 生成多个算法实例
        for _ in range(5):
            self.predictor.predict('comprehensive', generations=1)
            self.predictor.predict('weighted_random', generations=1)
        
        # 验证缓存存在
        self.assertGreater(len(self.predictor._algorithm_instances), 0)
        
        # 清空缓存
        self.predictor.clear_cache()
        
        # 验证缓存已清空
        self.assertEqual(len(self.predictor._algorithm_instances), 0)
        self.assertEqual(len(self.predictor._instance_access_order), 0)
    
    def test_predictor_lru_eviction(self):
        """测试 LRU 淘汰机制"""
        # 临时设置较小的缓存限制
        original_max = self.predictor.MAX_CACHED_INSTANCES
        self.predictor.MAX_CACHED_INSTANCES = 3
        
        try:
            # 创建超过限制的实例
            algorithms = ['comprehensive', 'weighted_random', 'normal_distribution', 'monte_carlo']
            for algo in algorithms:
                self.predictor.predict(algo, generations=1)
            
            # 验证缓存不超过限制
            self.assertLessEqual(len(self.predictor._algorithm_instances), 3)
        finally:
            # 恢复原始值
            self.predictor.MAX_CACHED_INSTANCES = original_max


class TestInputValidation(unittest.TestCase):
    """输入验证测试"""
    
    def test_ball_validation(self):
        """测试号码验证逻辑"""
        # 红球范围验证
        red_balls = [1, 15, 33]
        self.assertTrue(all(1 <= r <= 33 for r in red_balls))
        
        # 蓝球范围验证
        blue_ball = 16
        self.assertTrue(1 <= blue_ball <= 16)
        
        # 无效号码
        invalid_red = [0, 34, 100]
        self.assertFalse(all(1 <= r <= 33 for r in invalid_red))


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试
    suite.addTests(loader.loadTestsFromTestCase(TestAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestCache))
    suite.addTests(loader.loadTestsFromTestCase(TestPredictor))
    suite.addTests(loader.loadTestsFromTestCase(TestInputValidation))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 返回结果
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
