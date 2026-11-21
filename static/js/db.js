/**
 * IndexedDB 封装 - 替代后端 history.json 文件
 *
 * 设计目标:
 *   - 提供与原 crawler.load_history() / save_history() 兼容的接口
 *   - 支持按 issue 排序、批量插入、去重
 *   - 支持 my_numbers (用户收藏号码) 持久化
 *   - 支持 backups (快照列表)
 *
 * 浏览器 / WebView 都支持 IndexedDB. 容量: 浏览器无限制(直到磁盘满),
 * Android WebView >= 50MB 数据 + 取决于用户配额.
 */

(function () {
    'use strict';

    const DB_NAME = 'ssq-platform';
    const DB_VERSION = 1;
    const STORE_HISTORY = 'history';      // 主键: issue (string)
    const STORE_MY_NUMBERS = 'my_numbers'; // 主键: id (auto-increment)
    const STORE_BACKUPS = 'backups';      // 主键: id, 存 history 快照
    const STORE_META = 'meta';            // 主键: key, 存键值对

    let _dbPromise = null;

    function _openDB() {
        if (_dbPromise) return _dbPromise;

        _dbPromise = new Promise((resolve, reject) => {
            const req = indexedDB.open(DB_NAME, DB_VERSION);

            req.onupgradeneeded = (e) => {
                const db = e.target.result;

                if (!db.objectStoreNames.contains(STORE_HISTORY)) {
                    const store = db.createObjectStore(STORE_HISTORY, { keyPath: 'issue' });
                    store.createIndex('date', 'date', { unique: false });
                }

                if (!db.objectStoreNames.contains(STORE_MY_NUMBERS)) {
                    const store = db.createObjectStore(STORE_MY_NUMBERS, { keyPath: 'id', autoIncrement: true });
                    store.createIndex('created_at', 'created_at', { unique: false });
                }

                if (!db.objectStoreNames.contains(STORE_BACKUPS)) {
                    const store = db.createObjectStore(STORE_BACKUPS, { keyPath: 'id', autoIncrement: true });
                    store.createIndex('created_at', 'created_at', { unique: false });
                }

                if (!db.objectStoreNames.contains(STORE_META)) {
                    db.createObjectStore(STORE_META, { keyPath: 'key' });
                }
            };

            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
        });

        return _dbPromise;
    }

    function _tx(storeName, mode = 'readonly') {
        return _openDB().then(db => {
            const tx = db.transaction(storeName, mode);
            return tx.objectStore(storeName);
        });
    }

    function _reqToPromise(req) {
        return new Promise((resolve, reject) => {
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
        });
    }

    // ---------- History ----------

    /**
     * 批量插入或更新历史数据 (按 issue 去重, 已存在的会被覆盖).
     * 返回 { added, updated, total }.
     */
    async function putHistory(records) {
        const db = await _openDB();
        const tx = db.transaction(STORE_HISTORY, 'readwrite');
        const store = tx.objectStore(STORE_HISTORY);

        let added = 0, updated = 0;
        for (const r of records) {
            if (!r || !r.issue) continue;
            const existing = await _reqToPromise(store.get(r.issue));
            if (existing) updated++;
            else added++;
            store.put(r); // keyPath 模式, 直接 put 对象
        }

        await new Promise((res, rej) => {
            tx.oncomplete = res;
            tx.onerror = () => rej(tx.error);
        });

        const total = await countHistory();
        return { added, updated, total };
    }

    async function getHistoryAll() {
        const store = await _tx(STORE_HISTORY);
        const records = await _reqToPromise(store.getAll());
        // 按 issue 降序
        records.sort((a, b) => (b.issue || '').localeCompare(a.issue || ''));
        return records;
    }

    async function getLatest() {
        const store = await _tx(STORE_HISTORY);
        // 用 cursor 按 date/issue 倒序拿到第一条
        return new Promise((resolve, reject) => {
            const req = store.openCursor(null, 'prev');
            req.onsuccess = () => resolve(req.result ? req.result.value : null);
            req.onerror = () => reject(req.error);
        });
    }

    async function countHistory() {
        const store = await _tx(STORE_HISTORY);
        return _reqToPromise(store.count());
    }

    async function clearHistory() {
        const store = await _tx(STORE_HISTORY, 'readwrite');
        await _reqToPromise(store.clear());
    }

    async function deleteHistory(issue) {
        const store = await _tx(STORE_HISTORY, 'readwrite');
        await _reqToPromise(store.delete(issue));
    }

    // ---------- My Numbers ----------

    async function getMyNumbers() {
        const store = await _tx(STORE_MY_NUMBERS);
        const list = await _reqToPromise(store.getAll());
        list.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
        return list;
    }

    async function addMyNumber(item) {
        if (!item.created_at) item.created_at = new Date().toISOString();
        const store = await _tx(STORE_MY_NUMBERS, 'readwrite');
        const id = await _reqToPromise(store.add(item));
        return { ...item, id };
    }

    async function deleteMyNumber(id) {
        const store = await _tx(STORE_MY_NUMBERS, 'readwrite');
        await _reqToPromise(store.delete(id));
    }

    async function clearMyNumbers() {
        const store = await _tx(STORE_MY_NUMBERS, 'readwrite');
        await _reqToPromise(store.clear());
    }

    // ---------- Backups ----------

    async function createBackup(name) {
        const records = await getHistoryAll();
        const item = {
            name: name || ('backup-' + new Date().toISOString().replace(/[:.]/g, '-')),
            created_at: new Date().toISOString(),
            record_count: records.length,
            records
        };
        const store = await _tx(STORE_BACKUPS, 'readwrite');
        const id = await _reqToPromise(store.add(item));
        return { ...item, id };
    }

    async function getBackups() {
        const store = await _tx(STORE_BACKUPS);
        const list = await _reqToPromise(store.getAll());
        list.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
        // 不返回完整 records (太大), 只返回元数据
        return list.map(b => ({
            id: b.id,
            name: b.name,
            created_at: b.created_at,
            record_count: b.record_count
        }));
    }

    async function restoreBackup(id) {
        const store = await _tx(STORE_BACKUPS, 'readwrite');
        const backup = await _reqToPromise(store.get(id));
        if (!backup) throw new Error('Backup not found: ' + id);
        await clearHistory();
        await putHistory(backup.records);
        return { success: true, restored: backup.record_count };
    }

    async function deleteBackup(id) {
        const store = await _tx(STORE_BACKUPS, 'readwrite');
        await _reqToPromise(store.delete(id));
    }

    // ---------- Meta (键值对) ----------

    async function setMeta(key, value) {
        const store = await _tx(STORE_META, 'readwrite');
        await _reqToPromise(store.put({ key, value }));
    }

    async function getMeta(key) {
        const store = await _tx(STORE_META);
        const row = await _reqToPromise(store.get(key));
        return row ? row.value : null;
    }

    /**
     * 首次启动时 seed: 从 assets/data/history.json 导入, 仅当 DB 为空时.
     * 返回 { seeded: bool, count: number }.
     */
    async function seedIfEmpty(seedUrl) {
        const total = await countHistory();
        if (total > 0) return { seeded: false, count: total };

        try {
            const resp = await fetch(seedUrl);
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            const records = await resp.json();
            if (!Array.isArray(records) || records.length === 0) {
                return { seeded: false, count: 0 };
            }
            const result = await putHistory(records);
            return { seeded: true, ...result };
        } catch (e) {
            console.warn('[db] seed failed:', e.message);
            return { seeded: false, count: 0, error: e.message };
        }
    }

    // ---------- 导出 ----------
    self.ssqDB = {
        // history
        putHistory,
        getHistoryAll,
        getLatest,
        countHistory,
        clearHistory,
        deleteHistory,
        // my numbers
        getMyNumbers,
        addMyNumber,
        deleteMyNumber,
        clearMyNumbers,
        // backups
        createBackup,
        getBackups,
        restoreBackup,
        deleteBackup,
        // meta
        setMeta,
        getMeta,
        // seed
        seedIfEmpty,
        // low-level
        _open: _openDB
    };
})();
