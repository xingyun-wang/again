import { Card, Space, Tag, Typography } from 'antd'

const { Title, Paragraph } = Typography

export default function Questions() {
  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card>
        <Title level={3}>M2 组件 ① · 题库 CRUD</Title>
        <Paragraph type="secondary">placeholder · S 启动时替换</Paragraph>
        <Space size="middle">
          <Tag color="blue">路由: /questions</Tag>
          <Tag color="default">状态: M2 骨架 placeholder</Tag>
        </Space>
        <Paragraph style={{ marginTop: 16, marginBottom: 0 }}>
          M2 组件 ① · 题库 CRUD · placeholder · 已有真页(S 启动时替换)
        </Paragraph>
      </Card>
    </Space>
  )
}
