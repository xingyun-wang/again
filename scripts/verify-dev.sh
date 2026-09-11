#!/usr/bin/env bash
# verify-dev.sh — W1-T1 验证后端 8000 + 前端 5173 + /health
# 退出码：0 = 都通；1 = 任一不在或 /health 不对

set -euo pipefail

PORTS=(5173 8000)
MISSING=()

# 一次抓全 listening 信息
LISTEN_OUT="$(ss -ltn 2>/dev/null || true)"

for PORT in "${PORTS[@]}"; do
    if echo "${LISTEN_OUT}" | grep -E "[:.]${PORT}[[:space:]]" | grep -q LISTEN; then
        echo "[verify] port ${PORT} ✓ listening"
    else
        echo "[verify] port ${PORT} ✗ NOT listening" >&2
        MISSING+=("${PORT}")
    fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo "[verify] FAIL：缺端口 ${MISSING[*]}" >&2
    echo "[verify] 提示：跑 scripts/start-dev.sh 启服务" >&2
    exit 1
fi

# 后端 /health 真实可达且 JSON 正确
HEALTH_JSON="$(curl -sf http://127.0.0.1:8000/health 2>/dev/null || true)"
if [[ -z "${HEALTH_JSON}" ]]; then
    echo "[verify] port 8000 listening 但 /health 不可达" >&2
    exit 1
fi
if ! echo "${HEALTH_JSON}" | grep -q '"status":"ok"'; then
    echo "[verify] /health 返回非 ok：${HEALTH_JSON}" >&2
    exit 1
fi
echo "[verify] /health ✓ ${HEALTH_JSON}"

echo "[verify] PASS：5173 + 8000 都通，/health ok"
exit 0
