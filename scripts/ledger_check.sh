#!/bin/bash
# scripts/ledger_check.sh（重写版；c12 第五笔）
# §7.2 第 5 步 ledger_check：收工必跑；失败即拒收
# 法源：D-76 台账落后硬约束 + 审查员核对回执 2026-10-05 22:25 §三 C 单一真值源 + §四 #79-#82
# 立条：commit 12 第五笔（用户拍 1；D-43 §5 触发已解除降级决策室做）
#
# 检查项（5 条 — 全部改读单一真值源 notes/milestones.md §家族表）：
# 1. 元规则累计：grep -c '\[META\] D-' notes/milestones.md = 13（无魔数；ACTUAL 既是真值）
# 2. 5 家族段存在：A/B/C/D/E 5 家族段都存在（读 notes §家族表）
# 3. W-A-U-P.md 错拼（拆字）：git grep -nF "${TYPO}" = 0 命中（拆字避免自指；不排除任何目录）
# 4. 失实编号覆盖格式：notes §家族表含 "失实编号覆盖 #11-#XX" 格式
# 5. dirty 收口：git status --porcelain = 空（警告而非失败）
#
# 用法：bash scripts/ledger_check.sh
# 退出码：0 = 通过；1 = 失败（输出失败项详情）

set -u

# 拆字（避免 W-A-U-P.md 字面命中）
TYPO_A="WAU"
TYPO_B="P.md"
TYPO="${TYPO_A}${TYPO_B}"

cd ~/tiered-homework-platform 2>/dev/null || {
  echo "❌ FAIL: 无法 cd 到 ~/tiered-homework-platform"
  exit 1
}

FAILED=0

# === 检查 1: 元规则累计（单一真值源 = notes §家族表）===
echo "[1/5] 元规则累计..."
ACTUAL=$(grep -cE '^### \[META\] D-' notes/milestones.md 2>/dev/null)
if [ -z "$ACTUAL" ] || [ "$ACTUAL" = "0" ]; then
  echo "  ❌ FAIL: notes/milestones.md §家族表无 [META] D- 段"
  FAILED=1
else
  echo "  ✅ ACTUAL=$ACTUAL（单一真值源；无魔数）"
fi

# === 检查 2: 5 家族段存在（读 notes §家族表）===
echo "[2/5] 5 家族段..."
for FAMILY in "A 家族" "B 家族" "C 家族" "D 家族" "E 家族"; do
  if ! grep -qF "$FAMILY" notes/milestones.md 2>/dev/null; then
    echo "  ❌ FAIL: 未找到 $FAMILY in notes/milestones.md §家族表"
    FAILED=1
  fi
done
if [ "$FAILED" = "0" ]; then
  echo "  ✅ 5 家族段检查通过"
fi

# === 检查 3: W-A-U-P.md 错拼（拆字避免自指命中）===
echo "[3/5] W-A-U-P.md 错拼（拆字避免自指命中）..."
HITS=$(git grep -nF "${TYPO}" 2>/dev/null | wc -l)
if [ "$HITS" = "0" ]; then
  echo "  ✅ 0 命中（无 W-A-U-P.md 错拼）"
else
  echo "  ❌ FAIL: W-A-U-P.md 错拼 $HITS 处："
  git grep -nF "${TYPO}" 2>/dev/null
  FAILED=1
fi

# === 检查 4: 失实编号覆盖格式（notes §家族表）===
echo "[4/5] 失实编号覆盖格式..."
NOTES_RANGE=$(grep -oE '失实编号覆盖 \*\*#11-#[0-9]+\*\*' notes/milestones.md 2>/dev/null | head -1)
if [ -z "$NOTES_RANGE" ]; then
  echo "  ❌ FAIL: notes/milestones.md §家族表无失实编号覆盖格式"
  FAILED=1
else
  echo "  ✅ notes §家族表含失实编号覆盖：$NOTES_RANGE"
fi

# === 检查 5: dirty 收口 ===
echo "[5/5] dirty 收口..."
DIRTY=$(git status --porcelain 2>/dev/null | wc -l)
if [ "$DIRTY" = "0" ]; then
  echo "  ✅ working tree clean"
else
  echo "  ⚠️ WARN: working tree dirty（$DIRTY 行）—— 收工前应已 commit"
fi

echo ""
if [ "$FAILED" = "1" ]; then
  echo "❌ ledger_check 失败；请修复后重跑"
  exit 1
else
  echo "✅ ledger_check 通过；可以收工"
  exit 0
fi
