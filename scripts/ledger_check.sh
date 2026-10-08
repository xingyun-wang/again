#!/bin/bash
# scripts/ledger_check.sh（c12 第五笔 修法版；解 #84/#89/#87/#90 + 2026-10-08 扩 4 条元数据一致性检查；解 dc246aa 错位家族）
# WAKEUP.md 第 5 步 ledger_check：收工必跑；失败即拒收
# 法源：D-76 台账落后硬约束 + 审查员核对回执 2026-10-05 23:11 §三 #89/#90 + §四 拍 1 修法 a-d
# 立条：commit 12 第五笔 修法（用户拍 1；D-43 §5 触发已解除降级决策室做）
# 扩 4 条：用户拍 2026-10-08 16:00（机器检查取代人工自检；元规则不再立）：
#   ⑥ §7 表已填行数 == §7.1/§7.2/§7.3 段数（解 §7 表 3 行 2 种状态自相矛盾）
#   ⑦ §7 表「落实 commit」sha 真值（git log 存在 + stat 包含被引文件；解 :136/:158/:173 漏写 dc246aa）
#   ⑧ 文件自述「commit X 后」时 X 的 stat 必须包含该文件（解 plans/M2-A.1-brief.md 头部错位）
#   ⑨ 所有「详见 X」的 X 必须存在（防止跨文档引用失联）
#
# 检查项（9 条 — 单一真值源 + 双真值源同构 + 元数据一致性）：
# 1. 元规则累计：notes §家族表 [META] 段数 == decisions.md [META] 段数（双真值源同构；解 #84 + #89）
# 2. 5 家族段存在：A/B/C/D/E 5 家族段都存在（读 notes §家族表）
# 3. W-A-U-P.md 错拼：git grep -nF "${TYPO}" = 0 命中（文件面；消息面为已知盲区 — 解 #87 + #90）
# 4. 失实编号覆盖格式：notes §家族表含 "失实编号覆盖 #11-#XX" 格式
# 5. dirty 收口：git status --porcelain = 空（警告而非失败）
# 6. §7 表已填行数 == §7.1/§7.2/§7.3 段数（解 §7 表 3 行 2 种状态自相矛盾）
# 7. §7 表「落实 commit」sha 真值：git log 存在 + stat 包含被引文件（解 :136/:158/:173 漏写 dc246aa）
# 8. 文件自述「commit X 后」时 X 的 stat 必须包含该文件（解 plans/M2-A.1-brief.md 头部错位）
# 9. 所有「详见 X」的 X 必须存在
#
# 解 #90（消息面盲区）：
#   WAKEUP.md 第 5 步 ledger_check < 第 6 步 backup.sh（D-79 唯一真值源）
#   commit message 在 commit 后才存在；commit 前检查 message 结构上无效
#   历史 message 字面为永久审计 trail（按 D-72/D-74 §1）
#   不引入 git log -1 假判据；显式声明盲区
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

# === 检查 1: 元规则累计（双真值源同构；解 #84 + #89）===
echo "[1/9] 元规则累计（双真值源同构）..."
ACTUAL_NOTES=$(grep -cE '^### \[META\] D-' notes/milestones.md 2>/dev/null)
ACTUAL_DEC=$(grep -cE '^### \[META\] D-' docs/decisions.md 2>/dev/null)
if [ -z "$ACTUAL_NOTES" ] || [ "$ACTUAL_NOTES" = "0" ]; then
  echo "  ❌ FAIL: notes/milestones.md §家族表无 [META] D- 段"
  FAILED=1
elif [ "$ACTUAL_NOTES" != "$ACTUAL_DEC" ]; then
  echo "  ❌ FAIL: notes [META]=$ACTUAL_NOTES vs decisions [META]=$ACTUAL_DEC（D-76 台账落后）"
  FAILED=1
else
  echo "  ✅ ACTUAL=$ACTUAL_NOTES（notes [META] == decisions [META]；双真值源同构）"
fi

# === 检查 2: 5 家族段存在（读 notes §家族表）===
echo "[2/9] 5 家族段..."
for FAMILY in "A 家族" "B 家族" "C 家族" "D 家族" "E 家族"; do
  if ! grep -qF "$FAMILY" notes/milestones.md 2>/dev/null; then
    echo "  ❌ FAIL: 未找到 $FAMILY in notes/milestones.md §家族表"
    FAILED=1
  fi
done
if [ "$FAILED" = "0" ]; then
  echo "  ✅ 5 家族段检查通过"
fi

# === 检查 3: W-A-U-P.md 错拼（文件面；消息面为已知盲区；解 #87 + #90）===
echo "[3/9] W-A-U-P.md 错拼（文件面；消息面盲区已声明）..."
HITS=$(git grep -nF "${TYPO}" 2>/dev/null | wc -l)
if [ "$HITS" = "0" ]; then
  echo "  ✅ 0 命中（无 W-A-U-P.md 错拼；消息面为已知盲区）"
else
  echo "  ❌ FAIL: W-A-U-P.md 错拼 $HITS 处（文件面）："
  git grep -nF "${TYPO}" 2>/dev/null
  FAILED=1
fi

# === 检查 4: 失实编号覆盖格式（notes §家族表 · 按「当前失实编号覆盖」段锁定）===
echo "[4/9] 失实编号覆盖格式（按当前失实编号覆盖段锁定）..."
NOTES_RANGE=$(grep -A 2 '当前失实编号覆盖' notes/milestones.md 2>/dev/null | grep -oE '\*\*#11-#[0-9]+\*\*' | head -1)
if [ -z "$NOTES_RANGE" ]; then
  echo "  ❌ FAIL: notes/milestones.md 无「当前失实编号覆盖」段或段内无 #11-#XX 格式"
  FAILED=1
else
  echo "  ✅ notes 当前失实编号覆盖：$NOTES_RANGE（按段锁定，不再依赖行序）"
fi

# === 检查 5: dirty 收口 ===
echo "[5/9] dirty 收口..."
DIRTY=$(git status --porcelain 2>/dev/null | wc -l)
if [ "$DIRTY" = "0" ]; then
  echo "  ✅ working tree clean"
else
  echo "  ⚠️ WARN: working tree dirty（$DIRTY 行）—— 收工前应已 commit"
fi

# === 检查 6: §7 表已填行数 == §7.1/§7.2/§7.3 段数 ===
# 通用做法：从 §7.1/§7.2/§7.3 段标题里提取 D-M2-X 名，再去 §7 表里 check 这些行的拍板日期都不为 "—"
echo "[6/9] §7 表已填行数 == §7.1/§7.2/§7.3 段数..."
SECTION_DM2S=$(grep -oE '### 7\.[123] 拍板记录（D-M2-[0-9]+' docs/M2-kickoff-decision.md | grep -oE 'D-M2-[0-9]+')
CHECK6_FAIL=0
CHECK6_COUNT=0
for DM2 in $SECTION_DM2S; do
  CHECK6_COUNT=$((CHECK6_COUNT+1))
  DATE=$(grep -E "^\| $DM2 " docs/M2-kickoff-decision.md | awk -F'|' '{ gsub(/[ ]+/, "", $3); print $3 }')
  if [ -z "$DATE" ] || [ "$DATE" = "—" ]; then
    echo "  ❌ FAIL: §7 表 $DM2 行拍板日期未填（= '—' 或空）"
    CHECK6_FAIL=1
  fi
done
if [ "$CHECK6_FAIL" = "0" ]; then
  echo "  ✅ ACTUAL=$CHECK6_COUNT 个 D-M2-N 拍板段对应行拍板日期全部已填"
else
  FAILED=1
fi

# === 检查 7: §7 表「落实 commit」sha 真值（git log 存在 + stat 包含被引文件）===
echo "[7/9] §7 表「落实 commit」sha 真值..."
# 提取 §7 表中所有 sha（5+ 行 + 5+ 字符 hex；跨多 sha 用 space 拆）
SHAS_RAW=$(grep -E '^\| D-M2-' docs/M2-kickoff-decision.md | awk -F'|' '{ gsub(/[ `]+/, "", $5); print $5 }')
SHAS=$(echo "$SHAS_RAW" | grep -oE '[0-9a-f]{7,}')
CHECK7_FAIL=0
CHECK7_COUNT=0
for SHA in $SHAS; do
  CHECK7_COUNT=$((CHECK7_COUNT+1))
  if ! git log --oneline 2>/dev/null | grep -q "$SHA"; then
    echo "  ❌ FAIL: sha $SHA 不在 git log"
    CHECK7_FAIL=1
    continue
  fi
  STAT_FILES=$(git show --name-only --format="" "$SHA" 2>/dev/null)
  if ! echo "$STAT_FILES" | grep -qF "M2-kickoff-decision.md"; then
    echo "  ❌ FAIL: sha $SHA 的 stat 不包含 M2-kickoff-decision.md（被引文件）"
    CHECK7_FAIL=1
  fi
done
if [ "$CHECK7_FAIL" = "0" ]; then
  echo "  ✅ ACTUAL=$CHECK7_COUNT 个 sha 全部 OK（git log 存在 + stat 包含 M2-kickoff-decision.md）"
else
  FAILED=1
fi

# === 检查 8: 文件自述「commit X 后」时 X 的 stat 必须包含该文件 ===
echo "[8/9] 文件自述「commit X 后」时 X 的 stat 必须包含该文件..."
CHECK8_FAIL=0
CHECK8_COUNT=0
while IFS= read -r match; do
  if [ -z "$match" ]; then continue; fi
  # match 格式: filepath:lineno:content
  FILE=$(echo "$match" | cut -d':' -f1)
  SHA=$(echo "$match" | grep -oE 'commit [0-9a-f]{7,}' | head -1 | awk '{print $2}')
  if [ -z "$SHA" ]; then continue; fi
  CHECK8_COUNT=$((CHECK8_COUNT+1))
  STAT_FILES=$(git show --name-only --format="" "$SHA" 2>/dev/null)
  if ! echo "$STAT_FILES" | grep -qF "$FILE"; then
    echo "  ❌ FAIL: $FILE 引用 (commit $SHA 后) 但 $SHA 的 stat 不包含 $FILE"
    CHECK8_FAIL=1
  fi
done < <(grep -rnE '\(commit [0-9a-f]{7,}[a-z0-9]* 后\)' docs/ memory/ notes/ plans/ 2>/dev/null)
if [ "$CHECK8_FAIL" = "0" ]; then
  echo "  ✅ ACTUAL=$CHECK8_COUNT 个「commit X 后」引用，X 的 stat 全部包含被引文件"
else
  FAILED=1
fi

# === 检查 9: 所有「详见 X」的 X 必须存在 ===
echo "[9/9] 所有「详见 X」的 X 必须存在..."
CHECK9_FAIL=0
CHECK9_COUNT=0
while IFS= read -r match; do
  if [ -z "$match" ]; then continue; fi
  # 提取 XREF = 「详见」 后第一个 ASCII token（排除中文标点；不取 WAKEUP.md」、下面又把 这种）
  XREF_RAW=$(echo "$match" | sed -E 's/.*详见[[:space:]]+//')
  XREF=$(echo "$XREF_RAW" | grep -oE '^[`]?[a-zA-Z0-9_\./-]+' | head -1 | sed 's/^`//' | sed 's/`$//')
  if [ -z "$XREF" ]; then continue; fi
  # 跳过 markdown 链接
  if [[ "$XREF" == *"]"* ]]; then continue; fi
  # 跳过 § 标题 / 行号引用
  if [[ "$XREF" == §* ]] || [[ "$XREF" == \#* ]]; then continue; fi
  # 跳过 .bak 历史归档（项目仓有 .bak.2026-09-10/STATE.md 引用但归档可能已移走）
  if [[ "$XREF" == .bak.* ]] || [[ "$XREF" == */.bak.* ]]; then continue; fi
  # 必须含 / 或常见文件后缀（排除元规则编号如 B6 / P1-1）
  if [[ ! "$XREF" == */* ]] && [[ ! "$XREF" =~ \.(md|py|sh|json|txt|yaml|yml|conf|ini|toml|html|css|js|ts|tsx|jsx)$ ]]; then
    continue
  fi
  # 短 ID (< 5 字符) 且无 / 跳过
  if [[ ${#XREF} -le 4 ]] && [[ ! "$XREF" == */* ]]; then continue; fi
  CHECK9_COUNT=$((CHECK9_COUNT+1))
  # 路径解析：先相对当前，再常见目录（处理「详见 decisions.md」这种 bare name）
  if [ ! -e "$XREF" ] && [ ! -e "docs/$XREF" ] && [ ! -e "memory/$XREF" ] && [ ! -e "notes/$XREF" ] && [ ! -e "plans/$XREF" ] && [ ! -e "backend/$XREF" ]; then
    SRC_FILE=$(echo "$match" | cut -d':' -f1)
    echo "  ❌ FAIL: $SRC_FILE 引用 详见 $XREF 但不存在"
    CHECK9_FAIL=1
  fi
done < <(grep -rnE '详见\s+[`]?[^`)\(\s]+' docs/ memory/ notes/ plans/ 2>/dev/null)
if [ "$CHECK9_FAIL" = "0" ]; then
  echo "  ✅ ACTUAL=$CHECK9_COUNT 个「详见 X」引用，X 全部存在"
else
  FAILED=1
fi

# === 检查 10: tech-debt.md 引用必须与 HEAD mypy 真值一致（双向核对；防 N1 类镜像陈旧）===
echo "[10/10] tech-debt.md 引用必须与 HEAD mypy 真值一致（双向核对）..."
if [ -f docs/tech-debt.md ]; then
  # 1. 验证容器镜像与 HEAD 一致（防 N1 类镜像陈旧）
  CONTAINER_MD5=$(docker exec thp-backend md5sum /app/app/api/v1/routers/academic.py 2>/dev/null | awk '{print $1}')
  HEAD_MD5=$(md5sum backend/app/api/v1/routers/academic.py 2>/dev/null | awk '{print $1}')
  if [ -z "$CONTAINER_MD5" ]; then
    echo "  ❌ FAIL: 容器 thp-backend 不可达（docker exec 失败）"
    FAILED=1
  elif [ "$CONTAINER_MD5" != "$HEAD_MD5" ]; then
    echo "  ❌ FAIL: 容器镜像陈旧（academic.py md5 不一致）"
    echo "  容器: $CONTAINER_MD5"
    echo "  HEAD:  $HEAD_MD5"
    echo "  修法: docker cp HEAD 文件 / docker build 重建镜像"
    FAILED=1
  else
    # 2. 跑容器内 mypy 拿 HEAD 真值（容器已 sync）
    MYPY_OUT=$(docker exec thp-backend bash -c "cd /app && python3 -m mypy app/ 2>&1" | grep -E ":\d+: error:" || true)
    # 3. 路径归一化：mypy 输出 app/... → docs 格式 backend/app/...
    MYPY_NORMALIZED=$(echo "$MYPY_OUT" | sed 's|^app/|backend/app/|g' | sed 's| app/| backend/app/|g')

    # 4. 提取 tech-debt.md 中的 file:line 引用
    DOC_LINES=$(grep -oE 'backend/app/[^:]+:[0-9]+' docs/tech-debt.md | sort -u)

    # 5. 双向核对
    CHECK10_FAIL=0
    DOC_COUNT=0
    for LINE in $DOC_LINES; do
      DOC_COUNT=$((DOC_COUNT+1))
      if ! echo "$MYPY_NORMALIZED" | grep -q "$LINE"; then
        echo "  ❌ FAIL: docs/tech-debt.md 引用 $LINE 但 HEAD mypy 不报此错（行号错位）"
        CHECK10_FAIL=1
      fi
    done

    MYPY_LINES=$(echo "$MYPY_NORMALIZED" | grep -oE 'backend/app/[^:]+:[0-9]+' | sort -u)
    MYPY_COUNT=0
    for LINE in $MYPY_LINES; do
      MYPY_COUNT=$((MYPY_COUNT+1))
      if ! echo "$DOC_LINES" | grep -q "$LINE"; then
        echo "  ❌ FAIL: HEAD mypy 报 $LINE 但 docs/tech-debt.md 未登记（漏登记）"
        CHECK10_FAIL=1
      fi
    done

    if [ "$CHECK10_FAIL" = "0" ]; then
      echo "  ✅ ACTUAL=$DOC_COUNT 个 doc 引用 == $MYPY_COUNT 个 mypy 真值（双向核对完全一致）"
    else
      FAILED=1
    fi
  fi
else
  echo "  ⚠️ WARN: docs/tech-debt.md 不存在（无 tech-debt 引用）"
fi

echo ""
if [ "$FAILED" = "1" ]; then
  echo "❌ ledger_check 失败；请修复后重跑"
  exit 1
else
  echo "✅ ledger_check 通过；可以收工"
  exit 0
fi
