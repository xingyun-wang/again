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
