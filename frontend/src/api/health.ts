import axios from 'axios'

export interface HealthStatus {
  status: string
  version: string
}

// M0 绿页路径 = /api/health (无 v1)，与业务路由 /api/v1/* 解耦。
// 派工 v9 修：业务 baseURL 改 /api/v1 会让 apiClient.get('/health') 撞 /api/v1/health（404），
// 故 health 用 独立 axios 实例，固定走 /api/health，保留 timeout。
export async function fetchHealth(): Promise<HealthStatus> {
  const resp = await axios.get<HealthStatus>('/api/health', { timeout: 10000 })
  return resp.data
}
