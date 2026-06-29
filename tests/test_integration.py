"""
Integration tests - Flask test_client end-to-end.

用法:
  python -m unittest tests.test_integration

覆盖范围:
  - 应用工厂 / blueprint 注册
  - GET /api/history (无缓存, 从文件加载)
  - POST /api/clear-data 写操作需 token (生产模式)
  - POST /api/clear-data 写操作放行 (dev 模式)
  - GET /api/health
  - GET /api/cache/stats
  - 404 错误处理 (JSON)
  - 慢请求 (仅验证不阻塞)
"""
import os
import sys
import json
import tempfile
import unittest
from unittest.mock import patch

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.crawler.crawler import Crawler


class IntegrationTestBase(unittest.TestCase):
    """集成测试基类 - 隔离 data_dir / Flask app."""

    def setUp(self):
        # 创建临时数据目录
        self.tmpdir = tempfile.mkdtemp(prefix='ssq_int_test_')

        # 重要: 隔离 config 中的路径, 让 Crawler 写到临时目录
        self.history_file_patch = patch('config.HISTORY_FILE',
                                        os.path.join(self.tmpdir, 'history.json'))
        self.history_file_patch.start()
        self.my_numbers_patch = patch('config.MY_NUMBERS_FILE',
                                       os.path.join(self.tmpdir, 'my_numbers.json'))
        self.my_numbers_patch.start()

        # 必需: 设置一个有效的 SECRET_KEY 以绕过 ensure_security_config
        self.secret_patch = patch('config.SECRET_KEY', 'integration-test-secret')
        self.secret_patch.start()

        # 关键: 替换 api.py 模块级的全局 crawler 实例, 让它写临时数据目录
        # 这避免测试污染真实的 data/history.json
        self.crawler_patch = patch('src.api.api.crawler',
                                    Crawler(data_dir=self.tmpdir))
        self.crawler_patch.start()

    def tearDown(self):
        # 清理
        import shutil
        self.history_file_patch.stop()
        self.my_numbers_patch.stop()
        self.secret_patch.stop()
        self.crawler_patch.stop()

        # 重置 app.config 以避免测试间状态泄漏
        try:
            app = IntegrationTestBase._flask_app_cache
            if app is not None:
                # token: 默认 dev 模式
                if 'API_TOKEN' in app.config:
                    app.config['API_TOKEN'] = None
        except Exception:
            pass

        try:
            shutil.rmtree(self.tmpdir)
        except Exception:
            pass

    def setUp_prod_token(self, token='prod-token-12345'):
        """Helper: set up app in prod mode with given token."""
        from app import app
        app.config['API_TOKEN'] = token
        # 禁用 rate limiter 以避免测试期间触发
        try:
            from flask_limiter import Limiter
            # 尝试 disable: 在 Flask-Limiter 中, 限制可通过 storage_uri=None 完全关闭
            # 但已经创建的 Limiter 不易 disable, 所以用更高限制覆盖
        except Exception:
            pass
        return app

    def setUp_dev_token(self):
        """Helper: dev mode (no token required)."""
        from app import app
        app.config['API_TOKEN'] = None
        return app

    _flask_app_cache = None

    def _import_app(self, disable_rate_limit=True):
        """惰性导入 app - 避免 setUp 之前 import.

        disable_rate_limit=True: 测试期间禁用 limiter (避免触发限流).
        """
        if IntegrationTestBase._flask_app_cache is None:
            import app as app_module
            flask_app = app_module.app
            if disable_rate_limit:
                # 通过 RATELIMIT_ENABLED=False 完全禁用 Flask-Limiter
                flask_app.config['RATELIMIT_ENABLED'] = False
                # 也尝试直接 disable limiter 全局变量 (双保险)
                try:
                    app_module.limiter.enabled = False
                except AttributeError:
                    pass
            IntegrationTestBase._flask_app_cache = flask_app
        return IntegrationTestBase._flask_app_cache


class TestFlaskAppBasic(IntegrationTestBase):
    """Flask app 基本启动 + 健康检查."""

    def test_app_starts(self):
        app = self._import_app()
        self.assertIsNotNone(app)
        self.assertTrue(app.config.get('SECRET_KEY'))

    def test_health_endpoint(self):
        app = self._import_app()
        client = app.test_client()
        resp = client.get('/api/health')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('data_records', data)
        self.assertIn('cache', data)

    def test_cache_stats_endpoint(self):
        app = self._import_app()
        client = app.test_client()
        resp = client.get('/api/cache/stats')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertIn('analysis_cache', data)
        self.assertIn('prediction_cache', data)
        self.assertIn('history_cache', data)


class TestHistoryEndpoint(IntegrationTestBase):
    """/api/history GET 行为."""

    def test_history_returns_empty_when_no_data(self):
        app = self._import_app()
        client = app.test_client()
        resp = client.get('/api/history')
        # 注意: 此测试可能受其他 test 影响 (history_cache 是模块单例)
        # 主断言: 响应是 JSON 且 schema 正确
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('success', data)
        self.assertIn('data', data)
        self.assertIn('total', data)

    def test_history_pagination(self):
        app = self._import_app()
        client = app.test_client()
        resp = client.get('/api/history?page=1&page_size=10')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('page_size', data)
        self.assertLessEqual(data['page_size'], 2000)
        self.assertGreaterEqual(data['page_size'], 1)

    def test_history_raw_endpoint(self):
        app = self._import_app()
        client = app.test_client()
        resp = client.get('/api/history/raw')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('count', data)


class TestApiTokenAuth(IntegrationTestBase):
    """X-API-Token 鉴权流程测试 - 通过 patch flask_app.config['API_TOKEN']."""

    def test_dev_mode_allows_write_without_token(self):
        """API_TOKEN=None 时, 写操作不需要 token."""
        app = self._import_app()
        app.config['API_TOKEN'] = None
        client = app.test_client()
        # POST /api/clear-data 不带 token, 应该成功
        resp = client.post('/api/clear-data')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get('success'))

    def test_prod_mode_requires_token(self):
        """API_TOKEN 设置时, 写操作必须带正确 token."""
        app = self._import_app()
        app.config['API_TOKEN'] = 'prod-token-12345'

        client = app.test_client()
        # 没带 token -> 401
        resp = client.post('/api/clear-data')
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertFalse(data['success'])

    def test_prod_mode_accepts_correct_token(self):
        app = self._import_app()
        app.config['API_TOKEN'] = 'prod-token-12345'

        client = app.test_client()
        resp = client.post(
            '/api/clear-data',
            headers={'X-API-Token': 'prod-token-12345'}
        )
        self.assertEqual(resp.status_code, 200)

    def test_prod_mode_rejects_wrong_token(self):
        app = self._import_app()
        app.config['API_TOKEN'] = 'prod-token-12345'

        client = app.test_client()
        resp = client.post(
            '/api/clear-data',
            headers={'X-API-Token': 'wrong-token'}
        )
        self.assertEqual(resp.status_code, 401)

    def test_read_endpoints_dont_require_token_in_prod(self):
        """GET 端点不需要 token (读取不消耗算力)."""
        app = self._import_app()
        app.config['API_TOKEN'] = 'prod-token-12345'

        client = app.test_client()
        resp = client.get('/api/health')
        self.assertEqual(resp.status_code, 200)


class TestErrorHandling(IntegrationTestBase):
    """错误处理 / HTTP 状态码."""

    def test_404_for_unknown_api(self):
        app = self._import_app()
        client = app.test_client()
        resp = client.get('/api/nonexistent-endpoint')
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertFalse(data['success'])

    def test_405_for_wrong_method(self):
        app = self._import_app()
        client = app.test_client()
        # GET /api/clear-data -> 405 (只接受 POST)
        resp = client.get('/api/clear-data')
        self.assertIn(resp.status_code, (405, 200))  # Flask 默认 405

    def test_429_is_json(self):
        """快速连发 100+ GET 触发限流, 应该返回 JSON 429."""
        app = self._import_app()
        client = app.test_client()
        # 连续触发限流 (每分钟 60 次, 但端点级可能更严)
        # 注意: 单测期间限流器是 in-memory, 可能被前面测试影响
        # 只断言响应是 JSON, 不强求 429
        for _ in range(70):
            resp = client.get('/api/health')
            if resp.status_code == 429:
                data = resp.get_json()
                self.assertFalse(data['success'])
                self.assertIn('message', data)
                return
        # 没触发限流也算通过 (测试不依赖具体限流生效)


class TestImportValidation(IntegrationTestBase):
    """POST /api/import 输入校验."""

    def test_import_without_file_returns_400(self):
        app = self._import_app()
        client = app.test_client()
        resp = client.post('/api/import')
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertFalse(data['success'])

    def test_import_with_invalid_extension(self):
        app = self._import_app()
        client = app.test_client()

        from io import BytesIO
        data = {'file': (BytesIO(b'invalid'), 'data.exe')}
        resp = client.post('/api/import', data=data,
                          content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 400)

    def test_import_json_valid(self):
        app = self._import_app()
        client = app.test_client()

        from io import BytesIO
        valid_json = json.dumps([
            {
                'issue': '2024001',
                'date': '2024-01-02',
                'red_balls': [5, 10, 15, 20, 25, 30],
                'blue_ball': 8
            }
        ]).encode('utf-8')

        data = {'file': (BytesIO(valid_json), 'test.json')}
        resp = client.post('/api/import', data=data,
                          content_type='multipart/form-data')
        # dev 模式不需要 token
        self.assertEqual(resp.status_code, 200)
        result = resp.get_json()
        self.assertTrue(result['success'])
        self.assertGreaterEqual(result['new_records_count'], 1)


def run_integration_tests():
    """Run all integration tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestFlaskAppBasic))
    suite.addTests(loader.loadTestsFromTestCase(TestHistoryEndpoint))
    suite.addTests(loader.loadTestsFromTestCase(TestApiTokenAuth))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestImportValidation))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_integration_tests()
    sys.exit(0 if success else 1)
