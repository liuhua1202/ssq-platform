# 双色球预测平台 · SSQ Prediction Platform

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)](#-本地开发)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?logo=flask)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)](#-本地开发)

基于 **Flask + Playwright** 的双色球历史数据抓取与号码预测 Web 平台。仅供**娱乐**和**统计学习**用途。

> ⚠️ **重要免责声明**
> 彩票是**纯随机事件**，任何算法都无法预测中奖号码。本项目提供的所有"预测"功能均为**统计学娱乐**，
> 不构成任何投注建议。请理性看待结果，**未满 18 周岁请勿使用**，**理性购彩**。
> 项目作者不承担因使用本工具产生的任何损失。

---## ✨ 特性

- 🕷️ **多源爬虫** — 500 彩票网 / 中彩网 / 福彩官网，自动 fallback，**Playwright 兜底** JS 渲染
- 🧮 **13 种预测算法** — 加权随机、马尔可夫链、K-Means 聚类、遗传算法、蒙特卡洛、综合推荐等
- 📊 **历史数据分析** — 热号 / 冷号 / 遗漏值 / 和值分布 / 奇偶比 / 连号 / AC 指数
- 💾 **收藏号码 + 自动对奖** — 一键检查最新一期是否中奖，奖金等级自动判定
- 📥 **多格式导入导出** — JSON / CSV / TXT 历史数据，UTF-8 编码
- 🔒 **基础鉴权** — 写操作要求 `X-API-Token` header（开发模式可选）
- 📱 **响应式 UI** — 桌面 / 平板 / 手机自适应，静态资源按类型缓存
- 🪟 **可打包** — PyInstaller 打成单文件 `.exe`，双击即用

---## 📦 快速开始

### 环境要求

- **Python 3.9+**（推荐 3.11）
- **pip** 包管理
- **Playwright 浏览器**（仅首次运行爬虫时需要）

### 安装

```bash
git clone https://github.com/liuhua1202/ssq-platform.git
cd ssq-platform

# 推荐：虚拟环境
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate

pip install -r requirements.txt

# 仅当需要抓取数据时才装：
playwright install chromium
```

### 启动

```bash
# 方式一：直接启动（开发模式，会自动生成临时 SECRET_KEY）
python app.py

# 方式二：Windows 一键
start.bat
```

打开浏览器访问 `http://localhost:5000`。

### 运行测试

```bash
python tests/test_core.py
```

---## 🚀 生产部署

⚠️ **生产模式必须设置两个环境变量**，否则启动直接 `SystemExit`：

| 变量 | 说明 | 生成方法 |
|---|---|---|
| `SECRET_KEY` | Flask session 签名密钥 | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `API_TOKEN` | 写操作 API 鉴权 token | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `FLASK_DEBUG` | 必须设为 `False` | 直接 `export FLASK_DEBUG=False` |
| `LOG_LEVEL` | 日志级别（默认 INFO） | `INFO` / `WARNING` / `ERROR` |

### Gunicorn（推荐）

```bash
pip install gunicorn

export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export FLASK_DEBUG=False

gunicorn -w 2 -b 0.0.0.0:5000 app:app
```### Docker（参考）

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && playwright install --with-deps chromium
COPY . .
ENV FLASK_DEBUG=False
# SECRET_KEY 和 API_TOKEN 通过 -e 或 .env 注入
EXPOSE 5000
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]
```

### Windows 单文件打包

```bash
pip install pyinstaller
pyinstaller --onefile --add-data "templates;templates" --add-data "static;static" app.py
# 产物：dist/app.exe
```

---## 🔐 鉴权说明

从 **v2.1** 起，所有写操作 / 算力消耗端点都受 `X-API-Token` 保护。

| 模式 | `API_TOKEN` 环境变量 | 行为 |
|---|---|---|
| 开发（默认） | 未设置 | 写操作放行，logger.debug 提示 |
| 生产 | 已设置 | 缺少/错误 `X-API-Token` 头 → `401 Unauthorized` |

前端调用示例：

```javascript
// static/js/api.js
const resp = await fetch('/api/predict', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Token': window.__API_TOKEN__
  },
  body: JSON.stringify({ algorithm: 'comprehensive', generations: 5 })
});
```

被保护的端点：`/predict` `/check` `/auto-check` `/backup` `/restore` `/import` `/import-text` `/clear-data` `/my-numbers` `/fetch-latest` `/fetch-history` `/cache/clear`。读操作（GET）无需 token。

---## 🏗️ 技术栈

- **[Flask 3.0](https://flask.palletsprojects.com/)** — Web 框架
- **[Flask-Limiter](https://flask-limiter.readthedocs.io/)** — 全局限流（`200/天, 50/小时`，开发模式默认内存存储，生产建议配 Redis）
- **[Playwright + playwright-stealth](https://playwright.dev/python/)** — 反爬虫对抗 + JS 渲染兜底
- **[beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/)** — HTML 解析
- **[fake-useragent](https://github.com/fake-useragent/fake-useragent)** — UA 随机化
- **自研内存缓存** — TTL + LRU 淘汰，零外部依赖
- **PyInstaller** — Windows 单文件打包（可选）

---## 📂 项目结构

```
ssq-platform/
├── app.py                       # Flask 主应用 + 蓝图注册 + 速率限制
├── config.py                    # 配置常量 + 启动安全检查
├── start.bat                    # Windows 一键启动
├── requirements.txt             # 锁定版本依赖
├── README.md
├── LICENSE                      # MIT
│
├── src/
│   ├── api/api.py               # /api/* 蓝图（23 个端点）
│   ├── algorithms/              # 13 种预测算法实现
│   │   ├── base.py              #   基类 + 加权采样工具
│   │   ├── weighted_random.py   #   加权随机
│   │   ├── normal_distribution.py
│   │   ├── genetic.py           #   遗传算法
│   │   ├── monte_carlo.py       #   蒙特卡洛
│   │   ├── comprehensive.py     #   综合推荐
│   │   ├── smart_recommendation.py
│   │   ├── zone_distribution.py
│   │   ├── consecutive_analysis.py
│   │   ├── same_tail_analysis.py
│   │   ├── prime_composite.py
│   │   ├── big_small_analysis.py
│   │   ├── markov_chain.py
│   │   └── kmeans_clustering.py
│   ├── analyzer.py              # 数据分析（频次 / 遗漏 / 和值 / AC）
│   ├── cache.py                 # 内存缓存（TTL + LRU）
│   ├── crawler.py               # 多源爬虫 + 数据持久化
│   ├── online_fetcher.py        # 500 网专用 fetcher
│   └── predictor.py             # 算法调度器 + LRU 实例缓存
│
├── tests/
│   └── test_core.py             # 单元测试（23 项）
│
├── scripts/
│   └── test_online_fetch.py     # 在线抓取诊断脚本
│
├── templates/
│   ├── index.html               # 主页面（单页应用）
│   └── diagnose.html
│
├── static/
│   ├── css/style.css            # 主题样式
│   ├── js/                      # JS 模块
│   └── manifest.json            # PWA manifest
│
├── docs/                        # 文档 / 截图
├── data/                        # 运行时数据（gitignore）
│   ├── history.json             #   历史开奖数据
│   ├── my_numbers.json          #   收藏号码
│   └── backup/                  #   自动备份（保留最近 5 份）
└── logs/                        # 运行时日志（gitignore）
```

---## 📝 API 一览

| Method | Path | 用途 | 鉴权 |
|---|---|---|---|
| GET | `/` | 主页面 | — |
| GET | `/diagnose` | 诊断页面 | — |
| GET | `/api/health` | 健康检查 | — |
| GET | `/api/history` | 历史数据（带分页） | — |
| GET | `/api/history/raw` | 原始历史（导出用） | — |
| GET | `/api/analysis` | 综合分析报告 | — |
| POST | `/api/predict` | 生成预测 | ✅ |
| GET | `/api/statistics` | 统计信息 | — |
| POST | `/api/check` | 检查号码与历史匹配 | ✅ |
| POST | `/api/auto-check` | 自动对奖 | ✅ |
| GET | `/api/latest` | 最新一期 | — |
| POST | `/api/fetch-latest` | 抓取最新一期 | ✅ |
| POST | `/api/fetch-history` | 抓取历史数据 | ✅ |
| POST | `/api/backup` | 创建备份 | ✅ |
| GET | `/api/backups` | 备份列表 | — |
| DELETE | `/api/backup/` | 删除指定备份 | ✅ |
| POST | `/api/restore` | 从备份恢复 | ✅ |
| POST | `/api/import` | 导入（JSON/CSV/TXT） | ✅ |
| POST | `/api/import-text` | 导入（粘贴文本） | ✅ |
| POST | `/api/clear-data` | 清空历史 | ✅ |
| GET/POST | `/api/my-numbers` | 收藏号码读写 | POST ✅ |
| GET | `/api/export/my-numbers` | 导出收藏 | — |
| GET | `/api/export/history` | 导出历史 | — |
| GET | `/api/cache/stats` | 缓存统计 | — |
| POST | `/api/cache/clear` | 清空缓存 | ✅ |

---### 调用示例

```bash
# 生成 5 注综合推荐预测
curl -X POST http://localhost:5000/api/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Token: $API_TOKEN" \
  -d '{"algorithm": "comprehensive", "generations": 5}'

# 抓取最新一期开奖
curl -X POST http://localhost:5000/api/fetch-latest \
  -H "X-API-Token: $API_TOKEN"

# 检查号码 [3, 6, 13, 21, 28, 29] + 蓝球 6 的历史匹配
curl -X POST http://localhost:5000/api/check \
  -H "Content-Type: application/json" \
  -H "X-API-Token: $API_TOKEN" \
  -d '{"red_balls": [3, 6, 13, 21, 28, 29], "blue_ball": 6}'
```

---## 📋 v2.1 变更摘要

相比 v2.0，本版本以 **bugfix + 安全加固** 为主：

### 修复

- **crawler.py 方法重复定义** — 4 个方法（`_fetch_cwl_html` / `_fetch_with_requests` / `_fetch_with_playwright` / `_parse_cwl_html`）定义了两次，Python 取最后一份掩盖 bug。删除重复版本，仅保留含 curl_cffi 优化的实现。文件从 1224 行 → 1072 行
- **`/api/backup/` DELETE 路由 bug** — 路径尾 `/` + Flask 默认 `strict_slashes=True` 导致永远 404。改为 `/backup/` + `os.path.basename` 路径遍历防御
- **`_parse_cwl_html_robust` 月份过滤吃掉合法红球** — 旧代码按值范围 `1-12` 过滤"月份碎片"，但 01-12 也是合法红球。改为基于位置的 `skip_set`，只跳过已知 `issue/date` 成员
- **analyzer.get_missing_stats 数据顺序依赖** — 函数假设 `self.data` 已按期号降序，新增防御性排序 + 显式 docstring

### 安全

- **`SECRET_KEY` 启动校验** — 移除硬编码默认值字符串；DEBUG 模式自动生成 64 字符临时密钥 + warn；生产模式未设 / 用默认值 → `raise SystemExit` 拒绝启动
- **写操作 API_TOKEN 鉴权** — 13 个写 / 计算端点加 `@require_api_token` 装饰器，校验 `X-API-Token` header；开发模式放行，生产模式必须设置 `API_TOKEN` 环境变量
- **`import config` 替代 `from config import SECRET_KEY`** — 修复 `ensure_security_config()` 自动生成后本地变量未刷新的问题

### 清理

- **删除 `src/storage.py` 死代码**（222 行 + TestStorage 测试）— 设计了 JSONStorage / SQLiteStorage 抽象层但全项目无人调用，删除后 codebase 更干净

---## 🐛 故障排查

**Q: 启动报 `[SECURITY] 生产环境必须设置 SECRET_KEY`**

A: 你要么忘了设置 `FLASK_DEBUG=False`，要么没设 `SECRET_KEY`。生产部署必须显式设置：

```bash
export FLASK_DEBUG=False
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

---

**Q: 写操作返回 401 Unauthorized**

A: `API_TOKEN` 已设置但请求没带 `X-API-Token` 头，或 token 不匹配。前端代码：

```javascript
fetch('/api/predict', {
  headers: { 'X-API-Token': '<你的 token>' }
});
```

---

**Q: 爬虫抓取失败**

A: 500 彩票网 / 中彩网经常更新反爬策略，可能需要：
1. 检查 `playwright install chromium` 是否完成
2. 查看 `logs/app.log` 详细错误
3. 如果用了 VPN / 代理，可能被识别

> ⚠️ **法律提示**：高频爬取第三方网站可能违反其服务条款 / robots.txt。请控制频率（默认 `delay=1s`），并将本工具定位为**个人学习**用途。

---

**Q: `pip install` 报 `playwright` 错误**

A: Windows 上 `playwright install chromium` 会下载 ~150MB 浏览器二进制。如果下载慢，可设置：

```bash
set PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright
playwright install chromium
```

---

**Q: 端口 5000 被占用**

A: 修改 `config.py` 中 `WEB_CONFIG['port']`，或启动时 `app.run(port=5001)`。

---## 📄 许可证

[MIT](LICENSE) © 2026 liuhua1202

---

## 🙏 致谢

- 数据来源：[500 彩票网](https://www.500.com/) / [中彩网](http://www.zhcw.com/) / [福彩官网](https://www.cwl.gov.cn/)
- 算法灵感：[马尔可夫链蒙特卡洛](https://en.wikipedia.org/wiki/Markov_chain_Monte_Carlo) / [K-Means](https://en.wikipedia.org/wiki/K-means_clustering) / [遗传算法](https://en.wikipedia.org/wiki/Genetic_algorithm)

---

> 🎲 再次提醒：**彩票是娱乐，不是投资**。请理性购彩，未成年人禁止购买。