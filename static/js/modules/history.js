/**
 * 历史数据模块
 * 处理历史开奖数据展示和分页
 */
import { getHistory } from './api.js';
import { cacheHistoryData, getCachedHistory } from './utils.js';

export class HistoryModule {
    constructor() {
        this.allData = [];
        this.currentPage = 1;
        this.pageSize = 50;
        this.total = 0;
        this.init();
    }

    init() {
        // 绑定刷新按钮
        const refreshBtn = document.querySelector('[data-action="loadHistory"]');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadHistory());
        }
    }

    async loadHistory(page = 1) {
        const tbody = document.getElementById('history-body');
        if (!tbody) return;

        // 如果还没有加载过数据，则从服务器加载
        if (this.allData.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="loading">正在加载历史数据</td></tr>';
            try {
                // 一次性加载所有数据用于本地分页（上限2000条）
                const data = await getHistory(1, 2000);

                if (data.data && data.data.length > 0) {
                    cacheHistoryData(data.data);
                    this.allData = data.data;
                    this.total = data.data.length;
                } else {
                    tbody.innerHTML = '<tr><td colspan="4">暂无历史数据，请先更新数据</td></tr>';
                    return;
                }
            } catch (error) {
                // 如果服务器加载失败，尝试使用缓存
                const cachedData = getCachedHistory();
                if (cachedData && cachedData.length > 0) {
                    this.allData = cachedData;
                    this.total = cachedData.length;
                } else {
                    tbody.innerHTML = `<tr><td colspan="4" style="color: #e94560;">加载失败：${error.message}</td></tr>`;
                    return;
                }
            }
        }

        // 使用本地数据进行分页渲染
        this.renderHistoryTable(this.allData, page);
    }

    renderHistoryTable(allData, page = 1) {
        const tbody = document.getElementById('history-body');
        if (!tbody) return;

        const totalPages = Math.ceil(allData.length / this.pageSize);
        const start = (page - 1) * this.pageSize;
        const end = start + this.pageSize;
        const pageData = allData.slice(start, end);

        if (pageData.length > 0) {
            let html = pageData.map(record => `
                <tr>
                    <td>${record.issue || '-'}</td>
                    <td>${record.date || '-'}</td>
                    <td>
                        <div class="red-balls-display">
                            ${record.red_balls.map(b => `<span class="ball">${b}</span>`).join('')}
                        </div>
                    </td>
                    <td>
                        <div class="blue-ball-display">
                            <span class="ball">${record.blue_ball}</span>
                        </div>
                    </td>
                </tr>
            `).join('');

            // 添加分页控制
            html += `<tr id="pagination-row">
                <td colspan="4" style="padding: 16px; text-align: center;">
                    <div style="display: flex; justify-content: center; align-items: center; gap: 12px;">
                        <button class="btn-secondary" ${page === 1 ? 'disabled style="opacity:0.5"' : ''}
                            data-page="${page - 1}">上一页</button>
                        <span style="color: #666;">第 ${page} 页 / 共 ${totalPages} 页（共 ${allData.length} 条记录）</span>
                        <button class="btn-secondary" ${page >= totalPages ? 'disabled style="opacity:0.5"' : ''}
                            data-page="${page + 1}">下一页</button>
                        <input type="number" id="jump-page" min="1" max="${totalPages}" value="${page}"
                            style="width: 60px; padding: 6px; border: 1px solid #ddd; border-radius: 4px; text-align: center;">
                        <button class="btn-secondary" id="jump-btn">跳转</button>
                    </div>
                </td>
            </tr>`;

            tbody.innerHTML = html;

            // 绑定分页事件
            tbody.querySelectorAll('button[data-page]').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const targetPage = parseInt(e.currentTarget.dataset.page);
                    if (targetPage >= 1 && targetPage <= totalPages) {
                        this.loadHistory(targetPage);
                    }
                });
            });

            const jumpBtn = document.getElementById('jump-btn');
            const jumpPage = document.getElementById('jump-page');
            if (jumpBtn && jumpPage) {
                jumpBtn.addEventListener('click', () => {
                    const page = parseInt(jumpPage.value);
                    if (page >= 1 && page <= totalPages) {
                        this.loadHistory(page);
                    } else {
                        alert(`请输入 1-${totalPages} 之间的页码`);
                    }
                });
            }
        } else {
            tbody.innerHTML = '<tr><td colspan="4">暂无历史数据</td></tr>';
        }
    }
}
