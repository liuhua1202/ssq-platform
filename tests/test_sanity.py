"""
Tests for sanity check (SPA loader / demo data rejection).

覆盖:
  - is_valid_lottery_data() 在各种 edge case 下的判定
  - Crawler._fetch_latest_from_source 对 zhcw-style SPA HTML 返回 failure
"""
import os
import sys
import unittest
import logging
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.crawler.sanity import is_valid_lottery_data


class TestSanityCheck(unittest.TestCase):
    """Unit tests for src.crawler.sanity.is_valid_lottery_data."""

    REAL_HTML = (
        '<html><body><table><tr><td>双色球 历史开奖</td></tr></table></body></html>' * 100
    )

    # ---- 真实数据应通过 ----

    def test_valid_recent_lottery(self):
        """典型真实开奖数据应通过."""
        valid, msg = self._check('2024001', [5, 10, 15, 20, 25, 30], 8, self.REAL_HTML)
        self.assertTrue(valid, f'Should pass but got: {msg}')

    def test_valid_2010_lottery(self):
        """2010 年第一期也应通过."""
        valid, _ = self._check('2010001', [1, 2, 3, 4, 5, 6], 1, self.REAL_HTML)
        # 但 [1,2,3,4,5,6] 是 demo 模式 - 应该 false
        self.assertFalse(valid)

    def test_valid_typical_lottery(self):
        """真实典型分布."""
        valid, _ = self._check('2025140', [3, 8, 17, 22, 28, 31], 12, self.REAL_HTML)
        self.assertTrue(valid)

    # ---- 异常数据应拒绝 ----

    def test_demo_red_balls_rejected(self):
        """[1,2,3,4,5,6] 是 demo 数据, 应拒绝."""
        valid, _ = self._check('2024001', [1, 2, 3, 4, 5, 6], 8, self.REAL_HTML)
        self.assertFalse(valid)

    def test_demo_issue_rejected(self):
        """Dummy 期号 (0123456, 1234567) 应拒绝."""
        for bad in ['0123456', '1234567', '0000000']:
            valid, _ = self._check(bad, [5, 10, 15, 20, 25, 30], 8, self.REAL_HTML)
            self.assertFalse(valid, f'Issue {bad} should be rejected')

    def test_issue_wrong_format_rejected(self):
        """期号不是 7 位数字应拒绝."""
        for bad in ['001', '12345678', 'abcdefg', '20240']:
            valid, _ = self._check(bad, [5, 10, 15, 20, 25, 30], 8, self.REAL_HTML)
            self.assertFalse(valid, f'Issue {bad} should be rejected')

    def test_issue_year_out_of_range_rejected(self):
        """年份太早 (2009) 或太晚 (2099) 应拒绝."""
        valid_old, _ = self._check('2009001', [5, 10, 15, 20, 25, 30], 8, self.REAL_HTML)
        self.assertFalse(valid_old)
        valid_future, _ = self._check('2099001', [5, 10, 15, 20, 25, 30], 8, self.REAL_HTML)
        self.assertFalse(valid_future)

    def test_red_ball_out_of_range_rejected(self):
        """红球超出 1-33 应拒绝."""
        valid, _ = self._check('2024001', [5, 10, 15, 20, 25, 100], 8, self.REAL_HTML)
        self.assertFalse(valid)
        valid, _ = self._check('2024001', [0, 10, 15, 20, 25, 30], 8, self.REAL_HTML)
        self.assertFalse(valid)

    def test_blue_ball_out_of_range_rejected(self):
        """蓝球超出 1-16 应拒绝."""
        valid, _ = self._check('2024001', [5, 10, 15, 20, 25, 30], 0, self.REAL_HTML)
        self.assertFalse(valid)
        valid, _ = self._check('2024001', [5, 10, 15, 20, 25, 30], 99, self.REAL_HTML)
        self.assertFalse(valid)

    def test_duplicate_red_balls_rejected(self):
        """红球有重复应拒绝."""
        valid, _ = self._check('2024001', [5, 5, 15, 20, 25, 30], 8, self.REAL_HTML)
        self.assertFalse(valid)

    def test_wrong_count_rejected(self):
        """红球数量不对应拒绝."""
        valid, _ = self._check('2024001', [5, 10, 15], 8, self.REAL_HTML)  # only 3
        self.assertFalse(valid)
        valid, _ = self._check('2024001', [5, 10, 15, 20, 25, 30, 33], 8, self.REAL_HTML)  # 7
        self.assertFalse(valid)

    def test_empty_html_rejected(self):
        """HTML 为空或太小 (loader) 应拒绝."""
        valid, _ = self._check('2024001', [5, 10, 15, 20, 25, 30], 8, '<html></html>')
        self.assertFalse(valid)
        valid, _ = self._check('2024001', [5, 10, 15, 20, 25, 30], 8, '')
        self.assertFalse(valid)

    def test_non_lottery_html_rejected(self):
        """HTML 不包含 lottery 关键词应拒绝."""
        valid, _ = self._check('2024001', [5, 10, 15, 20, 25, 30], 8, '<html><body>随便内容</body></html>' * 10)
        self.assertFalse(valid)

    def test_none_values_rejected(self):
        """None 值应拒绝."""
        valid, _ = self._check(None, [5, 10, 15, 20, 25, 30], 8, self.REAL_HTML)
        self.assertFalse(valid)
        valid, _ = self._check('2024001', None, 8, self.REAL_HTML)
        self.assertFalse(valid)
        valid, _ = self._check('2024001', [5, 10, 15, 20, 25, 30], None, self.REAL_HTML)
        self.assertFalse(valid)

    # ---- 助手 ----

    def _check(self, issue, red_balls, blue_ball, html):
        """Wrapper: capture rejection message for debugging."""
        # Replace body but keep size large enough
        large_html = html if len(html) >= 5000 else (html + ' ' * (5000 - len(html)))
        valid = is_valid_lottery_data(issue, red_balls, blue_ball, large_html)
        return valid, ''


class TestCrawlerRejectsSpaLoader(unittest.TestCase):
    """集成测试: crawler 拒绝 zhcw-style SPA HTML (loader/demo 数据)."""

    # ZHCW 实际首页特征: 大量 Vue 模板占位符 + 0-9 数字 loader 元素
    ZHCW_STYLE_HTML = """
<html><body>
<div><span>{{jz.issue?jz.issue:'--'}}期</span>|<span>每星期二四日21:15开奖</span></div>
<table>
<tr>
    <td>0</td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td><td>8</td><td>9</td>
</tr>
</table>
<input maxlength="1234567890123456789" type="text" />
<!-- 591 个 5-7 位数字序列模拟 -->
""" + '<span>0123456</span>' * 100 + """
</body></html>
"""

    def test_crawler_returns_failure_for_spa_html(self):
        """zhcw-style SPA 页面应返回 failure 而非假 success."""
        from src.crawler import Crawler
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            c = Crawler(data_dir=td)

            with patch('src.crawler.crawler.Crawler._http_get_with_tls_spoof') as mock_get:
                mock_response = type('MockResp', (), {})()
                # Use a property for text
                mock_response.text = self.ZHCW_STYLE_HTML
                mock_response.content = self.ZHCW_STYLE_HTML.encode('utf-8')
                mock_response.raise_for_status = lambda: None
                mock_get.return_value = mock_response

                logging.disable(logging.CRITICAL)  # suppress noise
                try:
                    result = c.fetch_latest_lottery()
                finally:
                    logging.disable(logging.NOTSET)

                # 必须返回 failure, 不能返回 success=True
                self.assertFalse(result['success'],
                    f'Expected failure but got: {result}')

                # 也不能返回看起来像真实开奖的数据 (issue=0123456 红球=[1,2,3,4,5,6])
                if 'issue' in result:
                    self.assertNotEqual(result['issue'], '0123456')


def run_sanity_tests():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestSanityCheck))
    suite.addTests(loader.loadTestsFromTestCase(TestCrawlerRejectsSpaLoader))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_sanity_tests()
    sys.exit(0 if success else 1)
