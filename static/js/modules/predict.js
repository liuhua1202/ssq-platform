/**
 * 预测模块
 * 处理号码预测相关功能
 */
import { predict } from './api.js';
import { STORAGE_KEYS, getFromStorage, saveToStorage } from './utils.js';

export class PredictModule {
    constructor() {
        this.algorithm = 'comprehensive';
        this.generations = 5;
        this.init();
    }

    init() {
        // 绑定算法选择器
        const algorithmSelect = document.getElementById('algorithm');
        if (algorithmSelect) {
            algorithmSelect.addEventListener('change', (e) => {
                this.algorithm = e.target.value;
            });
        }

        // 绑定期数输入
        const generationsInput = document.getElementById('generations');
        if (generationsInput) {
            generationsInput.addEventListener('input', (e) => {
                this.generations = parseInt(e.target.value) || 5;
            });
        }

        // 绑定生成按钮
        const generateBtn = document.querySelector('[data-action="generatePrediction"]');
        if (generateBtn) {
            generateBtn.addEventListener('click', () => this.generatePrediction());
        }
    }

    async generatePrediction() {
        const resultsDiv = document.getElementById('prediction-results');
        if (!resultsDiv) return;

        resultsDiv.innerHTML = '<div class="loading">正在生成预测号码</div>';

        try {
            // 先从服务器同步收藏号码数据
            await this.syncMyNumbersFromServer();

            const data = await predict(this.algorithm, this.generations);

            if (data.success) {
                this.displayPredictions(data.predictions, data.algorithm);
            } else {
                resultsDiv.innerHTML = `<div class="card"><p style="color: #e94560;">${data.message}</p></div>`;
            }
        } catch (error) {
            resultsDiv.innerHTML = `<div class="card"><p style="color: #e94560;">请求失败：${error.message}</p></div>`;
        }
    }

    displayPredictions(predictions, algorithm) {
        const resultsDiv = document.getElementById('prediction-results');
        if (!resultsDiv) return;

        if (!predictions || predictions.length === 0) {
            resultsDiv.innerHTML = '<div class="card"><p>暂无预测结果</p></div>';
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
                        <th>和值</th>
                        <th>奇偶比</th>
                        <th>AC 指数</th>
                        <th>算法</th>
                        <th>备注</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody id="prediction-body"></tbody>
            </table>
        `;

        const tbody = document.getElementById('prediction-body');
        tbody.innerHTML = predictions.map((pred, index) => {
            const algoName = algorithmNames[pred.algorithm] || pred.algorithm;

            let remark = [];
            if (pred.fitness) remark.push(`评分:${pred.fitness.toFixed(1)}`);
            if (pred.target_sum) remark.push(`目标和:${pred.target_sum}`);
            if (pred.recommendation_basis) remark.push('基于遗漏值分析');
            if (pred.zone_ratio) remark.push(`区间比${pred.zone_ratio}`);
            if (pred.consecutive !== undefined) remark.push(`${pred.consecutive ? '含' : '无'}连号`);
            if (pred.tail_info) remark.push(`同尾数:${pred.tail_info.length}组`);
            if (pred.prime_count !== undefined) remark.push(`质:${pred.prime_count}合:${pred.composite_count}`);
            if (pred.size_ratio) remark.push(`大中小:${pred.size_ratio}`);
            if (pred.remark) remark.push(pred.remark);

            const remarkStr = remark.join(' | ') || '-';
            const numberKey = `${pred.red_balls.join(',')}-${pred.blue_ball}`;
            const isSaved = this.isNumberSaved(numberKey);

            return `
                <tr>
                    <td>${index + 1}</td>
                    <td>
                        <div class="red-balls-display">
                            ${pred.red_balls.map(b => `<span class="ball">${b}</span>`).join('')}
                        </div>
                    </td>
                    <td>
                        <div class="blue-ball-display">
                            <span class="ball">${pred.blue_ball}</span>
                        </div>
                    </td>
                    <td>${pred.sum}</td>
                    <td>${pred.odd_even}</td>
                    <td>${pred.ac_index}</td>
                    <td><span class="algo-badge">${algoName}</span></td>
                    <td class="remark">${remarkStr}</td>
                    <td>
                        <button class="btn-save" data-saved="${isSaved}"
                            data-key="${numberKey}" data-blue="${pred.blue_ball}"
                            data-reds="${pred.red_balls.join(',')}"
                            data-algorithm="${pred.algorithm}" data-remark="${remarkStr}">
                            ${isSaved ? '已收藏' : '收藏'}
                        </button>
                    </td>
                </tr>
            `;
        }).join('');

        // 绑定收藏按钮事件
        tbody.querySelectorAll('.btn-save').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const target = e.currentTarget;
                this.toggleSaveNumber(
                    target.dataset.key,
                    parseInt(target.dataset.blue),
                    target.dataset.reds,
                    target,
                    target.dataset.algorithm,
                    target.dataset.remark
                );
            });
        });
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

    isNumberSaved(numberKey) {
        const myNumbers = this.getMyNumbers();
        return myNumbers.some(n => n.key === numberKey);
    }

    getMyNumbers() {
        // 优先从 localStorage 读取（快速）
        const localData = getFromStorage(STORAGE_KEYS.MY_NUMBERS);
        if (localData) {
            return localData;
        }
        return [];
    }

    async syncMyNumbersFromServer() {
        // 从服务器同步数据到本地
        try {
            const { getMyNumbers } = await import('./api.js');
            const data = await getMyNumbers();
            if (data.success && data.numbers) {
                saveToStorage(STORAGE_KEYS.MY_NUMBERS, data.numbers);
                return data.numbers;
            }
        } catch (e) {
            console.log('从服务器同步失败:', e);
        }
        return this.getMyNumbers();
    }

    async toggleSaveNumber(key, blueBall, redBallsStr, button, algorithm = null, remark = null) {
        const redBalls = redBallsStr.split(',').map(n => parseInt(n));
        const myNumbers = this.getMyNumbers();
        const existingIndex = myNumbers.findIndex(n => n.key === key);

        if (existingIndex >= 0) {
            myNumbers.splice(existingIndex, 1);
        } else {
            myNumbers.push({
                key: key,
                red_balls: redBalls,
                blue_ball: blueBall,
                algorithm: algorithm,
                remark: remark,
                saved_at: new Date().toISOString()
            });
        }

        saveToStorage(STORAGE_KEYS.MY_NUMBERS, myNumbers);

        // 同步保存到服务器（必须成功）
        try {
            const { saveMyNumbers } = await import('./api.js');
            const result = await saveMyNumbers(myNumbers);
            if (!result.success) {
                console.error('服务器保存失败:', result.message);
            }
        } catch (e) {
            console.error('保存到服务器异常:', e);
        }

        // 更新按钮状态
        if (button) {
            const isSaved = existingIndex < 0;
            button.textContent = isSaved ? '已收藏' : '收藏';
            button.setAttribute('data-saved', isSaved);
        }
    }
}
