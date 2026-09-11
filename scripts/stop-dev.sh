#!/usr/bin/env bash
# stop-dev.sh — 按 .run/<port>.pid kill 干净
# 不强制 kill 端口占用者（避免误杀非本脚本的进程）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUN_DIR="${PROJECT_ROOT}/.run"

if [[ ! -d "${RUN_DIR}" ]]; then
    echo "[stop-dev] ${RUN_DIR} 不存在，没东西可停"
    exit 0
fi

PORTS=(5173 8000)
STOPPED=0
MISSING=0

for PORT in "${PORTS[@]}"; do
    PID_FILE="${RUN_DIR}/${PORT}.pid"

    if [[ ! -f "${PID_FILE}" ]]; then
        echo "[stop-dev] port ${PORT} 无 pid 文件（没启过？已停？）"
        MISSING=$((MISSING + 1))
        continue
    fi

    PID="$(cat "${PID_FILE}")"
    if [[ -z "${PID}" ]]; then
        echo "[stop-dev] port ${PORT} pid 文件为空，跳过"
        rm -f "${PID_FILE}"
        MISSING=$((MISSING + 1))
        continue
    fi

    if kill -0 "${PID}" 2>/dev/null; then
        # 进程活着：先 TERM，等一下，不行再 KILL
        kill -TERM "${PID}" 2>/dev/null || true
        # 等最多 2 秒
        for _ in 1 2 3 4 5 6 7 8 9 10; do
            if ! kill -0 "${PID}" 2>/dev/null; then
                break
            fi
            sleep 0.2
        done
        if kill -0 "${PID}" 2>/dev/null; then
            echo "[stop-dev] port ${PORT} pid=${PID} TERM 不响应，KILL" >&2
            kill -KILL "${PID}" 2>/dev/null || true
        fi
        # 领头的死了，但 vite/npm 可能会留下 child worker 继续监听端口
        # （W1-T1 新增：node 系进程常见问题）
        if ss -ltn "sport = :${PORT}" 2>/dev/null | tail -n +2 | grep -q LISTEN; then
            # 找端口的 listener pid，杀掉
            REM_PID="$(ss -ltnp "sport = :${PORT}" 2>/dev/null | awk 'tolower($0) ~ /users:/ { match($0, /pid=([0-9]+)/, a); if (a[1] != "") print a[1] }' | head -1)"
            if [[ -n "${REM_PID}" ]] && [[ "${REM_PID}" != "${PID}" ]]; then
                echo "[stop-dev] port ${PORT} pid=${REM_PID} 还在 listen（孤儿），补杀" >&2
                kill -TERM "${REM_PID}" 2>/dev/null || true
                sleep 0.5
                kill -KILL "${REM_PID}" 2>/dev/null || true
            fi
        fi
        echo "[stop-dev] port ${PORT} 已停（pid=${PID}）"
        STOPPED=$((STOPPED + 1))
    else
        echo "[stop-dev] port ${PORT} pid=${PID} 已不在（残留 pid 文件，清掉）"
        MISSING=$((MISSING + 1))
    fi

    rm -f "${PID_FILE}"
done

echo "[stop-dev] 停止 ${STOPPED} 个，缺失/已停 ${MISSING} 个"
exit 0
