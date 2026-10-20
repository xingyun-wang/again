/**
 * 题目图片数据访问（1c-1c 裁决，2026-10-20 14:48）。
 *
 * 🔴 两条硬约束（来自 1c-1c 派工单）：
 * 1. **禁止** `<img src="/api/...">` —— <img> 发不出 X-User-Id 头 ⇒ 401。
 *    必须走 axios（带 header）+ `responseType: 'blob'` + `URL.createObjectURL`。
 * 2. **禁止** nginx 静态挂载 / 开 /uploads location —— 会绕过 owner 校验。
 *    图片字节一律走后端 `/content` 端点（那里做归属校验）。
 *
 * createObjectURL 的对象 URL 不会自动回收 ⇒ 调用方必须 revokeObjectURL
 * （见 components/QuestionImages.tsx 的 urlsRef + 卸载清理）。
 */
import { apiClient } from './client'
import { AUTH_HEADERS, type QuestionImageSummary } from './questionTypes'

/** 列出题目图片（1c-1c 新增端点，只出 4 个对外字段） */
export async function listQuestionImages(
  questionId: number,
): Promise<QuestionImageSummary[]> {
  const resp = await apiClient.get<QuestionImageSummary[]>(
    `/academic/questions/${questionId}/images`,
    { headers: AUTH_HEADERS },
  )
  return resp.data ?? []
}

/**
 * 取图片字节并转成 objectURL。
 *
 * 调用方负责在不用时 `URL.revokeObjectURL(url)`。
 */
export async function fetchImageObjectUrl(
  questionId: number,
  imageId: number,
): Promise<string> {
  const resp = await apiClient.get<Blob>(
    `/academic/questions/${questionId}/images/${imageId}/content`,
    { headers: AUTH_HEADERS, responseType: 'blob' },
  )
  return URL.createObjectURL(resp.data as Blob)
}
