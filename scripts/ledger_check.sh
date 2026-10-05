#!/bin/bash
# scripts/ledger_check.sh
# §7.2 第 5 步 ledger_check：收工必跑；失败即拒收
# 法源：D-76 台账落后硬约束（载数失实须同笔刷台账；上位不刷 = 同型失实）
# 立条：commit 12 第三笔（用户拍 2；D-43 §5 触发已解除降级决策室做）
#
# 检查项（5 条）：
# 1. 台账增量：decisions.md D-67 至 D-76 段数 + 3（D-43 §5 + D-44 + D-66）== memory/notes 中"累计 N 条"
# 2. 失实入家族表：A/B/C/D/E 5 家族段都存在
# 3. WAUP.md 错拼：git grep -F "WAUP.md" = 0 命中（仅"WAKEUP.md"正确拼写）
# 4. notes-memory 对齐：notes §收口.2 失实编号覆盖 == memory §六.2 当前状态
# 5. dirty 收口：git status --porcelain = 空（警告而非失败）
#
# 用法：bash scripts/ledger_check.sh
# 退出码：0 = 通过；1 = 失败（输出失败项详情）

set -u  # 未定义变量报错（不用 -e 因为要继续检查所有项）

cd ~/tiered-homework-platform 2>/dev/null || {
  echo "❌ FAIL: 无法 cd 到 ~/tiered-homework-platform"
  exit 1
}

FAILED=0
TODAY=$(date '+%Y-%m-%d')

# === 检查 1: 台账增量 ===
echo "[1/5] 台账增量..."
ACTUAL=$(grep -cE '^### D-(6[7-9]|7[0-6])' docs/decisions.md 2>/dev/null || echo 0)
# 累计元规则 = ACTUAL + 3（D-43 §5 + D-44 + D-66）
EXPECTED=$((ACTUAL + 3))
ACCUMULATED=$(grep -oE '累计元规则 = [0-9]+ 条' "memory/${TODAY}.md" 2>/dev/null | head -1 | grep -oE '[0-9]+' || echo "")
if [ -z "$ACCUMULATED" ] || [ "$ACCUMULATED" = "0" ]; then
  echo "  ⚠️ WARN: 未在 memory/${TODAY}.md 找到'累计元规则 = N 条'；跳过（可能今天无新元规则）"
else
  if [ "$ACCUMULATED" = "$EXPECTED" ]; then
    echo "  ✅ ACTUAL+3=$EXPECTED == memory 累计=$ACCUMULATED"
  else
    echo "  ❌ FAIL: ACTUAL+3=$EXPECTED != memory 累计=$ACCUMULATED"
    FAILED=1
  fi
fi

# === 检查 2: 失实入家族表 ===
echo "[2/5] 失实入家族表..."
for FAMILY in "A 家族" "B 家族" "C 家族" "D 家族" "E 家族"; do
  if grep -qF "$FAMILY" "memory/${TODAY}.md" 2>/dev/null; then
    :
  else
    echo "  ❌ FAIL: 未找到 $FAMILY in memory/${TODAY}.md"
    FAILED=1
  fi
done
if [ "$FAILED" = "0" ]; then
  echo "  ✅ 5 家族段检查通过"
fi

# === 检查 3: WAUP.md 错拼 ===
echo "[3/5] WAUP.md 错拼（按 D-75 第 2 款 + D 家族 #62/#68）..."
WAUP_HITS=$(git grep -nF "WAUP.md" -- ':!scripts/' 2>/dev/null | wc -l)
if [ "$WAUP_HITS" = "0" ]; then
  echo "  ✅ 0 命中（无 WAUP.md 错拼）"
else
  echo "  ❌ FAIL: WAUP.md 错拼 $WAUP_HITS 处："
  git grep -nF "WAUP.md" -- ':!scripts/' 2>/dev/null
  FAILED=1
fi

# === 检查 4: notes-memory 对齐 ===
echo "[4/5] notes-memory 对齐..."
NOTES_RANGE=$(grep -oE '失实编号覆盖 \*\*#11-#[0-9]+\*\*' notes/milestones.md 2>/dev/null | head -1)
MEMORY_RANGE=$(grep -oE '失实编号覆盖 \*\*#11-#[0-9]+\*\*' "memory/${TODAY}.md" 2>/dev/null | head -1)
if [ -z "$NOTES_RANGE" ] && [ -z "$MEMORY_RANGE" ]; then
  echo "  ⚠️ WARN: 双方都未找到失实编号覆盖；跳过"
elif [ "$NOTES_RANGE" = "$MEMORY_RANGE" ] && [ -n "$NOTES_RANGE" ]; then
  echo "  ✅ notes / memory 一致：$NOTES_RANGE"
else
  echo "  ❌ FAIL: notes=$NOTES_RANGE / memory=$MEMORY_RANGE"
  FAILED=1
fi

# === 检查 5: dirty 收口 ===
echo "[5/5] dirty 收口..."
DIRTY=$(git status --porcelain 2>/dev/null | wc -l)
if [ "$DIRTY" = "0" ]; then
  echo "  ✅ working tree clean"
else
  echo "  ⚠️ WARN: working tree dirty（$DIRTY 行）—— 收工前应已 commit"
  # 警告而非失败
fi

echo ""
if [ "$FAILED" = "1" ]; then
  echo "❌ ledger_check 失败；请修复后重跑"
  exit 1
else
  echo "✅ ledger_check 通过（$TODAY）；可以收工"
  exit 0
fi
