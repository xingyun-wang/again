import { useEffect, useState } from 'react'
import { Card, Space, Typography, Alert, Spin, Tag } from 'antd'
import { fetchHealth, type HealthStatus } from '../api/health'

const { Title, Paragraph } = Typography

type LoadState =
  | { kind: 'loading' }
  | { kind: 'ok'; data: HealthStatus }
  | { kind: 'error'; message: string }

export default function Home() {
  const [state, setState] = useState<LoadState>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false
    fetchHealth()
      .then((data) => {
        if (!cancelled) setState({ kind: 'ok', data })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const message = err instanceof Error ? err.message : String(err)
        setState({ kind: 'error', message })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card>
        <Title level={3}>差异化作业系统 — M0 骨架</Title>
        <Paragraph type="secondary">
          本页用于验证前后端联通。M0 阶段后端仅暴露 <code>/api/health</code>。
        </Paragraph>

        {state.kind === 'loading' && (
          <Space>
            <Spin />
            <span>连接后端中...</span>
          </Space>
        )}

        {state.kind === 'ok' && (
          <Alert
            type="success"
            showIcon
            message="✅ 后端连接成功"
            description={
              <Space size="middle">
                <Tag color="green">status: {state.data.status}</Tag>
                <Tag color="blue">version: {state.data.version}</Tag>
              </Space>
            }
          />
        )}

        {state.kind === 'error' && (
          <Alert
            type="error"
            showIcon
            message="❌ 后端连接失败"
            description={state.message}
          />
        )}
      </Card>
    </Space>
  )
}
