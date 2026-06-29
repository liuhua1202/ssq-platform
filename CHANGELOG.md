# Changelog

本项目所有重要的变更都会记录在此文件中. 格式参照 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/).

## [Unreleased]

### Changed - 架构重构 (本次)

- **`src/crawler.py` 拆分为 `src/crawler/` 包** (1187 行 → 5 个模块)
  - `state.py` (87 行) - `CrawlState` 防爬虫阻塞 / 60s 缓存
  - `backup.py` (116 行) - `BackupManager` 数据备份管理
  - `parser.py` (362 行) - `IssueParser` 期号 / 记录 / HTML 解析 (纯函数)
  - `fetcher.py` (245 行) - `CWLFetcher` 网络层 (curl_cffi + playwright 三层)
  - `crawler.py` (551 行) - 顶层协调器 (向后兼容 wrapper)
- **`Crawler` / `CWLFetcher` 线程安全**: 每次请求新建 `requests.Session`, 不共享状态, 支持 gunicorn 多 worker

### Security - 增强 (本次)

- **CI/CD 流水线** (`.github/workflows/test.yml`)
  - Matrix 测试 (3 OS × 3 Python 版本)
  - pip-audit 漏洞扫描 (在 Ubuntu + Python 3.12 主分支上)
  - 测试日志自动上传 (失败时)
- **前端 JS 自动 `X-API-Token` 头**
  - `templates/index.html` + `templates/diagnose.html` 通过 Jinja 注入 token
  - `static/js/modules/api.js` 自动从 `window.__API_TOKEN__` 读取并加头
  - 调用方无需改动
- **API Token 通过 Jinja context_processor 注入** (`app.py`)

### Changed - 清理 (本次)

- **`src/api/api.py` 移除 20 个冗余 `try/except Exception` 块** (1370 行 → 1041 行)
  - 通用异常处理已由 `@api_error_handler` 装饰器兜底
  - 业务层 `try/except` 专注于特定异常 (ValueError, FileNotFoundError 等)
- **删除死代码**: `src/online_fetcher.py` (472 行, 0 调用) + `scripts/test_online_fetch.py` + 相关 docs

### Added - 测试覆盖 (本次)

- **`tests/test_integration.py`** (17 tests) - Flask `test_client` 端到端测试
  - 应用启动 / health / cache stats
  - GET 历史 / 分页
  - API Token 鉴权流程 (dev / prod / wrong token / read 端点)
  - 错误处理 (404 / 405)
  - POST `/api/import` 输入校验 + JSON 导入
- **`tests/test_network.py`** (34 tests) - 爬虫网络层 + 解析器单测
  - `IssueParser`: 期号归一化 / 7 号码解析 / 单条记录 / Web Copy / 批量 HTML
  - `BackupManager`: 创建 / 清理 / 恢复
  - `CWLFetcher`: mock 网络层 (requests.Session patch) + 线程安全验证
  - `Crawler.fetch_latest_lottery`: 多源 fallback
- **测试套件总计**: 53 → **104 个测试** (53 旧 + 17 集成 + 34 网络)

### Changed - 工具链 (本次)

- **`requirements.txt`** - `gunicorn==22.0.0` 取消注释 (生产部署用)
- **`start.bat`** - 添加 SECRET_KEY / API_TOKEN / FLASK_DEBUG 环境变量提示
- **`.github/workflows/test.yml`** 新增
- **`LICENSE`** (MIT) 新增
- **`Dockerfile`** 多阶段构建 + 非 root 用户 + 健康检查
- **`.dockerignore`** 新增 (排除 tests / logs / .git 等)

## [v2.1.0] - 2026-XX-XX (硬化加固)

### Changed

- **`src/api/api.py` 引入 `@require_api_token` 装饰器** (保护 13 个写操作端点)
  - 检查 `X-API-Token` 请求头, 与 `config.API_TOKEN` 环境变量匹配
  - 开发模式 (未设 `API_TOKEN`) 放行, 生产模式强制要求
- **`src/api/api.py` 引入 `@api_error_handler` 装饰器** (统一异常兜底)
  - 替换 endpoint 内的 `except Exception` 通用 catch
  - 返回 `{success: False, message: ...}` + 500
- **CrawlState 单例防爬虫阻塞** (`src/crawler.py`)
  - `threading.Lock` 非阻塞 acquire (拒绝重复并发请求, 返 429)
  - 60s 缓存避免重复抓取
- **`limiter` Redis 化**
  - `LIMITER_STORAGE_URI` 环境变量, 默认 `memory://`
  - 多 worker 部署必须改 Redis

### Security

- **删除 `SECRET_KEY` 默认字符串**
  - 生产环境启动时如果未设置 `SECRET_KEY` → `raise SystemExit`
  - DEBUG 模式自动生成临时密钥 (开发友好)
- **检测已知泄漏的密钥** (旧 `ssq-prediction-platform-2026-dev-only`), 生产环境拒绝

### Fixed

- **`crawler.py` 方法重复定义问题**
  - 4 个方法 (`_fetch_cwl_html` 等) 定义两次, Python 取最后一份
  - 保留含 `curl_cffi` 优化的版本, 移除重复定义
- **`my_numbers.json` 路径硬编码 bug 修复**
  - 收藏号码文件路径统一由 `config.MY_NUMBERS_FILE` 管理
- **`api.py` 调用 `crawler._xxx()` 私有方法 → public wrapper**
  - 新增 `crawler.create_backup()` / `parse_record()` / `parse_web_copy()` 公共方法
- **`crawler.py` `print()` → `logger` 统一**
- **`README.md` "如何调用 API" 章节完整重写** - 含 dev / prod 两种模式说明

## [v2.0.0] - 2026-XX-XX

### Added

- 初始版本 - 双色球预测平台
- 13 种预测算法 (comprehensive, weighted_random, normal_distribution, monte_carlo, genetic, markov_chain, kmeans_clustering, big_small_analysis, consecutive_analysis, prime_composite, same_tail_analysis, zone_distribution, smart_recommendation)
- 完整 API (历史 / 分析 / 预测 / 收藏号码 / 数据导入导出)
- PWA 支持 / 暗色模式 / 移动端响应式

### Security

- `/api/predict` 等算力消耗端点加请求频率限制 (Flask-Limiter)
- 客户端 PWA 缓存 (Service Worker)

[Unreleased]: https://github.com/your-repo/ssq-platform/compare/v2.1.0...HEAD
[v2.1.0]: https://github.com/your-repo/ssq-platform/compare/v2.0.0...v2.1.0
[v2.0.0]: https://github.com/your-repo/ssq-platform/releases/tag/v2.0.0
