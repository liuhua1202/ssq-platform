/**
 * Pyodide Runner - 在 WebView / 浏览器内运行 Python 算法
 *
 * 职责:
 *   1. 加载 Pyodide runtime (~14MB,本地 assets 或 CDN)
 *   2. 注入 algorithms zip 到 Python sys.path
 *   3. 提供 await pyBridge.ready 等待初始化完成
 *   4. 提供 pyBridge.runPython(code) 执行任意 Python
 *   5. 提供 pyBridge.api(method, params) 调用 SSQ 平台 API
 *
 * 使用:
 *   await pyBridge.ready;
 *   const result = await pyBridge.api('get_history', { page: 1 });
 */

(function () {
    'use strict';

    // ---------- 配置 ----------
    // 离线优先: 指向 Flask static 目录下的 pyodide/
    // 浏览器请求 ./static/pyodide/ 解析为 http://localhost:5000/static/pyodide/
    //   (Flask 默认服务 static_folder='/static')
    // 部署到子路径时, 可通过模板注入 window.__PYODIDE_BASE__ 覆盖
    const PYODIDE_BASE = self.__PYODIDE_BASE__ || './static/pyodide/';
    // v2.3 修复: 加 ?v= 缓存破坏, 浏览器 HTTP 缓存会跳过旧版 src.zip
    const ALGORITHMS_ZIP_URL = self.__ALGORITHMS_ZIP_URL__ || './static/python-lib/src.zip?v=2.3';
    const SEED_DATA_URL = self.__SEED_DATA_URL__ || './static/data/history.json?v=2.3';

    // ---------- 内部状态 ----------
    let _pyodide = null;
    let _ready = null; // Promise<pyodide>
    let _initLog = [];

    function _log(...args) {
        const msg = '[pyBridge] ' + args.join(' ');
        _initLog.push(msg);
        console.log(msg);
    }

    // ---------- 加载 Pyodide ----------
    async function _loadPyodide() {
        if (_pyodide) return _pyodide;

        _log('加载 Pyodide runtime from', PYODIDE_BASE);

        // 动态注入 <script src="pyodide.js"> 因为 pyodide 是 IIFE 暴露全局 loadPyodide
        await new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = PYODIDE_BASE + 'pyodide.js';
            script.onload = resolve;
            script.onerror = () => reject(new Error('Failed to load pyodide.js from ' + PYODIDE_BASE));
            document.head.appendChild(script);
        });

        const loadPyodide = self.loadPyodide;
        if (!loadPyodide) {
            throw new Error('loadPyodide not found on window after pyodide.js loaded');
        }

        const py = await loadPyodide({
            indexURL: PYODIDE_BASE,
            // fullStdLib 默认是 true, 但我们只用 core + 自带 stdlib.zip
            fullStdLib: false,
        });

        _log('Pyodide 已加载, Python', py.runPython('import sys; sys.version'));
        return py;
    }

    // ---------- 注入算法 zip ----------
    async function _installAlgorithms(py) {
        _log('安装算法包...');

        // 用 fetch + zipfile 解压 zip 到 Pyodide 虚拟文件系统
        // Pyodide 提供 pyodide.FS.writeFile / mkdir, 但 zip 解压用 Python 更方便
        const resp = await fetch(ALGORITHMS_ZIP_URL);
        if (!resp.ok) {
            throw new Error('Failed to fetch algorithms zip: ' + resp.status);
        }
        const buf = new Uint8Array(await resp.arrayBuffer());

        // 把 zip 写入 Pyodide 内存文件系统
        py.FS.writeFile('/tmp/src.zip', buf);

        // 用 Python zipfile 解压到 /home/pyodide/python-lib/src
        py.runPython(`
import zipfile, os, sys
target = '/home/pyodide/python-lib/src'
os.makedirs(target, exist_ok=True)
with zipfile.ZipFile('/tmp/src.zip', 'r') as z:
    z.extractall(target)

# 把 src 父目录加入 sys.path, 这样 'import src.algorithms.xxx' 能工作
parent = '/home/pyodide/python-lib'
if parent not in sys.path:
    sys.path.insert(0, parent)

# 验证导入
from src.algorithms import (
    WeightedRandomAlgorithm,
    NormalDistributionAlgorithm,
    GeneticAlgorithm,
    MonteCarloAlgorithm,
    ComprehensiveAlgorithm,
    SmartRecommendationAlgorithm,
    ZoneDistributionAlgorithm,
    ConsecutiveAnalysisAlgorithm,
    SameTailAnalysisAlgorithm,
    PrimeCompositeAlgorithm,
    BigSmallAnalysisAlgorithm,
    MarkovChainAlgorithm,
    KMeansClusteringAlgorithm,
)
from src.analyzer import Analyzer
from src.predictor import Predictor
print('Algorithms loaded OK')
`);

        _log('算法包安装完成');
    }

    // ---------- 注册 API 方法 ----------
    // 每个方法映射到一个 Python 函数, 通过 globals['api_<name>'] 调用
    function _registerApi(py) {
        _log('注册 API handlers...');

        py.runPython(`
import json as _json
from src.analyzer import Analyzer as _Analyzer
from src.predictor import Predictor as _Predictor

# 维护一份内存中的历史数据 (从 IndexedDB seed)
_history_data = []

def api_set_history(records_json):
    """设置历史数据 (JS 端传入 JSON 字符串)"""
    global _history_data
    _history_data = _json.loads(records_json)
    # 按 issue 降序
    _history_data.sort(key=lambda r: r.get('issue', ''), reverse=True)
    return {'success': True, 'count': len(_history_data)}

def api_get_history(page=1, page_size=50):
    """获取历史数据 (分页)"""
    if not _history_data:
        return {'success': False, 'message': '暂无历史数据', 'total': 0, 'data': []}
    start = (page - 1) * page_size
    end = start + page_size
    return {
        'success': True,
        'total': len(_history_data),
        'page': page,
        'page_size': page_size,
        'data': _history_data[start:end]
    }

def api_get_latest():
    """获取最新一期"""
    if not _history_data:
        return {'success': False, 'message': '暂无历史数据'}
    return {'success': True, 'data': _history_data[0]}

def api_get_history_raw():
    """获取全部历史数据"""
    return {'success': True, 'data': _history_data, 'count': len(_history_data)}

def api_get_analysis():
    """获取综合分析"""
    if not _history_data:
        return {'success': False, 'message': '暂无历史数据，请先更新数据'}
    analyzer = _Analyzer(_history_data)
    result = analyzer.get_comprehensive_analysis()
    result['cached'] = False
    return result

def api_get_statistics():
    """获取统计信息"""
    if not _history_data:
        return {'success': False, 'message': '暂无历史数据'}
    analyzer = _Analyzer(_history_data)
    hot = analyzer.get_hot_numbers()
    cold = analyzer.get_cold_numbers()
    missing = analyzer.get_missing_stats()
    odd_even = analyzer.get_odd_even_ratio()
    sum_a = analyzer.get_sum_analysis()
    blue = analyzer.get_blue_ball_analysis()
    return {
        'success': True,
        'total_records': len(_history_data),
        'hot_numbers': hot['overall'],
        'cold_numbers': cold['numbers'],
        'missing_stats': missing,
        'odd_even': odd_even,
        'sum_analysis': sum_a,
        'blue_ball': blue
    }

def api_predict(algorithm='comprehensive', generations=5):
    """生成预测号码"""
    if not _history_data:
        return {'success': False, 'message': '暂无历史数据，请先更新数据'}
    if not isinstance(generations, int) or generations < 1 or generations > 100:
        return {'success': False, 'message': 'generations 必须在 1-100 之间'}
    try:
        analyzer = _Analyzer(_history_data)
        predictor = _Predictor(analyzer)
        predictions = predictor.predict(algorithm, generations)
        return {
            'success': True,
            'algorithm': algorithm,
            'predictions': predictions,
            'cached': False
        }
    except ValueError as e:
        return {'success': False, 'message': str(e)}

def api_check_numbers(red_balls, blue_ball):
    """检查指定号码是否中奖 (与最新一期对比)"""
    if not _history_data:
        return {'success': False, 'message': '暂无历史数据'}
    latest = _history_data[0]
    red_set = set(latest.get('red_balls', []))
    red_hit = sum(1 for r in red_balls if r in red_set)
    blue_hit = 1 if blue_ball == latest.get('blue_ball') else 0
    return {
        'success': True,
        'latest_issue': latest.get('issue'),
        'latest_date': latest.get('date'),
        'latest_red_balls': latest.get('red_balls'),
        'latest_blue_ball': latest.get('blue_ball'),
        'red_hit': red_hit,
        'blue_hit': blue_hit,
        'your_red': red_balls,
        'your_blue': blue_ball
    }

def api_get_algorithms():
    """获取可用算法列表"""
    from src.predictor import Predictor
    return {'success': True, 'algorithms': Predictor.ALGORITHM_CLASSES.keys() if hasattr(Predictor.ALGORITHM_CLASSES, 'keys') else list(Predictor.ALGORITHM_CLASSES)}

print('API handlers registered:', [n for n in dir() if n.startswith('api_')])
`);

        _log('API handlers 已注册');
    }

    // ---------- seed 历史数据 ----------
    async function _seedHistoryFromAssets(py) {
        try {
            const resp = await fetch(SEED_DATA_URL);
            if (!resp.ok) {
                _log('seed data 未找到 (status=' + resp.status + '), 跳过');
                return false;
            }
            const records = await resp.json();
            if (!Array.isArray(records) || records.length === 0) {
                _log('seed data 为空, 跳过');
                return false;
            }
            const json = JSON.stringify(records);
            py.globals.get('api_set_history')(json);
            _log('seed 历史数据已加载:', records.length, '期');
            return true;
        } catch (e) {
            _log('seed 加载失败 (非致命):', e.message);
            return false;
        }
    }

    // ---------- 主初始化 ----------
    async function _init() {
        const py = await _loadPyodide();
        await _installAlgorithms(py);
        _registerApi(py);
        _pyodide = py;
        // 等待 _ready 解析后再 seed, 这样调用方拿到 ready 时数据已就绪
        await _seedHistoryFromAssets(py);
        _log('Pyodide bridge ready ✓');
        return py;
    }

    _ready = _init();

    // ---------- 公共 API ----------
    self.pyBridge = {
        /** 等待 Pyodide + 算法 + seed 数据全部就绪 */
        get ready() {
            return _ready;
        },

        /** 初始化日志 (调试用) */
        get log() {
            return _initLog.slice();
        },

        /** 直接执行 Python 代码, 返回 JS 值 (PyProxy 自动转换) */
        async runPython(code) {
            const py = await _ready;
            return py.runPython(code);
        },

        /** 调用 SSQ API 方法
         *  method: 字符串, 对应 Python api_<method> 函数
         *  params: 对象, 作为 **kwargs 传入
         */
        async api(method, params = {}) {
            const py = await _ready;
            const fn = py.globals.get('api_' + method);
            if (!fn) {
                throw new Error('Unknown API method: ' + method);
            }
            try {
                // 用临时变量避免重复执行, Python runPython 返回最后一个表达式的值
                const paramsJson = JSON.stringify(params);
                const code =
                    `_bridge_r = api_${method}(**_json.loads('${paramsJson.replace(/'/g, "\\'")}'));` +
                    `_json.dumps(_bridge_r)`;
                const resultJson = py.runPython(code);
                return JSON.parse(resultJson);
            } catch (e) {
                _log('API 调用失败:', method, e.message);
                throw e;
            }
        },

        /** 重新 seed 历史数据 (用户清空后想恢复初始数据时) */
        async reseedHistory() {
            const py = await _ready;
            return _seedHistoryFromAssets(py);
        },

        /** 重置整个 Pyodide (调试用) */
        async reset() {
            _pyodide = null;
            _ready = _init();
            await _ready;
        },

        /** 底层 Pyodide 句柄 (高级用法) */
        get pyodide() {
            return _pyodide;
        },
    };
})();
