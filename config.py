# 双色球预测平台配置文件
import os
import secrets


# 已知的默认值 - 用于检测泄露的密钥
_LEGACY_DEFAULT_KEY = 'ssq-prediction-platform-2026-dev-only'

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
MY_NUMBERS_FILE = "data/my_numbers.json"  # 收藏号码 (api 层使用)

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

# 安全配置 - SECRET_KEY 不再有默认字符串, 必须显式设置
# 启动时调用 ensure_security_config() 校验/生成
_raw_secret_key = os.environ.get('SECRET_KEY')
if _raw_secret_key:
    SECRET_KEY = _raw_secret_key
else:
    SECRET_KEY = None  # 启动时再决定


def ensure_security_config() -> bool:
    """
    启动时检查 SECRET_KEY 配置.

    规则:
      1. 如果 SECRET_KEY 已设置且不是已知默认值 -> 通过
      2. 如果 SECRET_KEY 是已知默认值 (旧代码遗留) ->
         - DEBUG 模式: 警告一次
         - 生产模式: 直接 raise SystemExit 拒绝启动
      3. 如果 SECRET_KEY 未设置 (None) ->
         - DEBUG 模式: 自动生成临时密钥 + 警告 (开发友好)
         - 生产模式: raise SystemExit 拒绝启动

    Returns:
        True 如果配置安全, False 表示使用了弱密钥但允许继续 (仅 DEBUG)
    """
    global SECRET_KEY
    debug = WEB_CONFIG['debug']

    if SECRET_KEY is None:
        # 未设置密钥
        if not debug:
            raise SystemExit(
                '\n[SECURITY] 生产环境必须设置 SECRET_KEY 环境变量.\n'
                '生成方法: python -c "import secrets; print(secrets.token_hex(32))"\n'
                '然后设置: set SECRET_KEY=<生成的密钥>  (Windows)\n'
                '       或 export SECRET_KEY=<生成的密钥>  (Linux/Mac)\n'
            )
        # DEBUG 模式自动生成临时密钥
        SECRET_KEY = secrets.token_hex(32)
        print(
            '\n[WARNING] SECRET_KEY 未设置, 已自动生成临时密钥用于开发环境.'
            '\n          此密钥每次重启会变化, 请勿用于生产部署.'
            '\n          生产部署请显式设置 SECRET_KEY 环境变量.\n'
        )
        return False

    if SECRET_KEY == _LEGACY_DEFAULT_KEY:
        # 旧代码中的默认值, 绝不能用于生产
        if not debug:
            raise SystemExit(
                '\n[SECURITY] SECRET_KEY 使用了已知的默认字符串, 生产环境禁止使用.\n'
                '请设置环境变量: export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")\n'
            )
        print(
            '\n[WARNING] SECRET_KEY 使用了已知的默认字符串, 仅在 DEBUG 模式下被允许.'
            '\n          生产部署前请设置唯一的 SECRET_KEY.\n'
        )
        return False

    return True


# 保留旧函数名作为别名, 向后兼容 (被 app.py / 其他脚本可能调用)
def check_security_config() -> bool:
    """向后兼容的别名. 建议使用 ensure_security_config()."""
    return ensure_security_config()


# 日志配置
LOGGING_CONFIG = {
    "level": os.environ.get('LOG_LEVEL', 'INFO'),
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "logs/app.log",
    "max_bytes": 10 * 1024 * 1024,  # 10MB
    "backup_count": 5
}

# API 配置
API_CONFIG = {
    "rate_limit": int(os.environ.get('API_RATE_LIMIT', '60')),  # 每分钟请求数
    "max_json_size": int(os.environ.get('MAX_JSON_SIZE', '1024')),  # KB
}

# 限流器存储后端
# 默认内存 (单进程); 多进程 / 多 worker 必须改 Redis
# 例如: redis://localhost:6379/0  或  redis://:password@host:6379/1
LIMITER_STORAGE_URI = os.environ.get('LIMITER_STORAGE_URI', 'memory://')

# 写操作鉴权 Token (None 表示不要求鉴权, 仅开发模式合理)
# 生产部署必须设置, 见 README
API_TOKEN = os.environ.get('API_TOKEN', None)


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