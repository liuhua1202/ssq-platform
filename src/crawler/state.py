"""
爬虫状态管理 - 防止请求线程被同步爬虫卡死.

提供两个能力:
  1. 单线程执行: 同时刻只有一个 fetch 在跑 (threading.Lock 非阻塞 acquire)
  2. 结果缓存: 最近一次成功结果缓存 60s, 重复请求直接返回

使用场景:
  - /api/fetch-latest 和 /api/fetch-history 端点
"""
import threading
from datetime import datetime
from typing import Optional, Any, Dict


class CrawlState:
    """线程安全的爬虫状态管理."""

    DEFAULT_CACHE_TTL = 60  # 秒

    def __init__(self):
        self._lock = threading.Lock()
        self._last_result: Optional[Any] = None
        self._last_fetched_at: Optional[datetime] = None
        self._cache_ttl: int = self.DEFAULT_CACHE_TTL

    def try_acquire(self) -> bool:
        """非阻塞获取锁. 成功返回 True, 失败返回 False."""
        return self._lock.acquire(blocking=False)

    def release(self) -> None:
        """释放锁. 调用方必须先成功 try_acquire."""
        try:
            self._lock.release()
        except RuntimeError:
            # 锁已经被释放过 - 静默忽略
            pass

    def get_cached(self) -> Optional[Any]:
        """获取缓存结果. 如果没缓存或已过期, 返回 None."""
        if self._last_result is None or self._last_fetched_at is None:
            return None
        age = (datetime.now() - self._last_fetched_at).total_seconds()
        if age > self._cache_ttl:
            return None
        return self._last_result

    def cache_result(self, result: Any) -> None:
        """缓存成功的结果."""
        self._last_result = result
        self._last_fetched_at = datetime.now()

    def invalidate(self) -> None:
        """清空缓存."""
        self._last_result = None
        self._last_fetched_at = None

    def get_status(self) -> Dict:
        """获取当前状态 (用于 /health 等监控端点).

        使用非阻塞 acquire 测试, 避免与持有锁的线程死锁.
        """
        got_lock = self._lock.acquire(blocking=False)
        if got_lock:
            self._lock.release()
            is_busy = False
        else:
            is_busy = True
        age = None
        if self._last_fetched_at:
            age = (datetime.now() - self._last_fetched_at).total_seconds()
        return {
            'is_busy': is_busy,
            'last_fetched_at': self._last_fetched_at.isoformat() if self._last_fetched_at else None,
            'last_result_age_seconds': age,
            'cache_ttl': self._cache_ttl,
            'has_cached_result': self._last_result is not None
        }


# 全局单例
_crawl_state = CrawlState()


def get_crawl_state() -> CrawlState:
    """获取全局爬虫状态单例."""
    return _crawl_state
