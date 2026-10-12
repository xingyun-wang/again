import { Card, Space, Tag, Typography } from 'antd'

const { Title, Paragraph } = Typography

export default function TierOverride() {
  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card>
        <Title level={3}>M2 组件 ⑤ · 手动覆盖 + K/M/N</Title>
        <Paragraph type="secondary">placeholder · S2 启动时替换</Paragraph>
        <Space size="middle">
          <Tag color="blue">路由: /tier-override</Tag>
          <Tag color="default">状态: M2 骨架 placeholder</Tag>
        </Space>
        <Paragraph style={{ marginTop: 16, marginBottom: 0 }}>
          M2 组件 ⑤ · 手动覆盖 + K/M/N · placeholder · S2 启动时替换
        </Paragraph>
      </Card>
    </Space>
  )
}
