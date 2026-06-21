/**
 * 号码检查模块
 * 处理号码分析功能
 */
import { checkNumbers, getMyNumbers, autoCheckMyNumbers } from './api.js';

export class CheckModule {
    constructor() {
        this.init();
    }

    init() {
        // 绑定分析按钮
        const checkBtn = document.querySelector('[data-action="checkNumbers"]');
        if (checkBtn) {
            checkBtn.addEventListener('click', () => this.analyzeNumbers());
        }

        // 绑定自动检查收藏号码按钮
        const autoCheckBtn = document.querySelector('[data-action="autoCheckMyNumbers"]');
        if (autoCheckBtn) {
            autoCheckBtn.addEventListener('click', () => this.autoCheckMyNumbers());
        }
    }

    async analyzeNumbers() {
        const redInput = document.getElementById('check-red');
        const blueInput = document.getElementById('check-blue');

        if (!redInput || !blueInput) return;

        const redValue = redInput.value.trim();
        const blueValue = blueInput.value.trim();

        if (!redValue || !blueValue) {
            alert('请输入红球和蓝球号码');
            return;
        }

        const redBalls = redValue.split(/\s+/).map(n => parseInt(n)).filter(n => !isNaN(n));

        if (redBalls.length !== 6) {
            alert('红球必须是 6 个数字，用空格分隔');
            return;
        }

        const blueBall = parseInt(blueValue);
        if (isNaN(blueBall) || blueBall < 1 || blueBall > 16) {
            alert('蓝球必须是 1-16 之间的数字');
            return;
        }

        const resultsDiv = document.getElementById('check-results');
        if (!resultsDiv) return;

        resultsDiv.innerHTML = '<div class="loading">正在分析号码</div>';

        try {
            const data = await checkNumbers(redBalls, blueBall);

            if (data.success) {
                this.displayResults(data);
            } else {
                resultsDiv.innerHTML = `<div class="card"><p style="color: #e94560;">${data.message}</p></div>`;
            }
        } catch (error) {
            resultsDiv.innerHTML = `<div class="card"><p style="color: #e94560;">请求失败：${error.message}</p></div>`;
        }
    }

    async autoCheckMyNumbers() {
        const resultsDiv = document.getElementById('check-results');
        if (!resultsDiv) return;

        resultsDiv.innerHTML = '<div class="loading">正在检查收藏号码</div>';

        try {
            // 先获取收藏号码
            const myNumbersData = await getMyNumbers();
            if (!myNumbersData.success || !myNumbersData.numbers || myNumbersData.numbers.length === 0) {
                resultsDiv.innerHTML = `
                    <div class="check-result-card">
                        <h4>自动检查收藏号码</h4>
                        <p style="color: #666;">您还没有收藏号码，请先收藏一些号码后再来检查。</p>
                    </div>
                `;
                return;
            }

            // 调用自动检查 API
            const checkData = await autoCheckMyNumbers(myNumbersData.numbers);

            if (checkData.success) {
                // 将收藏号码添加到返回数据中
                checkData.my_numbers = myNumbersData.numbers;
                this.displayAutoCheckResults(checkData);
            } else {
                resultsDiv.innerHTML = `<div class="card"><p style="color: #e94560;">${checkData.message}</p></div>`;
            }
        } catch (error) {
            resultsDiv.innerHTML = `<div class="card"><p style="color: #e94560;">请求失败：${error.message}</p></div>`;
        }
    }

    displayAutoCheckResults(data) {
        const resultsDiv = document.getElementById('check-results');
        if (!resultsDiv) return;

        const winners = data.winners || [];
        const totalChecked = data.total_checked || 0;
        const latestNumbers = data.latest_numbers || { red_balls: [], blue_ball: 0 };

        let html = `
            <div class="check-result-card">
                <div class="auto-check-header">
                    <h4>📊 检查结果</h4>
                    <div class="auto-check-stats">
                        <p>共检查 <strong>${totalChecked}</strong> 注</p>
                        <p>中奖 <strong class="${winners.length > 0 ? 'text-success' : ''}">${winners.length}</strong> 注</p>
                    </div>
                </div>

                <!-- 本期中奖号码 -->
                <div class="latest-numbers-card">
                    <div class="latest-numbers-header">
                        <p>🎯 本期中奖号码</p>
                        <p>期号：<strong>${data.latest_issue}</strong>（${data.latest_date}）</p>
                    </div>
                    <div class="latest-numbers-balls">
                        ${latestNumbers.red_balls.map(b => `<span class="ball ball-red">${b}</span>`).join('')}
                        <span class="ball ball-blue">${latestNumbers.blue_ball}</span>
                    </div>
                </div>

                <!-- 收藏号码列表 -->
                <div class="my-numbers-section">
                    <p class="section-title">📋 收藏号码</p>
                    <div class="my-numbers-list">
                        ${data.my_numbers ? data.my_numbers.map((num, idx) => `
                            <div class="my-number-item">
                                <span class="number-index">${idx + 1}</span>
                                <div class="number-balls">
                                    ${num.red_balls.map(b => `<span class="ball ball-red ball-small">${b}</span>`).join('')}
                                    <span class="ball ball-blue ball-small">${num.blue_ball}</span>
                                </div>
                            </div>
                        `).join('') : ''}
                    </div>
                </div>

                <!-- 中奖详情 -->
                <div class="winners-section">
                    ${winners.length > 0 ? `
                        <p class="section-title">中奖详情</p>
                        <div class="winners-list">
                            ${winners.map((winner, index) => `
                                <div class="winner-card">
                                    <div class="winner-header">
                                        <span class="winner-prize">${winner.prize_level}</span>
                                        <span class="winner-index">NO.${index + 1}</span>
                                    </div>
                                    <div class="winner-details">
                                        <span class="winner-badge">红球：${winner.red_match}个</span>
                                        <span class="winner-badge">蓝球：${winner.blue_match ? '中' : '未中'}</span>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    ` : `
                        <p class="no-winners-message">本期买到开心快乐幸福永相伴，下一期再接再厉吖😜</p>
                    `}
                </div>

                <!-- 提示信息 -->
                <div class="thank-you-card">
                    <p>🌟 发扬社会主义人道主义精神，衷心感谢您为社会福利事业做出的贡献！</p>
                </div>
            </div>
        `;

        resultsDiv.innerHTML = html;
    }

    displayResults(data) {
        const resultsDiv = document.getElementById('check-results');
        if (!resultsDiv) return;

        let html = `
            <div class="check-result-card">
                <h4>您的号码</h4>
                <div class="balls-display-container">
                    ${data.your_numbers.red_balls.map(b => `<span class="red-ball">${b}</span>`).join('')}
                    <span class="blue-ball">${data.your_numbers.blue_ball}</span>
                </div>
        `;

        if (data.best_matches && data.best_matches.length > 0) {
            html += `
                <div style="margin-top: 24px; padding-top: 20px; border-top: 2px solid var(--border-light);">
                    <h4 style="font-size: 1rem; margin-bottom: 16px;">历史匹配记录（最多 10 条）</h4>
                    ${data.best_matches.map(match => `
                        <div class="history-match-record">
                            <div class="record-info">
                                <span class="record-issue">期号 ${match.issue}</span>
                                <span class="record-date">${match.date || '-'}</span>
                                <div style="display: flex; gap: 4px; margin-top: 6px;">
                                    ${(match.historical_numbers?.red_balls || []).map(b => `<span class="ball" style="width: 26px; height: 26px; background: linear-gradient(135deg, #ef4444, #f87171); color: white; font-size: 10px; font-weight: bold; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%;">${b}</span>`).join('')}
                                    <span class="ball" style="width: 26px; height: 26px; background: linear-gradient(135deg, #3b82f6, #60a5fa); color: white; font-size: 10px; font-weight: bold; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%;">${match.historical_numbers?.blue_ball || '-'}</span>
                                </div>
                            </div>
                            <div class="record-match">
                                <span class="match-badge">红球：${match.red_match}个</span>
                                <span class="match-badge">蓝球：${match.blue_match ? '中' : '未中'}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        } else {
            html += `
                <div style="margin-top: 20px; padding-top: 16px; border-top: 2px solid var(--border-light);">
                    <p style="color: #666;">在历史 ${data.total_checked} 期数据中，没有找到匹配 3 个红球以上或蓝球匹配的记录。</p>
                    <p style="color: #888; margin-top: 8px;">这说明您的号码组合比较独特！</p>
                </div>
            `;
        }

        html += `</div>`;
        resultsDiv.innerHTML = html;
    }
}
