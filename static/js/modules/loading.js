/**
 * 加载状态管理模块
 * 提供统一的加载、错误、成功状态显示
 */

export const LoadingManager = {
    /**
     * 显示加载状态
     * @param {string} containerId - 容器 ID
     * @param {string} message - 加载消息
     */
    show(containerId, message = '加载中...') {
        const el = document.getElementById(containerId);
        if (!el) {
            console.warn(`容器不存在：${containerId}`);
            return;
        }
        
        el.innerHTML = `
            <div class="loading-container">
                <div class="loading-spinner"></div>
                <p class="loading-text">${message}</p>
            </div>
        `;
    },

    /**
     * 隐藏加载状态
     * @param {string} containerId - 容器 ID
     */
    hide(containerId) {
        const el = document.getElementById(containerId);
        if (!el) return;
        
        const loading = el.querySelector('.loading-container');
        if (loading) {
            loading.remove();
        }
    },

    /**
     * 显示错误信息
     * @param {string} containerId - 容器 ID
     * @param {string} message - 错误消息
     * @param {Function} onRetry - 重试回调（可选）
     */
    error(containerId, message, onRetry = null) {
        const el = document.getElementById(containerId);
        if (!el) return;
        
        const retryHtml = onRetry 
            ? `<button class="btn-retry" onclick="${onRetry.toString()}">重试</button>`
            : '';
        
        el.innerHTML = `
            <div class="error-container">
                <div class="error-icon">❌</div>
                <p class="error-message">${message}</p>
                ${retryHtml}
            </div>
        `;
    },

    /**
     * 显示成功提示
     * @param {string} containerId - 容器 ID
     * @param {string} message - 成功消息
     * @param {number} duration - 显示时长（毫秒）
     */
    success(containerId, message, duration = 3000) {
        const el = document.getElementById(containerId);
        if (!el) return;
        
        el.innerHTML = `
            <div class="success-container">
                <div class="success-icon">✅</div>
                <p class="success-message">${message}</p>
            </div>
        `;
        
        if (duration > 0) {
            setTimeout(() => {
                const container = el.querySelector('.success-container');
                if (container) {
                    container.style.opacity = '0';
                    container.style.transition = 'opacity 0.3s';
                    setTimeout(() => container.remove(), 300);
                }
            }, duration);
        }
    },

    /**
     * 显示空状态
     * @param {string} containerId - 容器 ID
     * @param {string} message - 空状态消息
     * @param {string} icon - 图标（可选）
     */
    empty(containerId, message = '暂无数据', icon = '📭') {
        const el = document.getElementById(containerId);
        if (!el) return;
        
        el.innerHTML = `
            <div class="empty-container">
                <div class="empty-icon">${icon}</div>
                <p class="empty-message">${message}</p>
            </div>
        `;
    },

    /**
     * 显示进度条
     * @param {string} containerId - 容器 ID
     * @param {number} percent - 进度百分比（0-100）
     * @param {string} message - 进度消息
     */
    progress(containerId, percent, message = '') {
        const el = document.getElementById(containerId);
        if (!el) return;
        
        const safePercent = Math.max(0, Math.min(100, percent));
        
        el.innerHTML = `
            <div class="progress-container">
                ${message ? `<p class="progress-text">${message}</p>` : ''}
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${safePercent}%"></div>
                </div>
                <p class="progress-percent">${safePercent.toFixed(0)}%</p>
            </div>
        `;
    }
};

/**
 *  Toast 通知管理
 */
export const ToastManager = {
    _container: null,

    _getContainer() {
        if (!this._container) {
            this._container = document.createElement('div');
            this._container.className = 'toast-container';
            this._container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
            `;
            document.body.appendChild(this._container);
        }
        return this._container;
    },

    /**
     * 显示 Toast 消息
     * @param {string} message - 消息内容
     * @param {string} type - 类型：success, error, warning, info
     * @param {number} duration - 显示时长（毫秒）
     */
    show(message, type = 'info', duration = 3000) {
        const container = this._getContainer();

        const toast = document.createElement('div');
        toast.className = `toast toast-${type} toast-success`;

        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };

        const colors = {
            success: '#10b981',
            error: '#ef4444',
            warning: '#f59e0b',
            info: '#6366f1'
        };

        toast.style.cssText = `
            background: #fff;
            border-left: 4px solid ${colors[type]};
            color: #1e293b;
            padding: 16px 24px;
            margin-bottom: 12px;
            border-radius: 12px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
            animation: slideIn 0.3s ease;
            min-width: 280px;
            max-width: 400px;
        `;

        const iconColor = colors[type];

        toast.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 20px; color: ${iconColor}; font-weight: bold;">${icons[type]}</span>
                <span style="font-size: 14px; font-weight: 500;">${message}</span>
            </div>
        `;

        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    },

    success(message, duration) {
        this.show(message, 'success', duration);
    },

    error(message, duration) {
        this.show(message, 'error', duration);
    },

    warning(message, duration) {
        this.show(message, 'warning', duration);
    },

    info(message, duration) {
        this.show(message, 'info', duration);
    }
};

// 添加动画样式
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    .loading-container, .error-container, .success-container, .empty-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 40px 20px;
        text-align: center;
    }
    
    .loading-spinner {
        width: 40px;
        height: 40px;
        border: 4px solid #f3f3f3;
        border-top: 4px solid #4CAF50;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin-bottom: 16px;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    .error-icon, .success-icon, .empty-icon {
        font-size: 48px;
        margin-bottom: 16px;
    }
    
    .error-message, .success-message, .empty-message, .loading-text {
        color: #666;
        font-size: 14px;
        margin: 0;
    }
    
    .progress-container {
        padding: 20px;
        text-align: center;
    }
    
    .progress-bar {
        width: 100%;
        height: 8px;
        background: #f3f3f3;
        border-radius: 4px;
        overflow: hidden;
        margin: 12px 0;
    }
    
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #4CAF50, #8BC34A);
        transition: width 0.3s ease;
    }
    
    .btn-retry {
        margin-top: 16px;
        padding: 8px 24px;
        background: #4CAF50;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
    }
    
    .btn-retry:hover {
        background: #45a049;
    }
`;
document.head.appendChild(style);
