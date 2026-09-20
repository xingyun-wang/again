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
        <Title level={3}>差异化作业系统 — M1 已上线（API）</Title>
        <Paragraph type="secondary">
          M1 范围：学科知识库 + AI 备课助手 <strong>API 已就位</strong>；
          前端 UI 仅占位（业务能力请走 <code>/api/v1/academic/*</code>）。
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
            message="✅ 后端 API 进程存活（M1 UI 占位）"
            description={
              <div>
                <Space size="middle" style={{ marginBottom: 8 }}>
                  <Tag color="green">status: {state.data.status}</Tag>
                  <Tag color="blue">version: {state.data.version}</Tag>
                </Space>
                <Paragraph type="warning" style={{ marginTop: 8, marginBottom: 0 }}>
                  ⚠️ 仅表示 API 进程存活，不代表数据库 / 依赖可用。
                  生产 readiness 拆分（M2+ 落地 <code>/api/health/live</code> + <code>/api/health/ready</code>）。
                </Paragraph>
              </div>
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
