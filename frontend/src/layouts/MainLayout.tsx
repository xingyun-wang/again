/**
 * MainLayout（W4-T1）
 *
 * 侧边导航 + 顶部 + 内容区。Ant Design Layout + Menu + React Router。
 */

import { useState } from 'react'
import { Layout, Menu, theme, Typography } from 'antd'
import {
  BookOutlined,
  TeamOutlined,
  FileTextOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'

const { Header, Sider, Content } = Layout
const { Title } = Typography

const MENU_ITEMS = [
  { key: '/questions', icon: <BookOutlined />, label: '题库' },
  { key: '/classes', icon: <TeamOutlined />, label: '班级 / 学生' },
  { key: '/homeworks', icon: <FileTextOutlined />, label: '作业' },
  { key: '/settings', icon: <SettingOutlined />, label: '设置' },
]

export function MainLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const {
    token: { colorBgContainer, borderRadiusLG },
  } = theme.useToken()

  // 当前选中项：取 pathname 第一个匹配
  const selectedKey =
    MENU_ITEMS.find((m) => location.pathname.startsWith(m.key))?.key || '/questions'

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontWeight: 600,
            fontSize: collapsed ? 14 : 16,
          }}
        >
          {collapsed ? '作业' : '差异化作业'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={MENU_ITEMS}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ background: colorBgContainer, padding: '0 24px' }}>
          <Title level={4} style={{ margin: 0, lineHeight: '64px' }}>
            差异化作业工作台
          </Title>
        </Header>
        <Content style={{ margin: 24, padding: 24, background: colorBgContainer, borderRadius: borderRadiusLG }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
