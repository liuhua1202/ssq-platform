# 双色球预测平台配置文件
import os

# 红球范围
RED_BALL_MIN = 1
RED_BALL_MAX = 33
RED_BALL_COUNT = 6

# 蓝球范围
BLUE_BALL_MIN = 1
BLUE_BALL_MAX = 16
BLUE_BALL_COUNT = 1

# 数据存储路径
DATA_DIR = "data"
HISTORY_FILE = "data/history.json"

# 存储配置（可选 json 或 sqlite）
STORAGE_CONFIG = {
    "type": os.environ.get('STORAGE_TYPE', 'json'),  # json 或 sqlite
    "data_dir": "data"
}

# 爬虫配置
CRAWLER_CONFIG = {
    "timeout": 10,
    "retry_times": 3,
    "delay": 1  # 请求间隔（秒）
}

# 预测算法配置
PREDICTOR_CONFIG = {
    "default_generations": 5,  # 生成注数
    "hot_weight": 0.4,  # 热号权重
    "cold_weight": 0.2,  # 冷号权重
    "missing_weight": 0.3,  # 遗漏值权重
    "trend_weight": 0.1,  # 趋势权重
}

# Web 配置
WEB_CONFIG = {
    "host": "0.0.0.0",
    "port": 5000,
    "debug": os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
}

# 安全配置
SECRET_KEY = os.environ.get('SECRET_KEY', 'ssq-prediction-platform-2026-dev-only')

# 生产环境安全检查
def check_security_config():
    """检查安全配置，生产环境必须设置安全的 SECRET_KEY"""
    import warnings
    
    # 检查是否使用默认密钥
    if SECRET_KEY == 'ssq-prediction-platform-2026-dev-only':
        # 开发环境允许使用默认密钥
        debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
        if not debug:
            warnings.warn(
                '⚠️ 警告：生产环境使用默认 SECRET_KEY！\n'
                '请设置环境变量：set SECRET_KEY=your-secure-random-key\n'
                '或使用 Python 生成：python -c "import secrets; print(secrets.token_hex(32))"',
                RuntimeWarning
            )
            return False
    return True

# 日志配置
LOGGING_CONFIG = {
    "level": os.environ.get('LOG_LEVEL', 'INFO'),
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "logs/app.log",
    "max_bytes": 10 * 1024 * 1024,  # 10MB
    "backup_count": 5
}

# API 配置（预留，供后续实现速率限制等功能使用）
API_CONFIG = {
    "rate_limit": int(os.environ.get('API_RATE_LIMIT', '60')),  # 每分钟请求数
    "max_json_size": int(os.environ.get('MAX_JSON_SIZE', '1024')),  # KB
}


def get_base_path():
    """获取项目基础路径（统一处理 PyInstaller 打包和源代码运行）"""
    import sys
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包运行：使用可执行文件所在目录
        return os.path.dirname(sys.executable)
    else:
        # 源代码运行：使用项目根目录
        return os.path.dirname(os.path.abspath(__file__))


def get_resource_path(relative_path):
    """获取资源文件的绝对路径（兼容打包和源代码运行）"""
    return os.path.join(get_base_path(), relative_path)
