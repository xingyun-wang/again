import { Card, Space, Tag, Typography } from 'antd'

const { Title, Paragraph } = Typography

export default function Tiering() {
  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card>
        <Title level={3}>M2 组件 ③ · 4 档差异化引擎</Title>
        <Paragraph type="secondary">placeholder · S1 启动时替换</Paragraph>
        <Space size="middle">
          <Tag color="blue">路由: /tiering</Tag>
          <Tag color="default">状态: M2 骨架 placeholder</Tag>
        </Space>
        <Paragraph style={{ marginTop: 16, marginBottom: 0 }}>
          M2 组件 ③ · 4 档差异化引擎 · placeholder · S1 启动时替换
        </Paragraph>
      </Card>
    </Space>
  )
}
