"""
双色球预测平台 - Flask 主应用
重构版本：使用蓝图组织 API
优化版本：添加日志配置、环境变量支持、性能监控
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from flask import Flask, render_template, send_from_directory, make_response, request, jsonify, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from src.api.api import api_bp
from src.crawler import Crawler
import config
from config import (
    LOGGING_CONFIG, WEB_CONFIG,
    ensure_security_config,
    LIMITER_STORAGE_URI,
)

def setup_logging(app):
    """配置日志系统"""

    # 确定日志目录路径
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包运行
        log_dir = os.path.join(os.path.dirname(sys.executable), 'logs')
    else:
        # 源代码运行
        log_dir = os.path.join(os.path.dirname(__file__), 'logs')

    os.makedirs(log_dir, exist_ok=True)

    # 日志文件路径
    log_file = os.path.join(log_dir, 'app.log')

    # 配置日志格式
    formatter = logging.Formatter(LOGGING_CONFIG['format'])

    # 文件处理器（轮转文件）
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=LOGGING_CONFIG['max_bytes'],
        backupCount=LOGGING_CONFIG['backup_count'],
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, LOGGING_CONFIG['level']))
    file_handler.setFormatter(formatter)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # 添加到应用 logger
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(getattr(logging, LOGGING_CONFIG['level']))

    # 配置 Flask 内置 logger
    flask_logger = logging.getLogger('werkzeug')
    flask_logger.addHandler(file_handler)
    flask_logger.addHandler(console_handler)

    app.logger.info("=" * 50)
    app.logger.info("双色球预测平台日志系统已初始化")
    app.logger.info(f"日志级别：{LOGGING_CONFIG['level']}")
    app.logger.info(f"日志文件：{log_file}")
    app.logger.info("=" * 50)


# 使用统一的路径处理函数
from config import get_base_path

base_path = get_base_path()
template_folder = os.path.join(base_path, 'templates')
static_folder = os.path.join(base_path, 'static')

# Startup security check (runs under gunicorn / flask run / python app.py)
# 生产环境 SECRET_KEY 未设置或为默认字符串时会直接 raise SystemExit
ensure_security_config()

app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
app.config['DATA_DIR'] = os.path.join(base_path, 'data')
app.config['LOGS_DIR'] = os.path.join(base_path, 'logs')

# 配置
app.config['JSON_AS_ASCII'] = False
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['API_TOKEN'] = config.API_TOKEN
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 最大 16MB

# 初始化速率限制器
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=config.LIMITER_STORAGE_URI,
    strategy="fixed-window"
)

# 配置日志
setup_logging(app)

# 注册蓝图
app.register_blueprint(api_bp)

# 初始化模块
crawler = Crawler()
app.logger.info("Crawler 模块已初始化")


@app.before_request
def record_start_time():
    """记录请求开始时间（用于性能监控）"""
    g.start_time = datetime.now()


@app.after_request
def after_request_handler(response):
    """请求后处理：日志记录 + 静态文件缓存优化"""
    if hasattr(g, 'start_time'):
        elapsed = (datetime.now() - g.start_time).total_seconds() * 1000
        if elapsed > 1000:
            app.logger.warning(f"慢请求：{request.method} {request.path} - {elapsed:.2f}ms")
        else:
            app.logger.info(f"{request.method} {request.path} - {elapsed:.2f}ms")

        if app.debug:
            response.headers['X-Response-Time'] = f'{elapsed:.2f}ms'

    # 静态文件缓存优化：根据文件类型设置不同缓存时间
    if request.path.startswith('/static/'):
        # JS/CSS 文件缓存 1 天（通过文件名哈希更新）
        if request.path.endswith(('.js', '.css')):
            response.headers['Cache-Control'] = 'public, max-age=86400, immutable'
        # 图片文件缓存 7 天
        elif request.path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico')):
            response.headers['Cache-Control'] = 'public, max-age=604800, immutable'
        # 其他静态文件缓存 1 小时
        else:
            response.headers['Cache-Control'] = 'public, max-age=3600'
        
        response.headers['X-Version'] = '20260429'  # 版本号用于强制更新

    return response


@app.route('/')
def index():
    """首页"""
    app.logger.info("访问首页")
    response = make_response(render_template('index.html'))
    # 禁止缓存 HTML 页面
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/diagnose')
def diagnose():
    """诊断页面"""
    app.logger.info("访问诊断页面")
    response = make_response(render_template('diagnose.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


@app.route('/favicon.ico')
def favicon():
    """ favicon 处理"""
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )


@app.errorhandler(404)
def not_found(error):
    """404 错误处理"""
    app.logger.warning(f"404 错误：{request.path}")
    # API 请求返回 JSON，页面请求返回 HTML
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': 'API 端点未找到'}), 404
    return render_template('index.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """500 错误处理"""
    app.logger.error(f"500 错误：{error}")
    # API 请求返回 JSON
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': '服务器内部错误'}), 500
    return jsonify({'success': False, 'message': '服务器内部错误'}), 500


@app.errorhandler(429)
def rate_limit_exceeded(e):
    """速率限制错误处理（返回 JSON）"""
    return jsonify({
        'success': False,
        'message': '请求过于频繁，请稍后再试'
    }), 429


if __name__ == '__main__':
    # 确保数据目录存在
    os.makedirs('data', exist_ok=True)
    os.makedirs('data/backup', exist_ok=True)
    os.makedirs('logs', exist_ok=True)

    # 启动应用
    app.logger.info("=" * 50)
    app.logger.info("双色球预测平台启动中...")
    app.logger.info(f"访问地址：http://localhost:{WEB_CONFIG['port']}")
    app.logger.info(f"调试模式：{WEB_CONFIG['debug']}")
    app.logger.info("=" * 50)
    print("=" * 50)
    print("双色球预测平台启动中...")
    print(f"访问地址：http://localhost:{WEB_CONFIG['port']}")
    print("=" * 50)
    app.run(host=WEB_CONFIG['host'], port=WEB_CONFIG['port'], debug=WEB_CONFIG['debug'])
