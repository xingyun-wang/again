import { Typography, Card } from 'antd'

const { Title, Paragraph } = Typography

export function Dashboard() {
  return (
    <div>
      <Title level={3}>欢迎</Title>
      <Paragraph>差异化作业系统 MVP（W1 + W3 全部完成）</Paragraph>
      <Card>
        <Paragraph>
          左侧导航：
          <ul>
            <li><b>题库</b> — 老师自建题（W3-T2）</li>
            <li><b>班级 / 学生</b> — 建班 / 批量导入学生 / 改密（W1-T4）</li>
            <li><b>作业</b> — 出作业（反马太） / 审阅 / 发布（W3-T4 + T5）</li>
          </ul>
        </Paragraph>
        <Paragraph type="secondary">
          本页是占位，具体页面 W4-T2/T3/T4 接入
        </Paragraph>
      </Card>
    </div>
  )
}
