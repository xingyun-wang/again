import { Routes, Route, Link } from 'react-router-dom'
import { Layout, Menu } from 'antd'
import Home from './pages/Home'

const { Header, Content, Footer } = Layout

function App() {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center' }}>
        <div style={{ color: '#fff', fontSize: 18, fontWeight: 600, marginRight: 32 }}>
          差异化作业系统
        </div>
        <Menu
          theme="dark"
          mode="horizontal"
          defaultSelectedKeys={['home']}
          items={[{ key: 'home', label: <Link to="/">首页</Link> }]}
        />
      </Header>
      <Content style={{ padding: '24px 48px' }}>
        <Routes>
          <Route path="/" element={<Home />} />
        </Routes>
      </Content>
      <Footer style={{ textAlign: 'center' }}>
        差异化作业系统 · M0 骨架 · v0.1.0
      </Footer>
    </Layout>
  )
}

export default App
