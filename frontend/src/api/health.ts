import { apiClient } from './client'

export interface HealthStatus {
  status: string
  version: string
}

export async function fetchHealth(): Promise<HealthStatus> {
  const resp = await apiClient.get<HealthStatus>('/health')
  return resp.data
}
