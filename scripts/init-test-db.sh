#!/usr/bin/env bash
# init-test-db.sh — B2 修法：test 库 DROP + CREATE + alembic upgrade head (idempotent)
#
# 触发: M2-#114 B2 修法 (§治理.19 升级为结构性防)
# 背景: notes/work-orders/113-9-pre-existing-test-failures.md §修复后验证清单 [1]
# 仿: .github/workflows/ci.yml:53 先例 (DATABASE_URL=...tiered_homework_test)
#
# 目的: 容器 pytest 必带 `-e DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/tiered_homework_test`
#       dev 库 0 接触 (per §治理.19 字面绿口头红 trap 防御)
#
# 必带使用 (B2 修法 §治理.19 升级为结构性防):
#   docker compose exec -T -e DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/tiered_homework_test \
#     backend python -m pytest -q
#
# Idempotent: 每次跑都 DROP + CREATE + alembic upgrade head (保证 schema 已知干净状态)
#   - test_pg_alembic_upgrade_downgrade_round_trip 会 drop_all + 重建,
#     其他 test fixture 也可能 drop_all; 每次 init 都从干净态出发 = 派工前后 4 验 baseline 一致性保证
set -euo pipefail

# 配置
TEST_DB_NAME="${TEST_DB_NAME:-tiered_homework_test}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
BACKEND_SERVICE="${BACKEND_SERVICE:-backend}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres}"
TEST_DB_URL="postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@${POSTGRES_SERVICE}:5432/${TEST_DB_NAME}"

echo "[B2 修法] test 库 setup: ${TEST_DB_NAME}"
echo ""

# 1. 等待 postgres ready (max 30s)
echo "[1/4] 等待 postgres ready..."
timeout 30 bash -c "until docker compose exec -T ${POSTGRES_SERVICE} pg_isready -U ${DB_USER} > /dev/null 2>&1; do sleep 1; done"
echo "  ✓ postgres ready"
echo ""

# 2. DROP DATABASE IF EXISTS (确保干净态; 防止 test 跑后 schema 残留)
echo "[2/4] DROP DATABASE IF EXISTS ${TEST_DB_NAME}..."
# 终止残留连接 (PostgreSQL 不允许 DROP 有活跃连接的 DB)
docker compose exec -T ${POSTGRES_SERVICE} psql -U ${DB_USER} -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${TEST_DB_NAME}' AND pid <> pg_backend_pid();" \
  > /dev/null 2>&1 || true
docker compose exec -T ${POSTGRES_SERVICE} psql -U ${DB_USER} -c "DROP DATABASE IF EXISTS ${TEST_DB_NAME};" > /dev/null
echo "  ✓ DROP 完成 (if existed)"
echo ""

# 3. CREATE DATABASE (干净创建)
echo "[3/4] CREATE DATABASE ${TEST_DB_NAME}..."
docker compose exec -T ${POSTGRES_SERVICE} psql -U ${DB_USER} -c "CREATE DATABASE ${TEST_DB_NAME};" > /dev/null
echo "  ✓ CREATE 完成"
echo ""

# 4. alembic upgrade head (against test 库) + 4 验 baseline
echo "[4/4] alembic upgrade head (against test 库)..."
docker compose exec -T \
  -e DATABASE_URL="${TEST_DB_URL}" \
  ${BACKEND_SERVICE} \
  alembic upgrade head 2>&1 | tail -3
echo ""

# 5. 验真 (4 验 baseline)
echo "[verify] 4 验 baseline (test 库):"
echo -n "  alembic: "
docker compose exec -T -e DATABASE_URL="${TEST_DB_URL}" ${BACKEND_SERVICE} alembic current 2>&1 | tail -1
echo -n "  user_tables: "
docker compose exec -T ${POSTGRES_SERVICE} psql -U ${DB_USER} -d ${TEST_DB_NAME} -tAc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name != 'alembic_version';"
echo -n "  enums: "
docker compose exec -T ${POSTGRES_SERVICE} psql -U ${DB_USER} -d ${TEST_DB_NAME} -tAc \
  "SELECT count(*) FROM pg_type WHERE typtype='e';"
echo ""

echo "✅ B2 修法 test 库 setup 完成: ${TEST_DB_NAME} @ ${TEST_DB_URL}"
echo ""
echo "必带使用 (容器 pytest 必显式 -e DATABASE_URL=...tiered_homework_test):"
echo "  docker compose exec -T -e DATABASE_URL='${TEST_DB_URL}' ${BACKEND_SERVICE} python -m pytest -q"
