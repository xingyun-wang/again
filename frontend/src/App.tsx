import { useRoutes, Link, useLocation } from 'react-router-dom'
import { Layout, Menu } from 'antd'
import type { MenuProps } from 'antd'
import { routes } from './router'

const { Header, Content, Footer } = Layout

type MenuItem = NonNullable<MenuProps['items']>[number]

/**
 * 顶部导航 8 项：1 个首页 + 7 段 M2 组件 placeholder
 * - key 与路由 path 1:1 映射，方便 selectedKeys 跟踪
 * - 决策书 §7.1 补丁 A：M2 7 组件 placeholder 入口（真页替换在各自 S 阶段）
 */
const menuItems: MenuItem[] = [
  { key: '/', label: <Link to="/">首页</Link> },
  { key: '/questions', label: <Link to="/questions">题库 CRUD</Link> },
  { key: '/import', label: <Link to="/import">外部题库导入</Link> },
  { key: '/tiering', label: <Link to="/tiering">4 档差异化引擎</Link> },
  { key: '/anti-matthew', label: <Link to="/anti-matthew">反马太引擎</Link> },
  { key: '/tier-override', label: <Link to="/tier-override">手动覆盖 + K/M/N</Link> },
  { key: '/assignments', label: <Link to="/assignments">作业生成 + 审阅 + PDF</Link> },
  { key: '/review', label: <Link to="/review">审阅硬约束</Link> },
]

function App() {
  const element = useRoutes(routes)
  const location = useLocation()
  // 当前路径即菜单 key；未知路径由 router/* 重定向到 /，故总能命中
  const selectedKeys = [location.pathname]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center' }}>
        <div style={{ color: '#fff', fontSize: 18, fontWeight: 600, marginRight: 32 }}>
          差异化作业系统
        </div>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={selectedKeys}
          items={menuItems}
        />
      </Header>
      <Content style={{ padding: '24px 48px' }}>
        {element}
      </Content>
      <Footer style={{ textAlign: 'center' }}>
        差异化作业系统 · M0 骨架 · v0.1.0
      </Footer>
    </Layout>
  )
}

export default App
