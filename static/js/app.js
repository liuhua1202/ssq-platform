/**
 * 双色球预测平台 - 主入口
 * Switch 主题版本
 * Version: 20260428 - 优化版
 */

// 全局命名空间（避免全局函数污染）
const SSQApp = {
    modules: {},

    /**
     * 注册模块
     */
    registerModule(name, module) {
        this.modules[name] = module;
    },

    /**
     * 获取模块
     */
    getModule(name) {
        return this.modules[name];
    },

    /**
     * 调用模块方法（统一入口，避免全局函数污染）
     */
    call(moduleName, methodName, ...args) {
        const module = this.modules[moduleName];
        if (!module) {
            console.warn(`模块 ${moduleName} 未加载`);
            return;
        }
        if (typeof module[methodName] !== 'function') {
            console.warn(`模块 ${moduleName} 没有方法 ${methodName}`);
            return;
        }
        return module[methodName](...args);
    }
};

/**
 * 异步加载单个模块，带错误处理
 */
async function loadModule(modulePath, moduleName) {
    try {
        const module = await import(modulePath);
        console.log(`✓ 模块加载成功：${moduleName}`);
        return module;
    } catch (error) {
        console.error(`✗ 模块加载失败：${moduleName} (${modulePath})`, error);
        throw new Error(`模块 ${moduleName} 加载失败`);
    }
}

/**
 * 初始化应用
 */
async function initApp() {
    console.log('%c 双色球预测平台 (Pyodide/WebView 版) 启动中...', 'color: #4CAF50; font-weight: bold; font-size: 14px;');
    console.log(`版本：20260429 - Pyodide 离线版`);

    const loadingEl = document.getElementById('loading');
    if (loadingEl) {
        loadingEl.innerHTML = '<p style="color: #666;">正在初始化 Python 运行时...</p>';
    }

    // 等待 Pyodide + 算法 + IndexedDB seed 完成
    try {
        if (window.pyBridge && window.pyBridge.ready) {
            // api.js 顶层 await 会等待 Pyodide + IndexedDB seed 完成
            // v2.3.7 fix: 重写 fetchLatestLottery / fetchHistoryLottery 走 cwl.gov.cn JSON API
            //              之前两个 parser (_parseZhcwHtml/_parseCwlHtml) 都是 TODO stub
            await import('./modules/api.js?v=2.3.7');
            console.log('api.js loaded, data seeded');
        }
    } catch (e) {
        console.error('Pyodide 初始化失败:', e);
        if (loadingEl) {
            loadingEl.innerHTML = `<p style="color: #f44336;">Python 运行时加载失败: ${e.message}</p>
                <p style="color: #666; font-size: 12px;">请检查网络连接后刷新页面</p>`;
        }
        return;
    }

    try {
        // 异步加载所有模块，带错误处理
        const modules = {};
        const moduleList = [
            { path: './modules/predict.js?v=2.3.6', name: 'PredictModule', key: 'predict' },
            { path: './modules/history.js?v=2.3.6', name: 'HistoryModule', key: 'history' },
            { path: './modules/analysis.js?v=2.3.6', name: 'AnalysisModule', key: 'analysis' },
            { path: './modules/check.js?v=2.3.6', name: 'CheckModule', key: 'check' },
            { path: './modules/myNumbers.js?v=2.3.6', name: 'MyNumbersModule', key: 'myNumbers' },
            { path: './modules/dataManager.js?v=2.3.6', name: 'DataManagerModule', key: 'dataManager' },
            { path: './modules/export.js?v=2.3.6', name: 'ExportModule', key: 'export' },
            { path: './modules/onlineFetch.js?v=2.3.6', name: 'OnlineFetchModule', key: 'onlineFetch' },
            { path: './modules/utils.js?v=2.3.6', name: 'getCachedHistory', key: 'utils' }
        ];

        // 逐个加载模块，避免一个失败全部失败
        for (const mod of moduleList) {
            try {
                modules[mod.key] = await loadModule(mod.path, mod.name);
            } catch (error) {
                console.warn(`模块 ${mod.name} 加载失败，将继续加载其他模块`);
            }
        }

        // 检查必需模块
        const requiredModules = ['predict', 'history', 'analysis', 'utils'];
        const missingRequired = requiredModules.filter(key => !modules[key]);
        
        if (missingRequired.length > 0) {
            throw new Error(`缺少必需模块：${missingRequired.join(', ')}`);
        }

        console.log('%c 所有模块加载成功', 'color: #4CAF50;');

        // 预加载缓存的历史数据
        if (modules.utils && modules.utils.getCachedHistory) {
            const cached = modules.utils.getCachedHistory();
            if (cached) {
                console.log(`使用缓存的历史数据：${cached.length} 条`);
            }
        }

        // 初始化各模块（使用命名空间）
        SSQApp.registerModule('predict', modules.predict ? new modules.predict.PredictModule() : null);
        SSQApp.registerModule('history', modules.history ? new modules.history.HistoryModule() : null);
        SSQApp.registerModule('analysis', modules.analysis ? new modules.analysis.AnalysisModule() : null);
        SSQApp.registerModule('check', modules.check ? new modules.check.CheckModule() : null);
        SSQApp.registerModule('myNumbers', modules.myNumbers ? new modules.myNumbers.MyNumbersModule() : null);
        SSQApp.registerModule('dataManager', modules.dataManager ? new modules.dataManager.DataManagerModule() : null);
        SSQApp.registerModule('export', modules.export ? new modules.export.ExportModule() : null);
        SSQApp.registerModule('onlineFetch', modules.onlineFetch ? new modules.onlineFetch.OnlineFetchModule() : null);

        // 标签切换处理
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

                btn.classList.add('active');
                const tabContent = document.getElementById(btn.dataset.tab);
                if (tabContent) {
                    tabContent.classList.add('active');
                }

                // 加载对应内容
                if (btn.dataset.tab === 'history' && SSQApp.getModule('history')) {
                    SSQApp.getModule('history').loadHistory();
                }
                if (btn.dataset.tab === 'analysis' && SSQApp.getModule('analysis')) {
                    SSQApp.getModule('analysis').loadAnalysis();
                }
                if (btn.dataset.tab === 'my-numbers' && SSQApp.getModule('myNumbers')) {
                    SSQApp.getModule('myNumbers').loadMyNumbers();
                }
            });
        });

        // 更新加载状态
        if (loadingEl) {
            loadingEl.innerHTML = '<p style="color: #4CAF50;">✓ 平台已就绪</p>';
            setTimeout(() => loadingEl.style.display = 'none', 1000);
        }

        // 隐藏 Pyodide splash
        if (typeof window.__HIDE_SPLASH__ === 'function') {
            window.__HIDE_SPLASH__();
        }

        console.log('%c 双色球预测平台初始化完成', 'color: #4CAF50; font-weight: bold;');
        
        // 触发初始化完成事件
        window.dispatchEvent(new CustomEvent('appInitialized'));
        
    } catch (error) {
        console.error('%c 初始化失败:', 'color: #f44336; font-weight: bold;', error);
        
        if (loadingEl) {
            loadingEl.innerHTML = `<p style="color: #f44336;">✗ 加载失败：${error.message}</p>
                <p style="color: #666; font-size: 12px;">请尝试：<br>1. 按 Ctrl+F5 强制刷新<br>2. 清除浏览器缓存</p>`;
        }
        
        // 非致命错误不弹窗，只在控制台显示
        if (error.message.includes('缺少必需模块')) {
            alert(`关键模块加载失败：${error.message}\n\n请清除浏览器缓存后刷新页面 (Ctrl+F5)`);
        }
    }
}

// DOM 加载完成后初始化
document.addEventListener('DOMContentLoaded', initApp);
