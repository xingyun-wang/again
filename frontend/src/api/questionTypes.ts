/**
 * 题库共享类型与工具（对齐 backend/app/api/v1/schemas/academic.py）。
 *
 * 抽出来是因为 M3-1c-1 起了 QuestionDrawer 组件，列表页与抽屉需要同一份
 * QuestionRead / ChoiceRead 定义 —— 复制两份必然漂移。
 */

/** GET /textbooks → TextbookSummary */
export interface TextbookSummary {
  id: number
  title: string
  grade: string | null
  subject: string | null
}

/** GET /textbooks/{id}/chapters → { textbook_id, chapters: ChapterSummary[] } */
export interface ChapterSummary {
  id: number
  chapter_number: number
  title: string
}

/** GET /chapters/{id} → ChapterDetailResponse.knowledge_points */
export interface KnowledgePointDetail {
  id: number
  name: string
  concept: string
  teaching_order: number
}

/** ChoiceBase + ChoiceRead（label ≤ 8 / content / is_correct / order_index） */
export interface ChoiceRead {
  id?: number
  label: string
  content: string
  is_correct: boolean
  order_index: number
}

/** GET /questions → QuestionRead */
export interface QuestionRead {
  id: number
  owner_user_id: number
  chapter_id: number
  content: string
  difficulty: 'D' | 'C' | 'B' | 'A'
  type: 'choice' | 'fill' | 'subjective'
  points: number
  answer_text: string | null
  knowledge_point_ids: number[]
  /** 可选：后端镜像不同步时可能不返（旧 QuestionRead 无此二字段） */
  knowledge_point_names?: string[]
  image_count?: number
  /** 仅 choice 类型有；后端 schema 恒返空列表 */
  choices?: ChoiceRead[]
  created_at: string
  updated_at: string
}

export interface QuestionListResponse {
  items: QuestionRead[]
  total: number
}

/**
 * GET /questions/{id}/images → QuestionImageSummary（1c-1c 裁决）。
 * 🔴 刻意只 4 字段：后端不返 storage_path / oss_object_key /
 * desensitization_status / uploaded_by_user_id 等内部字段。
 */
export interface QuestionImageSummary {
  id: number
  order_index: number
  file_ext: string
  uploaded_at: string
}

/**
 * POST /question-groups/{id}/images 的返回体（后端 QuestionImageRead，11 字段）。
 *
 * 🔴 **刻意不复用 QuestionImageSummary**（4 字段）：上传返回体带
 * storage_path / oss_object_key / desensitization_status / uploaded_by_user_id
 * 等内部字段，后端 schema 就是这个形状 ⇒ 前端照抄，不要自己"精简"。
 */
export interface QuestionGroupImageRead {
  id: number
  order_index: number
  file_ext: string
  storage_path: string
  source: 'self_built' | 'external_imported'
  desensitization_status: string
  desensitized_at: string | null
  uploaded_at: string
  uploaded_by_user_id: number
  oss_object_key: string | null
  oss_uploaded_at: string | null
}

// ──────────────── M3-1c-2 题组 / 材料块（对齐 backend schemas/academic.py 1a-2 段） ────────────────
//
// ⚠️ 字段名**照抄后端**，不自创（前端自创字段名 ⇒ axios 不报错 ⇒ 静默丢值）。
// 核源位置：backend/app/api/v1/schemas/academic.py
//   - ContentBlockTypeLiteral（text | image | table）
//   - ContentBlockInput / ContentBlockRead / QuestionGroupRead / QuestionGroupDetail

/** 难度字母（题组与题目共用同一套口径） */
export type QuestionDifficulty = QuestionRead['difficulty']

/** 材料块类型（后端 ContentBlockTypeLiteral 白名单） */
export type ContentBlockType = 'text' | 'image' | 'table'

/**
 * 收窄服务端返回的 block_type。
 *
 * ⭐ **为什么要收窄，而不是直接当 union 用**：
 *   后端**读取** schema（`ContentBlockRead.block_type`）是**裸 str**，
 *   只有**写入** schema（`ContentBlockInput.block_type`）才是 Literal 白名单。
 *   ⇒ 库里出现历史脏值（如 "formula"）时后端会**原样返回**。
 *   直接当 union 用 ⇒ `BLOCK_TYPE_LABEL[脏值]` = undefined
 *   ⇒ 渲染出一个**没有任何编辑器的空壳块**，用户完全看不出发生了什么；
 *   而 PUT 的 blocks 是**整体替换** ⇒ 一存就把那块数据**悄悄抹掉**了。
 *   ⇒ 必须收窄成「已知 / 未知」两路：未知走**显式告警 + 阻断保存**。
 */
export function isKnownBlockType(t: string): t is ContentBlockType {
  return t === 'text' || t === 'image' || t === 'table'
}

/** 图片宽度档位（后端 meta.image_width：50 / 75 / 100，单位 = 百分数不是像素） */
export type ImageWidthPercent = 50 | 75 | 100

/** 宽度档位下拉/单选选项（唯一真源，编辑器与回显共用） */
export const IMAGE_WIDTH_OPTIONS: { value: ImageWidthPercent; label: string }[] = [
  { value: 50, label: '50%' },
  { value: 75, label: '75%' },
  { value: 100, label: '100%' },
]

/** 图片宽度缺省值（新建图片块 = 100%） */
export const DEFAULT_IMAGE_WIDTH: ImageWidthPercent = 100

/** GET /question-groups 列表项（也用于 POST 返回） */
export interface QuestionGroupRead {
  id: number
  owner_user_id: number
  chapter_id: number
  difficulty: QuestionDifficulty
  small_question_count: number
  total_points: number
  knowledge_point_ids: number[]
  created_at: string
  updated_at: string
}

/** GET /question-groups/{id} 的材料块 */
export interface ContentBlockRead {
  id: number
  /**
   * ⚠️ 如实声明为 **string**（不是 ContentBlockType）：
   *   后端读取 schema 就是裸 str，库里可能有历史脏值。
   *   收窄交给 isKnownBlockType()，**别在这里骗自己**。
   */
  block_type: string
  order_index: number
  text_content: string | null
  image_id: number | null
  table_json: Record<string, unknown> | null
  meta: Record<string, unknown> | null
}

/** GET /question-groups/{id} 详情（= Read + blocks + questions） */
export interface QuestionGroupDetail extends QuestionGroupRead {
  blocks: ContentBlockRead[]
  questions: QuestionRead[]
}

/** PUT /question-groups/{id} 的材料块写入体 */
export interface ContentBlockInput {
  block_type: ContentBlockType
  text_content?: string | null
  image_id?: number | null
  table_json?: Record<string, unknown> | null
  meta?: Record<string, unknown> | null
}

/**
 * table_json 的结构约定：`header=true` 表示首行是表头。
 * 后端只当 dict 存（dict[str, Any]），语义由前端定 ⇒ 这里定死一份。
 */
export interface TableJson {
  header: boolean
  rows: string[][]
}

/** 鉴权 header（M1-B B.3 简化 auth；demo 阶段写死 user 1） */
export const AUTH_HEADERS = { 'X-User-Id': '1' }

// ──────────────── 显示名映射（难度显示中文名不显示字母） ────────────────

export const DIFFICULTY_LABEL: Record<QuestionRead['difficulty'], string> = {
  D: '基础',
  C: '进阶',
  B: '挑战',
  A: '扩展',
}

export const TYPE_LABEL: Record<QuestionRead['type'], string> = {
  choice: '选择题',
  fill: '填空题',
  subjective: '主观题',
}

/** 抽屉用：难度只显示中文版本名，不显示字母（规格 §1c，对齐决策 10） */
export const DIFFICULTY_OPTIONS_CHINESE = (
  Object.keys(DIFFICULTY_LABEL) as QuestionRead['difficulty'][]
).map((v) => ({ value: v, label: DIFFICULTY_LABEL[v] }))

export const TYPE_OPTIONS = (Object.keys(TYPE_LABEL) as QuestionRead['type'][]).map((v) => ({
  value: v,
  label: TYPE_LABEL[v],
}))

/** 全局 handler 把 detail 改写成 message（app/core/errors.py:107）⇒ 优先取 message。 */
export function errorMessageOf(err: unknown, fallback = '未知错误'): string {
  const e = err as { response?: { data?: unknown }; message?: string }
  const data = e?.response?.data
  if (data && typeof data === 'object') {
    const obj = data as { message?: string; detail?: string }
    return obj.message ?? obj.detail ?? fallback
  }
  return e?.message ?? fallback
}
