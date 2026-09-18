# ===== Stage 1: builder（含 dev 工具）=====
# 用途：跑 ruff / mypy / pytest（CI 等价物；docker build 时一次性校验，失败则镜像 build fail）
# 产物：/app 下装好所有依赖（含 ruff/mypy/pytest），源码完整 COPY 进来
# runtime 阶段会从这个 stage 复制 app/ + alembic/ + alembic.ini + scripts/ + tests/ + pyproject.toml
#
# M1-B B.0 修复：
# - builder pip install 加 "tenacity>=9.0.0"（pyproject 列了，但硬编码清单漏了，
#   app/core/llm/deepseek.py + tests/test_circuit_breaker.py 都 import tenacity）
# - runtime pip install 同样加（runtime 也会 import tenacity）
# - runtime COPY 加 scripts/（verify_deepseek_api.py 需要在容器内能跑真值 verify）
FROM python:3.11-slim AS builder

# 国内镜像源切源 + 装构建依赖
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null \
 || sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null \
 && apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=300

WORKDIR /app
COPY pyproject.toml ./
# 装运行时 + dev 依赖（builder 阶段需要 ruff/mypy/pytest 给 docker build 内的 lint）
# 关键：pip install --upgrade pip 必须也带 --index-url，否则会落到默认源 files.pythonhosted.org
# 国内网络下默认源 ~92kB/s 经常超时，Aliyun 镜像 ~5-10MB/s。PIP_DEFAULT_TIMEOUT=300 兜底网络抖动。
# M1-B B.0：硬编码清单必须与 pyproject.toml dependencies 对齐（M0 retro 教训），
# 否则 builder 跑 `python -m pytest -q` 时会 ImportError。
RUN pip install --no-cache-dir --index-url https://mirrors.tencent.com/pypi/simple/ --upgrade pip 2>/dev/null \
 || pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir \
        --index-url https://mirrors.tencent.com/pypi/simple/ \
        "fastapi>=0.115.0" "uvicorn[standard]>=0.32.0" "sqlalchemy>=2.0.36" \
        "psycopg[binary]>=3.2.3" "alembic>=1.14.0" "pymupdf>=1.24.0" \
        "pdfplumber>=0.11.0" "httpx>=0.27.0" "tenacity>=9.0.0" \
        "pydantic>=2.9.0" "pydantic-settings>=2.6.0" \
        "ruff>=0.7.0" "mypy>=1.13.0" "pytest>=8.3.0" "pytest-asyncio>=0.24.0"

COPY . .
# 在 builder 跑 lint / type-check / test（CI 镜像内做，不进 runtime）
# 这一层是 docker build 时跑，结果不进 runtime
# mypy 用 `mypy app`（匹配 pyproject.toml 的 files=["app"] 配置）—— CI 标准实践
# 不写 `mypy app tests/`，否则会覆盖 pyproject.toml 的 files 限制，把 tests/ 也拉进 strict 模式
# tests/ 的 conftest.py / helper 函数没标 type，扫了会 16+ 报错。
RUN ruff check . \
    && mypy app \
    && python -m pytest -q

# ===== Stage 2: runtime（仅运行时依赖 + non-root）=====
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=300

WORKDIR /app

# 装 curl 给 healthcheck 用
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null \
 || sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null \
 && apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 装运行时依赖（仅生产需要；省 ~50MB）
COPY pyproject.toml ./
# 同样给 pip upgrade 带 --index-url，避免落到默认源超时
# M1-B B.0：runtime 也加 tenacity（chat() 会 import）
RUN pip install --no-cache-dir --index-url https://mirrors.tencent.com/pypi/simple/ --upgrade pip 2>/dev/null \
 || pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir \
        --index-url https://mirrors.tencent.com/pypi/simple/ \
        "fastapi>=0.115.0" "uvicorn[standard]>=0.32.0" "sqlalchemy>=2.0.36" \
        "psycopg[binary]>=3.2.3" "alembic>=1.14.0" "pymupdf>=1.24.0" \
        "pdfplumber>=0.11.0" "httpx>=0.27.0" "tenacity>=9.0.0" \
        "pydantic>=2.9.0" "pydantic-settings>=2.6.0"

# 从 builder 复制源码（不含 dev 依赖）
COPY --from=builder /app/app /app/app
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini
# M1-B B.0：runtime 也要 COPY scripts/（verify_deepseek_api.py 在容器内能跑真值 verify）
COPY --from=builder /app/scripts /app/scripts
COPY --from=builder /app/tests /app/tests
COPY --from=builder /app/pyproject.toml /app/pyproject.toml

# 创建非 root user（uid 1000 = 容器内常见首个可登录 uid）
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# 默认启动（alembic upgrade head 由 docker-compose 控制）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]