# =============================================================================
# 双色球预测平台 - 生产环境 Dockerfile
# =============================================================================
# 多阶段构建:
#   - builder: 安装 Python 依赖和 Playwright 浏览器
#   - runtime: 精简运行时镜像, 只包含必要组件
# 参考: https://docs.docker.com/develop/develop-images/multistage-build/
# =============================================================================

# -----------------------------------------------------------------------------
# 阶段 1: builder
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

# 元数据
LABEL maintainer="ssq-platform" \
      version="2.2" \
      description="双色球预测平台 (SSQ Prediction Platform)"

# 避免 Python 生成 .pyc / 强制 stdout 无缓冲
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Playwright 浏览器安装路径 (供后续阶段 COPY)
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

# 系统依赖 (构建阶段需要 build-essential 用于某些 wheel)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# 先复制 requirements 单独安装依赖 (利用 Docker 缓存)
COPY requirements.txt .

# 安装 Python 依赖到指定目录 (供后续阶段 COPY)
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt

# 安装 playwright 但不下载浏览器 (在运行时阶段下载, 减小 builder 镜像)
RUN pip install --prefix=/install --no-cache-dir playwright==1.48.0 playwright-stealth==1.0.6

# 下载 Playwright 浏览器 (chromium)
RUN mkdir -p ${PLAYWRIGHT_BROWSERS_PATH} && \
    /install/bin/playwright install chromium && \
    /install/bin/playwright install-deps chromium 2>&1 | tail -5 || true

# -----------------------------------------------------------------------------
# 阶段 2: runtime
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
    PORT=5000 \
    WEB_CONCURRENCY=2

# Playwright 运行时的系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
        # 基础
        ca-certificates \
        curl \
        tini \
        # Playwright Chromium 运行时
        # (curl_cffi 通过 pyinstaller 捆绑的浏览器, 不需要额外系统依赖)
        libnss3 \
        libnspr4 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libpango-1.0-0 \
        libcairo2 \
        libasound2 \
        libxshmfence1 \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 阶段复制 Python 环境
COPY --from=builder /install /usr/local

# 从 builder 阶段复制 Playwright 浏览器
COPY --from=builder /opt/playwright /opt/playwright

# 创建非 root 用户 (安全最佳实践)
RUN groupadd --system --gid 1001 ssq && \
    useradd --system --uid 1001 --gid ssq --home-dir /app --shell /bin/false ssq

WORKDIR /app

# 复制应用代码 (利用 .dockerignore 排除 tests / .git / 等)
COPY --chown=ssq:ssq config.py app.py ./
COPY --chown=ssq:ssq src/ ./src/
COPY --chown=ssq:ssq templates/ ./templates/
COPY --chown=ssq:ssq static/ ./static/

# 运行时数据目录 (history / backups / logs)
RUN mkdir -p /app/data/backup /app/logs && \
    chown -R ssq:ssq /app

USER ssq

EXPOSE 5000

# 健康检查 (Flask /api/health 返回 JSON)
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:${PORT}/api/health || exit 1

# tini 作为 PID 1, 正确处理信号 (SIGTERM/SIGINT) 和僵尸进程
ENTRYPOINT ["/usr/bin/tini", "--"]

# 生产模式启动 gunicorn
#   - 2 workers (默认, 可通过 WEB_CONCURRENCY 环境变量调整)
#   - 同步 worker 类型 (爬虫阻塞请求)
#   - access log 走 stdout
CMD ["sh", "-c", "gunicorn \
        --bind 0.0.0.0:${PORT} \
        --workers ${WEB_CONCURRENCY} \
        --worker-class sync \
        --timeout 120 \
        --graceful-timeout 30 \
        --access-logfile - \
        --error-logfile - \
        app:app"]
