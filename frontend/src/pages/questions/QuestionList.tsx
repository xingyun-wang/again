/**
 * 题目 CRUD 页（W4-T2）
 *
 * 列表 + 创建 + 编辑 + 删除 + 过滤（chapter / level / question_type / teacher_id）
 * 对接 W3-T2 后端 6 个端点。
 */

import { useEffect, useState } from 'react'
import {
  Card,
  Table,
  Button,
  Space,
  Modal,
  Form,
  Input,
  Select,
  Tag,
  Popconfirm,
  App as AntApp,
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { apiFetch } from '../../api/client'

type Level = 'D' | 'C' | 'B' | 'A'
type Chapter = 'ch1_earth_movement' | 'ch2_landforms' | 'ch3_atmosphere' | 'ch4_water' | 'ch5_integrity_difference'
type QuestionType = 'single_choice' | 'multiple_choice' | 'true_false'

interface Question {
  id: number
  content: string
  options: string[]
  answer: string | string[]
  question_type: QuestionType
  level: Level
  chapter: Chapter
  teacher_id: number
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

const TYPE_OPTIONS: { value: QuestionType; label: string }[] = [
  { value: 'single_choice', label: '单选' },
  { value: 'multiple_choice', label: '多选' },
  { value: 'true_false', label: '判断' },
]

export function QuestionList() {
  const { message } = AntApp.useApp()
  const [questions, setQuestions] = useState<Question[]>([])
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<{ chapter?: Chapter; level?: Level; question_type?: QuestionType; teacher_id?: number }>({})
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Question | null>(null)
  const [form] = Form.useForm()

  async function load() {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      Object.entries(filters).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') params.set(k, String(v))
      })
      const qs = params.toString()
      const data = await apiFetch<Question[]>(`/api/questions${qs ? `?${qs}` : ''}`)
      setQuestions(data)
    } catch (e) {
      message.error(`加载失败：${(e as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters)])

  function openCreate() {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({
      question_type: 'single_choice',
      level: 'D',
      chapter: 'ch1_earth_movement',
      teacher_id: 1,
      options: ['A.', 'B.', 'C.', 'D.'],
    })
    setModalOpen(true)
  }

  function openEdit(q: Question) {
    setEditing(q)
    form.setFieldsValue({
      ...q,
      answer: Array.isArray(q.answer) ? q.answer.join(',') : q.answer,
    })
    setModalOpen(true)
  }

  async function onSubmit() {
    try {
      const values = await form.validateFields()
      const payload = {
        ...values,
        // 多选 answer 用逗号分隔的字符串（后端期望 JSON 数组字符串）
        answer:
          values.question_type === 'multiple_choice'
            ? JSON.stringify(
                (values.answer as string)
                  .split(',')
                  .map((s: string) => s.trim())
                  .filter(Boolean),
              )
            : values.answer,
      }
      if (editing) {
        await apiFetch(`/api/questions/${editing.id}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        })
        message.success('已更新')
      } else {
        await apiFetch('/api/questions', {
          method: 'POST',
          body: JSON.stringify(payload),
        })
        message.success('已创建')
      }
      setModalOpen(false)
      load()
    } catch (e) {
      if ((e as { errorFields?: unknown }).errorFields) return // 表单校验失败
      message.error(`保存失败：${(e as Error).message}`)
    }
  }

  async function onDelete(id: number) {
    try {
      await apiFetch(`/api/questions/${id}`, { method: 'DELETE' })
      message.success('已删除')
      load()
    } catch (e) {
      message.error(`删除失败：${(e as Error).message}`)
    }
  }

  const columns: ColumnsType<Question> = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    {
      title: '题干',
      dataIndex: 'content',
      ellipsis: true,
      width: 300,
    },
    {
      title: '档位',
      dataIndex: 'level',
      width: 80,
      render: (lv: Level) => {
        const opt = LEVEL_OPTIONS.find((o) => o.value === lv)
        return <Tag color={opt?.color}>{opt?.label || lv}</Tag>
      },
    },
    {
      title: '章节',
      dataIndex: 'chapter',
      ellipsis: true,
      render: (ch: Chapter) => CHAPTER_OPTIONS.find((o) => o.value === ch)?.label || ch,
    },
    {
      title: '题型',
      dataIndex: 'question_type',
      width: 80,
      render: (t: QuestionType) => TYPE_OPTIONS.find((o) => o.value === t)?.label || t,
    },
    {
      title: '答案',
      dataIndex: 'answer',
      width: 100,
      render: (a: string | string[]) => (Array.isArray(a) ? a.join(',') : a),
    },
    {
      title: '操作',
      width: 140,
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm
            title="确认删除？"
            onConfirm={() => onDelete(record.id)}
            okText="是"
            cancelText="否"
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Card
      title="题库（W3-T2：6 个端点）"
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={load}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            新建题目
          </Button>
        </Space>
      }
    >
      <Space style={{ marginBottom: 16 }} wrap>
        <Select
          placeholder="档位"
          allowClear
          style={{ width: 120 }}
          value={filters.level}
          onChange={(v) => setFilters({ ...filters, level: v })}
          options={LEVEL_OPTIONS}
        />
        <Select
          placeholder="章节"
          allowClear
          style={{ width: 200 }}
          value={filters.chapter}
          onChange={(v) => setFilters({ ...filters, chapter: v })}
          options={CHAPTER_OPTIONS}
        />
        <Select
          placeholder="题型"
          allowClear
          style={{ width: 100 }}
          value={filters.question_type}
          onChange={(v) => setFilters({ ...filters, question_type: v })}
          options={TYPE_OPTIONS}
        />
      </Space>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={questions}
        loading={loading}
        size="small"
        pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 题` }}
      />

      <Modal
        title={editing ? '编辑题目' : '新建题目'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={onSubmit}
        okText="保存"
        cancelText="取消"
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="content" label="题干" rules={[{ required: true, min: 2 }]}>
            <Input.TextArea rows={3} placeholder="例如：地球自转的方向是？" />
          </Form.Item>
          <Form.Item name="options" label="选项（每行一个）" rules={[{ required: true }]}>
            <Input.TextArea
              rows={4}
              placeholder={'A. 自西向东\nB. 自东向西\nC. 自南向北\nD. 自北向南'}
              onChange={(e) => {
                const arr = e.target.value.split('\n').filter((s) => s.trim())
                form.setFieldValue('options', arr)
              }}
            />
          </Form.Item>
          <Space>
            <Form.Item name="level" label="档位" rules={[{ required: true }]} style={{ width: 120 }}>
              <Select options={LEVEL_OPTIONS} />
            </Form.Item>
            <Form.Item name="chapter" label="章节" rules={[{ required: true }]} style={{ width: 280 }}>
              <Select options={CHAPTER_OPTIONS} />
            </Form.Item>
            <Form.Item name="question_type" label="题型" rules={[{ required: true }]} style={{ width: 120 }}>
              <Select options={TYPE_OPTIONS} />
            </Form.Item>
          </Space>
          <Form.Item name="teacher_id" label="老师 ID" rules={[{ required: true }]}>
            <Input type="number" placeholder="MVP 暂用 1" />
          </Form.Item>
          <Form.Item
            name="answer"
            label="答案（多选用英文逗号分隔，如 A,C）"
            rules={[{ required: true }]}
          >
            <Input placeholder="A  /  A.x  /  对  /  A,C" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
