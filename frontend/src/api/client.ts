/**
 * API 客户端（W4-T1）
 *
 * 统一 fetch 封装 + 错误处理 + 类型定义占位。
 * 后端 15 个端点的完整类型定义留给 W4-T2/T3/T4 阶段（每个页面对应端点）。
 */

const API_BASE = 'http://localhost:8000'

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`HTTP ${status}: ${detail}`)
  }
}

export async function apiFetch<T = unknown>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })
  if (!res.ok) {
    const body = await res.text()
    let detail = body
    try {
      const parsed = JSON.parse(body)
      detail = parsed.detail || body
    } catch {
      // not JSON, use raw body
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

export type HealthResponse = { status: string; service: string }

export async function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/health')
}
