import type { ReactNode } from 'react'
import type { RouteObject } from 'react-router-dom'
import { Navigate, useLocation } from 'react-router-dom'
import Layout from '../components/Layout'
import ErrorBoundary from '../components/ErrorBoundary'
import Home from '../pages/Home'
import Questions from '../pages/Questions'
import ImportPage from '../pages/Import'
import Tiering from '../pages/Tiering'
import AntiMatthew from '../pages/AntiMatthew'
import TierOverride from '../pages/TierOverride'
import Assignments from '../pages/Assignments'
import Review from '../pages/Review'

/**
 * M3 IA-1 路由表（决策书 §7.1 补丁 A + M3 派工 B1 改）：
 * - 顶层 pathless route = Layout 包裹（4 项一级导航 = 备课 / 出作业 / 学情 / 设置）
 * - children 维持 M2 9 路由原状（不动 children；只包 <Outlet />）
 * - /                首页（保留 Home.tsx，M1 状态桥接；学情占位）
 * - /questions       M2 组件 ① 题库 CRUD placeholder（设置入口）
 * - /import          M2 组件 ② 外部题库导入 placeholder（备课入口）
 * - /tiering         M2 组件 ③ 4 档差异化引擎 placeholder
 * - /anti-matthew    M2 组件 ④ 反马太引擎 placeholder
 * - /tier-override   M2 组件 ⑤ 手动覆盖 + K/M/N placeholder
 * - /assignments     M2 组件 ⑥ 作业生成 + 审阅 + PDF placeholder（出作业入口）
 * - /review          M2 组件 ⑦ 审阅硬约束 placeholder
 * - *                兜底重定向到首页
 */
/**
 * 页面级错误边界包装（P1 前端健壮性，星轨派工单 2026-10-20）。
 *
 * 逐页包而不是包 Layout：单页 render 抛错只降级该页，侧边导航（Layout 内）
 * 与其它页面不受影响，仍可点、仍能进 —— 这是派工单验收判据 2 的硬要求。
 * pathname 作 resetKey ⇒ 崩溃后切走再回来自动重新渲染，不必手动点「重试」。
 */
function Boundary({ children }: { children: ReactNode }) {
  const location = useLocation()
  return <ErrorBoundary resetKey={location.pathname}>{children}</ErrorBoundary>
}

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { path: '/', element: <Boundary><Home /></Boundary> },
      { path: '/questions', element: <Boundary><Questions /></Boundary> },
      { path: '/import', element: <Boundary><ImportPage /></Boundary> },
      { path: '/tiering', element: <Boundary><Tiering /></Boundary> },
      { path: '/anti-matthew', element: <Boundary><AntiMatthew /></Boundary> },
      { path: '/tier-override', element: <Boundary><TierOverride /></Boundary> },
      { path: '/assignments', element: <Boundary><Assignments /></Boundary> },
      { path: '/review', element: <Boundary><Review /></Boundary> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]
