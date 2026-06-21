/**
 * 前端表单验证模块
 * 提供号码输入验证、格式检查等功能
 */

export class Validator {
    /**
     * 验证红球号码
     * @param {string|Array} input - 红球输入（字符串或数组）
     * @returns {Object} 验证结果 {valid, message, numbers}
     */
    static validateRedBalls(input) {
        let numbers;
        
        // 处理字符串输入
        if (typeof input === 'string') {
            // 移除多余空格
            const cleaned = input.trim().replace(/\s+/g, ' ');
            numbers = cleaned.split(' ').filter(n => n !== '');
            
            // 转换为数字
            numbers = numbers.map(n => parseInt(n, 10));
        } else if (Array.isArray(input)) {
            numbers = input.map(n => parseInt(n, 10));
        } else {
            return {
                valid: false,
                message: '请输入红球号码'
            };
        }
        
        // 检查是否为有效数字
        if (numbers.some(n => isNaN(n))) {
            return {
                valid: false,
                message: '红球号码必须是数字'
            };
        }
        
        // 检查数量
        if (numbers.length !== 6) {
            return {
                valid: false,
                message: `需要 6 个红球号码，当前输入 ${numbers.length} 个`
            };
        }
        
        // 检查范围
        for (const num of numbers) {
            if (num < 1 || num > 33) {
                return {
                    valid: false,
                    message: `红球号码必须在 1-33 之间，${num} 超出范围`
                };
            }
        }
        
        // 检查重复
        const unique = new Set(numbers);
        if (unique.size !== numbers.length) {
            return {
                valid: false,
                message: '红球号码不能重复'
            };
        }
        
        return {
            valid: true,
            message: '验证通过',
            numbers: numbers.sort((a, b) => a - b)
        };
    }
    
    /**
     * 验证蓝球号码
     * @param {string|number} input - 蓝球输入
     * @returns {Object} 验证结果 {valid, message, number}
     */
    static validateBlueBall(input) {
        let number;
        
        if (typeof input === 'string') {
            number = parseInt(input.trim(), 10);
        } else if (typeof input === 'number') {
            number = input;
        } else {
            return {
                valid: false,
                message: '请输入蓝球号码'
            };
        }
        
        // 检查是否为有效数字
        if (isNaN(number)) {
            return {
                valid: false,
                message: '蓝球号码必须是数字'
            };
        }
        
        // 检查范围
        if (number < 1 || number > 16) {
            return {
                valid: false,
                message: `蓝球号码必须在 1-16 之间，${number} 超出范围`
            };
        }
        
        return {
            valid: true,
            message: '验证通过',
            number: number
        };
    }
    
    /**
     * 验证完整号码（6红球 + 1蓝球）
     * @param {string} redInput - 红球输入
     * @param {string} blueInput - 蓝球输入
     * @returns {Object} 验证结果
     */
    static validateFullNumbers(redInput, blueInput) {
        const redResult = this.validateRedBalls(redInput);
        if (!redResult.valid) {
            return redResult;
        }
        
        const blueResult = this.validateBlueBall(blueInput);
        if (!blueResult.valid) {
            return blueResult;
        }
        
        return {
            valid: true,
            message: '验证通过',
            red_balls: redResult.numbers,
            blue_ball: blueResult.number
        };
    }
    
    /**
     * 验证期号格式
     * @param {string} issue - 期号
     * @returns {Object} 验证结果
     */
    static validateIssue(issue) {
        if (!issue || typeof issue !== 'string') {
            return {
                valid: false,
                message: '请输入期号'
            };
        }
        
        const cleaned = issue.trim();
        
        // 期号格式：YYYYXXX（如 2024001）
        if (!/^\d{5,7}$/.test(cleaned)) {
            return {
                valid: false,
                message: '期号格式不正确，应为 5-7 位数字'
            };
        }
        
        return {
            valid: true,
            message: '验证通过',
            issue: cleaned
        };
    }
    
    /**
     * 验证日期格式
     * @param {string} date - 日期字符串
     * @returns {Object} 验证结果
     */
    static validateDate(date) {
        if (!date || typeof date !== 'string') {
            return {
                valid: false,
                message: '请输入日期'
            };
        }
        
        const cleaned = date.trim();
        
        // 日期格式：YYYY-MM-DD
        if (!/^\d{4}-\d{2}-\d{2}$/.test(cleaned)) {
            return {
                valid: false,
                message: '日期格式不正确，应为 YYYY-MM-DD'
            };
        }
        
        // 检查日期是否有效
        const dateObj = new Date(cleaned);
        if (isNaN(dateObj.getTime())) {
            return {
                valid: false,
                message: '无效的日期'
            };
        }
        
        return {
            valid: true,
            message: '验证通过',
            date: cleaned
        };
    }
    
    /**
     * 验证生成注数
     * @param {number|string} count - 注数
     * @returns {Object} 验证结果
     */
    static validateGenerations(count) {
        const num = parseInt(count, 10);
        
        if (isNaN(num)) {
            return {
                valid: false,
                message: '注数必须是数字'
            };
        }
        
        if (num < 1 || num > 100) {
            return {
                valid: false,
                message: '注数必须在 1-100 之间'
            };
        }
        
        return {
            valid: true,
            message: '验证通过',
            count: num
        };
    }
    
    /**
     * 显示验证错误提示
     * @param {string} message - 错误消息
     * @param {HTMLElement} targetElement - 目标元素
     */
    static showError(message, targetElement = null) {
        // 移除旧提示
        this.hideError();
        
        // 创建错误提示
        const errorDiv = document.createElement('div');
        errorDiv.className = 'validation-error';
        errorDiv.style.cssText = `
            background: #fef2f2;
            border: 1px solid #fecaca;
            color: #dc2626;
            padding: 10px 16px;
            border-radius: 8px;
            margin: 8px 0;
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            gap: 8px;
        `;
        errorDiv.innerHTML = `
            <span>⚠️</span>
            <span>${message}</span>
        `;
        
        if (targetElement) {
            targetElement.parentNode.insertBefore(errorDiv, targetElement.nextSibling);
        } else {
            // 默认插入到表单顶部
            const form = document.querySelector('.check-input');
            if (form) {
                form.insertBefore(errorDiv, form.firstChild);
            }
        }
        
        // 3秒后自动消失
        setTimeout(() => {
            this.hideError();
        }, 3000);
    }
    
    /**
     * 隐藏验证错误提示
     */
    static hideError() {
        const error = document.querySelector('.validation-error');
        if (error) {
            error.remove();
        }
    }
    
    /**
     * 显示成功提示
     * @param {string} message - 成功消息
     */
    static showSuccess(message) {
        // 创建成功提示
        const successDiv = document.createElement('div');
        successDiv.className = 'validation-success';
        successDiv.style.cssText = `
            background: #f0fdf4;
            border: 1px solid #bbf7d0;
            color: #16a34a;
            padding: 10px 16px;
            border-radius: 8px;
            margin: 8px 0;
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            gap: 8px;
        `;
        successDiv.innerHTML = `
            <span>✅</span>
            <span>${message}</span>
        `;
        
        const form = document.querySelector('.check-input');
        if (form) {
            form.insertBefore(successDiv, form.firstChild);
        }
        
        // 2秒后自动消失
        setTimeout(() => {
            const el = document.querySelector('.validation-success');
            if (el) el.remove();
        }, 2000);
    }
}

// 导出为全局可用
window.Validator = Validator;
