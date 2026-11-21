"""
src.crawler - 双色球历史数据爬虫包.

模块拆分:
  - state    : 爬虫状态管理 (CrawlState) - 防并发/防抖/60s 缓存
  - backup   : 数据备份管理 (BackupManager) - 自动备份 + 清理
  - parser   : 数据解析器 (IssueParser) - 期号/记录解析 (含 Scrapling adaptive 版)
  - fetcher  : 网络抓取层 (CWLFetcher) - Scrapling 三层 (Fetcher/StealthyFetcher/DynamicFetcher)
  - crawler  : 顶层协调器 (Crawler) - 组合上述组件 + 历史数据读写

向后兼容:
  `from src.crawler import Crawler, CrawlState, get_crawl_state` 仍然有效.

v2.2 变更:
  - 网络层从 requests + curl_cffi + playwright 切换为 Scrapling (单库三层)
  - 删除 playwright-stealth 依赖 (StealthyFetcher 自带反 bot)
  - parser.py 新增 parse_cwl_html_with_selector() 支持 adaptive 自适应
"""
from .crawler import Crawler
from .state import CrawlState, get_crawl_state

__all__ = ['Crawler', 'CrawlState', 'get_crawl_state']
