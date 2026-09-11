#!/usr/bin/env bash
# test-api.sh — W1-T4 集成测试全套。
#
# 跑法：bash backend/scripts/test-api.sh
# 前置：dev 服务已启（8000 listen）。
#
# 步骤：
#   0. 重置 DB（init + seed，让测试从干净状态开始）
#   1. 创建老师 → 取 TID
#   2. 创建班级 → 取 CID
#   3. CSV 批量导入学生
#   4. 单个改密
#   5. 批量改密
#
# 约定：
# - set -euo pipefail：任一 curl 失败立刻中止
# - curl -sf：HTTP 非 2xx 即报错，配合 set -e 让脚本 fail-fast
# - 用 python3 -c 'import json,sys; print(...)' 解析 JSON 拿 ID

set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000}"
BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHONPATH=".venv-backend/lib/python3.8/site-packages" \
    PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "=== Step 0: 重置 DB + 种子 ==="
cd "${BACKEND_DIR}"
"${PYTHON_BIN}" scripts/init-db.py >/dev/null
"${PYTHON_BIN}" scripts/seed-test-data.py >/dev/null
echo "  ✓ init + seed 完成"

echo "=== Step 1: 创建老师 ==="
TID=$(curl -sf -X POST "${BASE}/api/teachers" \
    -H "Content-Type: application/json" \
    -d '{"name":"测试老师A"}' \
    | "${PYTHON_BIN}" -c "import json,sys;print(json.load(sys.stdin)['id'])")
echo "  ✓ teacher created: TID=${TID}"

echo "=== Step 2: 创建班级 ==="
CID=$(curl -sf -X POST "${BASE}/api/classes" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"高二(2)班\",\"grade\":2,\"teacher_id\":${TID}}" \
    | "${PYTHON_BIN}" -c "import json,sys;print(json.load(sys.stdin)['id'])")
echo "  ✓ class created: CID=${CID}"

echo "=== Step 3: CSV 批量导入学生 ==="
cat > /tmp/students.csv <<EOF
name,student_no
学生A,202602010
学生B,202602011
学生C,202602012
EOF
curl -sf -X POST "${BASE}/api/classes/${CID}/students/bulk-import" \
    -F "file=@/tmp/students.csv" \
    | "${PYTHON_BIN}" -m json.tool

echo "=== Step 4: 单个改密 ==="
SID=$(curl -sf "${BASE}/api/classes/${CID}/students" \
    | "${PYTHON_BIN}" -c "import json,sys;print(json.load(sys.stdin)[0]['id'])")
echo "  取首个学生 SID=${SID}"
curl -sf -X POST "${BASE}/api/students/${SID}/change-password" \
    -H "Content-Type: application/json" \
    -d '{"new_password":"newpass123"}' \
    | "${PYTHON_BIN}" -m json.tool
echo "  ✓ single password changed"

echo "=== Step 5: 批量改密 ==="
curl -sf -X POST "${BASE}/api/classes/${CID}/students/reset-passwords" \
    -H "Content-Type: application/json" \
    -d '{"default_password":"reset123"}' \
    | "${PYTHON_BIN}" -m json.tool
echo "  ✓ batch password reset"

echo "=== ALL TESTS PASSED ==="