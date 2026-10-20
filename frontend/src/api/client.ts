import axios from 'axios'

const apiPrefix = import.meta.env.VITE_API_PREFIX || '/api'

export const apiClient = axios.create({
  baseURL: apiPrefix,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
  // 数组参数展平成重复键 ?a=1&a=2（P0，星轨复核 66783cb）。
  // axios 1.x 默认序列化为 ?a[]=1&a[]=2，FastAPI 的 list[int] 只认重复键，
  // 带方括号的是未声明参数 → 被静默忽略 → 筛选不报错但不生效。
  // 全局设一次，1c 表单与后续抽题再出现数组参数时无需逐处记得。
  paramsSerializer: { indexes: null },
})
