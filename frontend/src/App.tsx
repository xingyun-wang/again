import { useRoutes } from 'react-router-dom'
import { routes } from './router'

/**
 * M3 IA-1 App 壳：
 * - 4 项一级导航 + Sider 全部由 components/Layout.tsx 接管
 * - App.tsx 只负责 useRoutes 渲染路由表（路由表已把 9 路由挂在 Layout children 下）
 * - 移除原 M2 8 项横排 Header + Footer（决策书 §7.1 补丁 A → M3 精简为 4 项）
 */
function App() {
  const element = useRoutes(routes)
  return <>{element}</>
}

export default App
