"""Final smoke test: HTML path + JSON API path + adaptive path."""
import time
import sys
import json
sys.path.insert(0, '.')

from src.crawler.fetcher import CWLFetcher, _looks_blocked
from src.crawler.parser import IssueParser

URL_HTML = 'https://www.cwl.gov.cn/ygkj/wqkjgg/ssq/'

print('=' * 60)
print('Scrapling end-to-end smoke test (v2.2 final)')
print('=' * 60)

f = CWLFetcher()

# --- Test 1: Layer 1 alone (HTML) ---
t0 = time.time()
resp = f._fetch_fast(URL_HTML)
elapsed = time.time() - t0
if resp is None:
    print('FAIL: Fetcher returned None')
    sys.exit(1)

html = CWLFetcher._get_content(resp)
print(f'[HTML]  Layer 1 (Fetcher):  status={resp.status}  text={len(html)} chars  blocked={_looks_blocked(html)}  time={elapsed:.2f}s')

records_html = IssueParser.parse_cwl_html(html)
print(f'[HTML]  BS4 parse: {len(records_html)} records (may be 0 - page is search form, not history)')

# --- Test 2: JSON API path ---
print()
t0 = time.time()
api_result = f.fetch_cwl_api(page_no=1, page_size=20)
elapsed = time.time() - t0
print(f'[API]   fetch_cwl_api(): success={api_result.get("success")}  time={elapsed:.2f}s')
if api_result.get('success'):
    data = api_result.get('data', [])
    total = api_result.get('total', 0)
    print(f'[API]   total available: {total}, fetched: {len(data)} records')
    if data:
        first = data[0]
        print(f'[API]   first record: issue={first["issue"]} date={first["date"]} red={first["red_balls"]} blue={first["blue_ball"]}')

# --- Test 3: full multi-page API ---
print()
t0 = time.time()
multi = f.fetch_multi_page(max_pages=3, prefer_api=True)
elapsed = time.time() - t0
print(f'[MULTI] fetch_multi_page(prefer_api=True): success={multi.get("success")}  time={elapsed:.2f}s')
if multi.get('success'):
    data = multi.get('data', [])
    print(f'[MULTI] source={multi.get("source")}  total={multi.get("total")}  fetched={len(data)} records')
    if data:
        issues = [r['issue'] for r in data[:5]]
        print(f'[MULTI] first 5 issues: {issues}')

print()
print('=' * 60)
print('Smoke test complete')
print('=' * 60)
