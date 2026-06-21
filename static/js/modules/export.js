/**
 * 数据导出模块
 * 处理数据导出为 JSON、CSV、TXT 格式功能
 */
import { exportMyNumbers, exportHistory } from './api.js';

export class ExportModule {
    constructor() {
        // 绑定导出收藏号码按钮
        const exportNumbersBtn = document.querySelector('[data-action="exportMyNumbers"]');
        if (exportNumbersBtn) {
            exportNumbersBtn.addEventListener('click', () => this.exportMyNumbers());
        }

        // 绑定导出历史数据按钮
        const exportHistoryBtn = document.querySelector('[data-action="exportHistory"]');
        if (exportHistoryBtn) {
            exportHistoryBtn.addEventListener('click', () => this.exportHistory());
        }
    }

    /**
     * 获取当前选择的导出格式
     */
    getSelectedFormat() {
        const formatSelect = document.getElementById('export-format');
        return formatSelect ? formatSelect.value : 'json';
    }

    /**
     * 导出收藏号码
     * @param {string} format - 导出格式：json, csv, txt
     */
    async exportMyNumbers(format) {
        const selectedFormat = format || this.getSelectedFormat();

        try {
            const data = await exportMyNumbers(selectedFormat);

            if (data.success) {
                if (selectedFormat === 'json') {
                    this.downloadJSON(data.data, 'my_numbers.json');
                } else if (selectedFormat === 'csv') {
                    this.downloadContent(data.content, 'my_numbers.csv', 'text/csv');
                } else if (selectedFormat === 'txt') {
                    this.downloadContent(data.content, 'my_numbers.txt', 'text/plain');
                }
            } else {
                alert('导出失败：' + (data.message || '未知错误'));
            }
        } catch (error) {
            alert('导出失败：' + error.message);
        }
    }

    /**
     * 导出历史数据
     * @param {string} format - 导出格式：json, csv, txt
     */
    async exportHistory(format) {
        const selectedFormat = format || this.getSelectedFormat();

        try {
            const data = await exportHistory(selectedFormat);

            if (data.success) {
                if (selectedFormat === 'json') {
                    this.downloadJSON(data.data, 'history_data.json');
                } else if (selectedFormat === 'csv') {
                    this.downloadContent(data.content, 'history_data.csv', 'text/csv');
                } else if (selectedFormat === 'txt') {
                    this.downloadContent(data.content, 'history_data.txt', 'text/plain');
                }
            } else {
                alert('导出失败：' + (data.message || '未知错误'));
            }
        } catch (error) {
            alert('导出失败：' + error.message);
        }
    }

    /**
     * 下载 JSON 文件
     */
    downloadJSON(data, filename) {
        if (!data || data.length === 0) {
            alert('没有数据可导出');
            return;
        }
        const json = JSON.stringify(data, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        this.downloadBlob(blob, filename);
    }

    /**
     * 下载文本内容
     */
    downloadContent(content, filename, type) {
        if (!content) {
            alert('没有数据可导出');
            return;
        }
        const blob = new Blob([content], { type: type });
        this.downloadBlob(blob, filename);
    }

    /**
     * 下载 Blob 对象
     */
    downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }
}
