import axios from 'axios'

const apiPrefix = import.meta.env.VITE_API_PREFIX || '/api'

export const apiClient = axios.create({
  baseURL: apiPrefix,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})
