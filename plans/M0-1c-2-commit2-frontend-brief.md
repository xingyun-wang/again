# 1c-2 commit2 · 前端子任务 brief（题组行 + 内联新建小题 + 删组确认）

> 派工：载曜（父会话，实施方）｜日期：2026-10-24 17:1x
> 正式依据：`交付物/1c-2 brief 题组块编辑器（2026-10-23）.md` §四/§七/§十一
> + 星轨 OUTBOX #6 的 4 条裁决（2026-10-24 15:50 拍板）
> ⚠️ **brief §10.2 / §10.3 / §3.2 / §11.4 已就地勘误** —— 以本 brief 与勘误后原文为准。

---

## 0. 你的身份与边界

- 你是**实施子代理**。父会话（载曜）会**独立复核**你的产出 ⇒ **不要自我宣布「通过验收」**，只报「改了什么 / 跑了什么 / 结果是什么」。
- **只许改这 5 个前端文件**（其余只读）：

  1. `frontend/src/api/questionGroups.ts`（改）
  2. `frontend/src/api/questionTypes.ts`（改：**只许新增类型**，不许改已有类型的字段）
  3. `frontend/src/components/InlineQuestionForm.tsx`（**新增**）
  4. `frontend/src/components/QuestionGroupDrawer.tsx`（改）
  5. `frontend/src/pages/Questions.tsx`（改）

- **不许碰 `backend/`**（父会话并行在改 backend）。
- **不许 `git add` / `git commit` / `git push`**（父会话统一 commit）。

---

## 1. 后端契约（**父会话已实读源码确认，照此实现**）

后端本轮**同在 commit2 里同步改**，契约如下：

| 端点 | 本轮变化 |
|---|---|
| `POST /api/v1/academic/questions` | **不变**（单题建题） |
| `GET /api/v1/academic/questions` | **变了**：默认只返回 `group_id IS NULL` 的单题（组内小题**不再出现**）。分页参数与 `total` 口径**不变**（只管单题） |
| `POST /api/v1/academic/question-groups/{group_id}/questions` | **语义变了**：body 由 `{question_id, group_order}` 改为<br>`{ content, type, points, answer_text?, choices[]?, knowledge_point_ids[]? }`<br>⚠️ **没有 `group_order`**（后端 `max+1` 分配；`extra="forbid"` ⇒ 传了 **422**）<br>⚠️ **没有 `chapter_id` / 没有 `difficulty`**（后端从题组继承）<br>返回 `QuestionRead`（body 与 `QuestionRead` 同构） |
| `GET /api/v1/academic/question-groups` | **不变**：返回 `QuestionGroupRead[]` **全量**（**无分页、无 total**） |
| `GET /api/v1/academic/question-groups/{group_id}` | **不变**：`QuestionGroupDetail`（含 `blocks` + `questions`） |
| `DELETE /api/v1/academic/question-groups/{group_id}` | **不变**：无 `?force=true` 且组非空 ⇒ **409**，**body 的 `message`** 含三个计数（小题数/材料图数/材料块数）；带 `?force=true` ⇒ **204** |

**已有封装**（`src/api/questionGroups.ts`，**直接复用，不要重写**）：
`createQuestionGroup` / `listQuestionGroups(params?)` / `getQuestionGroup` / `updateQuestionGroup` /
`deleteQuestionGroup(groupId, force)` / `listGroupImages` / `deleteGroupImage`

**鉴权**：所有请求带 `AUTH_HEADERS`（= `X-User-Id: 1`，从 `src/api/questionTypes.ts` 导出），
用 `apiClient`（`src/api/client.ts`）。**数组参数**已全局 `paramsSerializer: {indexes: null}` ⇒ 重复键，**不要自己拼 query**。

**已有类型**（`src/api/questionTypes.ts`）：`QuestionRead`(:41) / `QuestionListResponse`(:60) /
`ChoiceRead`(:32) / `QuestionGroupRead`(:141) / `QuestionGroupDetail`(:170) / `ContentBlockRead`(:154) /
`QuestionDifficulty`(:106)。`QuestionRead` 里已有 `group_id` / `group_order` 字段。

---

## 2. 4 条裁决（星轨 15:50 拍板，**不可自行更改**）

| # | 裁决 | 对你的直接影响 |
|---|---|---|
| ① | **不做**「PATCH 单题改章节 ⇒ 409」守卫（后端无 `chapter_id` + `extra="forbid"` ⇒ 传了就是 422，那段守卫是**死代码**） | 你**不要**在前端写任何「改章节」的拦截 |
| ② | **前端不传 `group_order`**，后端 `max+1` | 建题 body **不含** `group_order` |
| ③ | **题组列表不分页**（全量列）；单题照旧分页 | 题组数据**独立 state**；**绝不**并入单题表的 `total` / `pagination` |
| ④ | **小题图失败不回滚** | 建题成功后才传图；图失败 ⇒ **保留该题** + 行上标「**待补图**」+ 给「**重传图片**」入口 + 文案必须含「**小题已创建（第 N 题），仅图片上传失败**」 |

---

## 3. 逐文件要求

### 3.1 `api/questionGroups.ts`（改）

新增 body 类型 + 一个函数：

```ts
export interface GroupQuestionCreateBody {
  content: string
  type: QuestionType
  points: number
  answer_text?: string
  choices?: ChoiceInput[]
  knowledge_point_ids?: number[]
}

/** POST /academic/question-groups/{id}/questions → QuestionRead（组内新建小题） */
export async function createGroupQuestion(
  groupId: number,
  body: GroupQuestionCreateBody,
): Promise<QuestionRead>
```

- `choices` 是**输入**类型：后端 `ChoiceBase` = `content` + `is_correct`。
  `questionTypes.ts` 现在只有读侧 `ChoiceRead` ⇒ **请新增 `ChoiceInput`**（只许加类型）。
- 若 `questionTypes.ts` 里已有同形状类型就**复用**，不要造重复类型。

### 3.2 `components/InlineQuestionForm.tsx`（**新增**，≈300 行）

**内联**表单（不是弹窗），两模式：`create` / `edit`。

- **章节**：**不显示选择器**（继承组）—— 判据 K。
- **难度**：**只读** `Tag` 显示组难度，**不给难度选择器** —— 判据 K。
- **知识点**：多选，默认继承组的，允许加减；只列**本章**知识点（由父级传 `knowledgePoints`）。
- **题型 / 分值 / 答案 / 选项**：与 1c-1 的 `components/QuestionDrawer.tsx` **同一套交互与校验**
  （`type=choice` 必填选项；`type≠choice` 不能有选项）。
  ⚠️ **去读 `QuestionDrawer.tsx` 照抄其表单结构与校验**，不要另发明一套。
- **小题图**：走 `POST /academic/questions/{question_id}/images`（multipart：`file` + `file_ext`）。
  ⚠️ **建题模式下没有 `question_id`** ⇒ 建题模式下**表单里不放图片上传**，图由父组件在**建题成功之后**再传（见 3.3）。
  编辑模式下可传/删图（`GET /academic/questions/{id}/images` / `DELETE /academic/questions/{id}/images/{image_id}`）。
- **保存**：编辑态走 `PATCH /academic/questions/{id}`（只传改动字段；⚠️ `QuestionUpdate` **没有 `chapter_id`**）。
  新建态由父组件负责建题（父组件知道 groupId 与继承字段），表单只负责收集并回传值。

### 3.3 `components/QuestionGroupDrawer.tsx`（改：小题区）

把现在的 **disabled 空壳**（`+ 新建小题` 按钮 + 占位文案）换成真实小题区：

- **数据源**：`GET /academic/question-groups/{id}` 的 `detail.questions`（**已有 `getQuestionGroup`**，别重写）。
- 每行显示：题序（**展示从 1 起**，库里 0 起）、题干摘要、题型、分值、知识点、图数、**「待补图」标记**。
- 「+ 新建小题」⇒ 内联展开 `InlineQuestionForm`（create）。
- 点已有小题行 ⇒ 内联展开 `InlineQuestionForm`（edit）⇒ 保存走 PATCH。
- 删除小题 ⇒ `Popconfirm` ⇒ `DELETE /academic/questions/{id}`。
- **不显示「移出题组」**（后端**没有** detach 端点）。

**建题 + 图的两段式（裁决 ④，顺序不可颠倒）**：

1. `POST /academic/question-groups/{id}/questions` 建题 ⇒ 成功拿到 `QuestionRead`；
2. **然后**才传图 `POST /academic/questions/{id}/images`；
3. 图失败 ⇒ **保留该题**（行留在组内列表 + 标「待补图」+ 给「重传图片」入口），
   并弹：`message.error(\`小题已创建（第 ${n} 题），仅图片上传失败\`)` ——
   ⚠️ **文案必须包含「小题已创建（第 N 题），仅图片上传失败」**（否则用户以为整笔失败 ⇒ 重试 ⇒ 建出第二道一样的题）；
4. **建题端点本身失败** ⇒ **不插入任何行**，弹 `message.error(后端 message 字段，**不是 detail**)`。

**🔴 既有硬边界，一个字都不要破坏**：

- `groupDrawerKey` **重挂载**模式（**不许用 `useEffect` 清 state**）；
- 图片字节走 axios `responseType:'blob'` + `createObjectURL` + 卸载 `revokeObjectURL`，
  **禁止 `<img src="/api/...">`**（发不出 `X-User-Id` ⇒ 401）；
- 未知 `block_type` 三层保护（`isKnownBlockType()` / `unsupportedType` / 保存前阻断 PUT + `blockToInput` 兜底抛错）**不要动**；
- T1 的会话图回收（`sessionUploadedImageIdsRef` / `registerSessionImage` / `cleanupOrphanSessionImages` /
  `deleteSessionImagesNotIn` / `handleClose` / `savedAtLabel`）**不要动**；
- 小题区也**不许**用 `useEffect` 清 state。

### 3.4 `pages/Questions.tsx`（改：题组行 + 删组确认 + 编辑态入口）

- **并行取** `GET /academic/question-groups`（**独立 state**；`params.chapter_id` = 当前章节）
  —— 与单题列表**分开管理**。
- **题组行与单题同表**：
  - `rowKey`：题组行 `group-<id>`，单题行 `q-<id>`；
  - 首列：题组行 = `[题组]` Tag + 「题组（N 小题）」；单题行照旧；
  - `Table.expandable`：展开题组行 ⇒ 内嵌小题摘要（题序/题干/分值/图数，只读即可）。
- **分页**：`pagination` **只管单题**；题组**不并入** `total`、**不参与分页** —— 判据 J。
- **删题组二次确认**（判据 D）：
  1. 用户点题组行的删除 ⇒ 先 `DELETE /academic/question-groups/{id}`（**不带 force**）；
  2. 若 **409** ⇒ 弹确认框，**把后端 `message` 原样透出**（含三个计数，**前端不许自己算**）；
  3. 用户确认后再 `DELETE ...?force=true`；
  4. 成功后刷新题组列表 + 单题列表。
- **编辑态入口**（commit1 缺的那个）：题组行点「编辑」⇒ 打开 `QuestionGroupDrawer` 的 **edit 模式**
  （`mode="edit"`、`groupId=<id>`）⇒ **沿用 `groupDrawerKey` 重挂载**（`key` 每次打开递增）。

---

## 4. 硬约束（违反即打回）

1. **不得改 `backend/`**。
2. **不得 commit / push**。
3. **不得用 `useEffect` 清 state**（1c-1 血泪：漏一个 state 就复现上一题的数据）。
4. **禁止 `<img src="/api/...">`**；图片字节只走 axios blob + objectURL。
5. **不得改**题组抽屉里材料层（blocks / 未知类型保护 / T1 回收）的既有实现。
6. 不得引入新依赖（无 npm install）。

---

## 5. 验收口径（**父会话独立复核；你不得自签**）

- 三条静态检查必须绿，**原始输出**贴进报告：
  `npm run lint`（`--max-warnings 0` ⇒ 0 warning）｜ `npx tsc -b --noEmit` ｜ `npm run build`
- 页面级判据 **A–K 由星轨**用 Playwright + 系统 Edge 执行 ⇒ **你不得声称页面通过**。

---

## 6. 交付（报告内容，缺项会被打回）

1. **改了什么**：逐文件 + 关键行号；
2. **跑了什么**：三条静态检查的**原始输出**；
3. **未覆盖声明**（**最重要**）：哪些路径你**没有**实现 / **没有**跑过 / 没跑浏览器验证 —— 逐条点名，**不要**写「应该没问题」；
4. **与契约的偏差**：若你发现本 brief 的契约与代码实际不符 ⇒ **停下并报告**，不要自己发明替代方案。
