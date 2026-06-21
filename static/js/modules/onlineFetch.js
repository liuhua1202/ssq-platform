/**
 * 在线获取开奖信息模块
 * 从福彩网获取开奖信息
 */
import { fetchLatestLottery, fetchHistoryLottery } from './api.js';

export class OnlineFetchModule {
    constructor() {
        // 绑定获取最新一期按钮
        const fetchBtn = document.querySelector('[data-action="fetchLatestLottery"]');
        if (fetchBtn) {
            fetchBtn.addEventListener('click', () => this.fetchLatest());
        }

        // 绑定获取所有历史数据按钮
        const fetchAllBtn = document.querySelector('[data-action="fetchAllHistory"]');
        if (fetchAllBtn) {
            fetchAllBtn.addEventListener('click', () => this.fetchAllHistory());
        }
    }

    /**
     * 获取最新一期开奖信息
     */
    async fetchLatest() {
        const btn = document.querySelector('[data-action="fetchLatestLottery"]');
        if (!btn) return;

        const originalText = btn.textContent;
        btn.disabled = true;
        btn.textContent = '🔔 获取中...';

        try {
            const data = await fetchLatestLottery();

            if (data.success) {
                const result = data.data;
                // 将新获取的开奖信息导入到历史数据中
                if (window.historyModule) {
                    await window.historyModule.loadHistory();
                }
                alert(`✅ 获取成功！\n\n期号：${result.issue}\n开奖日期：${result.date}\n红球：${result.red_balls.join(', ')}\n蓝球：${result.blue_ball}`);
            } else {
                alert(`⚠️ 获取失败：${data.message}`);
            }
        } catch (error) {
            console.error('获取开奖信息失败:', error);
            alert(`❌ 请求失败：${error.message}`);
        } finally {
            // 确保按钮状态恢复
            setTimeout(() => {
                btn.disabled = false;
                btn.textContent = originalText;
            }, 100);
        }
    }

    /**
     * 获取所有历史数据
     * 直接从数据源获取可用的历史数据，无需用户确认
     */
    async fetchAllHistory() {
        const btn = document.querySelector('[data-action="fetchAllHistory"]');
        if (!btn) return;

        const originalText = btn.textContent;
        btn.disabled = true;
        btn.textContent = '📥 获取中...';

        // 显示进度提示
        const progressMsg = document.createElement('div');
        progressMsg.style.cssText = 'position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); z-index: 9999;';
        progressMsg.innerHTML = '<p style="margin: 0; font-size: 16px;">正在从 500彩票网获取历史数据...</p><p style="margin: 10px 0 0 0; color: #666; font-size: 14px;">请稍候...</p>';
        document.body.appendChild(progressMsg);

        try {
            // 直接调用获取接口（后端会自动获取足够的数据）
            const data = await fetchHistoryLottery(1);

            if (data.success) {
                // 刷新历史数据
                if (window.historyModule) {
                    await window.historyModule.loadHistory();
                }
                alert(`✅ 获取成功！\n\n共获取 ${data.total || data.new_count || '未知'} 条历史记录`);
            } else {
                alert(`⚠️ 获取失败：${data.message}`);
            }
        } catch (error) {
            console.error('获取历史数据失败:', error);
            alert(`❌ 请求失败：${error.message}\n\n建议：\n1. 检查网络连接\n2. 稍后再试`);
        } finally {
            // 移除进度提示
            if (progressMsg && progressMsg.parentNode) {
                progressMsg.parentNode.removeChild(progressMsg);
            }
            
            // 确保按钮状态恢复
            setTimeout(() => {
                btn.disabled = false;
                btn.textContent = originalText;
            }, 100);
        }
    }
}
