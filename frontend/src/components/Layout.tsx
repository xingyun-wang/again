import { Layout as AntdLayout, Menu, Tooltip } from 'antd'
import type { ItemType } from 'antd/es/menu/interface'
import { Outlet, useLocation, Link } from 'react-router-dom'

const { Sider, Content } = AntdLayout

/**
 * M3 IA-1 一级导航（4 项）
 * - 备课    → /import          外部题库导入 = 教师备课辅助
 * - 出作业  → /assignments     作业生成 + 审阅 + PDF
 * - 学情    → /                首页占位（tooltip: M3 不做学情；交接书 §7 第 3 条）
 * - 设置    → /questions       题库 CRUD = 老师个人设置
 *
 * 4 项精简自原 M2 8 项横排；只剩一级入口；详细页（tiering / anti-matthew / tier-override / review）走子页面直达
 * 9 路由 children 维持原状，本组件只包 <Outlet />；具体 children 内容不在本 brief 范围
 */
function Layout() {
  const location = useLocation()
  // 当前路径即 menu key；未知路径由 router/* 重定向到 /，故总能命中
  const selectedKeys = [location.pathname]

  // 4 项菜单：学情项加 Tooltip 提示「M3 不做学情」；其他 3 项保持纯 Link
  const items: ItemType[] = [
    {
      key: '/',
      title: 'M3 不做学情',
      label: (
        <Tooltip title="M3 不做学情" placement="right">
          <Link to="/">学情</Link>
        </Tooltip>
      ),
    },
    { key: '/import', label: <Link to="/import">备课</Link> },
    { key: '/assignments', label: <Link to="/assignments">出作业</Link> },
    { key: '/questions', label: <Link to="/questions">设置</Link> },
  ]

  return (
    <AntdLayout style={{ minHeight: '100vh' }}>
      <Sider width={200} theme="dark" breakpoint="lg" collapsedWidth={0}>
        <div
          style={{
            color: '#fff',
            padding: '16px',
            fontSize: 16,
            fontWeight: 600,
            textAlign: 'center',
            borderBottom: '1px solid #1f1f1f',
          }}
        >
          差异化作业系统
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={selectedKeys}
          items={items}
        />
      </Sider>
      <AntdLayout>
        <Content style={{ padding: '24px 48px', background: '#fff' }}>
          <Outlet />
        </Content>
      </AntdLayout>
    </AntdLayout>
  )
}

export default Layout
