FROM python:3.11-slim

# 国内镜像源（apt + pip）。决策室授权的 judgment call —— 默认源在家庭网络下慢/不可达，
# Aliyun apt + Aliyun PyPI 是国内 build 的最低阻力配置。
# 清华 PyPI 不稳定（fastapi 0.115+ 拿不到），Aliyun 镜像在家庭网络下稳。
# pip 用 --index-url flag（per-RUN 显式）而非 ENV（避免污染容器全局 pip 配置）。

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 装系统依赖（curl 给 alembic/healthcheck 用；build-essential 给 psycopg 兜底）
# 先切 Aliyun apt 源（国内），再装包
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null \
 || sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null \
 && apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖（利用 Docker 缓存）
COPY pyproject.toml ./
# 国内 pip 镜像源（决策室授权）。pypi.org 默认 ~92kB/s（pymupdf 25.8MB 要 3+ 分钟；
# mypy 15.1MB 要 2+ 分钟；ruff 10.4MB 要 1+ 分钟）。Aliyun 镜像 ~5-10MB/s，
# build 时间压缩 50-100 倍。CI（GitHub Actions）走官方源——本 flag 仅 build-time 生效。
RUN pip install --upgrade pip \
    && pip install --no-cache-dir \
        --index-url https://mirrors.aliyun.com/pypi/simple/ \
        "fastapi>=0.115.0" \
        "uvicorn[standard]>=0.32.0" \
        "sqlalchemy>=2.0.36" \
        "psycopg[binary]>=3.2.3" \
        "alembic>=1.14.0" \
        "pymupdf>=1.24.0" \
        "pdfplumber>=0.11.0" \
        "httpx>=0.27.0" \
        "pydantic>=2.9.0" \
        "pydantic-settings>=2.6.0" \
        "ruff>=0.7.0" \
        "mypy>=1.13.0" \
        "pytest>=8.3.0" \
        "pytest-asyncio>=0.24.0"

# 复制源码
COPY . .

EXPOSE 8000

# 默认启动命令（alembic upgrade head + uvicorn 由 docker-compose 控制）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
