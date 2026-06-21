/**
 * 工具函数模块
 * 优化版本：添加 localStorage 容量管理
 */

/**
 * 存储键名
 */
export const STORAGE_KEYS = {
    MY_NUMBERS: 'ssq_my_numbers',
    HISTORY_CACHE: 'ssq_history_cache',
    HISTORY_CACHE_TIME: 'ssq_history_cache_time',
};

/**
 * localStorage 容量限制（4MB，留出安全余量）
 */
const STORAGE_LIMIT = 4 * 1024 * 1024;

/**
 * 从 localStorage 获取数据
 */
export function getFromStorage(key) {
    try {
        const data = localStorage.getItem(key);
        return data ? JSON.parse(data) : null;
    } catch (e) {
        console.error(`读取存储失败 (${key}):`, e);
        return null;
    }
}

/**
 * 保存数据到 localStorage（带容量检查）
 */
export function saveToStorage(key, value) {
    try {
        const serialized = JSON.stringify(value);
        
        // 检查是否会超出容量
        const currentUsage = Object.keys(localStorage)
            .reduce((sum, k) => sum + (localStorage[k].length || 0), 0);
        
        if (currentUsage + serialized.length > STORAGE_LIMIT) {
            console.warn('localStorage 容量不足，尝试清理旧数据...');
            // 清除最旧的缓存
            const oldCache = getFromStorage(STORAGE_KEYS.HISTORY_CACHE);
            const cacheTime = getFromStorage(STORAGE_KEYS.HISTORY_CACHE_TIME);
            if (oldCache && cacheTime) {
                const age = Date.now() - cacheTime;
                if (age > 60 * 60 * 1000) {  // 超过 1 小时
                    removeFromStorage(STORAGE_KEYS.HISTORY_CACHE);
                    removeFromStorage(STORAGE_KEYS.HISTORY_CACHE_TIME);
                    console.log('已清除旧缓存');
                }
            }
        }
        
        localStorage.setItem(key, serialized);
        return true;
    } catch (e) {
        if (e.name === 'QuotaExceededError') {
            console.error('localStorage 容量已满，请清除浏览器数据');
            // 尝试清除所有缓存
            removeFromStorage(STORAGE_KEYS.HISTORY_CACHE);
            removeFromStorage(STORAGE_KEYS.HISTORY_CACHE_TIME);
        } else {
            console.error(`保存存储失败 (${key}):`, e);
        }
        return false;
    }
}

/**
 * 从 localStorage 删除数据
 */
export function removeFromStorage(key) {
    try {
        localStorage.removeItem(key);
        return true;
    } catch (e) {
        console.error(`删除存储失败 (${key}):`, e);
        return false;
    }
}

/**
 * 获取存储使用情况
 */
export function getStorageUsage() {
    let total = 0;
    for (let key in localStorage) {
        if (localStorage.hasOwnProperty(key)) {
            total += localStorage[key].length;
        }
    }
    return {
        used: total,
        limit: STORAGE_LIMIT,
        percentage: (total / STORAGE_LIMIT * 100).toFixed(2)
    };
}

/**
 * 缓存历史数据
 */
export function cacheHistoryData(data) {
    // 只缓存最近 100 条，减少存储占用
    const limitedData = data.slice(0, 100);
    saveToStorage(STORAGE_KEYS.HISTORY_CACHE, limitedData);
    saveToStorage(STORAGE_KEYS.HISTORY_CACHE_TIME, Date.now());
}

/**
 * 获取缓存的历史数据
 */
export function getCachedHistory() {
    const cachedData = getFromStorage(STORAGE_KEYS.HISTORY_CACHE);
    const cacheTime = getFromStorage(STORAGE_KEYS.HISTORY_CACHE_TIME);

    if (!cachedData || !cacheTime) return null;

    const age = Date.now() - cacheTime;
    const maxAge = 24 * 60 * 60 * 1000; // 24 小时

    if (age > maxAge) {
        console.log('缓存已过期');
        removeFromStorage(STORAGE_KEYS.HISTORY_CACHE);
        removeFromStorage(STORAGE_KEYS.HISTORY_CACHE_TIME);
        return null;
    }

    return cachedData;
}

/**
 * 格式化日期
 */
export function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN');
}

/**
 * 格式化日期时间
 */
export function formatDateTime(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN');
}

/**
 * 数字补齐
 */
export function padNumber(num, length = 2) {
    return String(num).padStart(length, '0');
}

/**
 * 计算 AC 指数
 */
export function calculateACIndex(redBalls) {
    if (redBalls.length !== 6) return 0;

    const diffs = new Set();
    for (let i = 0; i < redBalls.length; i++) {
        for (let j = i + 1; j < redBalls.length; j++) {
            diffs.add(Math.abs(redBalls[i] - redBalls[j]));
        }
    }

    return diffs.size - 5;
}

/**
 * 计算奇偶比
 */
export function calculateOddEven(redBalls) {
    const odd = redBalls.filter(n => n % 2 === 1).length;
    const even = redBalls.length - odd;
    return `${odd}:${even}`;
}

/**
 * 计算和值
 */
export function calculateSum(redBalls) {
    return redBalls.reduce((a, b) => a + b, 0);
}

/**
 * 深拷贝
 */
export function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
}

/**
 * 防抖函数
 */
export function debounce(func, wait = 300) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * 节流函数
 */
export function throttle(func, limit = 300) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}
