/**
 * 作业生成页（M2-S3-frontend · brief §七）。
 *
 * 布局（3 Card）：
 * - Card 1: 创建作业表单（POST /api/v1/assignments）
 * - Card 2: 创建结果（Descriptions + Alert 展示 review 字段）
 * - 导出按钮：POST /api/v1/assignments/{id}/export
 *   - 200 → Alert success
 *   - 403 → Alert warning（§7.5 闸门：未通过审阅）
 *   - 404 → Alert error
 *   - 401 → Alert error
 *
 * 状态：纯 useState（不引 zustand / React Query / SWR；§三 严禁 + §7.5 简）
 * 鉴权：X-User-Id header 写死 "1"（M1-B B.2 简化 auth；demo 阶段）
 */

import { useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Form,
  InputNumber,
  Select,
  Space,
  Typography,
} from 'antd'
import type { AlertProps } from 'antd'

import { apiClient } from '../api/client'

const { Title, Paragraph } = Typography

// ──────────────── 类型定义（对齐 backend AssignmentRead brief §5.1） ────────────

interface ReviewBlock {
  review_status: 'pending' | 'reviewed' | 'modified'
  reviewed_by: number | null
  reviewed_at: string | null
  review_notes: string | null
}

interface AssignmentItem {
  id: number
  question_id: number
  position: number
  tier_origin: 'D' | 'C' | 'B' | 'A'
}

interface AssignmentRead {
  id: number
  owner_user_id: number
  chapter_id: number
  tier: 'D' | 'C' | 'B' | 'A'
  total_count: number
  d_count: number
  c_count: number
  b_count: number
  a_count: number
  seed: number | null
  created_at: string
  items: AssignmentItem[]
  review: ReviewBlock
}

// ──────────────── 表单值类型 ────────────────

interface CreateFormValues {
  chapter_id: number
  tier: 'D' | 'C' | 'B' | 'A'
  total_count: number
  seed: number | null
}

// ──────────────── Alert state 类型 ────────────────

type AlertKind = NonNullable<AlertProps['type']>

interface AlertState {
  kind: AlertKind
  message: string
  description?: string
}

// ──────────────── 主组件 ────────────────

export default function Assignments() {
  const [form] = Form.useForm<CreateFormValues>()
  const [submitting, setSubmitting] = useState(false)
  const [assignment, setAssignment] = useState<AssignmentRead | null>(null)
  const [createAlert, setCreateAlert] = useState<AlertState | null>(null)
  const [exporting, setExporting] = useState(false)
  const [exportAlert, setExportAlert] = useState<AlertState | null>(null)

  // 提交：POST /api/v1/assignments
  const onCreate = async (values: CreateFormValues) => {
    setSubmitting(true)
    setCreateAlert(null)
    setExportAlert(null)
    try {
      // seed 是可空 number，antd 给的是 number | null | undefined
      const body: {
        chapter_id: number
        tier: string
        total_count: number
        seed: number | null
      } = {
        chapter_id: values.chapter_id,
        tier: values.tier,
        total_count: values.total_count,
        seed: values.seed ?? null,
      }
      const resp = await apiClient.post<AssignmentRead>(
        '/assignments',
        body,
        { headers: { 'X-User-Id': '1' } },
      )
      setAssignment(resp.data)
      setCreateAlert({
        kind: 'success',
        message: `作业单 #${resp.data.id} 创建成功`,
        description: `review_status=${resp.data.review.review_status}（需通过审阅才能导出）`,
      })
    } catch (err) {
      const e = err as { response?: { status: number; data?: { detail?: string } } }
      const code = e?.response?.status
      const detail = e?.response?.data?.detail ?? '未知错误'
      if (code === 401) {
        setCreateAlert({ kind: 'error', message: 'X-User-Id 缺失', description: detail })
      } else if (code === 404) {
        setCreateAlert({ kind: 'error', message: 'chapter 不存在', description: detail })
      } else if (code === 422) {
        setCreateAlert({ kind: 'warning', message: '字段非法 / 题库不足', description: detail })
      } else {
        setCreateAlert({ kind: 'error', message: `创建失败（${code ?? '网络'}）`, description: detail })
      }
      setAssignment(null)
    } finally {
      setSubmitting(false)
    }
  }

  // 导出：POST /api/v1/assignments/{id}/export（M2-S4-b：S4 后端已流式直返 application/pdf）
  const onExport = async () => {
    if (!assignment) return
    setExporting(true)
    setExportAlert(null)
    try {
      // responseType: 'blob' → S4 后端直返 application/pdf bytes, 前端取 Blob 即可
      const resp = await apiClient.post<Blob>(
        `/assignments/${assignment.id}/export`,
        {},
        {
          headers: { 'X-User-Id': '1' },
          responseType: 'blob',
        },
      )
      // 文件名从 Content-Disposition 解析 (per §一.2; 后端已返 assignment_{id}_{ts}.pdf)
      const dispo = resp.headers['content-disposition'] ?? ''
      const filenameMatch = /filename="([^"]+)"/.exec(dispo)
      const filename = filenameMatch ? filenameMatch[1] : `assignment_${assignment.id}.pdf`
      // 触发浏览器下载 (per §一.2; URL.createObjectURL + <a> click)
      const blobUrl = URL.createObjectURL(resp.data)
      const a = document.createElement('a')
      a.href = blobUrl
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(blobUrl)
      setExportAlert({
        kind: 'success',
        message: `已生成作业单 (${filename}), 正在下载...`,
        description: 'PDF 已保存到浏览器下载目录',
      })
    } catch (err) {
      const e = err as { response?: { status: number; data?: { detail?: string } } }
      const code = e?.response?.status
      const detail = e?.response?.data?.detail ?? '未知错误'
      if (code === 403) {
        setExportAlert({
          kind: 'warning',
          message: '未通过教师审阅（§7.5 硬约束）',
          description: `${detail}；请先到「审阅」页 PATCH /review 标记 reviewed/modified。`,
        })
      } else if (code === 404) {
        setExportAlert({ kind: 'error', message: 'assignment 不存在', description: detail })
      } else if (code === 401) {
        setExportAlert({ kind: 'error', message: 'X-User-Id 缺失', description: detail })
      } else {
        setExportAlert({ kind: 'error', message: `导出失败（${code ?? '网络'}）`, description: detail })
      }
    } finally {
      setExporting(false)
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card>
        <Title level={3}>作业生成</Title>
        <Paragraph type="secondary">
          填写章节 + 档位 + 题数 → 创建作业单（POST /api/v1/assignments）
        </Paragraph>
      </Card>

      {/* Card 1: 创建表单 */}
      <Card title="创建作业单">
        <Form<CreateFormValues>
          form={form}
          layout="vertical"
          initialValues={{ chapter_id: 1, tier: 'D', total_count: 30, seed: null }}
          onFinish={onCreate}
        >
          <Form.Item
            label="章节 ID"
            name="chapter_id"
            rules={[{ required: true, message: '请输入章节 ID' }]}
          >
            <InputNumber min={1} style={{ width: '100%' }} placeholder="1" />
          </Form.Item>

          <Form.Item
            label="档位"
            name="tier"
            rules={[{ required: true, message: '请选择档位' }]}
          >
            <Select
              options={[
                { value: 'D', label: 'D 基础' },
                { value: 'C', label: 'C 进阶' },
                { value: 'B', label: 'B 挑战' },
                { value: 'A', label: 'A 扩展' },
              ]}
            />
          </Form.Item>

          <Form.Item
            label="总题数"
            name="total_count"
            rules={[{ required: true, message: '请输入总题数（1-200）' }]}
          >
            <InputNumber min={1} max={200} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item label="随机种子" name="seed">
            <InputNumber
              style={{ width: '100%' }}
              placeholder="留空 = 系统时间（不可复现）"
            />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={submitting}>
              创建作业单
            </Button>
          </Form.Item>
        </Form>

        {createAlert && (
          <Alert
            type={createAlert.kind}
            message={createAlert.message}
            description={createAlert.description}
            showIcon
            closable
            style={{ marginTop: 16 }}
          />
        )}
      </Card>

      {/* Card 2: 创建结果 */}
      {assignment && (
        <Card
          title={`作业单 #${assignment.id} 详情`}
          extra={
            <Button type="primary" onClick={onExport} loading={exporting}>
              导出 PDF
            </Button>
          }
        >
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="ID">{assignment.id}</Descriptions.Item>
            <Descriptions.Item label="owner_user_id">
              {assignment.owner_user_id}
            </Descriptions.Item>
            <Descriptions.Item label="chapter_id">
              {assignment.chapter_id}
            </Descriptions.Item>
            <Descriptions.Item label="tier">{assignment.tier}</Descriptions.Item>
            <Descriptions.Item label="total_count">
              {assignment.total_count}
            </Descriptions.Item>
            <Descriptions.Item label="seed">
              {assignment.seed ?? '—（系统时间）'}
            </Descriptions.Item>
            <Descriptions.Item label="d_count">{assignment.d_count}</Descriptions.Item>
            <Descriptions.Item label="c_count">{assignment.c_count}</Descriptions.Item>
            <Descriptions.Item label="b_count">{assignment.b_count}</Descriptions.Item>
            <Descriptions.Item label="a_count">{assignment.a_count}</Descriptions.Item>
            <Descriptions.Item label="created_at" span={2}>
              {assignment.created_at}
            </Descriptions.Item>
            <Descriptions.Item label="items 数" span={2}>
              {assignment.items.length}
            </Descriptions.Item>
          </Descriptions>

          <Alert
            style={{ marginTop: 16 }}
            type={
              assignment.review.review_status === 'pending'
                ? 'info'
                : assignment.review.review_status === 'reviewed'
                  ? 'success'
                  : 'warning'
            }
            message={`审阅状态：${assignment.review.review_status}`}
            description={
              <Descriptions column={1} size="small" colon={false}>
                <Descriptions.Item label="reviewed_by">
                  {assignment.review.reviewed_by ?? '—'}
                </Descriptions.Item>
                <Descriptions.Item label="reviewed_at">
                  {assignment.review.reviewed_at ?? '—'}
                </Descriptions.Item>
                <Descriptions.Item label="review_notes">
                  {assignment.review.review_notes ?? '—'}
                </Descriptions.Item>
              </Descriptions>
            }
            showIcon
          />

          {exportAlert && (
            <Alert
              style={{ marginTop: 16 }}
              type={exportAlert.kind}
              message={exportAlert.message}
              description={exportAlert.description}
              showIcon
              closable
            />
          )}
        </Card>
      )}
    </Space>
  )
}
