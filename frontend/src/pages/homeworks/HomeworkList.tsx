/**
 * 作业管理页（W4-T3 + T4）
 *
 * 列表 + 创建（生成作业含反马太）+ 详情 + 审阅（手动调档）+ 发布
 * 对接 W3-T4 + T5 后端 5 个端点：
 *   GET  /api/classes/{class_id}/homeworks
 *   POST /api/classes/{class_id}/homeworks/generate
 *   GET  /api/homeworks/{id}
 *   POST /api/homeworks/{id}/review
 *   POST /api/homeworks/{id}/publish
 */

import { useEffect, useState } from 'react'
import {
  Card,
  Row,
  Col,
  Button,
  Space,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  Switch,
  Table,
  Tag,
  Alert,
  App as AntApp,
  Statistic,
  Descriptions,
  Divider,
} from 'antd'
import {
  PlusOutlined,
  ReloadOutlined,
  EyeOutlined,
  EditOutlined,
  CloudUploadOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { apiFetch } from '../../api/client'

type Level = 'D' | 'C' | 'B' | 'A'
type Chapter = 'ch1_earth_movement' | 'ch2_landforms' | 'ch3_atmosphere' | 'ch4_water' | 'ch5_integrity_difference'
type Status = 'draft' | 'generated' | 'reviewed' | 'published'

interface HomeworkListItem {
  id: number
  class_id: number
  teacher_id: number
  title: string
  status: Status
  generated_at: string | null
  reviewed_at: string | null
  published_at: string | null
  question_count: number
}

interface HomeworkDetail {
  id: number
  class_id: number
  teacher_id: number
  title: string
  status: Status
  generated_at: string | null
  reviewed_at: string | null
  published_at: string | null
  questions: HomeworkQuestion[]
}

interface HomeworkQuestion {
  id: number
  question_id: number
  level: Level
  position: number
}

const LEVEL_OPTIONS: { value: Level; label: string; color: string }[] = [
  { value: 'D', label: 'D 基础', color: 'green' },
  { value: 'C', label: 'C 进阶', color: 'blue' },
  { value: 'B', label: 'B 挑战', color: 'orange' },
  { value: 'A', label: 'A 扩展', color: 'red' },
]

const CHAPTER_OPTIONS: { value: Chapter; label: string }[] = [
  { value: 'ch1_earth_movement', label: '第一章 地球的运动' },
  { value: 'ch2_landforms', label: '第二章 地表形态的塑造' },
  { value: 'ch3_atmosphere', label: '第三章 大气的运动' },
  { value: 'ch4_water', label: '第四章 水的运动' },
  { value: 'ch5_integrity_difference', label: '第五章 自然环境的整体性与差异性' },
]

const STATUS_META: Record<Status, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  generated: { color: 'processing', text: '已生成' },
  reviewed: { color: 'warning', text: '已审阅' },
  published: { color: 'success', text: '已发布' },
}

export function HomeworkList() {
  const { message } = AntApp.useApp()
  const [classId, setClassId] = useState<number | null>(null)
  const [homeworks, setHomeworks] = useState<HomeworkListItem[]>([])
  const [loading, setLoading] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [detail, setDetail] = useState<HomeworkDetail | null>(null)
  const [reviewMode, setReviewMode] = useState(false)
  const [editMap, setEditMap] = useState<Record<number, Level>>({})
  const [createForm] = Form.useForm()
  const [stats, setStats] = useState<{ d: number; c: number; b: number; a: number }>({
    d: 0,
    c: 0,
    b: 0,
    a: 0,
  })

  async function loadHomeworks() {
    if (!classId) return
    setLoading(true)
    try {
      const data = await apiFetch<HomeworkListItem[]>(`/api/classes/${classId}/homeworks`)
      setHomeworks(data)
    } catch (e) {
      message.error(`加载作业失败：${(e as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadHomeworks()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classId])

  function openCreate() {
    createForm.resetFields()
    createForm.setFieldsValue({
      teacher_id: 1,
      D: 5,
      C: 3,
      B: 2,
      A: 1,
      anti_matthew: true,
    })
    setCreateOpen(true)
  }

  async function onGenerate() {
    if (!classId) return
    try {
      const v = await createForm.validateFields()
      const { teacher_id, title, D, C, B, A, chapters, anti_matthew } = v
      const resp = await apiFetch<{
        homework: HomeworkDetail
        warnings: string[]
      }>(`/api/classes/${classId}/homeworks/generate`, {
        method: 'POST',
        body: JSON.stringify({
          teacher_id,
          title,
          questions_per_level: { D, C, B, A },
          chapters: chapters && chapters.length > 0 ? chapters : null,
          anti_matthew,
        }),
      })
      const warnings = resp.warnings || []
      if (warnings.length > 0) {
        Modal.warning({
          title: '生成成功（含警告）',
          content: (
            <div>
              {warnings.map((w, i) => (
                <div key={i}>⚠ {w}</div>
              ))}
            </div>
          ),
        })
      } else {
        message.success('作业生成成功')
      }
      setCreateOpen(false)
      setDetail(resp.homework)
      setReviewMode(false)
      // 编辑模式初始值（用当前 level）
      const m: Record<number, Level> = {}
      resp.homework.questions.forEach((q) => {
        m[q.id] = q.level
      })
      setEditMap(m)
      loadHomeworks()
    } catch (e) {
      if ((e as { errorFields?: unknown }).errorFields) return
      message.error(`生成失败：${(e as Error).message}`)
    }
  }

  async function openDetail(id: number) {
    try {
      const data = await apiFetch<HomeworkDetail>(`/api/homeworks/${id}`)
      setDetail(data)
      setReviewMode(false)
      const m: Record<number, Level> = {}
      data.questions.forEach((q) => {
        m[q.id] = q.level
      })
      setEditMap(m)
    } catch (e) {
      message.error(`加载详情失败：${(e as Error).message}`)
    }
  }

  async function onSaveReview() {
    if (!detail) return
    const questions = Object.entries(editMap)
      .filter(([hqid, lvl]) => {
        const orig = detail.questions.find((q) => q.id === Number(hqid))
        return orig && orig.level !== lvl
      })
      .map(([homework_question_id, new_level]) => ({
        homework_question_id: Number(homework_question_id),
        new_level,
      }))
    if (questions.length === 0) {
      message.info('无变化，直接退出审阅')
      setReviewMode(false)
      return
    }
    try {
      const updated = await apiFetch<HomeworkDetail>(`/api/homeworks/${detail.id}/review`, {
        method: 'POST',
        body: JSON.stringify({ questions }),
      })
      message.success(`已调整 ${questions.length} 题档位`)
      setDetail(updated)
      const m: Record<number, Level> = {}
      updated.questions.forEach((q) => {
        m[q.id] = q.level
      })
      setEditMap(m)
      setReviewMode(false)
      loadHomeworks()
    } catch (e) {
      message.error(`审阅失败：${(e as Error).message}`)
    }
  }

  async function onPublish() {
    if (!detail) return
    try {
      const updated = await apiFetch<HomeworkDetail>(`/api/homeworks/${detail.id}/publish`, {
        method: 'POST',
      })
      message.success('作业已发布')
      setDetail(updated)
      loadHomeworks()
    } catch (e) {
      message.error(`发布失败：${(e as Error).message}`)
    }
  }

  // 计算 D/C/B/A 题目数（详情打开时）
  useEffect(() => {
    if (!detail) {
      setStats({ d: 0, c: 0, b: 0, a: 0 })
      return
    }
    const s = { d: 0, c: 0, b: 0, a: 0 }
    Object.values(editMap).forEach((lv) => {
      if (lv === 'D') s.d++
      else if (lv === 'C') s.c++
      else if (lv === 'B') s.b++
      else if (lv === 'A') s.a++
    })
    setStats(s)
  }, [editMap, detail])

  const listColumns: ColumnsType<HomeworkListItem> = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '标题', dataIndex: 'title' },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (s: Status) => <Tag color={STATUS_META[s].color}>{STATUS_META[s].text}</Tag>,
    },
    { title: '题目数', dataIndex: 'question_count', width: 80 },
    {
      title: '生成时间',
      dataIndex: 'generated_at',
      width: 180,
      render: (t: string | null) => (t ? t.substring(0, 19).replace('T', ' ') : '—'),
    },
    {
      title: '审阅时间',
      dataIndex: 'reviewed_at',
      width: 180,
      render: (t: string | null) => (t ? t.substring(0, 19).replace('T', ' ') : '—'),
    },
    {
      title: '发布时间',
      dataIndex: 'published_at',
      width: 180,
      render: (t: string | null) => (t ? t.substring(0, 19).replace('T', ' ') : '—'),
    },
    {
      title: '操作',
      width: 100,
      render: (_, r) => (
        <Button size="small" icon={<EyeOutlined />} onClick={() => openDetail(r.id)}>
          查看
        </Button>
      ),
    },
  ]

  return (
    <Card title="作业（W3-T4/T5：生成含反马太 + 审阅手动调档 + 发布）">
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Select
            placeholder="选班级"
            style={{ width: '100%' }}
            value={classId || undefined}
            onChange={setClassId}
            options={[
              { value: 1, label: '高二(1)班（class id=1，W1-T4 seed）' },
              { value: 2, label: '高二(2)班（class id=2，e2e 验证用）' },
              { value: 3, label: 'class id=3' },
            ]}
            showSearch
          />
        </Col>
        <Col span={6}>
          <Button icon={<ReloadOutlined />} onClick={loadHomeworks} disabled={!classId}>
            刷新
          </Button>
        </Col>
        <Col span={6}>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            disabled={!classId}
            onClick={openCreate}
          >
            新建作业（含反马太）
          </Button>
        </Col>
      </Row>

      <Table
        rowKey="id"
        columns={listColumns}
        dataSource={homeworks}
        loading={loading}
        size="small"
        pagination={{ pageSize: 20 }}
      />

      {/* 创建作业 Modal */}
      <Modal
        title={
          <Space>
            <ThunderboltOutlined style={{ color: '#1677ff' }} />
            新建作业（D-W3-02 老师指定每档题数 + D-W3-03 反马太）
          </Space>
        }
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={onGenerate}
        okText="生成"
        cancelText="取消"
        width={600}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item name="title" label="作业标题" rules={[{ required: true, max: 200 }]}>
            <Input placeholder="如：第一章小测" />
          </Form.Item>
          <Form.Item name="teacher_id" label="老师 ID（MVP 暂用 1）" rules={[{ required: true }]}>
            <Input type="number" />
          </Form.Item>
          <Divider>每档题数</Divider>
          <Row gutter={16}>
            {(['D', 'C', 'B', 'A'] as Level[]).map((lv) => (
              <Col span={6} key={lv}>
                <Form.Item
                  name={lv}
                  label={
                    <Tag color={LEVEL_OPTIONS.find((o) => o.value === lv)?.color}>
                      {LEVEL_OPTIONS.find((o) => o.value === lv)?.label}
                    </Tag>
                  }
                  rules={[{ required: true }]}
                >
                  <InputNumber min={0} max={50} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
            ))}
          </Row>
          <Form.Item name="chapters" label="章节过滤（不选 = 全 5 章）">
            <Select
              mode="multiple"
              allowClear
              placeholder="全 5 章"
              options={CHAPTER_OPTIONS}
            />
          </Form.Item>
          <Form.Item
            name="anti_matthew"
            label="反马太（D 档强制 20% 拔高，CHARTER §4 硬约束）"
            valuePropName="checked"
          >
            <Switch defaultChecked />
          </Form.Item>
          <Alert
            message="反马太规则：D 档题数 N ≥ 5 时，随机选 floor(N/5) 个位置用 C 档题替换；N < 5 不插。"
            type="info"
            showIcon
          />
        </Form>
      </Modal>

      {/* 详情 / 审阅 / 发布 Modal */}
      <Modal
        title={
          detail ? (
            <Space>
              <span>作业 #{detail.id}：{detail.title}</span>
              <Tag color={STATUS_META[detail.status].color}>{STATUS_META[detail.status].text}</Tag>
            </Space>
          ) : (
            '详情'
          )
        }
        open={!!detail}
        onCancel={() => setDetail(null)}
        footer={null}
        width={900}
      >
        {detail && (
          <>
            <Descriptions column={3} size="small" bordered>
              <Descriptions.Item label="班级">{detail.class_id}</Descriptions.Item>
              <Descriptions.Item label="老师">{detail.teacher_id}</Descriptions.Item>
              <Descriptions.Item label="题目数">{detail.questions.length}</Descriptions.Item>
              <Descriptions.Item label="生成时间">
                {detail.generated_at?.substring(0, 19).replace('T', ' ') || '—'}
              </Descriptions.Item>
              <Descriptions.Item label="审阅时间">
                {detail.reviewed_at?.substring(0, 19).replace('T', ' ') || '—'}
              </Descriptions.Item>
              <Descriptions.Item label="发布时间">
                {detail.published_at?.substring(0, 19).replace('T', ' ') || '—'}
              </Descriptions.Item>
            </Descriptions>

            <Row gutter={16} style={{ margin: '16px 0' }}>
              <Col span={6}>
                <Statistic title="D 基础" value={stats.d} valueStyle={{ color: '#52c41a' }} />
              </Col>
              <Col span={6}>
                <Statistic title="C 进阶" value={stats.c} valueStyle={{ color: '#1677ff' }} />
              </Col>
              <Col span={6}>
                <Statistic title="B 挑战" value={stats.b} valueStyle={{ color: '#fa8c16' }} />
              </Col>
              <Col span={6}>
                <Statistic title="A 扩展" value={stats.a} valueStyle={{ color: '#f5222d' }} />
              </Col>
            </Row>

            <Space style={{ marginBottom: 16 }}>
              {!reviewMode && detail.status !== 'published' && (
                <Button
                  type="primary"
                  icon={<EditOutlined />}
                  onClick={() => setReviewMode(true)}
                >
                  审阅（手动调整档位）
                </Button>
              )}
              {reviewMode && (
                <>
                  <Button type="primary" onClick={onSaveReview}>
                    保存审阅
                  </Button>
                  <Button onClick={() => setReviewMode(false)}>取消</Button>
                </>
              )}
              {detail.status === 'reviewed' && (
                <Button
                  type="primary"
                  icon={<CloudUploadOutlined />}
                  onClick={onPublish}
                  style={{ background: '#52c41a', borderColor: '#52c41a' }}
                >
                  发布
                </Button>
              )}
            </Space>

            {reviewMode && (
              <Alert
                message="审阅模式：调整每题档位后点'保存审阅'，状态将变为 reviewed（可手动调整不会被反马太覆盖）"
                type="warning"
                showIcon
                style={{ marginBottom: 16 }}
              />
            )}

            <Table
              rowKey="id"
              size="small"
              pagination={false}
              dataSource={[...detail.questions].sort((a, b) => a.position - b.position)}
              columns={[
                { title: '顺序', dataIndex: 'position', width: 60 },
                {
                  title: '题目 ID',
                  dataIndex: 'question_id',
                  width: 100,
                },
                {
                  title: '档位',
                  dataIndex: 'level',
                  width: 180,
                  render: (lv: Level, record) =>
                    reviewMode ? (
                      <Select
                        style={{ width: 120 }}
                        value={editMap[record.id] || lv}
                        onChange={(v) =>
                          setEditMap({ ...editMap, [record.id]: v as Level })
                        }
                        options={LEVEL_OPTIONS}
                      />
                    ) : (
                      <Tag
                        color={LEVEL_OPTIONS.find((o) => o.value === lv)?.color}
                      >
                        {LEVEL_OPTIONS.find((o) => o.value === lv)?.label || lv}
                      </Tag>
                    ),
                },
              ]}
            />
          </>
        )}
      </Modal>
    </Card>
  )
}
