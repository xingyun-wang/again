/**
 * 审阅页（M2-S3-frontend · brief §八）。
 *
 * 布局（3 Card）：
 * - Card 1: 加载作业（InputNumber assignment_id + 加载按钮）
 *   - 200 → 显示 Card 2 + 3
 *   - 404 → Alert "assignment 不存在"
 *   - 401 → Alert "X-User-Id 缺失"
 * - Card 2: 作业详情（Descriptions + Alert 展示 review）
 * - Card 3: 审阅表单（PATCH /api/v1/assignments/{id}/review）
 *   - 200 → 更新 Card 2 + Alert "审阅成功"
 *   - 422 → Alert "status 必为 reviewed/modified"
 *   - 404 / 401 → Alert 错误
 *
 * 状态：纯 useState（不引 zustand / React Query / SWR；§三 严禁）
 * 鉴权：X-User-Id header 写死 "1"（M1-B B.2 简化 auth；demo 阶段）
 */

import { useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Typography,
} from 'antd'
import type { AlertProps } from 'antd'

import { apiClient } from '../api/client'

const { Title, Paragraph } = Typography

// ──────────────── 类型定义（对齐 backend AssignmentRead + PATCH /review） ─────

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

interface ReviewResponse {
  id: number
  review: ReviewBlock
}

// ──────────────── 表单 / Alert 类型 ────────────────

type AlertKind = NonNullable<AlertProps['type']>

interface AlertState {
  kind: AlertKind
  message: string
  description?: string
}

interface ReviewFormValues {
  status: 'reviewed' | 'modified'
  notes?: string
}

// ──────────────── 主组件 ────────────────

export default function Review() {
  const [aid, setAid] = useState<number | null>(null)
  const [aidInput, setAidInput] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [assignment, setAssignment] = useState<AssignmentRead | null>(null)
  const [loadAlert, setLoadAlert] = useState<AlertState | null>(null)
  const [reviewForm] = Form.useForm<ReviewFormValues>()
  const [reviewing, setReviewing] = useState(false)
  const [reviewAlert, setReviewAlert] = useState<AlertState | null>(null)

  // 加载：GET /api/v1/assignments/{id}
  const onLoad = async () => {
    if (aidInput === null || aidInput < 1) {
      setLoadAlert({
        kind: 'warning',
        message: '请输入合法的 assignment_id（≥1）',
      })
      setAssignment(null)
      return
    }
    setLoading(true)
    setLoadAlert(null)
    setReviewAlert(null)
    try {
      const resp = await apiClient.get<AssignmentRead>(
        `/assignments/${aidInput}`,
        { headers: { 'X-User-Id': '1' } },
      )
      setAssignment(resp.data)
      setAid(aidInput)
      setLoadAlert({
        kind: 'success',
        message: `已加载作业单 #${resp.data.id}`,
      })
      // 预填表单：status 默认 reviewed（更常用）
      reviewForm.setFieldsValue({
        status: 'reviewed',
        notes: resp.data.review.review_notes ?? '',
      })
    } catch (err) {
      const e = err as { response?: { status: number; data?: { detail?: string } } }
      const code = e?.response?.status
      const detail = e?.response?.data?.detail ?? '未知错误'
      if (code === 404) {
        setLoadAlert({ kind: 'error', message: 'assignment 不存在', description: detail })
      } else if (code === 401) {
        setLoadAlert({ kind: 'error', message: 'X-User-Id 缺失', description: detail })
      } else {
        setLoadAlert({ kind: 'error', message: `加载失败（${code ?? '网络'}）`, description: detail })
      }
      setAssignment(null)
      setAid(null)
    } finally {
      setLoading(false)
    }
  }

  // 审阅：PATCH /api/v1/assignments/{id}/review
  const onReview = async (values: ReviewFormValues) => {
    if (!assignment) return
    setReviewing(true)
    setReviewAlert(null)
    try {
      const resp = await apiClient.patch<ReviewResponse>(
        `/assignments/${assignment.id}/review`,
        { status: values.status, notes: values.notes ?? null },
        { headers: { 'X-User-Id': '1' } },
      )
      // 200：更新本地 assignment.review 子对象（Card 2 重渲染）
      setAssignment({
        ...assignment,
        review: resp.data.review,
      })
      setReviewAlert({
        kind: 'success',
        message: `审阅成功（status=${resp.data.review.review_status}）`,
        description:
          resp.data.review.review_status === 'reviewed'
            ? '现在可以到「作业生成」页导出 PDF。'
            : '已标记为修改。',
      })
    } catch (err) {
      const e = err as { response?: { status: number; data?: { detail?: string } } }
      const code = e?.response?.status
      const detail = e?.response?.data?.detail ?? '未知错误'
      if (code === 422) {
        setReviewAlert({
          kind: 'warning',
          message: 'status 必为 reviewed / modified（Literal 拒 pending）',
          description: detail,
        })
      } else if (code === 404) {
        setReviewAlert({ kind: 'error', message: 'assignment 不存在', description: detail })
      } else if (code === 401) {
        setReviewAlert({ kind: 'error', message: 'X-User-Id 缺失', description: detail })
      } else {
        setReviewAlert({ kind: 'error', message: `审阅失败（${code ?? '网络'}）`, description: detail })
      }
    } finally {
      setReviewing(false)
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card>
        <Title level={3}>教师审阅</Title>
        <Paragraph type="secondary">
          加载作业单 → 标记 reviewed / modified（PATCH /api/v1/assignments/{'{id}'}/review；§7.5 流程硬约束）
        </Paragraph>
      </Card>

      {/* Card 1: 加载 */}
      <Card title="加载作业单">
        <Space>
          <InputNumber
            min={1}
            placeholder="assignment_id"
            value={aidInput ?? undefined}
            onChange={(v) => setAidInput(typeof v === 'number' ? v : null)}
            style={{ width: 200 }}
          />
          <Button type="primary" onClick={onLoad} loading={loading}>
            加载
          </Button>
        </Space>

        {loadAlert && (
          <Alert
            style={{ marginTop: 16 }}
            type={loadAlert.kind}
            message={loadAlert.message}
            description={loadAlert.description}
            showIcon
            closable
          />
        )}
      </Card>

      {/* Card 2: 详情 */}
      {assignment && (
        <Card title={`作业单 #${assignment.id} 详情`}>
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
        </Card>
      )}

      {/* Card 3: 审阅表单 */}
      {assignment && (
        <Card title="审阅操作">
          <Form<ReviewFormValues>
            form={reviewForm}
            layout="vertical"
            onFinish={onReview}
          >
            <Form.Item
              label="审阅状态"
              name="status"
              rules={[{ required: true, message: '请选择审阅状态' }]}
            >
              <Select
                options={[
                  { value: 'reviewed', label: '通过 (reviewed)' },
                  { value: 'modified', label: '修改 (modified)' },
                ]}
              />
            </Form.Item>

            <Form.Item
              label="审阅备注"
              name="notes"
              rules={[{ max: 4000, message: '备注最多 4000 字符' }]}
            >
              <Input.TextArea rows={4} maxLength={4000} showCount />
            </Form.Item>

            <Form.Item>
              <Button type="primary" htmlType="submit" loading={reviewing}>
                提交审阅
              </Button>
            </Form.Item>
          </Form>

          {reviewAlert && (
            <Alert
              type={reviewAlert.kind}
              message={reviewAlert.message}
              description={reviewAlert.description}
              showIcon
              closable
            />
          )}
        </Card>
      )}

      {/* 调试 helper：显示当前 aid 状态（不写 console；可视化给老师看）*/}
      {aid !== null && (
        <Card size="small">
          <Paragraph type="secondary" style={{ marginBottom: 0 }}>
            当前加载：aid={aid}
          </Paragraph>
        </Card>
      )}
    </Space>
  )
}
