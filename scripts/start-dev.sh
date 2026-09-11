#!/usr/bin/env bash
# start-dev.sh — W1-T1 启 FastAPI (uvicorn) + Vite (React + TS)
# 后端：uvicorn backend.app.main:app --port 8000 --host 127.0.0.1
# 前端：vite --port 5173 --host 127.0.0.1
# PID 写到 .run/<port>.pid，日志到 .run/<port>.log
#
# 顺序：node 版本检查 → venv 准备（缺则建；缺 pip 则从用户 site 补）→ 后端启动（wait-for-port 8000）→ npm install（如缺）→ 前端启动（wait-for-port 5173）
# 保留 T3 flock 防重入 + 端口占用检测 + wait-for-port 5s 轮询

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUN_DIR="${PROJECT_ROOT}/.run"
BACKEND_DIR="${PROJECT_ROOT}/backend"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"
VENV_DIR="${BACKEND_DIR}/.venv-backend"

mkdir -p "${RUN_DIR}"

# flock 防重入
LOCK_FILE="${RUN_DIR}/.start-dev.lock"
exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
    echo "[start-dev] 已有 start-dev 在跑（lock: ${LOCK_FILE}）" >&2
    exit 1
fi

# === Step 1: Node 版本检查（vite 要求 ≥18）===
if ! command -v node >/dev/null 2>&1; then
    echo "[start-dev] ✗ node 不在 PATH" >&2
    exit 1
fi
NODE_MAJOR=$(node -v | sed -E 's/^v([0-9]+).*/\1/')
if [[ "${NODE_MAJOR}" -lt 18 ]]; then
    echo "[start-dev] ✗ node 版本 $(node -v) 低于 18，vite 要求 ≥18" >&2
    exit 1
fi
echo "[start-dev] node $(node -v) ✓"

# === Step 2: 后端 venv 准备 ===
if [[ ! -d "${VENV_DIR}" ]]; then
    echo "[start-dev] 创建 venv: ${VENV_DIR}"
    # python3 -m venv 会调 ensurepip，一些发行版（缺 python3-venv）会失败但 venv 本身已建好
    python3 -m venv "${VENV_DIR}" > "${RUN_DIR}/venv-create.log" 2>&1 || true
    # 若 site-packages 为空（ensurepip 失败），从用户 site-packages 拷贝 pip+wheel
    if [[ ! -f "${VENV_DIR}/lib/python3.8/site-packages/pip/__init__.py" ]]; then
        echo "[start-dev] venv 内无 pip（ensurepip 可能不可用），从用户 site-packages 补"
        USER_SITE="$(python3 -c "import site; print(site.getusersitepackages())" 2>/dev/null || true)"
        if [[ -z "${USER_SITE}" || ! -d "${USER_SITE}/pip" ]]; then
            echo "[start-dev] ✗ 用户 site-packages 无 pip，无法 bootstrap venv" >&2
            echo "[start-dev] 提示：先在系统跑 python3 -m pip install --user pip" >&2
            exit 1
        fi
        cp -r "${USER_SITE}/pip"* "${VENV_DIR}/lib/python3.8/site-packages/" 2>&1 | tail -3 || true
        cp -r "${USER_SITE}/wheel"* "${VENV_DIR}/lib/python3.8/site-packages/" 2>&1 | tail -3 || true
    fi
    if [[ ! -x "${VENV_DIR}/bin/python3" ]]; then
        echo "[start-dev] ✗ venv 创建失败（无 python3）" >&2
        exit 1
    fi
fi

PYTHON_BIN="${VENV_DIR}/bin/python3"
if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "[start-dev] ✗ venv python 不存在: ${PYTHON_BIN}" >&2
    exit 1
fi

# 检查 fastapi 是否已装，没装就装
if ! "${PYTHON_BIN}" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
    echo "[start-dev] 装后端依赖（首次或 venv 新建）..."
    PIP_INDEX="https://mirrors.aliyun.com/pypi/simple/"
    if ! timeout 180 "${PYTHON_BIN}" -m pip install \
        --no-deps --disable-pip-version-check --timeout 60 --retries 3 \
        -i "${PIP_INDEX}" \
        -r "${BACKEND_DIR}/requirements.txt" \
        >> "${RUN_DIR}/pip-install.log" 2>&1; then
        echo "[start-dev] ✗ pip install 失败，看日志：${RUN_DIR}/pip-install.log" >&2
        exit 1
    fi
    echo "[start-dev] ✓ 后端依赖已装"
else
    echo "[start-dev] 后端依赖已存在，跳过 pip install"
fi

# === Step 2.5: 防御性 export PYTHONPATH（layout-aware）===
# .venv-backend 是 pip --target 散装或真 venv（无 bin/activate），uvicorn python 子进程
# 可能需要显式 PYTHONPATH 才能找到依赖。
VENV_SP="${VENV_DIR}/lib/python3.8/site-packages"
if [[ -d "${VENV_SP}" ]]; then
    # 真 venv layout：site-packages 在标准位置
    export PYTHONPATH="${VENV_SP}:${PYTHONPATH:-}"
else
    # pip --target 散装 layout：包在 VENV_DIR 顶层
    export PYTHONPATH="${VENV_DIR}:${PYTHONPATH:-}"
fi
echo "[start-dev] PYTHONPATH=${PYTHONPATH}"

# === Step 3: 启动后端（uvicorn）===
start_service() {
    local PORT="$1"
    local LOG_PREFIX="$2"
    shift 2

    local PID_FILE="${RUN_DIR}/${PORT}.pid"
    local LOG_FILE="${RUN_DIR}/${PORT}.log"

    # 幂等：若 PID 文件存在且进程还活着，跳过
    if [[ -f "${PID_FILE}" ]]; then
        local EXISTING_PID
        EXISTING_PID="$(cat "${PID_FILE}")"
        if [[ -n "${EXISTING_PID}" ]] && kill -0 "${EXISTING_PID}" 2>/dev/null; then
            echo "[start-dev] port ${PORT} 已在跑（pid=${EXISTING_PID}），跳过"
            return 0
        fi
        rm -f "${PID_FILE}"
    fi

    # 端口占用检查（不强制 kill）
    if ss -ltn "sport = :${PORT}" 2>/dev/null | tail -n +2 | grep -q LISTEN; then
        echo "[start-dev] 端口 ${PORT} 已被占用（非本脚本启动的进程），拒绝启动以免误杀" >&2
        echo "[start-dev] 请先确认占用者身份再处理：ss -ltnp 'sport = :${PORT}'" >&2
        exit 1
    fi

    # 启动：setsid 进新 session，写 pid
    : > "${LOG_FILE}"
    setsid "$@" >> "${LOG_FILE}" 2>&1 < /dev/null &
    local NEW_PID=$!
    echo "${NEW_PID}" > "${PID_FILE}"

    # 等端口真的 listen 上（& 立即返回，进程还要 bind）—— 最多等 5 秒
    local BOUND=0
    for _ in $(seq 1 25); do
        if ! kill -0 "${NEW_PID}" 2>/dev/null; then
            echo "[start-dev] ${LOG_PREFIX} 启动失败（pid=${NEW_PID} 已退出），看日志：${LOG_FILE}" >&2
            rm -f "${PID_FILE}"
            exit 1
        fi
        if ss -ltn 2>/dev/null | grep -E "[:.]${PORT}[[:space:]]" | grep -q LISTEN; then
            BOUND=1
            break
        fi
        sleep 0.2
    done

    if [[ "${BOUND}" -ne 1 ]]; then
        echo "[start-dev] ${LOG_PREFIX} 5 秒内未 listen，放弃（pid=${NEW_PID}），看日志：${LOG_FILE}" >&2
        kill -TERM "${NEW_PID}" 2>/dev/null || true
        rm -f "${PID_FILE}"
        exit 1
    fi

    echo "[start-dev] ${LOG_PREFIX} 已启动（pid=${NEW_PID}, port=${PORT}, log=${LOG_FILE}）"
}

start_service 8000 "backend uvicorn" \
    "${PYTHON_BIN}" "-m" "uvicorn" "app.main:app" \
    "--host" "127.0.0.1" "--port" "8000" \
    --app-dir "${BACKEND_DIR}"

# === Step 4: npm install（如已 node_modules 则跳过；必须在 frontend/ 里跑）===
if [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
    echo "[start-dev] 装前端依赖（首次，5 分钟超时）..."
    if ! (
        cd "${FRONTEND_DIR}" && \
        timeout 300 npm install --no-audit --no-fund \
            >> "${RUN_DIR}/npm-install.log" 2>&1
    ); then
        echo "[start-dev] ✗ npm install 失败/超时，看日志：${RUN_DIR}/npm-install.log" >&2
        exit 1
    fi
    echo "[start-dev] ✓ 前端依赖已装"
else
    echo "[start-dev] 前端依赖已存在（node_modules/），跳过 npm install"
fi

# === Step 5: 启动前端（vite，npm run dev 需要在 frontend/ 里跑）===
(
    cd "${FRONTEND_DIR}"
    start_service 5173 "frontend vite" \
        npm run dev -- --port 5173 --host 127.0.0.1
)

exit 0