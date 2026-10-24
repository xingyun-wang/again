/**
 * 题组（材料层）数据访问 —— 1c-2 commit 1。
 *
 * 契约来源：backend/app/api/v1/routers/academic.py（1a-2 段）+ schemas/academic.py。
 * 已核源的三个**语义坑**（前端必须配合，写错就是静默丢数据）：
 *
 * ① PUT /question-groups/{id} 的 `blocks` 是**整体替换**：
 *    传则后端先 `delete(ContentBlock)` 再按**数组下标**重建 order_index；
 *    不传 = 不动。
 *    ⇒ 前端保存时必须传**完整**的块数组（顺序 = 数组顺序 = order_index），
 *      不能只传新增块。
 *
 * ② PUT 的 `knowledge_point_ids` 也是**整体替换**：
 *    传则先清空 group_knowledge_points 再按传序重建；**不传 = 不动**；
 *    传 `[]` = 清空。
 *    ⇒ 本模块保存时总是显式传数组（含空数组 = 清空语义明确）。
 *
 * ③ `DELETE /question-groups/{id}` 无 `?force=true` 且组非空 ⇒ 409，
 *    message（detail）里带「小题数 / 材料图数 / 材料块数」三个数字。
 *    前端**不许写死**这三个数字，必须读后端 message。
 *
 * 鉴权：所有请求带 `X-User-Id: 1`（M1-B B.2 简化 auth）。
 * 数组参数（knowledge_point_ids 之类）走 apiClient 的 paramsSerializer
 * （indexes: null ⇒ 重复键 ?a=1&a=2，FastAPI 的 list[int] 只认重复键）。
 */
import { apiClient } from './client'
import {
  AUTH_HEADERS,
  type ChoiceInput,
  type ContentBlockInput,
  type QuestionDifficulty,
  type QuestionGroupDetail,
  type QuestionGroupRead,
  type QuestionImageRead,
  type QuestionImageSummary,
  type QuestionRead,
  type QuestionType,
} from './questionTypes'

/** POST /question-groups 请求体（后端 QuestionGroupCreate） */
export interface QuestionGroupCreateBody {
  chapter_id: number
  difficulty: QuestionDifficulty
  knowledge_point_ids: number[]
}

/**
 * PUT /question-groups/{id} 请求体（后端 QuestionGroupUpdate）。
 *
 * ⚠️ 三字段都是「**传则整体替换，不传 = 不动**」⇒ 语义靠**在不在 body 里**区分，
 *    不是靠值。所以 blocks / knowledge_point_ids 一旦要改就必须传**全量**。
 */
export interface QuestionGroupUpdateBody {
  difficulty?: QuestionDifficulty
  blocks?: ContentBlockInput[]
  knowledge_point_ids?: number[]
}

/** POST /question-groups → 201 + QuestionGroupRead */
export async function createQuestionGroup(
  body: QuestionGroupCreateBody,
): Promise<QuestionGroupRead> {
  const resp = await apiClient.post<QuestionGroupRead>(
    '/academic/question-groups',
    body,
    { headers: AUTH_HEADERS },
  )
  return resp.data
}

/** GET /question-groups（可按 chapter_id / knowledge_point_id 筛） */
export async function listQuestionGroups(params?: {
  chapter_id?: number
  knowledge_point_id?: number
}): Promise<QuestionGroupRead[]> {
  const resp = await apiClient.get<QuestionGroupRead[]>('/academic/question-groups', {
    headers: AUTH_HEADERS,
    params,
  })
  return resp.data ?? []
}

/** GET /question-groups/{id} → 详情（材料块 + 小题） */
export async function getQuestionGroup(groupId: number): Promise<QuestionGroupDetail> {
  const resp = await apiClient.get<QuestionGroupDetail>(
    `/academic/question-groups/${groupId}`,
    { headers: AUTH_HEADERS },
  )
  return resp.data
}

/**
 * PUT /question-groups/{id} → 详情。
 *
 * ⚠️ axios 签名：put(url, data, config) —— **三参位**。
 *    （1c-1a 踩过：把 {headers, data} 当第二参传 ⇒ body 变成壳子、header 丢失 ⇒ 400）
 */
export async function updateQuestionGroup(
  groupId: number,
  body: QuestionGroupUpdateBody,
): Promise<QuestionGroupDetail> {
  const resp = await apiClient.put<QuestionGroupDetail>(
    `/academic/question-groups/${groupId}`,
    body,
    { headers: AUTH_HEADERS },
  )
  return resp.data
}

/**
 * DELETE /question-groups/{id}。
 *
 * 非空组必须 force=true（后端 409 + 三个计数在 message 里）。
 * 调用方负责把后端 message 原样透出，**前端不重算计数**。
 */
export async function deleteQuestionGroup(
  groupId: number,
  force = false,
): Promise<void> {
  await apiClient.delete(`/academic/question-groups/${groupId}`, {
    headers: AUTH_HEADERS,
    params: { force },
  })
}

/** GET /question-groups/{id}/images → QuestionImageSummary[]（4 字段；空组返 []） */
export async function listGroupImages(groupId: number): Promise<QuestionImageSummary[]> {
  const resp = await apiClient.get<QuestionImageSummary[]>(
    `/academic/question-groups/${groupId}/images`,
    { headers: AUTH_HEADERS },
  )
  return resp.data ?? []
}

/**
 * DELETE /question-groups/{id}/images/{image_id} → 204（删行 + 删磁盘文件）。
 *
 * 🔴 注意后端 content_blocks.image_id 上挂了 FK CASCADE：
 *    删图会**连带删掉引用它的材料块行**。
 *    ⇒ 前端换图/删图块时**不能立即删图**，必须排进「待删队列」，
 *      等 PUT（整体替换块）成功之后再删（见 QuestionGroupDrawer 的实现）。
 */
export async function deleteGroupImage(groupId: number, imageId: number): Promise<void> {
  await apiClient.delete(`/academic/question-groups/${groupId}/images/${imageId}`, {
    headers: AUTH_HEADERS,
  })
}

// ──────────────── 1c-2 commit 2：组内新建小题 + 小题图 ────────────────

/**
 * POST /question-groups/{group_id}/questions 请求体（**本轮语义已变**）。
 *
 * ⚠️ 三个「不许带」的字段（后端 extra="forbid" ⇒ 带了就是 422）：
 * - `group_order`：后端自己按 max+1 分配（裁决 ②）⇒ 前端**不传**；
 * - `chapter_id`  / `difficulty`：后端从题组继承（题组是唯一写入源）⇒ 前端**不传**。
 */
export interface GroupQuestionCreateBody {
  content: string
  type: QuestionType
  points: number
  answer_text?: string
  choices?: ChoiceInput[]
  knowledge_point_ids?: number[]
}

/**
 * POST /academic/question-groups/{group_id}/questions → QuestionRead（组内新建小题）。
 *
 * ⚠️ body **不含** group_order（后端 max+1 分配；extra="forbid" ⇒ 传了就是 422）
 * ⚠️ body **不含** chapter_id / difficulty（后端从题组继承）
 * ⚠️ choices 用后端 **ChoiceBase** 的形状（label / content / is_correct / order_index）：
 *    brief §3.1 写的是「ChoiceBase = content + is_correct」，但**实际后端源码**
 *    （schemas/academic.py 的 ChoiceBase + DB 列 choices.label NOT NULL）
 *    的 label 是**必填** ⇒ 前端按实际源码发全 4 字段
 *    （与 1c-1 QuestionDrawer 的 POST /questions 同一口径）。
 */
export async function createGroupQuestion(
  groupId: number,
  body: GroupQuestionCreateBody,
): Promise<QuestionRead> {
  const resp = await apiClient.post<QuestionRead>(
    `/academic/question-groups/${groupId}/questions`,
    body,
    { headers: AUTH_HEADERS },
  )
  return resp.data
}

/**
 * POST /academic/questions/{question_id}/images（multipart）→ QuestionImageRead。
 *
 * ⚠️ **不要**手写 'multipart/form-data'（手写值不带 boundary，浏览器 XHR 不会替你补
 *    ⇒ FastAPI 收不到 multipart ⇒ 422，见 api/client.ts 的注释）。
 * ⚠️ timeout 放宽到 60s（apiClient 全局 10s ⇒ 5MB 图在慢链路上会被前端先掐断）。
 * ⚠️ 后端校验顺序：owner → 存在性 → 格式 → 单题 ≤ 10 张 → ≤ 5MB（详见 router）。
 *
 * 📌 **为什么放在 questionGroups.ts 而不是 api/images.ts**：
 *    本笔 brief 的可改文件清单只有 5 个，`api/images.ts` 不在其中
 *    ⇒ 不新建、不修改它；小题图的上传封装落在这里，题组抽屉与内联表单共用。
 */
export async function uploadQuestionImage(
  questionId: number,
  file: File,
  fileExt: string,
  orderIndex: number,
): Promise<QuestionImageRead> {
  const form = new FormData()
  form.append('file', file)
  form.append('file_ext', fileExt)
  form.append('order_index', String(orderIndex))
  form.append('source', 'self_built')
  const resp = await apiClient.post<QuestionImageRead>(
    `/academic/questions/${questionId}/images`,
    form,
    { headers: AUTH_HEADERS, timeout: 60000 },
  )
  return resp.data
}
