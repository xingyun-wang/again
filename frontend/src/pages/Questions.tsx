/**
 * 题库列表页（M3-1b · brief §1b-2）。
 *
 * 筛选区 6 项：教材 / 章节（级联）/ 知识点（多选）/ 难度（中文名）/ 题型 / 关键词
 * 表格 9 列：ID / 题干摘要 / 题型 / 难度 / 分值 / 知识点标签 / 图片数 / 更新时间 / 操作
 *
 * 操作列 3 按钮：
 * - 编辑 / 看图 → 1c 才实现 ⇒ message.info（**不画半成品抽屉**，brief §1b-2 硬约束）
 * - 删除       → 真实现：Popconfirm → DELETE /questions/{id} → 刷新列表
 *
 * 状态：纯 useState（不引 zustand / React Query / SWR）
 * 鉴权：X-User-Id header 写死 "1"（M1-B B.2 简化 auth；demo 阶段）
 *
 * 路由前缀：academic router = /api/v1/academic，apiClient baseURL = /api/v1
 *          ⇒ 本页路径以 /academic 开头（main.py:127）。
 */

import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Input,
  Popconfirm,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import type { TableColumnsType } from 'antd'

import { apiClient } from '../api/client'
import QuestionDrawer from '../components/QuestionDrawer'
import {
  DIFFICULTY_LABEL,
  TYPE_LABEL,
  TYPE_OPTIONS,
  errorMessageOf,
  type ChapterSummary,
  type KnowledgePointDetail,
  type QuestionListResponse,
  type QuestionRead,
  type TextbookSummary,
} from '../api/questionTypes'

const { Title, Paragraph, Text } = Typography

// ──────────────── 类型与显示名映射 ────────────────
// 类型定义 / label 映射已抽到 api/questionTypes.ts（1c-1a 抽屉组件共用，避免两份定义漂移）
// 这里的 DIFFICULTY_OPTIONS 保留 1b 列表页口径（字母 · 中文名）

const DIFFICULTY_OPTIONS = (
  Object.keys(DIFFICULTY_LABEL) as QuestionRead['difficulty'][]
).map((v) => ({ value: v, label: `${v} · ${DIFFICULTY_LABEL[v]}` }))

const CONTENT_PREVIEW_LEN = 50

function previewOf(content: string): string {
  return content.length > CONTENT_PREVIEW_LEN
    ? `${content.slice(0, CONTENT_PREVIEW_LEN)}…`
    : content
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}`
}

const AUTH_HEADERS = { 'X-User-Id': '1' }

export default function Questions() {
  const [textbooks, setTextbooks] = useState<TextbookSummary[]>([])
  const [textbookId, setTextbookId] = useState<number | undefined>(undefined)
  const [chapters, setChapters] = useState<ChapterSummary[]>([])
  const [chapterId, setChapterId] = useState<number | undefined>(undefined)
  const [knowledgePoints, setKnowledgePoints] = useState<KnowledgePointDetail[]>([])

  const [difficulty, setDifficulty] = useState<string | undefined>(undefined)
  const [qtype, setQtype] = useState<string | undefined>(undefined)
  const [keyword, setKeyword] = useState('')
  const [kpIds, setKpIds] = useState<number[]>([])

  const [items, setItems] = useState<QuestionRead[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  const [loading, setLoading] = useState(false)
  const [filterLoading, setFilterLoading] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  // M3-1c-1a：新建 / 编辑抽屉
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerMode, setDrawerMode] = useState<'create' | 'edit'>('create')
  const [editingQuestion, setEditingQuestion] = useState<QuestionRead | null>(null)

  // ──────────────── 题目列表 ────────────────

  const fetchQuestions = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await apiClient.get<QuestionListResponse>('/academic/questions', {
        headers: AUTH_HEADERS,
        params: {
          chapter_id: chapterId,
          difficulty,
          type: qtype,
          // 既有单选参数保留 + 新增多选参数（OR 语义）；两者同时给 = AND
          knowledge_point_ids: kpIds.length > 0 ? kpIds : undefined,
          keyword: keyword.trim() !== '' ? keyword.trim() : undefined,
          limit: pageSize,
          offset: (page - 1) * pageSize,
        },
      })
      setItems(resp.data?.items ?? [])
      setTotal(resp.data?.total ?? 0)
    } catch (err) {
      setItems([])
      setTotal(0)
      setError(errorMessageOf(err, '题目列表加载失败'))
    } finally {
      setLoading(false)
    }
  }, [chapterId, difficulty, qtype, kpIds, keyword, page, pageSize])

  useEffect(() => {
    void fetchQuestions()
  }, [fetchQuestions])

  // ──────────────── 教材 / 章节 / 知识点 级联 ────────────────

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const resp = await apiClient.get<TextbookSummary[]>('/academic/textbooks', {
          headers: AUTH_HEADERS,
        })
        if (!cancelled) setTextbooks(resp.data ?? [])
      } catch (err) {
        if (!cancelled) setError(errorMessageOf(err, '教材列表加载失败'))
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  /** 拉某章节的 KP；未选章节时汇总所选教材下所有章节的 KP（可为空数组，不报错）。 */
  // P2（星轨复核 66783cb）：知识点只在「已选具体章节」时拉该章 1 个请求。
  // 原实现只选教材时会对该教材所有章节 Promise.all 拉 GET /chapters/{id}（N 个请求）。
  const loadKnowledgePoints = useCallback(
    async (nextChapterId?: number) => {
      setFilterLoading(true)
      try {
        if (nextChapterId === undefined) {
          setKnowledgePoints([])
          return
        }
        const resp = await apiClient.get<{ knowledge_points: KnowledgePointDetail[] }>(
          `/academic/chapters/${nextChapterId}`,
          { headers: AUTH_HEADERS },
        )
        setKnowledgePoints(resp.data.knowledge_points ?? [])
      } catch (err) {
        setKnowledgePoints([])
        setError(errorMessageOf(err, '知识点加载失败'))
      } finally {
        setFilterLoading(false)
      }
    },
    [],
  )

  const onTextbookChange = (value: number | undefined) => {
    setTextbookId(value)
    setChapterId(undefined)
    setKpIds([])
    setPage(1)
    if (value === undefined) {
      setChapters([])
      setKnowledgePoints([])
      return
    }
    setFilterLoading(true)
    const load = async () => {
      try {
        const resp = await apiClient.get<{
          textbook_id: number
          chapters: ChapterSummary[]
        }>(`/academic/textbooks/${value}/chapters`, { headers: AUTH_HEADERS })
        setChapters(resp.data.chapters ?? [])
      } catch (err) {
        setChapters([])
        setError(errorMessageOf(err, '章节列表加载失败'))
      } finally {
        setFilterLoading(false)
      }
    }
    void load()
    setKnowledgePoints([])
  }

  const onChapterChange = (value: number | undefined) => {
    setChapterId(value)
    setKpIds([])
    setPage(1)
    void loadKnowledgePoints(value)
  }

  const resetFilters = () => {
    setTextbookId(undefined)
    setChapters([])
    setChapterId(undefined)
    setKnowledgePoints([])
    setKpIds([])
    setDifficulty(undefined)
    setQtype(undefined)
    setKeyword('')
    setPage(1)
  }

  const onDelete = async (id: number) => {
    setDeletingId(id)
    setError(null)
    try {
      await apiClient.delete(`/academic/questions/${id}`, { headers: AUTH_HEADERS })
      message.success(`题目 #${id} 已删除`)
      // 删掉当页最后一条时回退一页，避免停在空页
      if (items.length === 1 && page > 1) {
        setPage(page - 1)
      } else {
        await fetchQuestions()
      }
    } catch (err) {
      setError(errorMessageOf(err, `题目 #${id} 删除失败`))
    } finally {
      setDeletingId(null)
    }
  }

  // ──────────────── 表格 9 列 ────────────────

  const columns: TableColumnsType<QuestionRead> = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 72 },
    {
      title: '题干摘要',
      dataIndex: 'content',
      key: 'content',
      ellipsis: true,
      render: (content: string) => (
        <Tooltip title={content}>
          <span>{previewOf(content)}</span>
        </Tooltip>
      ),
    },
    {
      title: '题型',
      dataIndex: 'type',
      key: 'type',
      width: 96,
      render: (t: QuestionRead['type']) => TYPE_LABEL[t] ?? t,
    },
    {
      title: '难度',
      dataIndex: 'difficulty',
      key: 'difficulty',
      width: 110,
      render: (d: QuestionRead['difficulty']) => (
        <Tag color={d === 'A' ? 'purple' : d === 'B' ? 'orange' : d === 'C' ? 'blue' : 'green'}>
          {DIFFICULTY_LABEL[d] ?? d}
        </Tag>
      ),
    },
    {
      title: '分值',
      dataIndex: 'points',
      key: 'points',
      width: 80,
      align: 'right',
    },
    {
      title: '知识点标签',
      dataIndex: 'knowledge_point_names',
      key: 'knowledge_point_names',
      render: (names: string[] | undefined) => {
        const list = names ?? []
        return list.length === 0 ? (
          <Text type="secondary">—</Text>
        ) : (
          <Space size={[4, 4]} wrap>
            {list.map((n) => (
              <Tag key={n} color="geekblue">
                {n}
              </Tag>
            ))}
          </Space>
        )
      },
    },
    {
      title: '图片数',
      dataIndex: 'image_count',
      key: 'image_count',
      width: 90,
      align: 'right',
      // 区分「0 张」与「字段缺失」：缺失显示 —，0 仍显示 0（不谎报）
      render: (n: number | undefined) =>
        n === undefined ? <Text type="secondary">—</Text> : n,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 150,
      render: (v: string) => formatTime(v),
    },
    {
      title: '操作',
      key: 'actions',
      width: 220,
      render: (_, record) => (
        <Space size="small">
          <Button
            size="small"
            disabled={loading || deletingId !== null}
            onClick={() => {
              setDrawerMode('edit')
              setEditingQuestion(record)
              setDrawerOpen(true)
            }}
          >
            编辑
          </Button>
          <Button
            size="small"
            disabled={loading || deletingId !== null}
            onClick={() => message.info('图片预览在 1c 实现')}
          >
            看图
          </Button>
          <Popconfirm
            title="删除该题目？"
            description="删除后不可恢复（选项与知识点关联级联清理）。"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={() => onDelete(record.id)}
          >
            <Button size="small" danger loading={deletingId === record.id} disabled={loading}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <>
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card>
        <Title level={3}>题库</Title>
        <Paragraph type="secondary">
          按教材 / 章节 / 知识点 / 难度 / 题型 / 关键词筛选自己的题目（D-29 §1.4 题库个人资产）
        </Paragraph>
        <Button
          type="primary"
          disabled={loading}
          onClick={() => {
            setDrawerMode('create')
            setEditingQuestion(null)
            setDrawerOpen(true)
          }}
        >
          新建题目
        </Button>
      </Card>

      <Card title="筛选" size="small">
        <Row gutter={[12, 12]}>
          <Col xs={24} sm={12} md={8} lg={4}>
            <Text type="secondary">教材</Text>
            <Select
              style={{ width: '100%' }}
              allowClear
              placeholder="全部教材"
              loading={filterLoading}
              disabled={loading}
              value={textbookId}
              options={textbooks.map((t) => ({
                value: t.id,
                label: `${t.title}${t.grade ? ` · ${t.grade}` : ''}`,
              }))}
              onChange={onTextbookChange}
            />
          </Col>
          <Col xs={24} sm={12} md={8} lg={5}>
            <Text type="secondary">章节</Text>
            <Select
              style={{ width: '100%' }}
              allowClear
              placeholder={textbookId === undefined ? '先选教材' : '全部章节'}
              loading={filterLoading}
              disabled={loading || textbookId === undefined}
              value={chapterId}
              options={chapters.map((c) => ({
                value: c.id,
                label: `${c.chapter_number}. ${c.title}`,
              }))}
              onChange={onChapterChange}
            />
          </Col>
          <Col xs={24} sm={12} md={8} lg={6}>
            <Text type="secondary">知识点（多选）</Text>
            <Select
              style={{ width: '100%' }}
              mode="multiple"
              allowClear
              maxTagCount="responsive"
              placeholder={
                chapterId === undefined
                  ? '先选章节'
                  : knowledgePoints.length === 0
                    ? '本章无知识点'
                    : '全部知识点'
              }
              loading={filterLoading}
              disabled={loading || chapterId === undefined}
              value={kpIds}
              options={knowledgePoints.map((kp) => ({ value: kp.id, label: kp.name }))}
              onChange={(v: number[]) => {
                setKpIds(v)
                setPage(1)
              }}
            />
          </Col>
          <Col xs={24} sm={12} md={8} lg={4}>
            <Text type="secondary">难度</Text>
            <Select
              style={{ width: '100%' }}
              allowClear
              placeholder="全部难度"
              loading={loading}
              disabled={loading}
              value={difficulty}
              options={DIFFICULTY_OPTIONS}
              onChange={(v: string | undefined) => {
                setDifficulty(v)
                setPage(1)
              }}
            />
          </Col>
          <Col xs={24} sm={12} md={8} lg={4}>
            <Text type="secondary">题型</Text>
            <Select
              style={{ width: '100%' }}
              allowClear
              placeholder="全部题型"
              loading={loading}
              disabled={loading}
              value={qtype}
              options={TYPE_OPTIONS}
              onChange={(v: string | undefined) => {
                setQtype(v)
                setPage(1)
              }}
            />
          </Col>
          <Col xs={24} sm={12} md={8} lg={4}>
            <Text type="secondary">关键词</Text>
            <Input.Search
              allowClear
              placeholder="题干包含…"
              disabled={loading}
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onSearch={(v) => {
                setKeyword(v)
                setPage(1)
              }}
            />
          </Col>
          <Col xs={24} lg={3}>
            <Button onClick={resetFilters} disabled={loading}>
              重置筛选
            </Button>
          </Col>
        </Row>
      </Card>

      {error !== null && (
        <Alert type="error" showIcon message="请求失败" description={error} closable onClose={() => setError(null)} />
      )}

      <Card size="small">
        <Table<QuestionRead>
          rowKey="id"
          columns={columns}
          dataSource={items}
          loading={loading}
          size="middle"
          scroll={{ x: 1200 }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            pageSizeOptions: ['20', '50', '100'],
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, ps) => {
              setPage(ps !== pageSize ? 1 : p)
              setPageSize(ps)
            },
          }}
        />
      </Card>
    </Space>
      <QuestionDrawer
        open={drawerOpen}
        mode={drawerMode}
        question={editingQuestion}
        onClose={() => setDrawerOpen(false)}
        onSaved={() => void fetchQuestions()}
      />
    </>
  )
}
