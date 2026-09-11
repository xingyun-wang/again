#!/usr/bin/env bash
# W3 端到端集成测试 — T6
# 覆盖：建老师 → 建班级 → 批量导入学生 → 改密 → 建题库 → 生成作业（含反马太） → 审阅 → 发布
#
# 用法：bash backend/scripts/test-e2e-w3.sh
# 前置：dev 服务在跑（bash scripts/start-dev.sh && bash scripts/verify-dev.sh）
# 特性：set -eo pipefail（不用 -u，避免 helper 函数空参报错），任何 step 失败立即 exit 1

set -eo pipefail

BASE="http://localhost:8000"
BACKEND_DIR="/home/wsq_1/tiered-homework-platform/backend"
export PYTHONPATH="$BACKEND_DIR/.venv-backend/lib/python3.8/site-packages"

# Helper: assert_eq <actual> <expected> <message>
assert_eq() {
    local actual="$1" expected="$2" msg="$3"
    if [ "$actual" = "$expected" ]; then
        echo "  PASS: $msg (= $expected)"
    else
        echo "  FAIL: $msg (expected '$expected', got '$actual')"
        exit 1
    fi
}

echo "=== 准备：reset 数据库 + seed 测试数据 ==="
cd "$BACKEND_DIR"
python3 scripts/init-db.py 2>&1 | tail -3
python3 scripts/seed-test-data.py 2>&1 | tail -2
python3 scripts/seed-test-questions.py 2>&1 | tail -2
python3 scripts/seed-test-homeworks.py 2>&1 | tail -2
echo ""

echo "=== Step 1: 建老师 ==="
RESP=$(curl -sf -X POST "$BASE/api/teachers" \
    -H "Content-Type: application/json" \
    -d '{"name":"e2e老师"}')
TID=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
echo "  TID=$TID"
case "$TID" in
    ''|*[!0-9]*) echo "  FAIL: teacher id 非数字: $TID"; exit 1 ;;
    *) echo "  PASS: teacher id 是整数 ($TID)" ;;
esac
echo ""

echo "=== Step 2: 建班级 ==="
RESP=$(curl -sf -X POST "$BASE/api/classes" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"e2e班级\",\"grade\":2,\"teacher_id\":$TID}")
CID=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
echo "  CID=$CID"
echo ""

echo "=== Step 3: 批量导入学生（CSV）==="
cat > /tmp/e2e-students.csv <<EOF
name,student_no
e2e-学生1,e2e001
e2e-学生2,e2e002
e2e-学生3,e2e003
e2e-学生4,e2e004
e2e-学生5,e2e005
EOF
RESP=$(curl -sf -X POST "$BASE/api/classes/$CID/students/bulk-import" -F "file=@/tmp/e2e-students.csv")
INS=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['inserted'])")
FAILED=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['failed']))")
echo "  inserted=$INS failed=$FAILED"
assert_eq "$INS" "5" "5 道学生全部入库"
assert_eq "$FAILED" "0" "无失败行"
echo ""

echo "=== Step 4: 单个改密 ==="
RESP=$(curl -sf "$BASE/api/classes/$CID/students")
SID=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['id'])")
echo "  SID=$SID"
RESP=$(curl -sf -X POST "$BASE/api/students/$SID/change-password" \
    -H "Content-Type: application/json" \
    -d '{"new_password":"newpw123"}')
NEW_PW=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['initial_password'])")
assert_eq "$NEW_PW" "newpw123" "单改密 DB 写入正确"
echo ""

echo "=== Step 5: 批量改密 ==="
RESP=$(curl -sf -X POST "$BASE/api/classes/$CID/students/reset-passwords" \
    -H "Content-Type: application/json" \
    -d '{"default_password":"reset123"}')
RESET_COUNT=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['reset_count'])")
assert_eq "$RESET_COUNT" "5" "5 个学生全部重置"
echo ""

echo "=== Step 6: 建题库（15 道题覆盖 4 档）==="
TID=$TID python3 -c "
import os
from app.database import SessionLocal
from app.models import Question, QuestionType, Level
tid = int(os.environ['TID'])
s = SessionLocal()
for i in range(1, 7):
    s.add(Question(content=f'e2e-D-{i}', options=['A','B','C','D'], answer='A',
                   question_type=QuestionType.SINGLE_CHOICE.value,
                   level=Level.D.value, chapter='ch1_earth_movement', teacher_id=tid))
for i in range(1, 5):
    s.add(Question(content=f'e2e-C-{i}', options=['A','B','C','D'], answer='A',
                   question_type=QuestionType.SINGLE_CHOICE.value,
                   level=Level.C.value, chapter='ch1_earth_movement', teacher_id=tid))
for i in range(1, 4):
    s.add(Question(content=f'e2e-B-{i}', options=['A','B','C','D'], answer='A',
                   question_type=QuestionType.SINGLE_CHOICE.value,
                   level=Level.B.value, chapter='ch1_earth_movement', teacher_id=tid))
for i in range(1, 3):
    s.add(Question(content=f'e2e-A-{i}', options=['A','B','C','D'], answer='A',
                   question_type=QuestionType.SINGLE_CHOICE.value,
                   level=Level.A.value, chapter='ch1_earth_movement', teacher_id=tid))
s.commit()
for lv in ['D','C','B','A']:
    n = s.query(Question).filter(Question.level==lv).count()
    print(f'  {lv} 档: {n}')
s.close()
"
echo ""

echo "=== Step 7: 生成作业（含反马太 D 档 20% 拔高）==="
RESP=$(curl -sf -X POST "$BASE/api/classes/$CID/homeworks/generate" \
    -H "Content-Type: application/json" \
    -d "{\"teacher_id\":$TID,\"title\":\"e2e作业\",\"questions_per_level\":{\"D\":5,\"C\":3,\"B\":2,\"A\":1},\"anti_matthew\":true}")
HW_ID=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['homework']['id'])")
TOTAL=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['homework']['questions']))")
N_C_IN_D=$(printf '%s' "$RESP" | python3 -c "
import json,sys
d = json.load(sys.stdin)['homework']['questions']
print(sum(1 for q in d if q['level']=='C' and q['position']<=5))
")
echo "  HW_ID=$HW_ID total=$TOTAL D档里有C档=$N_C_IN_D"
assert_eq "$TOTAL" "11" "总题数 5+3+2+1=11"
assert_eq "$N_C_IN_D" "1" "D 档 5 题里 1 道 C 档（反马太 20%）"
echo ""

echo "=== Step 8: 审阅 + 手动调整档位（D → B）==="
RESP=$(curl -sf "$BASE/api/homeworks/$HW_ID")
FIRST_QID=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['questions'][0]['id'])")
echo "  把 hq_id=$FIRST_QID 改成 B"
RESP=$(curl -sf -X POST "$BASE/api/homeworks/$HW_ID/review" \
    -H "Content-Type: application/json" \
    -d "{\"questions\":[{\"homework_question_id\":$FIRST_QID,\"new_level\":\"B\"}]}")
STATUS=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])")
FIRST_LEVEL=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['questions'][0]['level'])")
REVIEWED_AT=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['reviewed_at'])")
echo "  status=$STATUS reviewed_at=$REVIEWED_AT 第1题 level=$FIRST_LEVEL"
assert_eq "$STATUS" "reviewed" "review 后 status 是 reviewed"
assert_eq "$FIRST_LEVEL" "B" "第 1 题档位改成 B"
[ -n "$REVIEWED_AT" ] && echo "  PASS: reviewed_at 已写入" || { echo "  FAIL: reviewed_at 空"; exit 1; }
echo ""

echo "=== Step 9: 发布（REVIEWED → PUBLISHED）==="
RESP=$(curl -sf -X POST "$BASE/api/homeworks/$HW_ID/publish")
STATUS=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])")
PUBLISHED_AT=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['published_at'])")
echo "  status=$STATUS published_at=$PUBLISHED_AT"
assert_eq "$STATUS" "published" "publish 后 status 是 published"
[ -n "$PUBLISHED_AT" ] && echo "  PASS: published_at 已写入" || { echo "  FAIL: published_at 空"; exit 1; }
echo ""

echo "=== Step 10: 列作业 + 状态过滤 ==="
RESP=$(curl -sf "$BASE/api/classes/$CID/homeworks")
COUNT=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")
RESP=$(curl -sf "$BASE/api/classes/$CID/homeworks?status=published")
PUB_COUNT=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")
echo "  class $CID 总作业: $COUNT"
echo "  status=published: $PUB_COUNT"
assert_eq "$COUNT" "1" "1 个作业"
assert_eq "$PUB_COUNT" "1" "1 个 published"
echo ""

echo "=== Step 11: 反向验证 — 已发布不能重复发布（422）==="
HTTP=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/homeworks/$HW_ID/publish")
assert_eq "$HTTP" "422" "已发布再 publish 被拒"
echo ""

echo "=== Step 12: 反向验证 — 坏 CSV 行级失败 ==="
cat > /tmp/e2e-bad.csv <<EOF
name,student_no
好学生,e2e999
,
错学生无姓名,e2e998
好学生2,e2e001
EOF
RESP=$(curl -sf -X POST "$BASE/api/classes/$CID/students/bulk-import" -F "file=@/tmp/e2e-bad.csv")
INS2=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['inserted'])")
FAIL2=$(printf '%s' "$RESP" | python3 -c "import json,sys; print(len(json.load(sys.stdin)['failed']))")
echo "  坏 CSV: inserted=$INS2 failed=$FAIL2"
assert_eq "$INS2" "2" "坏 CSV 行级隔离：2 道成功"
assert_eq "$FAIL2" "2" "坏 CSV 失败 2 行"
echo ""

echo "============================================"
echo "=== W3 完整端到端闭环 PASS ==="
echo "============================================"
echo "建老师(id=$TID) → 建班级(id=$CID) → 批量导入5生 → 单/批改密"
echo " → 建15题 → 生成作业(id=$HW_ID,反马太) → 审阅手动调档 → 发布"
echo "============================================"
