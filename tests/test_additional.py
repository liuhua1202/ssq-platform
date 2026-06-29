"""
Additional tests for crawler parsing + config security.
Complements tests/test_core.py.
"""
import os
import sys
import unittest
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.crawler import Crawler, CrawlState, get_crawl_state
import config


class TestCrawlerConvertIssue(unittest.TestCase):
    """Tests for crawler._convert_issue (期号格式归一化)."""

    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp(prefix='ssq_test_')
        self.crawler = Crawler(data_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        try:
            shutil.rmtree(self.tmpdir)
        except Exception:
            pass

    def test_5digit_gets_20_prefix(self):
        self.assertEqual(self.crawler._convert_issue('24001'), '2024001')

    def test_6digit_not_starting_with_202_gets_20_prefix(self):
        self.assertEqual(self.crawler._convert_issue('24001'), '2024001')

    def test_7digit_already_complete(self):
        self.assertEqual(self.crawler._convert_issue('2024001'), '2024001')

    def test_6digit_starting_with_202_unchanged(self):
        self.assertEqual(self.crawler._convert_issue('202001'), '202001')


class TestCrawlerParseRecord(unittest.TestCase):
    """Tests for crawler.parse_record (公开 wrapper)."""

    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp(prefix='ssq_test_')
        self.crawler = Crawler(data_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        try:
            shutil.rmtree(self.tmpdir)
        except Exception:
            pass

    def test_valid_record(self):
        record = {
            'issue': '2024001',
            'date': '2024-01-02',
            'red_balls': [3, 8, 17, 22, 28, 31],
            'blue_ball': 12
        }
        result = self.crawler.parse_record(record)
        self.assertIsNotNone(result)
        self.assertEqual(result['issue'], '2024001')
        self.assertEqual(result['blue_ball'], 12)

    def test_string_red_balls_csv(self):
        record = {
            'issue': '2024002',
            'red_balls': '03,08,17,22,28,31',
            'blue_ball': 12
        }
        result = self.crawler.parse_record(record)
        self.assertIsNotNone(result)
        self.assertEqual(len(result['red_balls']), 6)

    def test_wrong_red_count_returns_none(self):
        record = {'issue': '2024003', 'red_balls': [1, 2, 3], 'blue_ball': 5}
        self.assertIsNone(self.crawler.parse_record(record))

    def test_red_out_of_range_returns_none(self):
        record = {'issue': '2024004', 'red_balls': [1, 2, 3, 4, 5, 100], 'blue_ball': 5}
        self.assertIsNone(self.crawler.parse_record(record))

    def test_blue_out_of_range_returns_none(self):
        record = {'issue': '2024005', 'red_balls': [1, 2, 3, 4, 5, 6], 'blue_ball': 99}
        self.assertIsNone(self.crawler.parse_record(record))

    def test_alt_field_names(self):
        """支持 expectNum / redBall 等替代字段名."""
        record = {
            'expectNum': '2024006',
            'openTime': '2024-01-08',
            'red': '03,08,17,22,28,31',
            'blue': 7
        }
        result = self.crawler.parse_record(record)
        self.assertIsNotNone(result)
        self.assertEqual(result['issue'], '2024006')


class TestCrawlerPublicWrappers(unittest.TestCase):
    """Verify public wrappers around private methods exist and work."""

    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp(prefix='ssq_test_')
        self.crawler = Crawler(data_dir=self.tmpdir)

    def tearDown(self):
        import shutil
        try:
            shutil.rmtree(self.tmpdir)
        except Exception:
            pass

    def test_public_create_backup(self):
        """create_backup() should be a working public method."""
        self.crawler.save_history([
            {'issue': '2024001', 'red_balls': [1, 2, 3, 4, 5, 6], 'blue_ball': 7}
        ])
        self.crawler.create_backup()
        backups = [f for f in os.listdir(self.crawler.backup_dir) if f.endswith('.json')]
        self.assertGreater(len(backups), 0)

    def test_public_parse_record(self):
        record = {'issue': '2024001', 'red_balls': [1, 2, 3, 4, 5, 6], 'blue_ball': 7}
        result = self.crawler.parse_record(record)
        self.assertIsNotNone(result)

    def test_public_parse_web_copy_short_input(self):
        """parse_web_copy() returns None for too-short input."""
        result = self.crawler.parse_web_copy({
            'issue': '2024001',
            'balls': '12345'
        })
        self.assertIsNone(result)


class TestCrawlState(unittest.TestCase):
    """Tests for CrawlState lock + cache (prevents request thread blocking)."""

    def test_acquire_release(self):
        state = CrawlState()
        self.assertTrue(state.try_acquire())
        # Second try should fail while held
        self.assertFalse(state.try_acquire())
        state.release()
        # After release, can acquire again
        self.assertTrue(state.try_acquire())
        state.release()

    def test_release_without_acquire_safe(self):
        """Releasing without acquiring should not raise."""
        state = CrawlState()
        # No prior acquire - release should be safe
        state.release()

    def test_cache_set_get(self):
        state = CrawlState()
        self.assertIsNone(state.get_cached())
        state.cache_result({'success': True, 'data': 'test'})
        cached = state.get_cached()
        self.assertEqual(cached['data'], 'test')

    def test_cache_expiry(self):
        state = CrawlState()
        state.cache_result({'success': True, 'data': 'test'})
        # Force expire by setting timestamp in past
        state._last_fetched_at = datetime.now() - timedelta(seconds=120)
        self.assertIsNone(state.get_cached())

    def test_invalidate(self):
        state = CrawlState()
        state.cache_result({'success': True})
        state.invalidate()
        self.assertIsNone(state.get_cached())

    def test_status_no_lock(self):
        """is_busy is False when lock not held."""
        state = CrawlState()
        status = state.get_status()
        self.assertFalse(status['is_busy'])
        self.assertFalse(status['has_cached_result'])

    def test_status_when_lock_held(self):
        state = CrawlState()
        state.try_acquire()
        try:
            status = state.get_status()
            self.assertTrue(status['is_busy'])
        finally:
            state.release()

    def test_global_singleton(self):
        """get_crawl_state() returns the same instance."""
        s1 = get_crawl_state()
        s2 = get_crawl_state()
        self.assertIs(s1, s2)


class TestEnsureSecurityConfig(unittest.TestCase):
    """Tests for config.ensure_security_config()."""

    def setUp(self):
        self._orig_secret = config.SECRET_KEY
        self._orig_debug = config.WEB_CONFIG['debug']

    def tearDown(self):
        config.SECRET_KEY = self._orig_secret
        config.WEB_CONFIG['debug'] = self._orig_debug

    def test_strong_secret_returns_true(self):
        config.SECRET_KEY = 'my-strong-random-key-12345'
        config.WEB_CONFIG['debug'] = False
        self.assertTrue(config.ensure_security_config())

    def test_none_secret_debug_mode_auto_gen(self):
        config.SECRET_KEY = None
        config.WEB_CONFIG['debug'] = True
        result = config.ensure_security_config()
        self.assertFalse(result)
        self.assertIsNotNone(config.SECRET_KEY)
        self.assertGreater(len(config.SECRET_KEY), 32)

    def test_none_secret_production_raises(self):
        config.SECRET_KEY = None
        config.WEB_CONFIG['debug'] = False
        with self.assertRaises(SystemExit):
            config.ensure_security_config()

    def test_default_secret_production_raises(self):
        config.SECRET_KEY = config._LEGACY_DEFAULT_KEY
        config.WEB_CONFIG['debug'] = False
        with self.assertRaises(SystemExit):
            config.ensure_security_config()

    def test_default_secret_debug_mode_warns(self):
        config.SECRET_KEY = config._LEGACY_DEFAULT_KEY
        config.WEB_CONFIG['debug'] = True
        result = config.ensure_security_config()
        self.assertFalse(result)


class TestApiDecorator(unittest.TestCase):
    """Tests for src.api.api module decorators without spinning up Flask.

    Verify the decorators are importable and apply correctly to dummy functions.
    """

    def test_require_api_token_passes_when_no_token_set(self):
        """In dev mode (API_TOKEN=None), require_api_token allows calls."""
        # Import inside test to avoid module-level side effects
        from src.api.api import require_api_token

        @require_api_token
        def dummy():
            return 'ok'

        # Build a fake request context
        from flask import Flask
        app = Flask(__name__)
        app.config['API_TOKEN'] = None  # dev mode
        with app.test_request_context('/'):
            result = dummy()
        self.assertEqual(result, 'ok')

    def test_require_api_token_401_when_token_set_no_header(self):
        from src.api.api import require_api_token

        from flask import Flask, jsonify
        app = Flask(__name__)
        app.config['API_TOKEN'] = 'expected-token'

        @app.route('/test', methods=['POST'])
        @require_api_token
        def handler():
            return jsonify({'success': True})

        client = app.test_client()
        resp = client.post('/test')
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertFalse(data['success'])

    def test_require_api_token_passes_with_correct_header(self):
        from src.api.api import require_api_token

        from flask import Flask, jsonify
        app = Flask(__name__)
        app.config['API_TOKEN'] = 'expected-token'

        @app.route('/test', methods=['POST'])
        @require_api_token
        def handler():
            return jsonify({'success': True})

        client = app.test_client()
        resp = client.post('/test', headers={'X-API-Token': 'expected-token'})
        self.assertEqual(resp.status_code, 200)

    def test_api_error_handler_catches_unhandled_exception(self):
        """api_error_handler catches Exception and returns 500."""
        from src.api.api import api_error_handler

        from flask import Flask, jsonify
        app = Flask(__name__)

        @app.route('/boom')
        @api_error_handler('测试操作')
        def handler():
            raise RuntimeError('boom!')

        client = app.test_client()
        resp = client.get('/boom')
        self.assertEqual(resp.status_code, 500)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertIn('测试操作失败', data['message'])


def run_additional_tests():
    """Run all additional tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestCrawlerConvertIssue))
    suite.addTests(loader.loadTestsFromTestCase(TestCrawlerParseRecord))
    suite.addTests(loader.loadTestsFromTestCase(TestCrawlerPublicWrappers))
    suite.addTests(loader.loadTestsFromTestCase(TestCrawlState))
    suite.addTests(loader.loadTestsFromTestCase(TestEnsureSecurityConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestApiDecorator))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_additional_tests()
    sys.exit(0 if success else 1)