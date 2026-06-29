"""
API 蓝图定义
优化版本：添加缓存、日志、输入验证
"""
import os
import json
import shutil
import logging
from functools import wraps
from flask import Blueprint, jsonify, request, g, current_app
from datetime import datetime
from src.crawler import Crawler, get_crawl_state
from src.analyzer import Analyzer
from src.predictor import Predictor
from src.cache import analysis_cache, prediction_cache, history_cache

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')

# 初始化模块
crawler = Crawler()

# 使用统一的缓存系统替代全局变量
def _get_cached_history():
    """获取缓存的历史数据，使用统一缓存层"""
    cache_key = "history_data:all"
    cached = history_cache.get(cache_key)
    
    if cached is not None:
        logger.debug("历史数据缓存命中")
        return cached
    
    # 缓存未命中，从文件加载
    data = crawler.load_history()
    history_cache.set(cache_key, data, ttl=60)  # 60秒缓存
    logger.debug(f"历史数据已缓存，共 {len(data)} 条")
    
    return data


def _clear_history_cache():
    """清除历史数据缓存"""
    history_cache.delete("history_data:all")
    logger.debug("历史数据缓存已清除")


def validate_json_required(f):
    """验证请求必须包含 JSON 数据"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            return jsonify({'success': False, 'message': '请求必须是 JSON 格式'}), 400
        return f(*args, **kwargs)
    return decorated_function


def validate_required_fields(required_fields: list):
    """验证请求必须包含指定字段"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            req_data = request.json or {}
            missing = [field for field in required_fields if field not in req_data]
            if missing:
                return jsonify({
                    'success': False,
                    'message': f'缺少必需字段：{", ".join(missing)}'
                }), 400
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_api_token(f):
    """写操作 / 算力消耗端点的鉴权装饰器.

    行为:
      - 如果 config.API_TOKEN 未设置 (开发模式) -> 放行, 但 logger.debug 提示
      - 如果 config.API_TOKEN 已设置 -> 要求请求头 X-API-Token 与之匹配

    生产部署必须设置 API_TOKEN 环境变量. 生成方法同 SECRET_KEY.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        expected = current_app.config.get('API_TOKEN')
        if not expected:
            logger.debug(f'API_TOKEN 未设置, 跳过鉴权: {request.path}')
            return f(*args, **kwargs)
        provided = request.headers.get('X-API-Token', '')
        if not provided or provided != expected:
            logger.warning(f'API_TOKEN 校验失败: {request.path} from {request.remote_addr}')
            return jsonify({
                'success': False,
                'message': '需要有效的 X-API-Token 头'
            }), 401
        return f(*args, **kwargs)
    return decorated


def api_error_handler(operation_name: str):
    """统一异常处理装饰器 (作为 endpoint 的外层兜底).

    行为:
      - 捕获 endpoint 函数内未被内层 try/except 捕获的 Exception
      - 记录 logger.error 包含完整堆栈 (exc_info=True)
      - 返回 {'success': False, 'message': ...} + 500 状态码

    适用场景: endpoint 函数被意外 patch / 导入错误等不可控情况.
    业务异常处理应该保留 endpoint 自己的 try/except.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                logger.error(f'{operation_name}失败 (兜底): {e}', exc_info=True)
                return jsonify({
                    'success': False,
                    'message': f'{operation_name}失败: {str(e)}'
                }), 500
        return wrapped
    return decorator


@api_error_handler('获取历史数据')
@api_bp.route('/history')
def get_history():
    """获取历史数据（带缓存）"""
    try:
        data = _get_cached_history()
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 50, type=int)

        # 限制 page_size 范围（提高上限以支持前端本地分页）
        page_size = min(max(page_size, 1), 2000)

        start = (page - 1) * page_size
        end = start + page_size

        logger.info(f"获取历史数据：page={page}, page_size={page_size}, total={len(data)}")

        return jsonify({
            'success': True,
            'total': len(data),
            'page': page,
            'page_size': page_size,
            'data': data[start:end]
        })
    except Exception as e:
        logger.error(f"获取历史数据失败：{e}")
        return jsonify({
            'success': False,
            'message': f'获取历史数据失败：{str(e)}'
        }), 500


@api_error_handler('获取原始历史数据')
@api_bp.route('/history/raw')
def get_history_raw():
    """获取原始历史数据（用于导出）"""
    try:
        data = _get_cached_history()
        return jsonify({
            'success': True,
            'data': data,
            'count': len(data)
        })
    except Exception as e:
        logger.error(f"获取原始历史数据失败：{e}")
        return jsonify({
            'success': False,
            'message': f'获取数据失败：{str(e)}'
        }), 500


@api_error_handler('分析数据')
@api_bp.route('/analysis')
def get_analysis():
    """获取分析报告（带缓存）"""
    try:
        data = _get_cached_history()
        if not data:
            return jsonify({
                'success': False,
                'message': '暂无历史数据，请先更新数据'
            })

        # 使用缓存的分析结果
        cache_key = f"comprehensive_analysis:{len(data)}"
        cached = analysis_cache.get(cache_key)
        if cached:
            logger.info("分析结果缓存命中")
            cached['cached'] = True
            return jsonify(cached)

        logger.info("开始分析数据...")
        analyzer = Analyzer(data)
        analysis = analyzer.get_comprehensive_analysis()
        analysis['cached'] = False
        
        # 缓存分析结果
        analysis_cache.set(cache_key, analysis, ttl=300)
        logger.info(f"分析完成，已缓存，共 {len(data)} 条记录")

        return jsonify(analysis)
    except Exception as e:
        logger.error(f"分析数据失败：{e}")
        return jsonify({
            'success': False,
            'message': f'分析失败：{str(e)}'
        }), 500


@api_error_handler('生成预测')
@api_bp.route('/predict', methods=['POST'])
@require_api_token
@validate_json_required
def predict():
    """生成预测号码（带缓存）"""
    try:
        data = _get_cached_history()
        if not data:
            return jsonify({
                'success': False,
                'message': '暂无历史数据，请先更新数据'
            })

        req_data = request.json
        algorithm = req_data.get('algorithm', 'comprehensive')
        generations = req_data.get('generations', 5)

        # 验证参数
        if not isinstance(generations, int) or generations < 1 or generations > 100:
            return jsonify({
                'success': False,
                'message': 'generations 必须在 1-100 之间'
            }), 400

        logger.info(f"开始预测：algorithm={algorithm}, generations={generations}")
        analyzer = Analyzer(data)
        predictor = Predictor(analyzer)

        predictions = predictor.predict(algorithm, generations)

        logger.info(f"预测完成，生成 {len(predictions)} 注号码")

        return jsonify({
            'success': True,
            'algorithm': algorithm,
            'predictions': predictions,
            'cached': False
        })
    except ValueError as e:
        logger.warning(f"预测参数错误：{e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
    except Exception as e:
        logger.error(f"预测失败：{e}")
        return jsonify({
            'success': False,
            'message': f'预测失败：{str(e)}'
        }), 500


@api_error_handler('获取统计信息')
@api_bp.route('/statistics')
def get_statistics():
    """获取统计信息（带缓存）"""
    try:
        data = _get_cached_history()
        if not data:
            return jsonify({
                'success': False,
                'message': '暂无历史数据'
            })

        # 使用缓存
        cache_key = f"statistics:{len(data)}"
        cached = analysis_cache.get(cache_key)
        if cached:
            return jsonify(cached)

        analyzer = Analyzer(data)
        stats = {
            'hot_numbers': analyzer.get_hot_numbers(),
            'cold_numbers': analyzer.get_cold_numbers(),
            'missing_stats': analyzer.get_missing_stats(),
            'odd_even': analyzer.get_odd_even_ratio(),
            'sum_analysis': analyzer.get_sum_analysis(),
            'blue_ball': analyzer.get_blue_ball_analysis(),
            'consecutive': analyzer.get_consecutive_numbers_analysis()
        }

        analysis_cache.set(cache_key, stats, ttl=300)
        return jsonify(stats)
    except Exception as e:
        logger.error(f"获取统计信息失败：{e}")
        return jsonify({
            'success': False,
            'message': f'获取统计信息失败：{str(e)}'
        }), 500


@api_error_handler('检查号码')
@api_bp.route('/check', methods=['POST'])
@require_api_token
@validate_json_required
@validate_required_fields(['red_balls', 'blue_ball'])
def check_numbers():
    """检查用户输入号码与历史数据的匹配情况"""
    try:
        req_data = request.json
        red_balls = req_data.get('red_balls', [])
        blue_ball = req_data.get('blue_ball')

        # 验证红球
        if not isinstance(red_balls, list) or len(red_balls) != 6:
            return jsonify({'success': False, 'message': '红球必须是 6 个'}), 400

        if not all(isinstance(r, int) and 1 <= r <= 33 for r in red_balls):
            return jsonify({'success': False, 'message': '红球必须在 1-33 范围内'}), 400

        # 验证蓝球
        if not isinstance(blue_ball, int) or not 1 <= blue_ball <= 16:
            return jsonify({'success': False, 'message': '蓝球必须在 1-16 范围内'}), 400

        data = _get_cached_history()
        red_balls_sorted = sorted(red_balls)
        matches = []

        for record in data:
            hist_reds = set(record.get('red_balls', []))
            hist_blue = record.get('blue_ball')

            red_match = len(set(red_balls_sorted) & hist_reds)
            blue_match = (blue_ball == hist_blue)

            if red_match >= 3 or blue_match:
                matches.append({
                    'issue': record.get('issue'),
                    'date': record.get('date'),
                    'red_match': red_match,
                    'blue_match': blue_match,
                    'historical_numbers': {
                        'red_balls': list(hist_reds),
                        'blue_ball': hist_blue
                    }
                })

        matches.sort(key=lambda x: (x['red_match'], x['blue_match']), reverse=True)

        logger.info(f"号码检查完成：{red_balls_sorted}+{blue_ball}, 匹配 {len(matches)} 条")
        
        return jsonify({
            'success': True,
            'your_numbers': {
                'red_balls': red_balls_sorted,
                'blue_ball': blue_ball
            },
            'best_matches': matches[:10],
            'total_checked': len(data)
        })
    except Exception as e:
        logger.error(f"号码检查失败：{e}")
        return jsonify({
            'success': False,
            'message': f'检查失败：{str(e)}'
        }), 500


@api_error_handler('创建备份')
@api_bp.route('/backup', methods=['POST'])
@require_api_token
def create_backup():
    """手动创建数据备份"""
    try:
        logger.info("手动创建备份")
        crawler.create_backup()
        return jsonify({
            'success': True,
            'message': '备份创建成功'
        })
    except Exception as e:
        logger.error(f"创建备份失败：{e}")
        return jsonify({
            'success': False,
            'message': f'备份失败：{str(e)}'
        }), 500


@api_error_handler('获取备份列表')
@api_bp.route('/backups', methods=['GET'])
def get_backups():
    """获取备份文件列表"""
    try:
        if not os.path.exists(crawler.backup_dir):
            return jsonify({'success': True, 'backups': []})

        backup_files = []
        for f in sorted(os.listdir(crawler.backup_dir), reverse=True):
            if f.endswith('.json'):
                filepath = os.path.join(crawler.backup_dir, f)
                stat = os.stat(filepath)
                backup_files.append({
                    'filename': f,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
                })

        return jsonify({
            'success': True,
            'backups': backup_files
        })
    except Exception as e:
        logger.error(f"获取备份列表失败：{e}")
        return jsonify({
            'success': False,
            'message': f'获取备份列表失败：{str(e)}'
        }), 500


@api_error_handler('删除备份')
@require_api_token
@api_bp.route('/backup/<filename>', methods=['DELETE'])
def delete_backup(filename):
    """删除指定的备份文件"""
    try:
        # 防止路径遍历攻击: 取 basename
        safe_filename = os.path.basename(filename)
        if not safe_filename.endswith('.json'):
            return jsonify({
                'success': False,
                'message': '无效的备份文件'
            }), 400

        backup_path = os.path.join(crawler.backup_dir, safe_filename)
        # 确认路径仍在 backup_dir 之下
        if not os.path.abspath(backup_path).startswith(os.path.abspath(crawler.backup_dir)):
            return jsonify({
                'success': False,
                'message': '非法的备份文件路径'
            }), 400

        if not os.path.exists(backup_path):
            return jsonify({
                'success': False,
                'message': '备份文件不存在'
            }), 404

        os.remove(backup_path)
        logger.info(f"删除备份：{safe_filename}")
        return jsonify({
            'success': True,
            'message': f'备份文件 "{safe_filename}" 已删除'
        })
    except Exception as e:
        logger.error(f"删除备份失败：{e}")
        return jsonify({
            'success': False,
            'message': f'删除失败：{str(e)}'
        }), 500


@api_error_handler('恢复备份')
@api_bp.route('/restore', methods=['POST'])
@require_api_token
@validate_json_required
@validate_required_fields(['filename'])
def restore_backup():
    """从备份文件恢复数据"""
    try:
        req_data = request.json
        filename = req_data.get('filename')

        backup_path = os.path.join(crawler.backup_dir, filename)
        if not os.path.exists(backup_path):
            return jsonify({
                'success': False,
                'message': '备份文件不存在'
            }), 404

        logger.info(f"恢复备份：{filename}")
        crawler.create_backup()
        shutil.copy2(backup_path, crawler.history_file)
        
        # 清除缓存
        _clear_history_cache()
        analysis_cache.clear()
        prediction_cache.clear()

        return jsonify({
            'success': True,
            'message': '数据恢复成功'
        })
    except Exception as e:
        logger.error(f"恢复备份失败：{e}")
        return jsonify({
            'success': False,
            'message': f'恢复失败：{str(e)}'
        }), 500


@api_error_handler('导入数据')
@api_bp.route('/import', methods=['POST'])
@require_api_token
def import_data():
    """导入历史数据（支持 CSV/JSON 格式）"""
    import csv
    import io

    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': '请上传文件'
            }), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': '文件名为空'
            }), 400

        # 验证文件名和扩展名
        filename = file.filename.lower()
        if not (filename.endswith('.json') or filename.endswith('.csv') or filename.endswith('.txt')):
            return jsonify({
                'success': False,
                'message': '不支持的文件格式，请上传 JSON/CSV/TXT 文件'
            }), 400

        # 验证 MIME 类型
        allowed_mimetypes = {
            '.json': ['application/json', 'text/json', 'text/plain'],
            '.csv': ['text/csv', 'text/plain', 'application/vnd.ms-excel'],
            '.txt': ['text/plain', 'text/csv']
        }
        
        file_ext = os.path.splitext(filename)[1]
        allowed_types = allowed_mimetypes.get(file_ext, [])
        
        # 如果提供了 MIME 类型，进行验证
        if file.content_type and allowed_types:
            if file.content_type not in allowed_types:
                logger.warning(f"MIME类型不匹配：{file.content_type}, 期望：{allowed_types}")
                # 仅警告，不阻止（某些浏览器可能发送错误的 MIME 类型）

        # 读取文件内容并验证
        file_content = file.read()
        
        # 验证文件大小（10MB限制）
        if len(file_content) > 10 * 1024 * 1024:
            return jsonify({
                'success': False,
                'message': '文件过大，请限制在 10MB 以内'
            }), 400

        logger.info(f"导入文件：{file.filename}, 大小：{len(file_content)} bytes")
        new_records = []

        if filename.endswith('.json'):
            try:
                data = json.loads(file_content.decode('utf-8'))
                if not isinstance(data, list):
                    return jsonify({
                        'success': False,
                        'message': 'JSON 格式错误：必须是数组格式'
                    }), 400

                logger.info(f"JSON 文件包含 {len(data)} 条原始记录")
                for idx, item in enumerate(data):
                    record = crawler.parse_record(item)
                    if record:
                        new_records.append(record)
                    else:
                        logger.warning(f"记录 {idx} 解析失败: {item}")
                        
            except UnicodeDecodeError:
                return jsonify({
                    'success': False,
                    'message': '文件编码错误，请使用 UTF-8 编码'
                }), 400
            except json.JSONDecodeError as e:
                return jsonify({
                    'success': False,
                    'message': f'JSON 解析失败：{str(e)}'
                }), 400

        elif filename.endswith('.csv'):
            try:
                text_content = file_content.decode('utf-8')
                stream = io.StringIO(text_content)
                reader = csv.DictReader(stream)
                for row in reader:
                    record = crawler.parse_record(row)
                    if record:
                        new_records.append(record)
            except UnicodeDecodeError:
                return jsonify({
                    'success': False,
                    'message': '文件编码错误，请使用 UTF-8 编码'
                }), 400

        elif filename.endswith('.txt'):
            try:
                text_content = file_content.decode('utf-8')
                for line in text_content.split('\n'):
                    try:
                        line = line.strip()
                        if not line:
                            continue

                        # 支持逗号或制表符分隔
                        if '\t' in line:
                            parts = line.split('\t')
                        else:
                            parts = line.split(',')

                        # 清理空格
                        parts = [p.strip() for p in parts]

                        # 跳过表头
                        if parts[0].lower() in ['issue', '期号', 'expectnum']:
                            continue

                        record = None

                        # 格式 1: 9列 (期号, 日期, 红1, 红2, 红3, 红4, 红5, 红6, 蓝)
                        if len(parts) >= 9:
                            record = crawler.parse_record({
                                'issue': parts[0],
                                'date': parts[1],
                                'red_balls': parts[2:8],
                                'blue_ball': parts[8]
                            })
                        
                        # 格式 2: 8列 (期号, 红1, 红2, 红3, 红4, 红5, 红6, 蓝)
                        elif len(parts) >= 8:
                            record = crawler.parse_record({
                                'issue': parts[0],
                                'date': None,
                                'red_balls': parts[1:7],
                                'blue_ball': parts[7]
                            })
                        
                        # 格式 3: 兼容网页复制粘贴格式 (期号, 日期, 连号字符串)
                        elif len(parts) >= 3:
                            record = crawler.parse_web_copy({
                                'issue': parts[0],
                                'date': parts[1] if len(parts) > 1 else None,
                                'balls': parts[2] if len(parts) > 2 else None
                            })

                        if record:
                            new_records.append(record)
                        else:
                            logger.debug(f"TXT 行解析失败: {line}")

                    except Exception as e:
                        logger.debug(f"TXT 行解析异常: {line}, 错误: {e}")
                        continue
            except UnicodeDecodeError:
                return jsonify({
                    'success': False,
                    'message': '文件编码错误，请使用 UTF-8 编码'
                }), 400

        existing = _get_cached_history()
        existing_issues = {item['issue']: item for item in existing}

        for record in new_records:
            existing_issues[record['issue']] = record

        existing = list(existing_issues.values())
        existing.sort(key=lambda x: x['issue'], reverse=True)
        crawler.save_history(existing)
        
        # 清除缓存
        _clear_history_cache()
        analysis_cache.clear()
        prediction_cache.clear()

        logger.info(f"成功导入 {len(new_records)} 条记录")
        return jsonify({
            'success': True,
            'message': f'成功导入 {len(new_records)} 条记录',
            'new_records_count': len(new_records),
            'total_records': len(existing)
        })

    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败：{e}")
        return jsonify({
            'success': False,
            'message': f'JSON 格式错误：{str(e)}'
        }), 400
    except Exception as e:
        logger.error(f"导入失败：{e}")
        return jsonify({
            'success': False,
            'message': f'导入失败：{str(e)}'
        }), 500


@api_error_handler('导入文本数据')
@api_bp.route('/import-text', methods=['POST'])
@require_api_token
@validate_json_required
def import_text_data():
    """从文本导入历史数据"""
    try:
        req_data = request.json or {}
        text_data = req_data.get('text', '')

        # 验证输入长度
        if not text_data:
            return jsonify({
                'success': False,
                'message': '请提供文本数据'
            }), 400

        if len(text_data) > 4194304:  # 限制 4096KB (4MB)
            return jsonify({
                'success': False,
                'message': '文本数据过大，请限制在 4096KB 以内'
            }), 400

        new_records = []
        lines = text_data.strip().split('\n')

        # 限制行数
        if len(lines) > 5000:
            return jsonify({
                'success': False,
                'message': '行数过多，请限制在 5000 行以内'
            }), 400

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if '期号' in line or '开奖号码' in line or '注数' in line:
                continue

            try:
                if '\t' in line:
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        record = crawler.parse_web_copy({
                            'issue': parts[0].strip(),
                            'date': parts[1].strip() if len(parts) > 1 else None,
                            'balls': parts[2].strip() if len(parts) > 2 else None
                        })
                        if record:
                            new_records.append(record)
                else:
                    parts = line.split(',')
                    if len(parts) >= 8:
                        record = crawler.parse_record({
                            'issue': parts[0],
                            'red_balls': parts[1:7],
                            'blue_ball': parts[7]
                        })
                        if record:
                            new_records.append(record)
            except Exception:
                continue

        if not new_records:
            return jsonify({
                'success': False,
                'message': '未能解析任何数据，请检查格式是否正确'
            }), 400

        existing = _get_cached_history()
        existing_issues = {item['issue']: item for item in existing}

        for record in new_records:
            existing_issues[record['issue']] = record

        existing = list(existing_issues.values())
        existing.sort(key=lambda x: x['issue'], reverse=True)
        crawler.save_history(existing)
        
        # 清除缓存
        _clear_history_cache()
        analysis_cache.clear()
        prediction_cache.clear()

        logger.info(f"文本导入成功：{len(new_records)} 条记录")
        return jsonify({
            'success': True,
            'message': f'成功导入 {len(new_records)} 条记录',
            'new_records_count': len(new_records),
            'total_records': len(existing)
        })

    except Exception as e:
        logger.error(f"文本导入失败：{e}")
        return jsonify({
            'success': False,
            'message': f'导入失败：{str(e)}'
        }), 500


@api_error_handler('清空历史数据')
@api_bp.route('/clear-data', methods=['POST'])
@require_api_token
def clear_history_data():
    """清空历史数据"""
    try:
        # 清空数据时不自动创建备份，避免产生多余的备份文件
        crawler.save_history([], backup=False)
        _clear_history_cache()
        analysis_cache.clear()
        prediction_cache.clear()

        logger.warning("历史数据已清空")
        return jsonify({
            'success': True,
            'message': '历史数据已清空',
            'warning': '请刷新页面或清除浏览器缓存以更新显示'
        })

    except Exception as e:
        logger.error(f"清空数据失败：{e}")
        return jsonify({
            'success': False,
            'message': f'清空失败：{str(e)}'
        }), 500


@api_error_handler('获取最新数据')
@api_bp.route('/latest', methods=['GET'])
def get_latest():
    """获取最新开奖数据"""
    try:
        data = _get_cached_history()
        if data:
            return jsonify({
                'success': True,
                'latest': data[0]
            })
        return jsonify({
            'success': False,
            'message': '暂无数据'
        })
    except Exception as e:
        logger.error(f"获取最新数据失败：{e}")
        return jsonify({
            'success': False,
            'message': f'获取失败：{str(e)}'
        }), 500


@api_error_handler('抓取最新开奖')
@api_bp.route('/fetch-latest', methods=['POST'])
@require_api_token
def fetch_latest_from_web():
    """从官方源获取最新开奖信息（使用 crawler 模块）"""
    crawl_state = get_crawl_state()

    # 1. 检查缓存 - 60s 内的重复请求直接返回
    cached = crawl_state.get_cached()
    if cached and cached.get('success') and 'latest' in cached:
        logger.info("返回缓存的抓取结果 (避免重复抓取)")
        return jsonify({**cached, 'cached': True})

    # 2. 尝试获取锁 - 防止并发抓取
    if not crawl_state.try_acquire():
        logger.warning("抓取正在进行中, 拒绝重复请求")
        return jsonify({
            'success': False,
            'message': '正在抓取中, 请稍后再试'
        }), 429

    try:
        logger.info("正在获取最新开奖信息...")

        # 直接使用 crawler 模块（已从 kaijiang.500.com 等多源获取）
        result = crawler.fetch_latest_lottery()

        # fetch_latest_lottery 直接返回数据字段，不是嵌套在 'data' 中
        if result.get('success'):
            # 数据直接在 result 中，不需要再从 'data' 中提取
            latest = {
                'issue': result.get('issue'),
                'date': result.get('date'),
                'red_balls': result.get('red_balls'),
                'blue_ball': result.get('blue_ball')
            }

            if not latest.get('issue') or not latest.get('red_balls'):
                error_msg = '返回数据不完整'
                logger.error(f"获取失败：{error_msg}")
                response = {
                    'success': False,
                    'message': f'获取失败：{error_msg}'
                }
                return jsonify(response), 400

            source = '500彩票网开奖页面'
            logger.info(f"获取成功：期号={latest.get('issue')}, 来源={source}")

            # 保存逻辑
            data = _get_cached_history()
            exists = any(r.get('issue') == latest.get('issue') for r in (data or []))
            if not exists:
                data = [latest] + (data if data else [])
                crawler.save_history(data)
                _clear_history_cache()
                logger.info(f"新增数据已保存：期号={latest.get('issue')}")
            else:
                logger.info(f"数据已存在：期号={latest.get('issue')}")

            response = {
                'success': True,
                'message': f'获取成功（来源：{source}）',
                'data': latest
            }
            # 缓存成功结果
            crawl_state.cache_result({'success': True, 'latest': latest, 'source': source})
            return jsonify({**response, 'cached': False})

        error_msg = result.get('message', '获取失败')
        logger.error(f"获取失败：{error_msg}")
        return jsonify({
            'success': False,
            'message': f'获取失败：{error_msg}'
        }), 400

    finally:
        crawl_state.release()


@api_error_handler('抓取历史开奖')
@api_bp.route('/fetch-history', methods=['POST'])
@require_api_token
def fetch_history_from_web():
    """从网络获取历史开奖记录（使用 crawler 模块）"""
    crawl_state = get_crawl_state()

    # 1. 检查缓存 - 60s 内的重复请求直接返回
    cached = crawl_state.get_cached()
    if cached and cached.get('success') and 'history' in cached:
        logger.info("返回缓存的抓取结果 (避免重复抓取)")
        return jsonify({**cached['history'], 'cached': True})

    # 2. 尝试获取锁 - 防止并发抓取
    if not crawl_state.try_acquire():
        logger.warning("抓取正在进行中, 拒绝重复请求")
        return jsonify({
            'success': False,
            'message': '正在抓取中, 请稍后再试'
        }), 429

    try:
        logger.info("开始从 500彩票网主页获取历史数据")

        # 直接从主页获取历史数据（包含最近10期）
        result = crawler.fetch_lottery_history(page=1, page_size=20)

        if not result.get('success') or not result.get('data'):
            logger.error("获取数据失败")
            return jsonify({
                'success': False,
                'message': result.get('message', '获取失败，请检查网络连接')
            }), 400

        new_data = result.get('data', [])
        logger.info(f"500彩票网获取成功，共 {len(new_data)} 条")

        # 合并到现有历史数据
        current_data = _get_cached_history() or []

        # 去重（以期号为准）
        existing_issues = {record.get('issue') for record in current_data}
        merged_count = 0
        for record in new_data:
            if record.get('issue') not in existing_issues:
                current_data.append(record)
                existing_issues.add(record.get('issue'))
                merged_count += 1

        # 按期号排序（最新的在前）
        current_data.sort(key=lambda x: x.get('issue', ''), reverse=True)

        # 保存
        crawler.save_history(current_data)
        _clear_history_cache()

        logger.info(f"数据保存成功，总计 {len(current_data)} 条，新增 {merged_count} 条")
        response = {
            'success': True,
            'message': f'成功获取 {len(new_data)} 条，新增 {merged_count} 条',
            'new_count': merged_count,
            'total': len(current_data)
        }
        # 缓存成功结果
        crawl_state.cache_result({'success': True, 'history': response})
        return jsonify({**response, 'cached': False})

    finally:
        crawl_state.release()


def get_prize_level(red_match: int, blue_match: bool) -> str:
    """根据匹配情况判断奖级"""
    if red_match == 6 and blue_match:
        return "一等奖"
    elif red_match == 6 and not blue_match:
        return "二等奖"
    elif red_match == 5 and blue_match:
        return "三等奖"
    elif (red_match == 5 and not blue_match) or (red_match == 4 and blue_match):
        return "四等奖"
    elif (red_match == 4 and not blue_match) or (red_match == 3 and blue_match):
        return "五等奖"
    elif blue_match:
        return "六等奖"
    elif red_match >= 3:
        return "福运奖"
    else:
        return "未中奖"


@api_error_handler('自动检查中奖')
@api_bp.route('/auto-check', methods=['POST'])
@require_api_token
def auto_check_my_numbers():
    """自动检查收藏号码是否中奖"""
    try:
        req_data = request.json or {}
        my_numbers = req_data.get('my_numbers', [])

        if not my_numbers:
            my_numbers_file = config.MY_NUMBERS_FILE
            if os.path.exists(my_numbers_file):
                with open(my_numbers_file, 'r', encoding='utf-8') as f:
                    my_numbers = json.load(f)
            else:
                return jsonify({
                    'success': False,
                    'message': '没有收藏号码'
                }), 400

        data = _get_cached_history()
        if not data:
            return jsonify({
                'success': False,
                'message': '暂无历史数据'
            }), 400

        latest = data[0]
        latest_reds = set(latest["red_balls"])
        latest_blue = latest["blue_ball"]

        winners = []
        for item in my_numbers:
            red_balls = set(item["red_balls"])
            blue_ball = item["blue_ball"]

            red_match = len(red_balls & latest_reds)
            blue_match = blue_ball == latest_blue

            # 只统计真正中奖的号码（福运奖/六等奖及以上）
            prize_level = get_prize_level(red_match, blue_match)
            if prize_level != "未中奖":
                winners.append({
                    "number": item,
                    "red_match": red_match,
                    "blue_match": blue_match,
                    "prize_level": prize_level,
                    "latest_issue": latest.get("issue"),
                    "latest_date": latest.get("date")
                })

        logger.info(f"自动检查中奖：检查 {len(my_numbers)} 注，中奖 {len(winners)} 注")

        return jsonify({
            'success': True,
            'latest_issue': latest.get("issue"),
            'latest_date': latest.get("date"),
            'latest_numbers': {
                'red_balls': latest["red_balls"],
                'blue_ball': latest["blue_ball"]
            },
            'total_checked': len(my_numbers),
            'winners': winners
        })

    except Exception as e:
        logger.error(f"自动检查中奖失败：{e}")
        return jsonify({
            'success': False,
            'message': f'检查失败：{str(e)}'
        }), 500


@api_error_handler('获取收藏号码')
@api_bp.route('/my-numbers', methods=['GET'])
def get_my_numbers_file():
    """获取收藏号码"""
    try:
        my_numbers_file = config.MY_NUMBERS_FILE
        if os.path.exists(my_numbers_file):
            with open(my_numbers_file, 'r', encoding='utf-8') as f:
                my_numbers = json.load(f)
            return jsonify({
                'success': True,
                'numbers': my_numbers
            })
        return jsonify({
            'success': True,
            'numbers': []
        })
    except Exception as e:
        logger.error(f"获取收藏号码失败：{e}")
        return jsonify({
            'success': False,
            'message': f'获取失败：{str(e)}'
        }), 500


@api_error_handler('保存收藏号码')
@api_bp.route('/my-numbers', methods=['POST'])
@require_api_token
@validate_json_required
def save_my_numbers_file():
    """保存收藏号码"""
    try:
        req_data = request.json or {}
        my_numbers = req_data.get('numbers', [])

        # 验证数据
        if not isinstance(my_numbers, list):
            return jsonify({
                'success': False,
                'message': 'numbers 必须是数组'
            }), 400
        
        if len(my_numbers) > 100:  # 限制最多 100 注
            return jsonify({
                'success': False,
                'message': '最多保存 100 注号码'
            }), 400

        my_numbers_file = config.MY_NUMBERS_FILE
        os.makedirs(os.path.dirname(config.MY_NUMBERS_FILE), exist_ok=True)

        with open(my_numbers_file, 'w', encoding='utf-8') as f:
            json.dump(my_numbers, f, ensure_ascii=False, indent=2)

        logger.info(f"保存收藏号码：{len(my_numbers)} 注")
        return jsonify({
            'success': True,
            'message': f'已保存 {len(my_numbers)} 个号码'
        })
    except Exception as e:
        logger.error(f"保存收藏号码失败：{e}")
        return jsonify({
            'success': False,
            'message': f'保存失败：{str(e)}'
        }), 500


@api_error_handler('导出收藏号码')
@api_bp.route('/export/my-numbers', methods=['GET'])
def export_my_numbers():
    """导出收藏号码，支持 JSON、CSV、TXT 格式"""
    try:
        format_type = request.args.get('format', 'json').lower()
        my_numbers_file = config.MY_NUMBERS_FILE

        if os.path.exists(my_numbers_file):
            with open(my_numbers_file, 'r', encoding='utf-8') as f:
                my_numbers = json.load(f)
        else:
            my_numbers = []

        if format_type == 'json':
            return jsonify({
                'success': True,
                'data': my_numbers,
                'count': len(my_numbers)
            })

        elif format_type == 'csv':
            # 生成 CSV 格式
            csv_lines = ['key,red_balls,blue_ball,algorithm,remark,saved_at']
            for item in my_numbers:
                red_balls = ','.join(map(str, item.get('red_balls', [])))
                csv_lines.append(f"{item.get('key', '')},{red_balls},{item.get('blue_ball', '')},{item.get('algorithm', '')},{item.get('remark', '')},{item.get('saved_at', '')}")

            return jsonify({
                'success': True,
                'format': 'csv',
                'content': '\n'.join(csv_lines),
                'count': len(my_numbers)
            })

        elif format_type == 'txt':
            # 生成 TXT 格式（每行：红球 1,红球 2,红球 3,红球 4,红球 5,红球 6,蓝球）
            txt_lines = []
            for item in my_numbers:
                red_balls = ','.join(map(str, item.get('red_balls', [])))
                blue_ball = item.get('blue_ball', '')
                txt_lines.append(f"{red_balls},{blue_ball}")

            return jsonify({
                'success': True,
                'format': 'txt',
                'content': '\n'.join(txt_lines),
                'count': len(my_numbers)
            })

        return jsonify({
            'success': False,
            'message': f'不支持的导出格式：{format_type}'
        }), 400

    except Exception as e:
        logger.error(f"导出收藏号码失败：{e}")
        return jsonify({
            'success': False,
            'message': f'导出失败：{str(e)}'
        }), 500


@api_error_handler('导出历史数据')
@api_bp.route('/export/history', methods=['GET'])
def export_history():
    """导出历史数据，支持 JSON、CSV、TXT 格式"""
    try:
        format_type = request.args.get('format', 'json').lower()
        data = _get_cached_history()

        if format_type == 'json':
            return jsonify({
                'success': True,
                'data': data,
                'count': len(data)
            })

        elif format_type == 'csv':
            # 生成 CSV 格式（标准列格式：期号, 日期, 红1, 红2, 红3, 红4, 红5, 红6, 蓝）
            csv_lines = ['issue,date,red1,red2,red3,red4,red5,red6,blue']
            for item in data:
                red_balls = item.get('red_balls', [])
                # 补齐 6 个红球（防止数据异常）
                while len(red_balls) < 6:
                    red_balls.append('')
                csv_lines.append(f"{item.get('issue', '')},{item.get('date', '')},{','.join(map(str, red_balls[:6]))},{item.get('blue_ball', '')}")

            return jsonify({
                'success': True,
                'format': 'csv',
                'content': '\n'.join(csv_lines),
                'count': len(data)
            })

        elif format_type == 'txt':
            # 生成 TXT 格式（标准列格式：期号, 日期, 红1, 红2, 红3, 红4, 红5, 红6, 蓝）
            txt_lines = []
            for item in data:
                issue = item.get('issue', '')
                date = item.get('date', '')
                red_balls = item.get('red_balls', [])
                blue_ball = item.get('blue_ball', '')
                
                # 补齐 6 个红球
                while len(red_balls) < 6:
                    red_balls.append('')
                
                # 格式：期号, 日期, 红1, 红2, 红3, 红4, 红5, 红6, 蓝
                txt_lines.append(f"{issue},{date},{','.join(map(str, red_balls[:6]))},{blue_ball}")

            return jsonify({
                'success': True,
                'format': 'txt',
                'content': '\n'.join(txt_lines),
                'count': len(data)
            })

        return jsonify({
            'success': False,
            'message': f'不支持的导出格式：{format_type}'
        }), 400

    except Exception as e:
        logger.error(f"导出历史数据失败：{e}")
        return jsonify({
            'success': False,
            'message': f'导出失败：{str(e)}'
        }), 500


@api_error_handler('健康检查')
@api_bp.route('/health')
def health_check():
    """健康检查"""
    try:
        from src.cache import analysis_cache, prediction_cache, history_cache
        
        data = _get_cached_history()
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'data_records': len(data) if data else 0,
            'cache': {
                'analysis': analysis_cache.stats(),
                'prediction': prediction_cache.stats(),
                'history': history_cache.stats()
            }
        })
    except Exception as e:
        logger.error(f"健康检查失败：{e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


@api_error_handler('获取缓存统计')
@api_bp.route('/cache/stats', methods=['GET'])
def get_cache_stats():
    """获取缓存统计信息"""
    try:
        return jsonify({
            'success': True,
            'analysis_cache': analysis_cache.stats(),
            'prediction_cache': prediction_cache.stats(),
            'history_cache': history_cache.stats()
        })
    except Exception as e:
        logger.error(f"获取缓存统计失败：{e}")
        return jsonify({
            'success': False,
            'message': f'获取缓存统计失败：{str(e)}'
        }), 500


@api_error_handler('清除缓存')
@api_bp.route('/cache/clear', methods=['POST'])
@require_api_token
def clear_cache():
    """清除所有缓存"""
    try:
        _clear_history_cache()
        analysis_cache.clear()
        prediction_cache.clear()
        history_cache.clear()
        
        logger.info("所有缓存已清除")
        return jsonify({
            'success': True,
            'message': '所有缓存已清除'
        })
    except Exception as e:
        logger.error(f"清除缓存失败：{e}")
        return jsonify({
            'success': False,
            'message': f'清除缓存失败：{str(e)}'
        }), 500
