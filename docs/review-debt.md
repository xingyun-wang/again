# 审查欠账台账（Review Debt）

> **建立**：2026-10-23（星轨代码审查批 1 之后）
> **读者**：星轨（审查方）、星云（需求方）、载曜（实施方）
> **定位**：记录**审查方提出、当前不阻塞**的问题。P0/P1 走当轮返工（不记这里）；
> **P2/P3 记这里** —— 记下来 ≠ 忘了，每条都要有归属和触发时机。

---

## 0. 与 `docs/tech-debt.md` 的分工

| 文档 | 记什么 | 门禁关联 |
|---|---|---|
| `docs/tech-debt.md` | **mypy pre-existing errors**（历史欠下的类型债） | 门禁第 10 项**双向核对**：文档里的 `backend/app/...:行号` 必须与 HEAD mypy 真值完全对上 |
| `docs/review-debt.md`（本文件） | **代码审查提出的非阻塞问题**（P2/P3） | 无门禁耦合（正因如此才能自由记行号） |

⚠️ **别把本文件的内容写进 `tech-debt.md`** —— 那里每条 `backend/app/x.py:123` 引用
都会被门禁拿去和 mypy 真值逐条对，行号错位或漏登记都会让门禁红。

---

## 批 1（星轨，2026-10-23；范围 `ab02079..e11de97`）

> 审查结论：**0 × P0 ｜ 2 × P1 ｜ 5 × P2 ｜ 1 × P3**
> 两个 P1 已当轮返工完毕（见 `交付物/运行时证据-代码审查批1 修复（2026-10-23）.md`）。
> 本节只记 **P2 × 5 + P3 × 1**。
>
> **⭐ 销账状态（2026-10-24 22:xx）**：**6 条全部已修** ——
> P2-3 + P3-1（`4450007`）／P2-1 + P2-2 + P2-4 + P2-5（本笔）。
> 回归网：`backend/tests/api/v1/test_review_debt_p2.py`（P2-1/2/4/5 四条）
> ＋ `backend/tests/api/v1/test_question_groups.py::test_p2_3_orphan_image_reclaimed_on_block_replace`（P2-3）
> ＋ `backend/tests/api/v1/test_question_groups.py::test_c2_判据 J`（P3-1）。
> 证据：`交付物/运行时证据-1c-2 P2P3 + 批1 P2 清账（2026-10-24）.md`。

### P2-1 · 删组只 unlink 组图，小题自己的图全留在磁盘 — ✅ **已修（2026-10-24 本笔）**

- **位置**：`backend/app/api/v1/routers/academic.py:2306`（`delete_question_group` 内 `storage_paths` 收集）
- **现状**：
  ```python
  storage_paths = [
      row.storage_path
      for row in db.query(QuestionImage)
      .filter(QuestionImage.group_id == group.id)   # ← 只收组图
      .all()
      if row.storage_path
  ]
  ```
- **机制**：删组时 DB 级 CASCADE 会带走**组内小题**（`questions.group_id` FK CASCADE），
  小题的图（`question_images.question_id` 有值）随小题一起**行没了**，
  但 `storage_paths` 没收集它们 ⇒ **文件留在磁盘**（孤儿文件）。
- **影响**：一次删组留 N 个孤儿文件，长期累积；磁盘用量只涨不跌。
- **归属**：载曜
- **触发时机**：1c-2 commit2 之后（题组删除功能真正上线前），或独立一笔修复。
  建议改法：删组时**先**收集组内小题的图路径（`question_id IN (组内小题)`），
  一并纳入 unlink 列表。
- **核源**：✅ 星轨的机制描述与代码一致（`e11de97:2228` 同款逻辑，仅行号因本轮修复位移）。
- **✅ 修法（2026-10-24 本笔）**：删组前**同时**收两批 `storage_path` ——
  ① `QuestionImage.group_id == group.id`（组图）② `QuestionImage.question_id IN (组内小题 id 列表)`（小题题图）
  ⇒ DB commit 之后逐个 best-effort `Path.unlink(missing_ok=True)`。
  两批不重复：`question_images` 有 XOR CHECK（`ck_question_images_owner_not_null`）⇒ group_id 侧与 question_id 侧**互斥**。
  题组删除仍用 `db.execute(delete(QuestionGroup).where(...))` 走 DB 级 `ON DELETE CASCADE`（不走 ORM de-associate，
  避免 ORM 把小题**移出组**从而触发 `ck_question_images_owner_not_null`）。
- **✅ 回归网**：`backend/tests/api/v1/test_review_debt_p2.py::test_p2_1_delete_group_reclaims_group_question_image_file`
  （断言**小题题图行没了 + 磁盘文件没了** + 题组行没了三件事）。

### P2-2 · 500 响应体拼 `{e}` ⇒ 客户端能看到 SQL / 表名 / 约束名 — ✅ **已修（2026-10-24 本笔）**

- **位置**：`backend/app/core/errors.py:119` 是放大器 —— `detail` 被直接当 `message` 返回：
  ```python
  message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
  ```
- **⭐ 我核出的修正数**：星轨报告写「9 处」，**实际是 15 处** `status_code=500` 且 `detail` 含 `{e}`：
  ```
  339 · 563 · 771 · 960 · 1069 · 1596 · 1620 · 1646 · 1660 · 1876
  2537 · 2554 · 2580 · 2593 · 2713
  ```
  （行号按本文件登记时的**工作树**；本轮 P1-1 修复使行号相对 `e11de97` 位移。）
- **另有 4 处非 500 码也拼 `{e}`**（星轨清单里混了进来，一并记）：
  `:297`（400 文件读取失败）· `:522`（422 LLM 结构异常）· `:523`（502 LLM 调用失败）· `:935`（502 LLM 调用失败）
- **机制**：`psycopg` / `SQLAlchemy` 的异常文本里带**表名、约束名、SQL 片段** ⇒ 客户端可读。
- **归属**：载曜
- **触发时机**：对外暴露前（部署到真实用户环境前）必须处理。
- **建议改法**：`detail` 里**不拼 `{e}`**，改记 `logger.exception(...)`；
  客户端只看到固定文案（如「服务暂时不可用，请稍后重试」）。
  ⚠️ 注意 `core/errors.py:121-124` 会吞掉 `details` ⇒ 业务计数类信息要写进
  `detail`/`message` 字符串，别指望 `details`（这条已在 MEMORY.md 记过）。
- **✅ 修法（2026-10-24 本笔）**：
  1. `backend/app/core/errors.py` 新增固定文案常量
     `INTERNAL_ERROR_MESSAGE = "服务暂时不可用，请稍后重试"`（`:43`）；
  2. **全部 5xx 站点改用该常量**（**原始异常细节只进 `logger.exception(...)` 服务端日志**）；
  3. `backend/app/services/textbook_upload.py` 里 9 处 `f"...：{e}"` ⇒ 受控文案 + 日志留细节；
  4. 额外收尾：连 `TextbookUploadError` 里把**内部设计**（字段名 `extraction_source` + 规则号 D-37 + fail-closed 口径）
     透给客户端的那条也改掉（细节进 `logger.error`，客户端拿受控文案）。
- **✅ 核源真值（AST 遍历 `raise HTTPException(...)` 全量统计，容器 py3.11）**：
  | 指标 | 改前 | 改后 |
  |---|---|---|
  | `academic.py`：**5xx 且 detail 含异常文本** | **15** | **0** |
  | `academic.py`：HTTPException（带 `detail=`）总数 | 90 | 90（**未减少，只换文案**） |
  | 残留 4xx 且 detail 含 `str(e)`（业务文案，按台账口径**保留**） | — | 6 处（`:295` `:311` `:333` `:1686` `:2729` ＋ `assignments.py:153`） |
  ⇒ 改前 15 与本条登记的 15 处**完全对上**（星轨报告写 9 处、实测 15 处的修正数得到复核）。
- **✅ 回归网**：`backend/tests/api/v1/test_review_debt_p2.py::test_p2_2_5xx_message_must_not_leak_internal_details`
  （哨兵异常文本含 `psycopg2` / `unique constraint` ⇒ 断言 500 的 `message` 不含哨兵/约束名，且 == 固定文案）。

### P2-3 · 替换材料块后，无引用的图留在库里也留在磁盘 — ✅ **已修（1c-2 commit2 · `4450007`）**

- **位置**：`backend/app/api/v1/routers/academic.py`（`_replace_group_blocks`）
- **修法**：替换前算出「旧块引用 ∧ 新块不引用」的 `image_id` 集合 ⇒ 确认**全库**无块引用
  ⇒ 删 `question_images` 行；**磁盘文件在 DB commit 之后**才 unlink（先落定再动磁盘）。
- **回归网**：`tests/api/v1/test_question_groups.py::test_p2_3_orphan_image_reclaimed_on_block_replace`
  （断言**行没了 + 磁盘文件没了 + 计数不虚高**三件事）。
- **旧现状（保留供追溯）**：整体替换时**只删块**（`delete(ContentBlock)`），**不删图**。
  旧块引用的图在新块里没出现 ⇒ 那张图**没人引用了**，但：
  - 行还在 `question_images`（`group_id` 仍指向本组）⇒ **计数虚高**；
  - 文件还在磁盘 ⇒ 孤儿文件。
- **影响**：撞 `MAX_IMAGES_PER_GROUP = 10` 上限时更明显 ——
  明明只有 3 张图在用，却报「已达 10 张图上限」。
- **归属**：载曜
- **触发时机**：1c-2 commit2（材料块编辑器上线）**之前** ——
  编辑器每次保存都整体替换，孤儿会**每次保存累积一批**。
- **建议改法**：替换前算出「旧块引用但新块不再引用」的 image_id 集合，
  确认组内无其他块引用后删行 + unlink。

### P2-4 · `delete_question` 只删行不 unlink 题图（pre-existing） — ✅ **已修（2026-10-24 本笔）**

- **位置**：`backend/app/api/v1/routers/academic.py:1408`（`delete_question`）
- **现状**：题图随 `questions` CASCADE 删行，但**磁盘文件留下**。
  （对照：`delete_question_image`（`:1830`）与 `delete_group_image` **有** unlink。）
- **影响**：与 P2-1 同族；删组时放大（P2-1 会把组内小题的图也留下）。
- **归属**：载曜
- **触发时机**：与 P2-1 一起修（同一处逻辑，抽公共函数最省）。
- **✅ 修法（2026-10-24 本笔）**：`db.delete(q)` 前用**显式 query** 收 `storage_path` ⇒ `db.commit()` 之后 unlink。
  - ⚠️ **不能用 `q.images` 关系集合**：`Question.images` 是 `lazy="selectin"` ⇒ 首次访问就把集合**加载并缓存**在
    identity map 里；而 session 是 `expire_on_commit=False` ⇒ 后续 commit **不刷新**它。
    上传端点又是先 `db.get(Question, ...)`（此刻集合 = **空**）→ 再 `db.add(image)` 直插 `question_images` 行
    （**不进集合**）⇒ 删题时读 `q.images` 拿到的是**陈旧的空集合** ⇒ `storage_paths` 为空 ⇒ 磁盘文件永远不删。
    （这是我第一版的真 bug，被本笔新增的回归网当场抓住 ⇒ 已在证据文件 §1.1 留档。）
  - unlink 抛 `OSError` ⇒ 只 `logger.warning` 记「孤儿文件」⇒ **不返 5xx**（删除本身的成功语义不变）。
- **✅ 回归网**：`backend/tests/api/v1/test_review_debt_p2.py::test_p2_4_delete_question_reclaims_question_image_file`
  （断言**题图行没了 + 磁盘文件没了**）。

### P2-5 · `MAX_QUESTION_IMAGE_BYTES` 被组图复用（命名与语义不符） — ✅ **已修（2026-10-24 本笔）**

- **位置**：常量定义 `backend/app/api/v1/routers/academic.py:1451`；
  单题使用 `:1631`；**组图复用** `:2565`
- **现状**：常量名带 `QUESTION`，但题组材料图也用它判 5MB 上限。
- **影响**：**当前无功能缺陷**（值相同，行为正确）；风险在未来 ——
  哪天调「单题图 10MB」，会**误伤组图**（一起变成 10MB）。
- **归属**：载曜
- **触发时机**：任一次调整图片大小上限时**必须先拆常量**。
- **建议改法**：拆成 `MAX_IMAGE_BYTES`（共用）+ 若需分开再各自派生。
- **✅ 修法（2026-10-24 本笔）**：拆成**两个独立常量**（值相同 5MB，但**不是彼此的别名**）：
  ```python
  MAX_QUESTION_IMAGE_BYTES = 5 * 1024 * 1024   # 单题题图（:1494）
  MAX_GROUP_IMAGE_BYTES   = 5 * 1024 * 1024   # 题组材料图（:1496）
  ```
  组材料图上传流改用 `MAX_GROUP_IMAGE_BYTES`（`:2720`）⇒ 将来单独调其中一个**不会误伤**另一个。
- **✅ 回归网**：`backend/tests/api/v1/test_review_debt_p2.py::test_p2_5_question_and_group_image_size_limits_are_separate_constants`
  （两个常量都在、**不是彼此的别名**、且组常量**真被组图路径用到**）。
- ⚠️ **本条当前无功能差异**（值相同 5MB）⇒ **页面级看不出任何变化** ⇒ 星轨若要从页面核 P2-5，只能核代码常量。

### P3-1 · `GET /questions` 不排除组内小题 — ✅ **已修（`4450007`，台账漏划，本笔补记）**

- **原状态**：星轨已受理，**1c-2 commit2 已列入改造范围** ⇒ 此处只登记，不重复计。
- **✅ 核源更正（2026-10-24 本笔）**：本条**代码早已修完**，是**台账漏划** ⇒ 按「行号会漂，以代码为准」同源原则补记。
  - 代码真值：`backend/app/api/v1/routers/academic.py:1303`
    ```python
    query = db.query(Question).filter(
        Question.owner_user_id == user_id,
        Question.group_id.is_(None),   # ← 组内小题不进题库列表
    )
    ```
  - 出处：`git log -S "Question.group_id.is_(None)"` ⇒ 唯一命中 **`4450007`**（1c-2 commit2）。
  - ⇒ **本条不是欠账，是台账失实**（我上一轮收工时按台账原样抄进了 `STATE.md`「P2-1/P2-4/P2-5 + P3-1 仍在」⇒ 一并更正）。
- **回归网**：`backend/tests/api/v1/test_question_groups.py`（判据 J 用例）。

---

## 环境债（非审查问题，但会造成**误报**）

### ENV-1 · 宿主 Python 3.8 ≠ CI 3.11 ⇒ 报错长得像「我的改动炸了」

- **现状**：开发盒宿主 `python3` = **3.8.10**；CI / 容器 = **3.11.16**。
- **机制**：`backend/app/models/academic.py` 用了 `Mapped[list[Question]]` 这类
  **PEP 585 泛型下标**（`list[X]`）⇒ 3.8 在**收集期**就抛
  `sqlalchemy.orm.exc.MappedAnnotationError`。
  ⚠️ **报错位置在 `app/models/`，与「本轮改了什么」毫无关系** ⇒ 极易误判成
  「我的改动把模型炸了」，进而去改本来正确的代码。
- **⭐ 已落护栏**（2026-10-23，星云/星轨拍板 Q2）：`backend/tests/conftest.py:21`
  加 3 行守卫，宿主 `py<3.9` 直接 `pytest.exit("请在容器内跑 pytest：…")`。
  实测：宿主退出码 **4** + 清晰文案；容器 py3.11 收集 **392 条**不受影响。
  ⇒ **护栏比文档可靠** —— 文档会忘，护栏不会。
- **归属**：载曜（已修）
- **触发时机**：已修（2026-10-23）。**今后任何 pytest 报错，先看是不是这个护栏。**
- **⚠️ 为什么不写进 `WAKEUP.md`**：WAKEUP 是**收工流程真值源**，9 步每步都得可执行；
  「宿主 3.8 不支持 PEP 585」是**环境约束**不是步骤 ⇒ 塞进去它会长成杂物间，
  久了没人读（星云 2026-10-23 拍板）。

---

## 记账规则（防止这份文档变成垃圾场）

1. **每条必须有**：位置（file:行号）+ 现状（代码引用）+ 机制（为什么会这样）
   + 影响 + 归属 + **触发时机**。
2. **触发时机不许写「以后再说」** —— 必须写清在哪个里程碑/哪笔之前处理。
3. **修完一条就在本文件里划掉**（保留条目 + 加「已修」+ 指向修复 commit），
   **不要删条目** —— 删了就看不出「这里曾经漏过」。
4. **行号会漂**：本文件登记时的工作树为准；行号对不上时**以代码为准**，
   顺手更新本文件，**不要因为行号不对就不改代码**。
5. **⭐ 清理测试数据只删「本次运行记录下来的 id」，不按列表全量删**
   （2026-10-24 认领；星轨 OUTBOX #4 §四 的事故直接暴露）
   - **事故**：星轨复核时按 `GET /question-groups` 全量删除 ⇒ 连带删掉 3 个**不是我建的**题组
     （`small_question_count` 均为 0，是我 curl/UI 探针造的）。题组本体零损失，
     但**流程错了** —— 没先问、没先导出。
   - **根因**：这条纪律**没写在任何台账里** ⇒ 双方都只能凭印象 ⇒ 靠「我记得哪些 id 是我建的」这种不可靠记忆。
   - **⇒ 规则**：任何测试/自检建的数据，必须**当场记下 id**（本次运行的清单），
     清理时**只按这份清单删**；禁止「先 GET 列表再逐个删」这种全量删法。
   - **落地方式**：探针/自检脚本应把本次创建的 id 写进自己的输出日志，
     清理步骤从该日志读 id 清单。

---

## 变更说明

见 `notes/changelog/review-debt.md`（变更说明不与文件同体，D-77）。
