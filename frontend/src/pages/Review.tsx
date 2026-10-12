import { Card, Space, Tag, Typography } from 'antd'

const { Title, Paragraph } = Typography

export default function Review() {
  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card>
        <Title level={3}>M2 组件 ⑦ · 审阅硬约束</Title>
        <Paragraph type="secondary">placeholder · S3 启动时替换</Paragraph>
        <Space size="middle">
          <Tag color="blue">路由: /review</Tag>
          <Tag color="default">状态: M2 骨架 placeholder</Tag>
        </Space>
        <Paragraph style={{ marginTop: 16, marginBottom: 0 }}>
          M2 组件 ⑦ · 审阅硬约束 · placeholder · S3 启动时替换
        </Paragraph>
      </Card>
    </Space>
  )
}
