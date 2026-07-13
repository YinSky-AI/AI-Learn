# =============================================================================
# AI 智能学习平台 - Backend Dockerfile
# Python 3.12-slim + FastAPI + Uvicorn
# =============================================================================

# -- Stage 1: 构建依赖层 --
FROM python:3.12-slim AS builder

WORKDIR /build

# 安装构建工具（编译 psycopg2-binary 依赖）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

# 先复制依赖文件，利用 Docker 缓存
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# -- Stage 2: 运行时镜像 --
FROM python:3.12-slim AS runtime

WORKDIR /app

# 安装运行时依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        curl && \
    rm -rf /var/lib/apt/lists/*

# 从 builder 复制已安装的 Python 包
COPY --from=builder /install /usr/local

# 复制项目源码
COPY . .

# 创建非 root 用户运行
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser && \
    chown -R appuser:appuser /app

USER appuser

# 暴露端口
EXPOSE 8000

# 使用 uvicorn 启动
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info", \
     "--access-log"]
