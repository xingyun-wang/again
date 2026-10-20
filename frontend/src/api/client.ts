import axios from 'axios'

const apiPrefix = import.meta.env.VITE_API_PREFIX || '/api'

export const apiClient = axios.create({
  baseURL: apiPrefix,
  timeout: 10000,
  // ⚠️ 这里**不要**写死 Content-Type（P1，2026-10-20 21:21 星云报障 / 载曜修复）。
  //
  // 全局写死 'application/json' 时，axios 1.20.0 的 transformRequest 走这一支：
  //     if (isFormData) return hasJSONContentType ? JSON.stringify(formDataToJSON(data)) : data;
  // ⇒ FormData 被 formDataToJSON 转成**普通 JSON 对象**再 stringify，
  //    File/Blob 无法 JSON 序列化 ⇒ 图片字节直接丢失。
  // 实测上线原文：Content-Type=application/json，body={"file":{},"file_ext":"png",...}（68 字节）
  //    ⇒ FastAPI 根本收不到 multipart ⇒ 422。
  //
  // 删掉后交给 axios 按 data 类型自己判断（实测上线原文）：
  //     普通对象 → Content-Type: application/json
  //     FormData → Content-Type: multipart/form-data; boundary=axios-1.20.0-boundary-…（与 body 一致）
  //
  // ⚠️ 也**不要**在上传处手写 'multipart/form-data'：手写值不带 boundary，
  //    浏览器 XHR 不会替你补 ⇒ 同样 422（Node 下会被补，浏览器不会 —— 恰好是最容易测漏的组合）。
  //
  // 数组参数展平成重复键 ?a=1&a=2（P0，星轨复核 66783cb）。
  // axios 1.x 默认序列化为 ?a[]=1&a[]=2，FastAPI 的 list[int] 只认重复键，
  // 带方括号的是未声明参数 → 被静默忽略 → 筛选不报错但不生效。
  // 全局设一次，1c 表单与后续抽题再出现数组参数时无需逐处记得。
  paramsSerializer: { indexes: null },
})
