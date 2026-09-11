#!/bin/bash
# setup-backend.sh — W1-T2b: 一次性 bootstrap 后端环境（幂等可重跑）
#
# 用法：
#   bash backend/scripts/setup-backend.sh
#
# 行为：
#   1. 检测 .venv-backend layout（真 venv vs pip --target 散装）
#   2. 缺则创建（优先真 venv，ensurepip 失败时 fallback 到 pip --target）
#   3. 缺依赖则装（阿里源，--timeout 60 --retries 3）
#   4. 验证 sqlalchemy/fastapi/uvicorn/pydantic 可导入
#   5. 跑 init-db.py（create_all 幂等，不破坏数据）
#
# 幂等：第二次跑会跳过装依赖，只跑 init-db。
# 不依赖 VIRTUAL_ENV：所有调用都用绝对路径或显式 PYTHONPATH。

set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$BACKEND_DIR/.venv-backend"
REQUIREMENTS="$BACKEND_DIR/requirements.txt"
PIP_INDEX="https://mirrors.aliyun.com/pypi/simple/"
PIP_TIMEOUT_OPTS="--timeout 60 --retries 3"

# === 1. 检测 python3 ===
if ! command -v python3 &>/dev/null; then
    echo "[setup] FAIL: python3 not found" >&2
    exit 1
fi
echo "[setup] python3: $(python3 --version) ($(command -v python3))"

# === 2. 检测现有 layout ===
#   真 venv layout:  有 bin/python3 + lib/python3.8/site-packages/
#   pip --target:    无 bin/，包散装在 VENV_DIR 顶层
detect_layout() {
    if [[ -d "$VENV_DIR/bin" ]] && [[ -d "$VENV_DIR/lib/python3.8/site-packages" ]]; then
        echo "venv"
    elif [[ -d "$VENV_DIR" ]] && [[ -n "$(ls -A "$VENV_DIR" 2>/dev/null | grep -v -E '^(bin|include|lib|lib64|pyvenv.cfg)$')" ]]; then
        echo "target"
    else
        echo "missing"
    fi
}

LAYOUT="$(detect_layout)"
echo "[setup] 当前 layout: ${LAYOUT}"

# === 3. 检查依赖是否齐全（按 layout 走）===
deps_ok() {
    case "$1" in
        venv)
            [[ -x "$VENV_DIR/bin/python3" ]] && \
                "$VENV_DIR/bin/python3" -c "import sqlalchemy, fastapi, uvicorn, pydantic" 2>/dev/null
            ;;
        target)
            PYTHONPATH="$VENV_DIR" python3 -c "import sqlalchemy, fastapi, uvicorn, pydantic" 2>/dev/null
            ;;
        *)
            return 1
            ;;
    esac
}

NEED_INSTALL=0
if deps_ok "$LAYOUT"; then
    echo "[setup] 依赖齐全（layout=${LAYOUT}），跳过 pip install"
else
    echo "[setup] 依赖不全（layout=${LAYOUT}），需要装"
    NEED_INSTALL=1
fi

# === 4. 创建/重建 venv（如缺）===
if [[ "$LAYOUT" == "missing" ]]; then
    echo "[setup] 创建 venv ..."
    if python3 -m venv "$VENV_DIR" 2>/dev/null && \
       [[ -x "$VENV_DIR/bin/python3" ]] && \
       [[ -d "$VENV_DIR/lib/python3.8/site-packages" ]]; then
        echo "[setup] 真 venv 创建成功"
        LAYOUT="venv"
    else
        echo "[setup] 真 venv 失败（缺 ensurepip），fallback 到 pip --target"
        rm -rf "$VENV_DIR"
        mkdir -p "$VENV_DIR"
        LAYOUT="target"
    fi
fi

# === 5. 装依赖（按 layout 走）===
if [[ "$NEED_INSTALL" == "1" ]]; then
    echo "[setup] 安装依赖（layout=${LAYOUT}）..."
    case "$LAYOUT" in
        venv)
            "$VENV_DIR/bin/python3" -m pip install \
                ${PIP_TIMEOUT_OPTS} \
                -i "$PIP_INDEX" \
                -r "$REQUIREMENTS"
            ;;
        target)
            python3 -m pip install \
                ${PIP_TIMEOUT_OPTS} \
                -i "$PIP_INDEX" \
                --target "$VENV_DIR" \
                -r "$REQUIREMENTS"
            ;;
        *)
            echo "[setup] FAIL: 未知 layout '$LAYOUT'" >&2
            exit 1
            ;;
    esac
fi

# === 6. 验证依赖 ===
echo "[setup] 验证依赖 ..."
if ! deps_ok "$LAYOUT"; then
    echo "[setup] FAIL: 依赖导入失败（layout=${LAYOUT}）" >&2
    exit 1
fi
case "$LAYOUT" in
    venv)
        echo "[setup]   sqlalchemy=$("$VENV_DIR/bin/python3" -c 'import sqlalchemy; print(sqlalchemy.__version__)')"
        ;;
    target)
        echo "[setup]   sqlalchemy=$(PYTHONPATH="$VENV_DIR" python3 -c 'import sqlalchemy; print(sqlalchemy.__version__)')"
        ;;
esac

# === 7. 跑 init-db（按 layout 走）===
echo "[setup] 初始化数据库（layout=${LAYOUT}）..."
case "$LAYOUT" in
    venv)
        "$VENV_DIR/bin/python3" "$BACKEND_DIR/scripts/init-db.py"
        ;;
    target)
        PYTHONPATH="$VENV_DIR" python3 "$BACKEND_DIR/scripts/init-db.py"
        ;;
esac

echo "[setup] OK"
