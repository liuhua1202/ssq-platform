"""端到端爬取测试: 多源 fallback + JSON API + 历史数据 + 数据落盘.

跑法: cd 项目根目录 && python scripts/e2e_crawl_test.py
输出: data/crawl_test_output_<timestamp>.json (含全部抓到的真实数据)
"""
import json
import time
import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, '.')

from src.crawler import Crawler
from src.crawler.fetcher import CWLFetcher
from src.crawler.parser import IssueParser


def _bar(label: str) -> None:
    print('\n' + '=' * 70)
    print(f'  {label}')
    print('=' * 70)


def _ok(msg: str) -> None:
    print(f'  [OK]   {msg}')


def _fail(msg: str) -> None:
    print(f'  [FAIL] {msg}')


def main():
    project_root = Path(__file__).resolve().parent.parent
    out_dir = project_root / 'data'
    out_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    all_data = {
        'test_run_at': datetime.now().isoformat(),
        'cwl_api': None,
        'cwl_html': None,
        'multi_page_api': None,
        'crawler_latest': None,
        'crawler_history': None,
    }

    crawler = Crawler()
    fetcher = CWLFetcher()

    # ============================================================
    # Test 1: cwl.gov.cn JSON API 单页 (新功能, 应该成功)
    # ============================================================
    _bar('Test 1: cwl.gov.cn 官方 JSON API (单页)')
    t0 = time.time()
    api_result = fetcher.fetch_cwl_api(page_no=1, page_size=20)
    elapsed = time.time() - t0

    if api_result.get('success'):
        records = api_result.get('data', [])
        _ok(f'API 抓取成功, {len(records)} 条, {elapsed:.2f}s, total={api_result.get("total")}')
        first = records[0] if records else {}
        _ok(f'最新一期: issue={first.get("issue")} date={first.get("date")} '
            f'red={first.get("red_balls")} blue={first.get("blue_ball")}')
        all_data['cwl_api'] = {
            'success': True,
            'elapsed_sec': round(elapsed, 3),
            'fetched_count': len(records),
            'total_available': api_result.get('total'),
            'first_3': records[:3],
        }
    else:
        _fail(f'API 抓取失败: {api_result.get("message")}')
        all_data['cwl_api'] = {'success': False, 'message': api_result.get('message')}

    # ============================================================
    # Test 2: cwl.gov.cn HTML 路径 (旧功能, 已知是搜索表单 → 0 记录)
    # ============================================================
    _bar('Test 2: cwl.gov.cn HTML 路径 (旧版, 用于对比)')
    t0 = time.time()
    resp = fetcher._fetch_fast('https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/')
    elapsed = time.time() - t0
    if resp is not None:
        html = CWLFetcher._get_content(resp)
        records = IssueParser.parse_cwl_html(html)
        _ok(f'HTML 抓取: {len(html)} chars, BS4 解析 {len(records)} 条, {elapsed:.2f}s')
        if records:
            _ok(f'  最新: {records[0]["issue"]} red={records[0]["red_balls"]}')
        else:
            print('  [INFO] HTML 路径 0 记录 (页面是搜索表单, 预期)')
        all_data['cwl_html'] = {
            'elapsed_sec': round(elapsed, 3),
            'html_chars': len(html),
            'records_parsed': len(records),
        }
    else:
        _fail('HTML 抓取完全失败')
        all_data['cwl_html'] = {'success': False}

    # ============================================================
    # Test 3: 多页 JSON API 抓 90 条 (历史数据基础量)
    # ============================================================
    _bar('Test 3: cwl.gov.cn JSON API 多页 (3 页 = 90 条)')
    t0 = time.time()
    multi = fetcher.fetch_multi_page(max_pages=3, prefer_api=True)
    elapsed = time.time() - t0

    if multi.get('success'):
        records = multi.get('data', [])
        _ok(f'多页 API: {len(records)} 条, source={multi.get("source")}, {elapsed:.2f}s')
        _ok(f'按期号降序前 5 条: {[r["issue"] for r in records[:5]]}')
        _ok(f'按期号升序末 5 条: {[r["issue"] for r in records[-5:]]}')
        all_data['multi_page_api'] = {
            'success': True,
            'elapsed_sec': round(elapsed, 3),
            'source': multi.get('source'),
            'fetched_count': len(records),
            'first_3': records[:3],
            'last_3': records[-3:],
        }
    else:
        _fail(f'多页 API 失败: {multi.get("message")}')
        all_data['multi_page_api'] = {'success': False}

    # ============================================================
    # Test 4: Crawler.fetch_latest_lottery (多源 fallback)
    # ============================================================
    _bar('Test 4: Crawler.fetch_latest_lottery() (500网 → cwl.gov.cn fallback)')
    t0 = time.time()
    latest = crawler.fetch_latest_lottery()
    elapsed = time.time() - t0

    if latest.get('success'):
        _ok(f'最新一期: issue={latest.get("issue")} date={latest.get("date")}')
        _ok(f'  red={latest.get("red_balls")} blue={latest.get("blue_ball")}')
        _ok(f'  source={latest.get("source", "(未填)")}, {elapsed:.2f}s')
        all_data['crawler_latest'] = {
            'success': True,
            'elapsed_sec': round(elapsed, 3),
            'data': latest,
        }
    else:
        _fail(f'fetch_latest_lottery 失败: {latest.get("message")}')
        all_data['crawler_latest'] = {'success': False, 'message': latest.get('message')}

    # ============================================================
    # Test 5: Crawler.fetch_lottery_history (500网)
    # ============================================================
    _bar('Test 5: Crawler.fetch_lottery_history(page=1, page_size=10) (500网)')
    t0 = time.time()
    history = crawler.fetch_lottery_history(page=1, page_size=10)
    elapsed = time.time() - t0

    if history.get('success'):
        records = history.get('data', [])
        _ok(f'历史 {len(records)} 条, {elapsed:.2f}s')
        if records:
            _ok(f'最新: {records[0].get("issue")} red={records[0].get("red_balls")}')
        all_data['crawler_history'] = {
            'success': True,
            'elapsed_sec': round(elapsed, 3),
            'fetched_count': len(records),
            'records': records,
        }
    else:
        _fail(f'fetch_lottery_history 失败: {history.get("message")}')
        all_data['crawler_history'] = {'success': False, 'message': history.get('message')}

    # ============================================================
    # 落盘结果
    # ============================================================
    out_file = out_dir / f'crawl_test_output_{timestamp}.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2, default=str)
    _bar('落盘完成')
    _ok(f'结果已写入: {out_file}')
    _ok(f'文件大小: {out_file.stat().st_size} bytes')

    # 总结
    _bar('总结')
    test_results = [
        ('Test 1: cwl API 单页', all_data['cwl_api'].get('success') if isinstance(all_data['cwl_api'], dict) else False),
        ('Test 2: cwl HTML (对比)', 'records_parsed' in (all_data['cwl_html'] or {})),
        ('Test 3: cwl API 多页', all_data['multi_page_api'].get('success') if isinstance(all_data['multi_page_api'], dict) else False),
        ('Test 4: Crawler.latest', all_data['crawler_latest'].get('success') if isinstance(all_data['crawler_latest'], dict) else False),
        ('Test 5: Crawler.history', all_data['crawler_history'].get('success') if isinstance(all_data['crawler_history'], dict) else False),
    ]
    passed = sum(1 for _, ok in test_results if ok)
    for name, ok in test_results:
        _ok(name) if ok else _fail(name)
    print(f'\n  通过: {passed}/{len(test_results)}')


if __name__ == '__main__':
    main()
