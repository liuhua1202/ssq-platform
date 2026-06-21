/**
 * 收藏号码模块
 * 处理我的收藏号码功能
 */
import { getMyNumbers, saveMyNumbers } from './api.js';
import { STORAGE_KEYS, getFromStorage, saveToStorage } from './utils.js';

export class MyNumbersModule {
    constructor() {
        this.numbers = null;
        this.init();
    }

    init() {
        // 绑定清空按钮
        const clearBtn = document.querySelector('[data-action="clearMyNumbers"]');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearMyNumbers());
        }
    }

    async loadMyNumbers() {
        const resultsDiv = document.getElementById('my-numbers-results');
        if (!resultsDiv) return;

        // 优先从服务器加载
        let myNumbers = await this.loadFromServer();

        if (myNumbers.length === 0) {
            resultsDiv.innerHTML = `
                <div class="card" style="text-align: center; padding: 60px 20px;">
                    <p style="color: #999; font-size: 1.1rem;">暂无收藏号码</p>
                    <p style="color: #ccc; margin-top: 10px;">在"号码预测"页面点击"收藏"按钮保存您心仪的号码</p>
                </div>
            `;
            return;
        }

        const algorithmNames = this.getAlgorithmNames();

        resultsDiv.innerHTML = `
            <table class="prediction-table">
                <thead>
                    <tr>
                        <th>序号</th>
                        <th>红球</th>
                        <th>蓝球</th>
                        <th>算法</th>
                        <th>备注</th>
                        <th>保存时间</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody id="my-numbers-body"></tbody>
            </table>
        `;

        const tbody = document.getElementById('my-numbers-body');
        tbody.innerHTML = myNumbers.map((item, index) => {
            const algoName = item.algorithm ? (algorithmNames[item.algorithm] || item.algorithm) : '-';
            const remark = item.remark || '-';
            return `
                <tr>
                    <td>${index + 1}</td>
                    <td>
                        <div class="red-balls-display">
                            ${item.red_balls.map(b => `<span class="ball">${b}</span>`).join('')}
                        </div>
                    </td>
                    <td>
                        <div class="blue-ball-display">
                            <span class="ball">${item.blue_ball}</span>
                        </div>
                    </td>
                    <td><span class="algo-badge">${algoName}</span></td>
                    <td class="remark">${remark}</td>
                    <td>${this.formatDateTime(item.saved_at)}</td>
                    <td>
                        <button class="btn-delete" data-key="${item.key}">删除</button>
                    </td>
                </tr>
            `;
        }).join('');

        // 绑定删除按钮事件
        tbody.querySelectorAll('.btn-delete').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const target = e.currentTarget;
                this.deleteMyNumber(target.dataset.key);
            });
        });
    }

    async loadFromServer() {
        try {
            const data = await getMyNumbers();
            if (data.success && data.numbers) {
                // 更新内部缓存
                this.numbers = data.numbers;
                // 同步到 localStorage
                saveToStorage(STORAGE_KEYS.MY_NUMBERS, data.numbers);
                return data.numbers;
            }
        } catch (e) {
            console.log('从服务器加载失败，使用本地缓存:', e);
        }
        // 降级到本地缓存
        return this.getMyNumbers();
    }

    getMyNumbers() {
        // 如果已加载，直接返回
        if (this.numbers !== null) {
            return this.numbers;
        }

        // 降级到本地缓存
        return getFromStorage(STORAGE_KEYS.MY_NUMBERS) || [];
    }

    async deleteMyNumber(key) {
        if (!confirm('确定要删除这个号码吗？')) return;

        const myNumbers = this.getMyNumbers();
        const filtered = myNumbers.filter(n => n.key !== key);
        this.numbers = filtered;
        saveToStorage(STORAGE_KEYS.MY_NUMBERS, filtered);

        // 同步保存到服务器
        try {
            await saveMyNumbers(filtered);
        } catch (e) {
            console.log('保存到服务器失败:', e);
        }

        this.loadMyNumbers();
    }

    async clearMyNumbers() {
        if (!confirm('确定要清空所有收藏号码吗？此操作不可恢复。')) return;

        this.numbers = [];
        saveToStorage(STORAGE_KEYS.MY_NUMBERS, []);

        // 同步保存到服务器
        try {
            await saveMyNumbers([]);
        } catch (e) {
            console.log('保存到服务器失败:', e);
        }

        this.loadMyNumbers();
    }

    getAlgorithmNames() {
        return {
            'weighted_random': '加权随机',
            'normal_distribution': '正态分布',
            'genetic': '遗传算法',
            'genetic_algorithm': '遗传算法',
            'monte_carlo': '蒙特卡洛',
            'comprehensive': '综合推荐',
            'smart_recommendation': '智能推荐',
            'zone_distribution': '区间分布',
            'consecutive_analysis': '连号分析',
            'same_tail_analysis': '同尾号分析',
            'prime_composite': '质合数分析',
            'big_small_analysis': '大小号分析',
            'markov_chain': '马尔可夫链',
            'kmeans_clustering': 'K 均值聚类'
        };
    }

    formatDateTime(dateStr) {
        if (!dateStr) return '-';
        const date = new Date(dateStr);
        return date.toLocaleString('zh-CN');
    }
}
