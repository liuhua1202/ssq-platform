/**
 * 数据管理模块
 * 处理数据导入、备份、恢复等功能
 */
import { createBackup, getBackups, restoreBackup, clearData, importData as apiImportData, importTextData, deleteBackup } from './api.js';

export class DataManagerModule {
    constructor() {
        this.init();
        // 页面加载时自动加载备份列表
        this.loadBackups();
    }

    init() {
        // 绑定创建备份按钮
        const backupBtn = document.querySelector('[data-action="createBackup"]');
        if (backupBtn) {
            backupBtn.addEventListener('click', () => this.createBackup());
        }

        // 绑定刷新备份按钮
        const refreshBtn = document.querySelector('[data-action="loadBackups"]');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadBackups());
        }

        // 绑定清空数据按钮
        const clearBtn = document.querySelector('[data-action="clearAllData"]');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearAllData());
        }

        // 绑定导入按钮
        const importBtn = document.querySelector('[data-action="importData"]');
        if (importBtn) {
            importBtn.addEventListener('click', () => this.importData());
        }

        // 绑定粘贴导入按钮
        const importTextBtn = document.querySelector('[data-action="importTextData"]');
        if (importTextBtn) {
            importTextBtn.addEventListener('click', () => this.importTextData());
        }

        // 绑定清空导入文本按钮
        const clearImportBtn = document.querySelector('[data-action="clearImportText"]');
        if (clearImportBtn) {
            clearImportBtn.addEventListener('click', () => {
                const textarea = document.getElementById('import-text');
                if (textarea) {
                    textarea.value = '';
                    textarea.focus();
                }
            });
        }
    }

    async createBackup() {
        try {
            await createBackup();
            this.loadBackups();
        } catch (error) {
            alert(`请求失败：${error.message}`);
        }
    }

    async loadBackups() {
        const backupsList = document.getElementById('backups-list');
        if (!backupsList) {
            console.error('backups-list 元素不存在');
            return;
        }

        // 显示加载状态
        backupsList.innerHTML = '<p style="color: #999; text-align: center; padding: 40px;">正在加载备份列表</p>';

        try {
            const data = await getBackups();

            if (data.success && data.backups && data.backups.length > 0) {
                backupsList.innerHTML = `
                    <table class="history-table">
                        <thead>
                            <tr>
                                <th>文件名</th>
                                <th>大小</th>
                                <th>创建时间</th>
                                <th>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.backups.map(backup => `
                                <tr>
                                    <td>${backup.filename}</td>
                                    <td>${(backup.size / 1024).toFixed(1)} KB</td>
                                    <td>${backup.created}</td>
                                    <td>
                                        <button class="btn-save" data-filename="${backup.filename}" style="margin-right: 8px;">恢复</button>
                                        <button class="btn-delete" data-filename="${backup.filename}" style="background: #ffebee; color: #c62828; border-color: #ffcdd2;">删除</button>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;

                // 绑定恢复按钮事件
                backupsList.querySelectorAll('.btn-save').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        const target = e.currentTarget;
                        this.restoreBackup(target.dataset.filename);
                    });
                });

                // 绑定删除按钮事件
                backupsList.querySelectorAll('.btn-delete').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        const target = e.currentTarget;
                        this.deleteBackup(target.dataset.filename);
                    });
                });
            } else {
                // 无备份文件
                backupsList.innerHTML = '<p style="color: #999; text-align: center; padding: 40px;">暂无备份文件</p>';
            }
        } catch (error) {
            // 出错时显示错误信息
            console.error('加载备份失败:', error);
            backupsList.innerHTML = `<p style="color: #e94560; text-align: center; padding: 40px;">加载失败：${error.message}</p>`;
        }
    }

    async restoreBackup(filename) {
        if (!confirm(`确定要从备份文件 "${filename}" 恢复数据吗？\n\n当前数据将被备份。`)) return;

        try {
            await restoreBackup(filename);
            this.loadBackups();
            // 刷新历史数据
            if (window.loadHistory) {
                window.loadHistory();
            }
        } catch (error) {
            alert(`请求失败：${error.message}`);
        }
    }

    async deleteBackup(filename) {
        if (!confirm(`确定要删除备份文件 "${filename}" 吗？\n\n此操作不可撤销。`)) return;

        try {
            await deleteBackup(filename);
            this.loadBackups();
        } catch (error) {
            alert(`请求失败：${error.message}`);
        }
    }

    async clearAllData() {
        // 首先检查是否有备份
        let hasBackup = false;
        try {
            const data = await getBackups();
            if (data.success && data.backups && data.backups.length > 0) {
                hasBackup = true;
            }
        } catch (e) {
            console.log('检查备份失败:', e);
        }

        let confirmMsg = '确定要清空所有历史数据吗？\n\n此操作不可撤销，清空后：\n';
        confirmMsg += '• 所有开奖记录将被删除\n';
        confirmMsg += '• 预测和分析功能将无法使用\n';
        confirmMsg += '• 需要从备份恢复或重新导入数据\n\n';

        if (!hasBackup) {
            confirmMsg += '⚠️ 警告：当前没有备份文件，建议先创建备份！\n\n';
        }

        confirmMsg += '点击"确定"继续，或点击"取消"返回。';

        if (!confirm(confirmMsg)) return;

        try {
            await clearData();
            // 清除浏览器缓存
            localStorage.removeItem('ssq_history_cache');
            localStorage.removeItem('ssq_history_cache_time');
            // 刷新历史数据页面
            if (window.loadHistory) {
                window.loadHistory();
            }
        } catch (error) {
            alert(`请求失败：${error.message}`);
        }
    }

    async importData() {
        const fileInput = document.getElementById('import-file');
        if (!fileInput) {
            console.error('import-file 元素不存在');
            alert('导入功能初始化失败，请刷新页面重试');
            return;
        }

        if (!fileInput.files || fileInput.files.length === 0) {
            alert('请选择要导入的文件');
            return;
        }

        const file = fileInput.files[0];
        console.log('准备导入文件:', file.name, '大小:', file.size, 'bytes');

        const formData = new FormData();
        formData.append('file', file);

        try {
            console.log('开始发送导入请求...');
            const result = await apiImportData(formData);
            console.log('导入请求成功:', result);
            
            fileInput.value = '';
            
            if (result.success) {
                alert(`✅ 导入成功！\n\n新增 ${result.new_records_count || 0} 条记录\n总计 ${result.total_records || 0} 条记录`);
                // 刷新历史数据
                if (window.loadHistory) {
                    window.loadHistory();
                }
            } else {
                alert(`❌ 导入失败：${result.message}`);
            }
        } catch (error) {
            console.error('导入请求失败:', error);
            alert(`❌ 请求失败：${error.message}\n\n请检查文件格式或控制台日志`);
        }
    }

    async importTextData() {
        const textInput = document.getElementById('import-text');
        if (!textInput) return;

        const textData = textInput.value.trim();

        if (!textData) {
            alert('请输入要导入的数据');
            return;
        }

        // 计算行数
        const lines = textData.split('\n').filter(line => {
            const trimmed = line.trim();
            return trimmed && !trimmed.includes('期号') && !trimmed.includes('注数');
        });

        if (lines.length === 0) {
            alert('未找到有效数据');
            return;
        }

        if (!confirm(`确定要导入 ${lines.length} 条记录吗？\n\n导入后相同期号的数据将被覆盖。`)) {
            return;
        }

        try {
            await importTextData(textData);
            textInput.value = '';
            if (window.loadHistory) {
                window.loadHistory();
            }
        } catch (error) {
            alert(`请求失败：${error.message}`);
        }
    }

    goToImport() {
        // 切换到数据管理标签页
        const guideTab = document.querySelector('[data-tab="guide"]');
        if (guideTab) {
            guideTab.click();
        }
    }
}
