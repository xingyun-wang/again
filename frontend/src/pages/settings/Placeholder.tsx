import { Typography, Card, Tag } from 'antd'

const { Title, Paragraph } = Typography

export function SettingsPlaceholder() {
  return (
    <div>
      <Title level={3}>设置</Title>
      <Card>
        <Tag color="processing">W4 占位</Tag>
        <Paragraph style={{ marginTop: 16 }}>
          该页面将在 W4 后续接入：账号、老师信息、反马太规则默认参数等。
        </Paragraph>
      </Card>
    </div>
  )
}
