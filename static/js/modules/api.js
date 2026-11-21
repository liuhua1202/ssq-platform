/**
 * API 请求封装模块 - WebView/Pyodide 版本
 *
 * 重构: 不再走 HTTP fetch, 改为本地调用
 *   - 数据查询: ssqDB (IndexedDB) + pyBridge.api (Pyodide 算法)
 *   - 数据导入: ssqDB.putHistory
 *   - 在线下单: ssqDB.getMyNumbers / addMyNumber
 *   - fetch-latest: 浏览器 fetch 远程, 失败回退 manual import-text
 *
 * v3.0: Pyodide 版本, 完全离线 (除非用户主动 fetch-latest)
 *
 * 对外接口保持不变: 所有 export 函数仍然返回 Promise<{success, ...}>
 * 这样调用方 (predict.js, history.js, analysis.js 等 12 个模块) 无需修改.
 */

// ----------------------------------------------------------------------
// 依赖
// ----------------------------------------------------------------------
// 由 index.html 在 <head> 里同步加载 pyodide-runner.js 和 db.js,
// 这样 self.pyBridge 和 self.ssqDB 在 ES module 求值时已经可用.
//
// 顶层 await (ES2022) 让 import 此文件的模块在 seed 完成后再继续.
await self.pyBridge.ready;

// IndexedDB seed (仅首次启动时执行)
const _seedUrl = self.__SEED_DATA_URL__ || './data/history.json';
await self.ssqDB.seedIfEmpty(_seedUrl);

// 同步 IndexedDB → Pyodide 内存 (供算法使用)
const _initRecords = await self.ssqDB.getHistoryAll();
if (_initRecords.length > 0) {
    await self.pyBridge.api('set_history', { records_json: JSON.stringify(_initRecords) });
}

console.log(`[api.js] Pyodide + IndexedDB 就绪, ${_initRecords.length} 期历史数据`);

// ----------------------------------------------------------------------
// 鉴权头 (Pyodide 版本不再需要)
// ----------------------------------------------------------------------
function withAuthHeaders(options = {}) {
    return options; // noop
}

// ----------------------------------------------------------------------
// 通用错误包装
// ----------------------------------------------------------------------
function _wrap(promise) {
    return promise.catch(err => {
        console.error('[api]', err);
        return { success: false, message: err.message || String(err) };
    });
}

// ==================== History ====================

export async function getHistory(page = 1, pageSize = 50) {
    await pyBridge.ready;
    return _wrap((async () => {
        const data = await self.ssqDB.getHistoryAll();
        const start = (page - 1) * pageSize;
        const end = start + pageSize;
        return {
            success: true,
            total: data.length,
            page,
            page_size: pageSize,
            data: data.slice(start, end)
        };
    })());
}

export async function getLatest() {
    await pyBridge.ready;
    return _wrap((async () => {
        const latest = await self.ssqDB.getLatest();
        if (!latest) return { success: false, message: '暂无历史数据' };
        return { success: true, data: latest };
    })());
}

export async function getHistoryRaw() {
    await pyBridge.ready;
    return _wrap((async () => {
        const data = await self.ssqDB.getHistoryAll();
        return { success: true, data, count: data.length };
    })());
}

// ==================== Analysis / Statistics ====================

export async function getAnalysis() {
    await pyBridge.ready;
    // v2.3.5 fix: 把 IndexedDB history 传给 Pyodide, Python 端 Analyzer 需要数据
    const data = await self.ssqDB.getHistoryAll();
    return _wrap(self.pyBridge.api('get_analysis', { history: data }));
}

export async function getStatistics() {
    await pyBridge.ready;
    // v2.3.5 fix: 同上
    const data = await self.ssqDB.getHistoryAll();
    return _wrap(self.pyBridge.api('get_statistics', { history: data }));
}

// ==================== Predict / Check ====================

export async function predict(algorithm = 'comprehensive', generations = 5) {
    await pyBridge.ready;
    const data = await self.ssqDB.getHistoryAll();
    return _wrap(self.pyBridge.api('predict', { history: data, algorithm, generations }));
}

export async function checkNumbers(redBalls, blueBall) {
    await pyBridge.ready;
    const data = await self.ssqDB.getHistoryAll();
    return _wrap(self.pyBridge.api('check_numbers', {
        history: data,
        red_balls: redBalls,
        blue_ball: blueBall
    }));
}

// ==================== My Numbers ====================

export async function getMyNumbers() {
    await pyBridge.ready;
    return _wrap((async () => {
        const list = await self.ssqDB.getMyNumbers();
        return { success: true, data: list, count: list.length };
    })());
}

export async function saveMyNumbers(numbers) {
    await pyBridge.ready;
    return _wrap((async () => {
        // numbers: [{red_balls, blue_ball, note?}, ...]
        const added = [];
        for (const n of numbers) {
            const item = await self.ssqDB.addMyNumber({
                red_balls: n.red_balls,
                blue_ball: n.blue_ball,
                note: n.note || '',
                created_at: new Date().toISOString()
            });
            added.push(item);
        }
        return { success: true, added: added.length, data: added };
    })());
}

export async function autoCheckMyNumbers(myNumbers) {
    await pyBridge.ready;
    return _wrap((async () => {
        if (!myNumbers || myNumbers.length === 0) {
            return { success: false, message: '没有可检测的号码' };
        }
        const latest = await self.ssqDB.getLatest();
        if (!latest) return { success: false, message: '暂无最新开奖数据' };
        const results = [];
        for (const n of myNumbers) {
            const r = await checkNumbers(n.red_balls, n.blue_ball);
            results.push({ ...r, note: n.note });
        }
        return { success: true, latest, results };
    })());
}

// ==================== Backup / Restore ====================

export async function createBackup() {
    await pyBridge.ready;
    return _wrap((async () => {
        const b = await self.ssqDB.createBackup();
        return { success: true, filename: b.name, id: b.id, record_count: b.record_count };
    })());
}

export async function getBackups() {
    await pyBridge.ready;
    return _wrap((async () => {
        const list = await self.ssqDB.getBackups();
        return { success: true, data: list };
    })());
}

export async function restoreBackup(filename) {
    await pyBridge.ready;
    return _wrap((async () => {
        // filename 可能是 id (数字) 或 name (字符串)
        const id = parseInt(filename, 10);
        const realId = isNaN(id) ? filename : id;
        const result = await self.ssqDB.restoreBackup(realId);
        // 重新同步 Pyodide 内存
        const records = await self.ssqDB.getHistoryAll();
        await self.pyBridge.api('set_history', { records_json: JSON.stringify(records) });
        return { success: true, restored: result.restored };
    })());
}

export async function deleteBackup(filename) {
    await pyBridge.ready;
    return _wrap((async () => {
        const id = parseInt(filename, 10);
        await self.ssqDB.deleteBackup(isNaN(id) ? filename : id);
        return { success: true };
    })());
}

export async function clearData() {
    await pyBridge.ready;
    return _wrap((async () => {
        await self.ssqDB.clearHistory();
        await self.pyBridge.api('set_history', { records_json: '[]' });
        return { success: true, message: '数据已清空' };
    })());
}

// ==================== Import ====================

/**
 * importData(formData): 从 File 对象导入 JSON
 * formData 是 FormData, 包含 'file' 字段
 */
export async function importData(formData) {
    await pyBridge.ready;
    return _wrap((async () => {
        const file = formData.get('file');
        if (!file) return { success: false, message: '未提供文件' };
        const text = await file.text();
        let records;
        try {
            records = JSON.parse(text);
        } catch (e) {
            return { success: false, message: 'JSON 解析失败: ' + e.message };
        }
        if (!Array.isArray(records)) {
            return { success: false, message: '文件内容不是数组' };
        }
        const result = await self.ssqDB.putHistory(records);
        // 同步到 Pyodide
        const all = await self.ssqDB.getHistoryAll();
        await self.pyBridge.api('set_history', { records_json: JSON.stringify(all) });
        return {
            success: true,
            added: result.added,
            updated: result.updated,
            total: result.total
        };
    })());
}

/**
 * importTextData(text): 解析用户粘贴的开奖文本
 * 复用后端 import-text 的解析逻辑 (简化版, 前端实现)
 * 支持的格式:
 *   - "2024-001 2024-01-01 01 02 03 04 05 06 07"
 *   - "2024-001 (2024-01-01) 01,02,03,04,05,06 + 07"
 *   - JSON 数组
 */
export async function importTextData(text) {
    await pyBridge.ready;
    return _wrap((async () => {
        if (!text || !text.trim()) {
            return { success: false, message: '文本为空' };
        }

        const records = _parseLotteryText(text);
        if (records.length === 0) {
            return { success: false, message: '未能从文本中解析出有效数据, 请检查格式' };
        }
        const result = await self.ssqDB.putHistory(records);
        // 同步到 Pyodide
        const all = await self.ssqDB.getHistoryAll();
        await self.pyBridge.api('set_history', { records_json: JSON.stringify(all) });
        return {
            success: true,
            imported: records.length,
            added: result.added,
            updated: result.updated,
            total: result.total
        };
    })());
}

/**
 * 解析用户粘贴的开奖文本 (前端实现, 兼容后端 import-text 行为)
 */
function _parseLotteryText(text) {
    const records = [];

    // 先尝试 JSON
    try {
        const obj = JSON.parse(text);
        if (Array.isArray(obj)) {
            return obj.filter(r => r && r.issue && Array.isArray(r.red_balls));
        }
        if (obj.issue && Array.isArray(obj.red_balls)) {
            return [obj];
        }
    } catch (_) {
        // 不是 JSON, 走文本解析
    }

    // 按行分割
    const lines = text.split(/[\r\n]+/).map(l => l.trim()).filter(Boolean);
    for (const line of lines) {
        const rec = _parseLine(line);
        if (rec) records.push(rec);
    }
    return records;
}

function _parseLine(line) {
    // 多种格式尝试:
    // 1) "2024-001 2024-01-01 01 02 03 04 05 06 07"
    // 2) "2024001 2024-01-01 01 02 03 04 05 06 07"
    // 3) "2024-001 (2024-01-01) 01,02,03,04,05,06 + 07"
    // 4) "2024-001|2024-01-01|01|02|03|04|05|06|07"

    // 抽离所有数字
    const nums = line.match(/\d+/g);
    if (!nums || nums.length < 8) return null;

    // 第 1 个是 issue, 第 2 个可能是 date (8 位或带 -)
    let issue = nums[0];
    let date = '';
    let ballStartIdx = 1;

    // 判断第 2 个是 date 还是 ball
    if (/^\d{4}[-/]?\d{1,2}[-/]?\d{1,2}$/.test(nums[1]) ||
        /^\d{8}$/.test(nums[1])) {
        date = _normalizeDate(nums[1]);
        ballStartIdx = 2;
    } else if (/^\d{7}$/.test(nums[1])) {
        // 双色球期号是 7 位, 不太可能撞
        issue = nums[1];
        ballStartIdx = 2;
    }

    const balls = nums.slice(ballStartIdx, ballStartIdx + 7).map(n => parseInt(n, 10));
    if (balls.length !== 7) return null;
    const red = balls.slice(0, 6);
    const blue = balls[6];

    // 校验范围
    if (red.some(b => b < 1 || b > 33)) return null;
    if (blue < 1 || blue > 16) return null;
    if (new Set(red).size !== 6) return null; // 红球不能重复

    return {
        issue: _normalizeIssue(issue),
        date: date || _guessDate(issue),
        red_balls: red.sort((a, b) => a - b),
        blue_ball: blue
    };
}

function _normalizeIssue(s) {
    // 接受 "2024-001", "2024001", "24-001", 转成 7 位 "2024001"
    const digits = String(s).replace(/\D/g, '');
    if (digits.length === 7) return digits;
    if (digits.length === 5) return '20' + digits; // 24-001 -> 2024001
    if (digits.length === 8 && digits.startsWith('20')) return digits.slice(1); // 2024001 -> 024001? 不, 应保留 8 位
    return digits;
}

function _normalizeDate(s) {
    const d = String(s).replace(/\D/g, '');
    if (d.length === 8) return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`;
    return s;
}

function _guessDate(issue) {
    // 根据 issue 推算大概日期 (粗略, 用户手动填)
    const s = _normalizeIssue(issue);
    if (s.length === 7) {
        const year = parseInt(s.slice(0, 4), 10);
        const idx = parseInt(s.slice(4), 10);
        // 双色球每年约 150 期, 3 期/周
        const month = Math.floor((idx - 1) / 13) + 1;
        const day = ((idx - 1) % 13) * 7 + 1;
        return `${year}-${String(month).padStart(2, '0')}-${String(Math.min(day, 28)).padStart(2, '0')}`;
    }
    return new Date().toISOString().slice(0, 10);
}

// ==================== Export ====================

function _downloadBlob(filename, content, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function exportMyNumbers(format = 'json') {
    await pyBridge.ready;
    return _wrap((async () => {
        const list = await self.ssqDB.getMyNumbers();
        const stamp = new Date().toISOString().slice(0, 10);
        if (format === 'csv') {
            const csv = ['issue,date,red1,red2,red3,red4,red5,red6,blue_ball,note']
                .concat(list.map(n => [
                    n.issue || '',
                    n.created_at || '',
                    ...(n.red_balls || []),
                    n.blue_ball || '',
                    '"' + (n.note || '').replace(/"/g, '""') + '"'
                ].join(',')))
                .join('\n');
            _downloadBlob(`my-numbers-${stamp}.csv`, csv, 'text/csv;charset=utf-8');
        } else {
            _downloadBlob(`my-numbers-${stamp}.json`, JSON.stringify(list, null, 2), 'application/json');
        }
        return { success: true, count: list.length };
    })());
}

export async function exportHistory(format = 'json') {
    await pyBridge.ready;
    return _wrap((async () => {
        const data = await self.ssqDB.getHistoryAll();
        const stamp = new Date().toISOString().slice(0, 10);
        if (format === 'csv') {
            const csv = ['issue,date,red1,red2,red3,red4,red5,red6,blue_ball']
                .concat(data.map(r => [
                    r.issue, r.date || '',
                    ...(r.red_balls || []),
                    r.blue_ball
                ].join(',')))
                .join('\n');
            _downloadBlob(`history-${stamp}.csv`, csv, 'text/csv;charset=utf-8');
        } else {
            _downloadBlob(`history-${stamp}.json`, JSON.stringify(data, null, 2), 'application/json');
        }
        return { success: true, count: data.length };
    })());
}

// ==================== Fetch Latest (在线 + 手动引导) ====================

/**
 * cwl.gov.cn 官方 JSON API
 * - 返回纯 JSON (CORS 友好, 不需要 scrapling / headless 浏览器)
 * - 单期结构: {code: '2026105', date: '2026-09-10(四)', red: '02,04,13,14,15,30', blue: '08', ...}
 * - 全量 2063 期, 分页 pageNo=1, pageSize=20 拿最新 20 期
 */
const CWL_API = 'https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice';
const CWL_API_PARAMS = 'name=ssq&systemType=PC';

function _parseCwlApiRecord(item) {
    if (!item || !item.code || !item.red || !item.blue) return null;
    const redArr = String(item.red)
        .split(',')
        .map(s => parseInt(s.trim(), 10))
        .filter(n => Number.isInteger(n) && n >= 1 && n <= 33);
    if (redArr.length !== 6) return null;
    const blueNum = parseInt(String(item.blue).trim(), 10);
    if (!Number.isInteger(blueNum) || blueNum < 1 || blueNum > 16) return null;
    return {
        issue: String(item.code),
        date: String(item.date || ''),
        red_balls: redArr,
        blue_ball: blueNum
    };
}

async function _cwlFetchJson(pageNo, pageSize) {
    const url = `${CWL_API}?${CWL_API_PARAMS}&pageNo=${pageNo}&pageSize=${pageSize}`;
    const resp = await fetch(url, {
        method: 'GET',
        headers: {
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.cwl.gov.cn/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        },
        credentials: 'omit',
        cache: 'no-store',
        signal: AbortSignal.timeout(8000)
    });
    if (!resp.ok) throw new Error('cwl.gov.cn HTTP ' + resp.status);
    const data = await resp.json();
    if (!data || data.state !== 0) {
        throw new Error('cwl.gov.cn 返回错误: ' + (data && data.message ? data.message : 'state=' + (data && data.state)));
    }
    if (!Array.isArray(data.result) || data.result.length === 0) {
        throw new Error('cwl.gov.cn 返回空 result (page=' + pageNo + ')');
    }
    return data;
}

const MANUAL_SOURCES = [
    { name: '福彩官方 (列表页)', url: 'https://www.cwl.gov.cn/c/2024-09/wckjgg/ssq/' },
    { name: '中彩网 (历史开奖)', url: 'https://www.zhcw.com/kjgg/ssq/' }
];

/**
 * 在线获取最新一期.
 * 优先 cwl.gov.cn 官方 JSON API (CORS 友好, 不需要 scrapling);
 * 失败时返回 need_manual=true 引导用户手动 import-text.
 */
export async function fetchLatestLottery() {
    await pyBridge.ready;
    return _wrap((async () => {
        try {
            const data = await _cwlFetchJson(1, 1);
            const rec = _parseCwlApiRecord(data.result[0]);
            if (!rec) throw new Error('cwl.gov.cn record 解析失败');
            const put = await self.ssqDB.putHistory([rec]);
            const all = await self.ssqDB.getHistoryAll();
            await self.pyBridge.api('set_history', { records_json: JSON.stringify(all) });
            return {
                success: true,
                source: 'cwl.gov.cn (官方 JSON API)',
                data: rec,
                added: put.added,
                updated: put.updated
            };
        } catch (e) {
            console.warn('[fetch-latest] cwl.gov.cn failed:', e.message);
            return {
                success: false,
                need_manual: true,
                message: '在线获取失败 (' + e.message + '), 请手动复制开奖文本后使用 import-text 功能',
                manual_sources: MANUAL_SOURCES
            };
        }
    })());
}

/**
 * 在线获取历史数据 (默认拉 1 页 = 最新 20 期).
 * 拉取多页时, 同一 pageSize 的总条数 = data.total, 翻到末页即可.
 * @param {number} page  - 页码 (1-based)
 * @param {number} pageSize - 每页条数 (默认 20, 最大 30)
 */
export async function fetchHistoryLottery(page = 1, pageSize = 20) {
    await pyBridge.ready;
    return _wrap((async () => {
        try {
            const ps = Math.max(1, Math.min(30, parseInt(pageSize, 10) || 20));
            const data = await _cwlFetchJson(page, ps);
            const records = [];
            for (const item of data.result) {
                const rec = _parseCwlApiRecord(item);
                if (rec) records.push(rec);
            }
            if (records.length === 0) {
                throw new Error('cwl.gov.cn 返回 ' + data.result.length + ' 条但全部解析失败');
            }
            const put = await self.ssqDB.putHistory(records);
            const all = await self.ssqDB.getHistoryAll();
            await self.pyBridge.api('set_history', { records_json: JSON.stringify(all) });
            return {
                success: true,
                source: 'cwl.gov.cn (官方 JSON API)',
                total: data.total || records.length,
                page: page,
                page_size: ps,
                fetched: records.length,
                new_count: put.added + put.updated,
                added: put.added,
                updated: put.updated,
                db_total: all.length
            };
        } catch (e) {
            console.warn('[fetch-history] cwl.gov.cn failed:', e.message);
            return {
                success: false,
                need_manual: true,
                message: '在线获取历史失败 (' + e.message + '), 请手动复制开奖文本后使用 import-text 功能',
                manual_sources: MANUAL_SOURCES
            };
        }
    })());
}

// ==================== Cache / Health ====================

export async function getCacheStats() {
    await pyBridge.ready;
    return _wrap((async () => {
        const histCount = await self.ssqDB.countHistory();
        const mineCount = (await self.ssqDB.getMyNumbers()).length;
        const backups = await self.ssqDB.getBackups();
        return {
            success: true,
            history_count: histCount,
            my_numbers_count: mineCount,
            backup_count: backups.length
        };
    })());
}

export async function clearCache() {
    await pyBridge.ready;
    return _wrap((async () => {
        await self.ssqDB.clearHistory();
        await self.pyBridge.api('set_history', { records_json: '[]' });
        return { success: true, message: '缓存已清空 (等同于清空数据)' };
    })());
}

export async function healthCheck() {
    await pyBridge.ready;
    return _wrap((async () => {
        const count = await self.ssqDB.countHistory();
        return {
            success: true,
            status: 'ok',
            pyodide_ready: true,
            history_count: count,
            timestamp: new Date().toISOString()
        };
    })());
}

// ==================== 兼容旧 import 风格的 get/post/del ====================
// 这些被一些模块直接 import 使用 (getMyNumbers 等已经重写, 保留以防万一)

export async function get(url, params = {}) {
    console.warn('[api.get] deprecated direct call:', url);
    return { success: false, message: 'Direct GET not supported in Pyodide mode' };
}

export async function post(url, data = {}) {
    console.warn('[api.post] deprecated direct call:', url);
    return { success: false, message: 'Direct POST not supported in Pyodide mode' };
}

export async function del(url) {
    console.warn('[api.del] deprecated direct call:', url);
    return { success: false, message: 'Direct DELETE not supported in Pyodide mode' };
}

export async function put(url, data = {}) {
    console.warn('[api.put] deprecated direct call:', url);
    return { success: false, message: 'Direct PUT not supported in Pyodide mode' };
}
