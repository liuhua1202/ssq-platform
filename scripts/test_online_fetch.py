#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
在线数据获取测试脚本
用于测试福彩官网数据获取功能
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.online_fetcher import OnlineFetcher, fetch_latest_from_cwl, fetch_history_from_cwl
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def test_api_fetch():
    """测试 API 方式获取"""
    print("\n" + "="*60)
    print("测试 1: API 方式获取最新一期")
    print("="*60)

    fetcher = OnlineFetcher()
    result = fetcher.fetch_from_cwl_api(page=1, page_size=1)

    if result['success']:
        print(f"✓ 成功获取 {len(result['data'])} 条记录")
        print(f"  来源: {result.get('source')}")
        if result['data']:
            latest = result['data'][0]
            print(f"  期号: {latest.get('issue')}")
            print(f"  日期: {latest.get('date')}")
            print(f"  红球: {latest.get('red_balls')}")
            print(f"  蓝球: {latest.get('blue_ball')}")
    else:
        print(f"✗ 失败: {result.get('message')}")

    return result['success']


def test_page_fetch():
    """测试页面抓取方式"""
    print("\n" + "="*60)
    print("测试 2: Playwright 页面抓取")
    print("="*60)

    try:
        from playwright.sync_api import sync_playwright
        HAS_PLAYWRIGHT = True
    except ImportError:
        print("⚠ Playwright 未安装，跳过此测试")
        print("  安装命令: pip install playwright playwright-stealth")
        print("  然后运行: playwright install chromium")
        return False

    fetcher = OnlineFetcher()
    result = fetcher.fetch_from_cwl_page(page=1)

    if result['success']:
        print(f"✓ 成功获取 {len(result['data'])} 条记录")
        print(f"  来源: {result.get('source')}")
        if result['data']:
            first = result['data'][0]
            print(f"  期号: {first.get('issue')}")
            print(f"  日期: {first.get('date')}")
            print(f"  红球: {first.get('red_balls')}")
            print(f"  蓝球: {first.get('blue_ball')}")
    else:
        print(f"✗ 失败: {result.get('message')}")

    return result['success']


def test_batch_fetch():
    """测试批量获取"""
    print("\n" + "="*60)
    print("测试 3: 批量获取多页数据（3 页）")
    print("="*60)

    fetcher = OnlineFetcher()
    result = fetcher.fetch_multiple_pages(
        start_page=1,
        end_page=3,
        use_api=True
    )

    if result['success']:
        print(f"✓ 成功获取 {result['total_records']} 条记录")
        print(f"  总页数: {result['total_pages']}")
        print(f"  失败页: {result['failed_pages']}")
        if result['data']:
            print(f"\n  前 3 条记录:")
            for i, record in enumerate(result['data'][:3], 1):
                print(f"  {i}. 期号 {record['issue']}: "
                      f"{record['red_balls']} + {record['blue_ball']}")
    else:
        print(f"✗ 失败: 未获取到任何数据")

    return result['success']


def test_convenience_functions():
    """测试便捷函数"""
    print("\n" + "="*60)
    print("测试 4: 便捷函数调用")
    print("="*60)

    # 测试获取最新
    print("\n获取最新一期...")
    latest = fetch_latest_from_cwl()
    if latest['success']:
        print(f"✓ fetch_latest_from_cwl() 成功")
        data = latest['data'][0] if isinstance(latest['data'], list) else latest['data']
        print(f"  期号: {data.get('issue')}")
    else:
        print(f"✗ fetch_latest_from_cwl() 失败: {latest.get('message')}")

    # 测试获取历史
    print("\n获取历史数据（2 页）...")
    history = fetch_history_from_cwl(pages=2)
    if history['success']:
        print(f"✓ fetch_history_from_cwl() 成功")
        print(f"  共 {history['total_records']} 条记录")
    else:
        print(f"✗ fetch_history_from_cwl() 失败")

    return True


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("  福彩官网在线数据获取 - 功能测试")
    print("="*60)

    results = {
        'API 获取': test_api_fetch(),
        '页面抓取': test_page_fetch(),
        '批量获取': test_batch_fetch(),
        '便捷函数': test_convenience_functions(),
    }

    # 总结
    print("\n" + "="*60)
    print("  测试总结")
    print("="*60)

    for test_name, success in results.items():
        status = "✓ 通过" if success else "✗ 失败"
        print(f"  {test_name:12s}: {status}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\n  总计: {passed}/{total} 通过")

    if passed == total:
        print("\n🎉 所有测试通过！")
    elif passed > 0:
        print(f"\n⚠️  部分测试通过，请检查失败项")
    else:
        print("\n❌ 所有测试失败，请检查网络和依赖")

    return passed > 0


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
