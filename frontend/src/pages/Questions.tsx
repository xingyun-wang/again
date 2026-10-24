/**
 * 题库列表页（M3-1b · brief §1b-2）。
 *
 * 筛选区 6 项：教材 / 章节（级联）/ 知识点（多选）/ 难度（中文名）/ 题型 / 关键词
 * 表格 9 列：ID / 题干摘要 / 题型 / 难度 / 分值 / 知识点标签 / 图片数 / 更新时间 / 操作
 *
 * 操作列 3 按钮：
 * - 编辑 → 1c-1a 抽屉；看图 → 1c-1c 图片弹窗（blob → objectURL 渲染）
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
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd'
import type { TableColumnsType } from 'antd'

import { apiClient } from '../api/client'
import QuestionDrawer from '../components/QuestionDrawer'
import QuestionGroupDrawer from '../components/QuestionGroupDrawer'
import QuestionImages from '../components/QuestionImages'
import {
  deleteQuestionGroup,
  getQuestionGroup,
  listQuestionGroups,
  toUserFacingDeleteHint,
} from '../api/questionGroups'
import {
  DIFFICULTY_LABEL,
  TYPE_LABEL,
  TYPE_OPTIONS,
  errorMessageOf,
  type ChapterSummary,
  type GroupQuestionRead,
  type KnowledgePointDetail,
  type QuestionGroupDetail,
  type QuestionGroupRead,
  type QuestionListResponse,
  type QuestionRead,
  type TextbookSummary,
} from '../api/questionTypes'

const { Title, Paragraph, Text } = Typography

// ──────────────── 行模型（题组行 + 单题行同表） ────────────────
//
// ⚠️ **题组与单题是两张表、两套分页口径**（裁决 ③）：
//   - 单题：分页（pagination 只管它，total 也只算它）
//   - 题组：全量列（后端 GET /question-groups 无分页、无 total）
//   ⇒ 合并到同一张展示表，但**分页与 total 绝不含题组**。
type Row =
  | { kind: 'question'; key: string; question: QuestionRead }
  | { kind: 'group'; key: string; group: QuestionGroupRead }


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

  // M3-1c-2 commit 2：题组列表（**独立 state**；全量、不分页、不并入单题 total）。
  const [groups, setGroups] = useState<QuestionGroupRead[]>([])
  const [groupsLoading, setGroupsLoading] = useState(false)
  /** 展开题组行时懒加载的题组详情（小题摘要用） */
  const [groupDetails, setGroupDetails] = useState<Record<number, QuestionGroupDetail>>({})
  const [groupDetailLoadingId, setGroupDetailLoadingId] = useState<number | null>(null)
  const [deletingGroupId, setDeletingGroupId] = useState<number | null>(null)

  const [loading, setLoading] = useState(false)
  const [filterLoading, setFilterLoading] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  // M3-1c-1a：新建 / 编辑抽屉
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerMode, setDrawerMode] = useState<'create' | 'edit'>('create')
  const [editingQuestion, setEditingQuestion] = useState<QuestionRead | null>(null)
  // M3-1c-1 P2（星轨派工单 2026-10-21 13:26）：每次打开抽屉 = 一个新会话。
  //
  // 为什么需要 key：QuestionDrawer 有 21 个 useState，其中 createdQuestionId /
  // imageFiles / uploadedImages / uploadError 四个是「图片会话态」。
  // create 分支（QuestionDrawer.tsx:202-216）只重置了 12 个表单 state，
  // 唯独漏了这 4 个 ⇒ 上一次建题留下的 createdQuestionId 会活到下一次新建，
  // galleryId（:476）拿到上一题 id ⇒ 图片区直接显示上一题的图片。
  // 抽屉上 destroyOnClose 只销毁 children DOM，管不到组件自身的 useState。
  //
  // 这里用 key 让抽屉在「每次打开时整体重挂载」，21 个 state 一次性归零，
  // 不必在 create 分支里逐个补 setState（漏一个就复现）。
  // ⚠️ 别删这个 state，也别把递增点挪进 close：递增只发生在 openDrawer
  //    的两个调用点，关闭时不变 ⇒ 上传失败留在抽屉里点「重试上传」
  //    （QuestionDrawer.tsx:452-456 的提前 return）不会重挂载，会话态保留。
  const [drawerKey, setDrawerKey] = useState(0)
  // M3-1c-1c：列表页「看图」弹窗（题 id，null=关闭）
  const [galleryQuestionId, setGalleryQuestionId] = useState<number | null>(null)

  // M3-1c-2 commit 1：题组抽屉（纯前端材料层）。
  //
  // ⚠️ **同样的 key 重挂载纪律**（1c-1 血泪，1c-2 继续沿用）：
  //    题组抽屉的状态更多（教材/章节/知识点/难度/材料块草稿/待删图片队列…），
  //    靠 useEffect 清 state 一定会漏一个 ⇒ 每次打开 = 整体重挂载，
  //    状态一次性归零。递增点只在 openGroupDrawer 里，关闭时不变。
  const [groupDrawerOpen, setGroupDrawerOpen] = useState(false)
  const [groupDrawerKey, setGroupDrawerKey] = useState(0)
  // commit 2：题组抽屉的**编辑态入口**（列表页题组行 → mode="edit" + groupId）
  const [groupDrawerMode, setGroupDrawerMode] = useState<'create' | 'edit'>('create')
  const [editingGroupId, setEditingGroupId] = useState<number | null>(null)

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

  // ──────────────── 题组列表（1c-2 commit 2） ────────────────
  //
  // ⚠️ **与单题列表分开管理**（裁决 ③）：
  //   - 独立 state（groups），**不并入** items / total / pagination；
  //   - 后端 GET /question-groups **全量返回**（无分页、无 total）；
  //   - 筛选只按 chapter_id（当前章节）；未选章节 = 不传该参数（全部题组）。

  const fetchGroups = useCallback(async () => {
    setGroupsLoading(true)
    try {
      const list = await listQuestionGroups(
        chapterId === undefined ? undefined : { chapter_id: chapterId },
      )
      setGroups(list)
    } catch (err) {
      setGroups([])
      setError(errorMessageOf(err, '题组列表加载失败'))
    } finally {
      setGroupsLoading(false)
    }
  }, [chapterId])

  useEffect(() => {
    void fetchGroups()
  }, [fetchGroups])

  /** 刷新两张表（题组 + 单题） */
  const refreshAll = useCallback(async () => {
    await Promise.all([fetchQuestions(), fetchGroups()])
  }, [fetchQuestions, fetchGroups])

  /** 展开题组行时懒加载题组详情（拿小题摘要；只读） */
  const loadGroupDetail = useCallback(async (groupId: number) => {
    setGroupDetailLoadingId(groupId)
    try {
      const detail = await getQuestionGroup(groupId)
      setGroupDetails((prev) => ({ ...prev, [groupId]: detail }))
    } catch (err) {
      message.error(errorMessageOf(err, '题组小题加载失败'))
    } finally {
      setGroupDetailLoadingId(null)
    }
  }, [])

  /**
   * 删题组（二次确认，判据 D）。
   *
   * 1. 先 DELETE（**不带 force**）；
   * 2. 409 ⇒ 弹确认框，**把后端 message 原样透出**（含小题数/材料图数/材料块数三个计数，
   *    **前端不许自己算**）；
   * 3. 用户确认后再 DELETE ...?force=true；
   * 4. 成功后刷新题组列表 + 单题列表。
   */
  const onDeleteGroup = async (groupId: number) => {
    setDeletingGroupId(groupId)
    try {
      await deleteQuestionGroup(groupId)
      message.success('题组已删除')
      await refreshAll()
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 409) {
        // 后端 409 的 body.message 里带三个计数 ⇒ 原样透出
        // ⚠️ 但要裁掉后半句「；确认删除请加 ?force=true」——
        //    那是给开发者看的 API 用法，老师看不懂（星轨 1c-2 欠账 P3）。
        //    前半句「题组含 N 道小题、M 张材料图、K 个材料块」必须保留（= 告诉用户在删什么）。
        const backendMessage = toUserFacingDeleteHint(
          errorMessageOf(err, '题组非空'),
        )
        Modal.confirm({
          title: '确认删除该题组？',
          content: (
            <Space direction="vertical" size={4}>
              <Text>{backendMessage}</Text>
              <Text type="secondary" style={{ fontSize: 12 }}>
                删除后不可恢复（小题、材料图、材料块一并删除）。
              </Text>
            </Space>
          ),
          okText: '确认删除',
          cancelText: '取消',
          okButtonProps: { danger: true },
          onOk: async () => {
            try {
              await deleteQuestionGroup(groupId, true)
              message.success('题组已删除')
              await refreshAll()
            } catch (err2) {
              message.error(errorMessageOf(err2, '删除题组失败'))
            }
          },
        })
      } else {
        setError(errorMessageOf(err, '题组删除失败'))
      }
    } finally {
      setDeletingGroupId(null)
    }
  }

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

  // ──────────────── 表格 9 列（题组行 + 单题行同表） ────────────────

  const columns: TableColumnsType<Row> = [
    {
      title: 'ID',
      key: 'id',
      width: 150,
      render: (_, record) =>
        record.kind === 'group' ? (
          <Space size="small">
            <Tag color="blue">题组</Tag>
            <Text>题组（{record.group.small_question_count} 小题）</Text>
          </Space>
        ) : (
          <Text>{record.question.id}</Text>
        ),
    },
    {
      title: '题干摘要',
      key: 'content',
      ellipsis: true,
      render: (_, record) =>
        record.kind === 'group' ? (
          <Tooltip title={`题组 #${record.group.id}`}>
            <span>{`题组 #${record.group.id}（材料 + ${record.group.small_question_count} 道小题）`}</span>
          </Tooltip>
        ) : (
          <Tooltip title={record.question.content}>
            <span>{previewOf(record.question.content)}</span>
          </Tooltip>
        ),
    },
    {
      title: '题型',
      key: 'type',
      width: 96,
      render: (_, record) =>
        record.kind === 'group' ? (
          <Text type="secondary">—</Text>
        ) : (
          TYPE_LABEL[record.question.type] ?? record.question.type
        ),
    },
    {
      title: '难度',
      key: 'difficulty',
      width: 110,
      render: (_, record) => {
        const d = record.kind === 'group' ? record.group.difficulty : record.question.difficulty
        return (
          <Tag color={d === 'A' ? 'purple' : d === 'B' ? 'orange' : d === 'C' ? 'blue' : 'green'}>
            {DIFFICULTY_LABEL[d] ?? d}
          </Tag>
        )
      },
    },
    {
      title: '分值',
      key: 'points',
      width: 80,
      align: 'right',
      render: (_, record) =>
        record.kind === 'group' ? record.group.total_points : record.question.points,
    },
    {
      title: '知识点标签',
      key: 'knowledge_point_names',
      render: (_, record) => {
        if (record.kind === 'group') {
          // 题组只返 knowledge_point_ids（无名字）⇒ 如实报个数，不编名字
          const n = record.group.knowledge_point_ids?.length ?? 0
          return n === 0 ? (
            <Text type="secondary">—</Text>
          ) : (
            <Text type="secondary">{n} 个知识点</Text>
          )
        }
        const list = record.question.knowledge_point_names ?? []
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
      key: 'image_count',
      width: 90,
      align: 'right',
      // 区分「0 张」与「字段缺失」：缺失显示 —，0 仍显示 0（不谎报）
      render: (_, record) => {
        if (record.kind === 'group') {
          // QuestionGroupRead **没有** image_count 字段（后端 schema）⇒ 不编数字
          return <Text type="secondary">—</Text>
        }
        const n = record.question.image_count
        return n === undefined ? <Text type="secondary">—</Text> : n
      },
    },
    {
      title: '更新时间',
      key: 'updated_at',
      width: 150,
      render: (_, record) =>
        formatTime(record.kind === 'group' ? record.group.updated_at : record.question.updated_at),
    },
    {
      title: '操作',
      key: 'actions',
      width: 260,
      render: (_, record) =>
        record.kind === 'group' ? (
          <Space size="small">
            <Button
              size="small"
              disabled={loading || groupsLoading || deletingGroupId !== null}
              onClick={() => {
                // 编辑态入口（commit 1 缺的那个）：沿用 groupDrawerKey 重挂载
                setGroupDrawerMode('edit')
                setEditingGroupId(record.group.id)
                setGroupDrawerKey((k) => k + 1)
                setGroupDrawerOpen(true)
              }}
            >
              编辑
            </Button>
            {/* ⚠️ **不套 Popconfirm**：按 brief §3.4 第 1 条，
                「用户点题组行的删除 ⇒ 先 DELETE（不带 force）」；
                二次确认由后端 409 ⇒ Modal.confirm 承担（判据 D）。
                （单题删除仍用 Popconfirm —— 那是既有行为，未动。） */}
            <Button
              size="small"
              danger
              loading={deletingGroupId === record.group.id}
              disabled={loading || groupsLoading}
              onClick={() => void onDeleteGroup(record.group.id)}
            >
              删除
            </Button>
          </Space>
        ) : (
          <Space size="small">
            <Button
              size="small"
              disabled={loading || deletingId !== null}
              onClick={() => {
                setDrawerMode('edit')
                setEditingQuestion(record.question)
                // 每次打开 = 新会话 ⇒ 重挂载（见 drawerKey 注释）
                setDrawerKey((k) => k + 1)
                setDrawerOpen(true)
              }}
            >
              编辑
            </Button>
            <Button
              size="small"
              disabled={loading || deletingId !== null}
              onClick={() => setGalleryQuestionId(record.question.id)}
            >
              看图
            </Button>
            <Popconfirm
              title="删除该题目？"
              description="删除后不可恢复（选项与知识点关联级联清理）。"
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={() => onDelete(record.question.id)}
            >
              <Button
                size="small"
                danger
                loading={deletingId === record.question.id}
                disabled={loading}
              >
                删除
              </Button>
            </Popconfirm>
          </Space>
        ),
    },
  ]

  // ──────────────── 表格数据（题组行在前，单题行在后） ────────────────

  const rows: Row[] = [
    ...groups.map((g) => ({ kind: 'group' as const, key: `group-${g.id}`, group: g })),
    ...items.map((q) => ({ kind: 'question' as const, key: `q-${q.id}`, question: q })),
  ]

  /** 题组行展开 ⇒ 内嵌小题摘要（只读） */
  const expandedRowRender = (record: Row) => {
    if (record.kind !== 'group') return null
    const detail = groupDetails[record.group.id]
    if (detail === undefined) {
      return (
        <Space>
          <Spin size="small" />
          <Text type="secondary">
            {groupDetailLoadingId === record.group.id ? '加载小题…' : '暂无小题数据'}
          </Text>
        </Space>
      )
    }
    const subQuestions = detail.questions ?? []
    return (
      <Table<QuestionRead>
        size="small"
        rowKey="id"
        dataSource={subQuestions}
        pagination={false}
        columns={[
          {
            title: '题序',
            key: 'order',
            width: 90,
            render: (_, q, idx) => {
              const g = q as GroupQuestionRead
              const order = typeof g.group_order === 'number' ? g.group_order : idx
              return `第 ${order + 1} 题`
            },
          },
          {
            title: '题干',
            dataIndex: 'content',
            key: 'content',
            ellipsis: true,
            render: (c: string) => (
              <Tooltip title={c}>
                <span>{previewOf(c)}</span>
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
            title: '分值',
            dataIndex: 'points',
            key: 'points',
            width: 80,
            align: 'right',
          },
          {
            title: '图数',
            dataIndex: 'image_count',
            key: 'image_count',
            width: 80,
            align: 'right',
            render: (n: number | undefined) =>
              n === undefined ? <Text type="secondary">—</Text> : n,
          },
        ]}
      />
    )
  }

  return (
    <>
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card>
        <Title level={3}>题库</Title>
        <Paragraph type="secondary">
          按教材 / 章节 / 知识点 / 难度 / 题型 / 关键词筛选自己的题目（D-29 §1.4 题库个人资产）
        </Paragraph>
        <Space>
          <Button
            type="primary"
            disabled={loading}
            onClick={() => {
              setDrawerMode('create')
              setEditingQuestion(null)
              // 每次打开 = 新会话 ⇒ 重挂载（见 drawerKey 注释）
              setDrawerKey((k) => k + 1)
              setDrawerOpen(true)
            }}
          >
            新建题目
          </Button>
          <Button
            disabled={loading}
            onClick={() => {
              // 每次打开 = 新会话 ⇒ 重挂载（见 groupDrawerKey 注释）
              setGroupDrawerMode('create')
              setEditingGroupId(null)
              setGroupDrawerKey((k) => k + 1)
              setGroupDrawerOpen(true)
            }}
          >
            新建题组
          </Button>
        </Space>
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
        <Table<Row>
          rowKey="key"
          columns={columns}
          dataSource={rows}
          loading={loading || groupsLoading}
          size="middle"
          scroll={{ x: 1200 }}
          expandable={{
            // 只有题组行可展开（单题行不展开）
            rowExpandable: (record) => record.kind === 'group',
            expandedRowRender,
            onExpand: (expanded, record) => {
              if (expanded && record.kind === 'group') {
                void loadGroupDetail(record.group.id)
              }
            },
          }}
          pagination={{
            // ⚠️ pagination **只管单题**：total 不含题组（裁决 ③ / 判据 J）
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
      <Modal
        open={galleryQuestionId !== null}
        title={`题目 #${galleryQuestionId ?? ''} 的图片`}
        footer={null}
        onCancel={() => setGalleryQuestionId(null)}
        width={640}
      >
        {galleryQuestionId !== null && (
          <QuestionImages
            questionId={galleryQuestionId}
            onChanged={() => void fetchQuestions()}
          />
        )}
      </Modal>
      <QuestionDrawer
        key={drawerKey}
        open={drawerOpen}
        mode={drawerMode}
        question={editingQuestion}
        onClose={() => setDrawerOpen(false)}
        onSaved={() => void fetchQuestions()}
      />
      {/* M3-1c-2 commit 1：题组抽屉（材料层）。
          key 变化 = 整体重挂载 = 状态归零（见 groupDrawerKey 注释）。
          commit 2：mode / groupId 由列表页的「新建题组」与题组行「编辑」驱动。 */}
      <QuestionGroupDrawer
        key={groupDrawerKey}
        open={groupDrawerOpen}
        mode={groupDrawerMode}
        groupId={editingGroupId}
        onClose={() => setGroupDrawerOpen(false)}
        onSaved={() => void refreshAll()}
      />
    </>
  )
}
