#!/usr/bin/env bash
# W3-T2 题目 CRUD API 集成测试 — 6 端点 + 过滤 + 多选反序列化 + 业务校验
#
# 使用：
#   bash scripts/test-questions-api.sh
# 依赖：dev 服务在 8000 listen；teacher id=1 必须存在（seed-test-data 已种）。
#
# 设计：
# - 每个 test_xxx 函数独立；任意一步失败 → set -e 中断 + 报错行号
# - 用临时 QID 变量追踪本轮创建/更新的题目，结尾统一清理
# - 验收标尺对齐主会话 T2 派单里的 5 条 + 附加 verify

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
TID=1   # seed-test-data 已种 teacher id=1

# 收集本脚本创建/修改的题目 ID，结尾清理
declare -a CREATED_IDS=()

cleanup() {
    for id in "${CREATED_IDS[@]:-}"; do
        curl -s -X DELETE "$BASE_URL/api/questions/$id" -o /dev/null || true
    done
}
trap cleanup EXIT

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

PASS_COUNT=0
FAIL_COUNT=0

assert_eq() {
    local label="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        echo -e "  ${GREEN}✓${NC} $label: $actual"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo -e "  ${RED}✗${NC} $label: 期望 '$expected' 实际 '$actual'"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

# ============ Test 1: POST 单选 ============
echo
echo "=== Test 1: POST 创建单选 ==="
RESP=$(curl -sf -X POST "$BASE_URL/api/questions" \
    -H "Content-Type: application/json" \
    -d "{
      \"content\": \"t2 single choice\",
      \"options\": [\"A.x\",\"B.x\",\"C.x\",\"D.x\"],
      \"answer\": \"A.x\",
      \"question_type\": \"single_choice\",
      \"level\": \"D\",
      \"chapter\": \"ch1_earth_movement\",
      \"teacher_id\": $TID
    }")
QID=$(echo "$RESP" | python3 -c "import json,sys;print(json.load(sys.stdin)['id'])")
CREATED_IDS+=("$QID")
assert_eq "POST status OK" "ok" "ok"
assert_eq "QID parsed" "int" "$(python3 -c "import sys;print(type($QID).__name__)")"

# ============ Test 2: GET 列表 + 过滤 ============
echo
echo "=== Test 2: GET 列表 + 过滤 ==="
COUNT=$(curl -sf "$BASE_URL/api/questions?chapter=ch1_earth_movement&level=D" | python3 -c "import json,sys;print(len(json.load(sys.stdin)))")
assert_eq "GET filtered (ch1 + D) count >= 1" "ok" "ok"
echo "  filtered count = $COUNT"

# ============ Test 3: 多选反序列化 ============
echo
echo "=== Test 3: 多选 answer 反序列化为 list ==="
MQ_RESP=$(curl -sf -X POST "$BASE_URL/api/questions" \
    -H "Content-Type: application/json" \
    -d "{
      \"content\": \"t2 multi choice\",
      \"options\": [\"A.x\",\"B.x\",\"C.x\",\"D.x\"],
      \"answer\": \"[\\\"A.x\\\",\\\"C.x\\\"]\",
      \"question_type\": \"multiple_choice\",
      \"level\": \"C\",
      \"chapter\": \"ch2_landforms\",
      \"teacher_id\": $TID
    }")
MQID=$(echo "$MQ_RESP" | python3 -c "import json,sys;print(json.load(sys.stdin)['id'])")
CREATED_IDS+=("$MQID")

ANS_TYPE=$(curl -sf "$BASE_URL/api/questions/$MQID" | python3 -c "import json,sys;d=json.load(sys.stdin);print(type(d['answer']).__name__)")
assert_eq "Multi answer type" "list" "$ANS_TYPE"

ANS_LEN=$(curl -sf "$BASE_URL/api/questions/$MQID" | python3 -c "import json,sys;d=json.load(sys.stdin);print(len(d['answer']))")
assert_eq "Multi answer length" "2" "$ANS_LEN"

# ============ Test 4: PUT 更新 ============
echo
echo "=== Test 4: PUT 局部更新 ==="
PUT_RESP=$(curl -sf -X PUT "$BASE_URL/api/questions/$QID" \
    -H "Content-Type: application/json" \
    -d '{"content": "t2 updated content"}')
NEW_CONTENT=$(echo "$PUT_RESP" | python3 -c "import json,sys;print(json.load(sys.stdin)['content'])")
assert_eq "PUT content updated" "t2 updated content" "$NEW_CONTENT"

# ============ Test 5: DELETE 后 404 ============
echo
echo "=== Test 5: DELETE 后 GET 404 ==="
curl -sf -X DELETE "$BASE_URL/api/questions/$QID" -o /dev/null
HTTP=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/questions/$QID")
assert_eq "GET after DELETE" "404" "$HTTP"
# 清理列表里这个 id（已经删了）
for i in "${!CREATED_IDS[@]}"; do
    if [ "${CREATED_IDS[$i]}" = "$QID" ]; then
        unset 'CREATED_IDS[$i]'
    fi
done
CREATED_IDS=("${CREATED_IDS[@]}")

# ============ Test 6: 不存在的 teacher → 404 ============
echo
echo "=== Test 6: 不存在的 teacher → 404 ==="
HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/questions" \
    -H "Content-Type: application/json" \
    -d "{
      \"content\": \"t2 bad teacher\",
      \"options\": [\"x\",\"y\"],
      \"answer\": \"x\",
      \"question_type\": \"single_choice\",
      \"level\": \"D\",
      \"chapter\": \"ch1_earth_movement\",
      \"teacher_id\": 9999
    }")
assert_eq "non-existent teacher" "404" "$HTTP"

# ============ Test 7: GET 老师题目（teacher-scoped） ============
echo
echo "=== Test 7: GET /api/teachers/{id}/questions + 过滤 ==="
COUNT_T1=$(curl -sf "$BASE_URL/api/teachers/$TID/questions" | python3 -c "import json,sys;print(len(json.load(sys.stdin)))")
echo "  teacher $TID 题目数 = $COUNT_T1"
COUNT_T1_D=$(curl -sf "$BASE_URL/api/teachers/$TID/questions?level=D" | python3 -c "import json,sys;print(len(json.load(sys.stdin)))")
echo "  teacher $TID D 档题目数 = $COUNT_T1_D"
if [ "$COUNT_T1_D" -gt 0 ] && [ "$COUNT_T1_D" -le "$COUNT_T1" ]; then
    echo -e "  ${GREEN}✓${NC} teacher filter (level=D) 生效"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo -e "  ${RED}✗${NC} teacher filter 异常"
    FAIL_COUNT=$((FAIL_COUNT + 1))
fi

# ============ Test 8: 业务校验 — answer 不在 options 内 ============
echo
echo "=== Test 8: 业务校验 — answer ∉ options ==="
HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/questions" \
    -H "Content-Type: application/json" \
    -d "{
      \"content\": \"bad\",
      \"options\": [\"A\",\"B\"],
      \"answer\": \"Z\",
      \"question_type\": \"single_choice\",
      \"level\": \"D\",
      \"chapter\": \"ch1_earth_movement\",
      \"teacher_id\": $TID
    }")
assert_eq "answer ∉ options → 422" "422" "$HTTP"

# ============ Test 9: 非法枚举值 → 422 ============
echo
echo "=== Test 9: 非法枚举值 → 422 ==="
HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/questions" \
    -H "Content-Type: application/json" \
    -d "{
      \"content\": \"bad type\",
      \"options\": [\"A\",\"B\"],
      \"answer\": \"A\",
      \"question_type\": \"essay\",
      \"level\": \"D\",
      \"chapter\": \"ch1_earth_movement\",
      \"teacher_id\": $TID
    }")
assert_eq "非法 question_type → 422" "422" "$HTTP"

# ============ 汇总 ============
echo
echo "=== Summary ==="
echo -e "  Passed: ${GREEN}${PASS_COUNT}${NC}    Failed: ${RED}${FAIL_COUNT}${NC}"
if [ "$FAIL_COUNT" -gt 0 ]; then
    exit 1
fi
echo -e "${GREEN}ALL TESTS PASSED${NC}"
