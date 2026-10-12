import type { RouteObject } from 'react-router-dom'
import { Navigate } from 'react-router-dom'
import Home from '../pages/Home'
import Questions from '../pages/Questions'
import ImportPage from '../pages/Import'
import Tiering from '../pages/Tiering'
import AntiMatthew from '../pages/AntiMatthew'
import TierOverride from '../pages/TierOverride'
import Assignments from '../pages/Assignments'
import Review from '../pages/Review'

/**
 * M2 骨架路由表（决策书 §7.1 补丁 A）：
 * - /                首页（保留 Home.tsx，M1 状态桥接）
 * - /questions       M2 组件 ① 题库 CRUD placeholder
 * - /import          M2 组件 ② 外部题库导入 placeholder
 * - /tiering         M2 组件 ③ 4 档差异化引擎 placeholder
 * - /anti-matthew    M2 组件 ④ 反马太引擎 placeholder
 * - /tier-override   M2 组件 ⑤ 手动覆盖 + K/M/N placeholder
 * - /assignments     M2 组件 ⑥ 作业生成 + 审阅 + PDF placeholder
 * - /review          M2 组件 ⑦ 审阅硬约束 placeholder
 * - *                兜底重定向到首页
 */
export const routes: RouteObject[] = [
  { path: '/', element: <Home /> },
  { path: '/questions', element: <Questions /> },
  { path: '/import', element: <ImportPage /> },
  { path: '/tiering', element: <Tiering /> },
  { path: '/anti-matthew', element: <AntiMatthew /> },
  { path: '/tier-override', element: <TierOverride /> },
  { path: '/assignments', element: <Assignments /> },
  { path: '/review', element: <Review /> },
  { path: '*', element: <Navigate to="/" replace /> },
]
