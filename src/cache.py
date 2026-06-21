"""
数据缓存层
用于缓存分析结果和预测数据，提升性能
"""
import hashlib
import json
import logging
import time
from functools import lru_cache, wraps
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CacheEntry:
    """缓存条目，包含值和时间戳"""
    __slots__ = ['value', 'timestamp', 'ttl']
    
    def __init__(self, value: Any, ttl: int):
        self.value = value
        self.timestamp = time.time()
        self.ttl = ttl
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() - self.timestamp > self.ttl


class DataCache:
    """数据缓存类"""

    def __init__(self, max_size: int = 100, ttl: int = 300):
        """
        初始化缓存

        Args:
            max_size: 最大缓存条目数
            ttl: 默认生存时间（秒）
        """
        self.max_size = max_size
        self.default_ttl = ttl
        self._cache: dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0

    def _generate_key(self, *args, **kwargs) -> str:
        """生成缓存键"""
        key_data = json.dumps({'args': args, 'kwargs': kwargs}, sort_keys=True, default=str)
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或已过期则返回 None
        """
        if key not in self._cache:
            self._misses += 1
            return None

        entry = self._cache[key]
        if entry.is_expired():
            self.delete(key)
            self._misses += 1
            logger.debug(f"缓存键 {key[:8]}... 已过期")
            return None

        self._hits += 1
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 生存时间（秒），None 使用默认值
        """
        if len(self._cache) >= self.max_size:
            self._evict_expired_or_oldest()

        actual_ttl = ttl if ttl is not None else self.default_ttl
        self._cache[key] = CacheEntry(value, actual_ttl)
        logger.debug(f"缓存已设置：{key[:8]}..., TTL={actual_ttl}s")

    def delete(self, key: str) -> bool:
        """
        删除缓存

        Args:
            key: 缓存键

        Returns:
            是否删除成功
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """清空所有缓存"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def _evict_expired_or_oldest(self) -> None:
        """淘汰过期或最旧的缓存"""
        if not self._cache:
            return

        # 先尝试删除过期的
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        if expired_keys:
            for k in expired_keys:
                del self._cache[k]
            logger.debug(f"已清理 {len(expired_keys)} 个过期缓存")
            return

        # 如果没有过期的，删除最旧的
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].timestamp)
        del self._cache[oldest_key]
        logger.debug(f"已删除最旧缓存：{oldest_key[:8]}...")

    def cleanup_expired(self) -> int:
        """清理所有过期缓存，返回清理数量"""
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        for k in expired_keys:
            del self._cache[k]
        if expired_keys:
            logger.info(f"清理了 {len(expired_keys)} 个过期缓存")
        return len(expired_keys)

    def stats(self) -> dict:
        """获取缓存统计信息"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': f"{hit_rate:.2f}%",
            'keys': list(self._cache.keys())[:10]  # 只返回前 10 个键
        }


# 全局缓存实例
analysis_cache = DataCache(max_size=50, ttl=300)  # 分析结果缓存 5 分钟
prediction_cache = DataCache(max_size=100, ttl=60)  # 预测结果缓存 1 分钟
history_cache = DataCache(max_size=20, ttl=600)  # 历史数据缓存 10 分钟


def cached_analysis(func):
    """分析结果缓存装饰器（忽略 top_n 参数）"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 移除 top_n 参数，因为它只影响返回数量，不影响计算结果
        cache_kwargs = {k: v for k, v in kwargs.items() if k != 'top_n'}
        key = f"{func.__name__}:{hashlib.md5(json.dumps({'args': args, 'kwargs': cache_kwargs}, sort_keys=True, default=str).encode()).hexdigest()}"

        cached = analysis_cache.get(key)
        if cached is not None:
            logger.debug(f"缓存命中：{func.__name__}")
            return cached

        result = func(*args, **kwargs)
        analysis_cache.set(key, result)
        logger.debug(f"缓存未命中，已计算并缓存：{func.__name__}")
        return result
    return wrapper


def cached_prediction(func):
    """预测结果缓存装饰器"""
    def wrapper(*args, **kwargs):
        key = f"{func.__name__}:{hashlib.md5(json.dumps({'args': args, 'kwargs': kwargs}, sort_keys=True, default=str).encode()).hexdigest()}"

        cached = prediction_cache.get(key)
        if cached is not None:
            logger.debug(f"预测缓存命中：{func.__name__}")
            return cached

        result = func(*args, **kwargs)
        prediction_cache.set(key, result, ttl=60)  # 预测结果缓存 1 分钟
        logger.debug(f"预测缓存未命中，已计算并缓存：{func.__name__}")
        return result
    return wrapper


def cached_history(func):
    """历史数据缓存装饰器"""
    def wrapper(*args, **kwargs):
        key = f"{func.__name__}:{hashlib.md5(json.dumps({'args': args, 'kwargs': kwargs}, sort_keys=True, default=str).encode()).hexdigest()}"

        cached = history_cache.get(key)
        if cached is not None:
            return cached

        result = func(*args, **kwargs)
        history_cache.set(key, result, ttl=600)
        return result
    return wrapper
