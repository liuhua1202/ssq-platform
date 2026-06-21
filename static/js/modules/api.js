/**
 * API 请求封装模块
 * 优化版本：添加重试机制、超时控制、错误处理
 */

const API_BASE = '';
const DEFAULT_TIMEOUT = 30000;  // 30 秒超时（批量获取需要更长时间）
const DEFAULT_RETRY_COUNT = 2;  // 重试次数（减少到 2 次避免等待过久）

/**
 * 带超时的 fetch
 */
async function fetchWithTimeout(url, options = {}, timeout = DEFAULT_TIMEOUT) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    
    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal
        });
        return response;
    } finally {
        clearTimeout(timeoutId);
    }
}

/**
 * 通用请求处理（带重试）
 */
async function request(url, options = {}, retryCount = DEFAULT_RETRY_COUNT, timeout = DEFAULT_TIMEOUT) {
    let lastError = null;

    for (let i = 0; i < retryCount; i++) {
        try {
            // 如果是 FormData，不设置 Content-Type（让浏览器自动设置 multipart/form-data）
            const isFormData = options.body instanceof FormData;
            const defaultOptions = isFormData ? {} : {
                headers: {
                    'Content-Type': 'application/json',
                },
            };

            const response = await fetchWithTimeout(API_BASE + url, { ...defaultOptions, ...options }, timeout);
            
            // 先检查响应类型，避免解析 HTML 报错
            let data;
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                data = await response.json();
            } else {
                // 如果不是 JSON，尝试读取文本
                const text = await response.text();
                if (!response.ok) {
                    throw new Error(`服务器错误 (${response.status})：${text.substring(0, 100)}...`);
                }
                // 如果是 200 但不是 JSON，可能是路由问题
                throw new Error('服务器返回了非 JSON 数据，请检查 API 路由');
            }

            if (!response.ok) {
                throw new Error(data.message || `HTTP ${response.status}`);
            }

            return data;
        } catch (error) {
            lastError = error;

            // 记录重试
            if (i < retryCount - 1) {
                console.warn(`API 请求失败 (${url})，第 ${i + 1} 次重试...`, error.message);
                // 指数退避：1s, 2s
                await new Promise(resolve => setTimeout(resolve, 1000 * Math.pow(2, i)));
            }
        }
    }

    // 所有重试失败
    console.error(`API Error (${url}): 所有重试失败`, lastError);
    throw new Error(lastError?.message || '请求失败，请检查网络连接');
}

/**
 * GET 请求
 */
export async function get(url, params = {}) {
    const queryString = new URLSearchParams(params).toString();
    const fullUrl = queryString ? `${url}?${queryString}` : url;
    return request(fullUrl, { method: 'GET' });
}

/**
 * POST 请求
 */
export async function post(url, data = {}) {
    return request(url, {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

/**
 * DELETE 请求
 */
export async function del(url) {
    return request(url, { method: 'DELETE' });
}

/**
 * PUT 请求
 */
export async function put(url, data = {}) {
    return request(url, {
        method: 'PUT',
        body: JSON.stringify(data),
    });
}

// ==================== API 方法 ====================

// 历史数据
export function getHistory(page = 1, pageSize = 50) {
    return get('/api/history', { page, page_size: pageSize });
}

export function getLatest() {
    return get('/api/latest');
}

export function getHistoryRaw() {
    return get('/api/history/raw');
}

// 分析数据
export function getAnalysis() {
    return get('/api/analysis');
}

export function getStatistics() {
    return get('/api/statistics');
}

// 预测
export function predict(algorithm, generations = 5) {
    return post('/api/predict', { algorithm, generations });
}

// 号码检查
export function checkNumbers(redBalls, blueBall) {
    return post('/api/check', { red_balls: redBalls, blue_ball: blueBall });
}

// 收藏号码
export function getMyNumbers() {
    return get('/api/my-numbers');
}

export function saveMyNumbers(numbers) {
    return post('/api/my-numbers', { numbers });
}

export function autoCheckMyNumbers(myNumbers) {
    return post('/api/auto-check', { my_numbers: myNumbers });
}

// 数据管理
export function createBackup() {
    return post('/api/backup');
}

export function getBackups() {
    return get('/api/backups');
}

export function restoreBackup(filename) {
    return post('/api/restore', { filename });
}

export function deleteBackup(filename) {
    return del('/api/backup/' + encodeURIComponent(filename));
}

export function clearData() {
    return post('/api/clear-data');
}

export function importData(formData) {
    // 文件上传不使用 JSON，让浏览器自动设置 Content-Type
    return request('/api/import', {
        method: 'POST',
        body: formData
    });
}

export function importTextData(text) {
    return post('/api/import-text', { text });
}

// 导出
export function exportMyNumbers(format = 'json') {
    return get('/api/export/my-numbers', { format });
}

export function exportHistory(format = 'json') {
    return get('/api/export/history', { format });
}

// 在线获取开奖信息
export function fetchLatestLottery() {
    return post('/api/fetch-latest');
}

export function fetchHistoryLottery(page = 1) {
    // 批量获取时使用更长的超时时间（60 秒）
    const timeout = page > 5 ? 60000 : DEFAULT_TIMEOUT;
    return request('/api/fetch-history', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ page }),
    }, 2, timeout);  // 重试 2 次，使用自定义超时
}

// 缓存管理
export function getCacheStats() {
    return get('/api/cache/stats');
}

export function clearCache() {
    return post('/api/cache/clear');
}

// 健康检查
export function healthCheck() {
    return get('/api/health');
}
