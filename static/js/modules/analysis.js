/**
 * 数据分析模块
 * 处理数据统计分析展示
 */
import { getStatistics } from './api.js';

export class AnalysisModule {
    constructor() {
        this.init();
    }

    init() {
        // 绑定刷新按钮
        const refreshBtn = document.querySelector('[data-action="loadAnalysis"]');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadAnalysis());
        }
    }

    async loadAnalysis() {
        const resultsDiv = document.getElementById('analysis-results');
        if (!resultsDiv) return;

        // 显示加载状态
        const hotNumbersEl = document.getElementById('hot-numbers');
        if (hotNumbersEl) {
            hotNumbersEl.innerHTML = '<span class="loading">加载中</span>';
        }

        try {
            const data = await getStatistics();

            if (data.hot_numbers) {
                this.renderHotNumbers(data.hot_numbers);
                this.renderColdNumbers(data.cold_numbers);
                this.renderMissingStats(data.missing_stats);
                this.renderBlueAnalysis(data.blue_ball);
            }

            if (data.odd_even) {
                this.renderOddEvenChart(data.odd_even);
            }

            if (data.sum_analysis) {
                this.renderSumChart(data.sum_analysis);
            }

        } catch (error) {
            console.error('[analysis] full error:', error);
            resultsDiv.innerHTML = `<div style="color: #e94560; padding: 12px; background: #fef2f2; border-radius: 6px;">
                    <p><b>加载失败：</b>${error.message}</p>
                    <p><b>错误名：</b>${error.name}</p>
                    <pre style="font-size: 11px; background: #fff; padding: 8px; overflow: auto; max-height: 200px;">${(error.stack || '(no stack)').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
                </div>`;
        }
    }

    renderHotNumbers(hot) {
        const el = document.getElementById('hot-numbers');
        if (!el) return;

        el.innerHTML = (hot.overall || []).map(n => `<span class="ball hot">${n}</span>`).join('');
    }

    renderColdNumbers(cold) {
        const el = document.getElementById('cold-numbers');
        if (!el) return;

        el.innerHTML = (cold.numbers || []).map(n => `<span class="ball cold">${n}</span>`).join('');
    }

    renderMissingStats(missingStats) {
        const el = document.getElementById('missing-stats');
        if (!el || !missingStats) return;

        const missingEntries = Object.entries(missingStats)
            .sort((a, b) => b[1].current_missing - a[1].current_missing)
            .slice(0, 10);

        el.innerHTML = missingEntries
            .map(([num, stats]) =>
                `<span class="ball missing" title="遗漏${stats.current_missing}期">${num}</span>`
            ).join('');
    }

    renderBlueAnalysis(blue) {
        const el = document.getElementById('blue-analysis');
        if (!el || !blue) return;

        el.innerHTML = `
            <div class="blue-analysis-section">
                <strong>热号:</strong>
                ${(blue.hot_numbers || []).map(n => `<span class="ball hot">${n}</span>`).join('')}
            </div>
            <div class="blue-analysis-section">
                <strong>冷号:</strong>
                ${(blue.cold_numbers || []).map(n => `<span class="ball cold">${n}</span>`).join('')}
            </div>
            <div class="blue-analysis-ratio">
                奇偶比：${blue.odd_even?.ratio || '-'} |
                大小比：${blue.big_small?.ratio || '-'}
            </div>
        `;
    }

    renderOddEvenChart(oddEven) {
        const el = document.getElementById('odd-even-chart');
        if (!el || !oddEven.distribution) return;

        el.innerHTML = `
            <div class="numbers-display odd-even-grid">
                ${Object.entries(oddEven.distribution).map(([ratio, info]) => `
                    <div class="ratio-card">
                        <strong>${ratio}</strong>
                        <div class="ratio-info">
                            ${info.count}次 (${info.percentage.toFixed(1)}%)
                        </div>
                    </div>
                `).join('')}
            </div>
            <div class="ratio-summary">
                最常见奇偶比：${oddEven.most_common || '-'}
            </div>
        `;
    }

    renderSumChart(sumAnalysis) {
        const el = document.getElementById('sum-chart');
        if (!el || !sumAnalysis) return;

        el.innerHTML = `
            <div class="sum-stats-grid">
                <div class="sum-stat-card">
                    <div class="sum-stat-label">最小值</div>
                    <div class="sum-stat-value">${sumAnalysis.min || '-'}</div>
                </div>
                <div class="sum-stat-card">
                    <div class="sum-stat-label">最大值</div>
                    <div class="sum-stat-value">${sumAnalysis.max || '-'}</div>
                </div>
                <div class="sum-stat-card">
                    <div class="sum-stat-label">平均值</div>
                    <div class="sum-stat-value">${sumAnalysis.mean?.toFixed(1) || '-'}</div>
                </div>
                <div class="sum-stat-card">
                    <div class="sum-stat-label">最常见和值</div>
                    <div class="sum-stat-value">${sumAnalysis.most_common_sum?.[0] || '-'}</div>
                </div>
            </div>
        `;
    }
}
