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
import {
  AUTH_HEADERS,
  type QuestionGroupImageRead,
  type QuestionImageSummary,
} from './questionTypes'

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

/**
 * 上传题组材料图（1c-2 commit 1 新增）。
 *
 * 🔴 multipart 三件套：file / file_ext / order_index / source。
 * - **不要**手写 'multipart/form-data'：手写值不带 boundary，浏览器 XHR
 *   不会替你补 ⇒ FastAPI 收不到 multipart ⇒ 422（1c-1 踩过，见 client.ts 注释）。
 * - 单组 ≤ 10 张、单张 ≤ 5MB、仅 png/jpg/jpeg/webp（svg 不收）—— 后端会拒，
 *   前端也做本地预校验（见 ContentBlockEditor.uploadMaterialImage）。
 * - timeout 放宽到 60s：apiClient 全局是 10s，5MB 图片在慢链路上会被前端先掐断。
 *
 * ⚠️ 返回体是 **QuestionImageRead（11 字段）**，与列表端点的
 *    QuestionImageSummary（4 字段）**不是同一个类型**，别混用。
 */
export async function uploadGroupImage(
  groupId: number,
  file: File,
  fileExt: string,
  orderIndex: number,
  source: 'self_built' | 'external_imported' = 'self_built',
): Promise<QuestionGroupImageRead> {
  const form = new FormData()
  form.append('file', file)
  form.append('file_ext', fileExt)
  form.append('order_index', String(orderIndex))
  form.append('source', source)
  const resp = await apiClient.post<QuestionGroupImageRead>(
    `/academic/question-groups/${groupId}/images`,
    form,
    { headers: AUTH_HEADERS, timeout: 60000 },
  )
  return resp.data
}

/**
 * 取题组材料图字节并转成 objectURL（1c-2 commit 1 新增）。
 *
 * 🔴 同 fetchImageObjectUrl：<img> 发不出 X-User-Id ⇒ 401，
 *    必须 axios(blob) + URL.createObjectURL；<img src> 只能是 blob: URL。
 *    调用方负责 revokeObjectURL。
 */
export async function fetchGroupImageObjectUrl(
  groupId: number,
  imageId: number,
): Promise<string> {
  const resp = await apiClient.get<Blob>(
    `/academic/question-groups/${groupId}/images/${imageId}/content`,
    { headers: AUTH_HEADERS, responseType: 'blob' },
  )
  return URL.createObjectURL(resp.data as Blob)
}
