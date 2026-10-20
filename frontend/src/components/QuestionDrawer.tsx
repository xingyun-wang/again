/**
 * 题目新建 / 编辑抽屉（M3-1c-1a）。
 *
 * 规格来源：星云《题库层设计 · 第 1 步》§1c（8 个字段 + 控件）。
 * 工程细节来源：星轨《派工单 — 1c-1 新建 / 编辑抽屉（2026-10-20）》。
 *
 * 8 个字段：章节（教材→章节级联）/ 知识点（多选）/ 题型 / 难度 / 题干 / 分值 / 参考答案 / 选项
 *
 * 两条必须绕开的契约限制（派工单 §0，已核源 backend/app/api/v1/schemas/academic.py）：
 * ① QuestionUpdate 里没有 chapter_id ⇒ **编辑态章节只读**（新建时才可选）。
 *    不为此改后端加字段（那是 1a-2 的事）。
 * ② 图片必须挂在已存在的题目下（上传接口要 question_id）⇒ 图片走两阶段，
 *    见 1c-1b；本笔（1c-1a）不含图片。
 *
 * 提交语义（后端 PATCH：仅修改传 in body 的字段；choices 传则完全替换）：
 * - 新建：POST /questions，choices 与题目一次建完
 * - 编辑：PATCH /questions/{id}，choices 每次保存都传完整列表（完全替换语义）
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Drawer,
  Input,
  InputNumber,
  Radio,
  Select,
  Space,
  Typography,
  message,
} from 'antd'
import { apiClient } from '../api/client'
import {
  DIFFICULTY_OPTIONS_CHINESE,
  TYPE_OPTIONS,
  errorMessageOf,
  type ChapterSummary,
  type KnowledgePointDetail,
  type QuestionRead,
  type TextbookSummary,
} from '../api/questionTypes'

const { Text } = Typography
const AUTH_HEADERS = { 'X-User-Id': '1' }

/** 选项默认 4 项，最多 8 项，最少 2 项（派工单 §1 选项区规则） */
const CHOICE_MIN = 2
const CHOICE_MAX = 8
const CHOICE_DEFAULT = 4

/** label 自动生成 A/B/C…，删中间项后重排，不留洞 */
const LETTERS = 'ABCDEFGH'.split('')

/** 抽屉内部选项草稿（label 由下标派生，不单独存） */
interface ChoiceDraft {
  key: string
  content: string
  is_correct: boolean
}

let draftSeq = 0
function newDraft(content = '', is_correct = false): ChoiceDraft {
  draftSeq += 1
  return { key: `c${draftSeq}`, content, is_correct }
}

function defaultChoices(): ChoiceDraft[] {
  return Array.from({ length: CHOICE_DEFAULT }, () => newDraft())
}

export interface QuestionDrawerProps {
  open: boolean
  mode: 'create' | 'edit'
  /** edit 模式必传（列表行的 QuestionRead，含 choices 用来预填选项） */
  question: QuestionRead | null
  onClose: () => void
  /** 保存成功回调（列表页据此刷新） */
  onSaved: () => void
}

export default function QuestionDrawer({
  open,
  mode,
  question,
  onClose,
  onSaved,
}: QuestionDrawerProps) {
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [textbooks, setTextbooks] = useState<TextbookSummary[]>([])
  const [textbookId, setTextbookId] = useState<number | undefined>(undefined)
  const [chapters, setChapters] = useState<ChapterSummary[]>([])
  const [chapterId, setChapterId] = useState<number | undefined>(undefined)
  const [chapterTitle, setChapterTitle] = useState<string>('')
  const [knowledgePoints, setKnowledgePoints] = useState<KnowledgePointDetail[]>([])
  const [kpIds, setKpIds] = useState<number[]>([])

  const [qtype, setQtype] = useState<QuestionRead['type']>('choice')
  const [difficulty, setDifficulty] = useState<QuestionRead['difficulty']>('D')
  const [content, setContent] = useState('')
  const [points, setPoints] = useState<number>(2)
  const [answerText, setAnswerText] = useState('')
  const [choices, setChoices] = useState<ChoiceDraft[]>(defaultChoices())

  const isEdit = mode === 'edit'
  const showChoices = qtype === 'choice'

  // ──────────────── 数据加载 ────────────────

  const loadChapters = useCallback(async (tid: number) => {
    const resp = await apiClient.get<{
      textbook_id: number
      chapters: ChapterSummary[]
    }>(`/academic/textbooks/${tid}/chapters`, { headers: AUTH_HEADERS })
    setChapters(resp.data?.chapters ?? [])
  }, [])

  const loadKnowledgePoints = useCallback(async (cid: number) => {
    const resp = await apiClient.get<{ knowledge_points: KnowledgePointDetail[] }>(
      `/academic/chapters/${cid}`,
      { headers: AUTH_HEADERS },
    )
    setKnowledgePoints(resp.data?.knowledge_points ?? [])
  }, [])

  /** 打开抽屉时初始化：create = 空表单；edit = 反查教材/章节 + 预填字段 */
  useEffect(() => {
    if (!open) return
    let cancelled = false

    const init = async () => {
      setLoading(true)
      setError(null)
      try {
        const tbResp = await apiClient.get<TextbookSummary[]>('/academic/textbooks', {
          headers: AUTH_HEADERS,
        })
        if (cancelled) return
        const tbs = tbResp.data ?? []
        setTextbooks(tbs)

        if (mode === 'edit' && question) {
          // 反查：章节详情里带 textbook_id + title
          const chResp = await apiClient.get<{
            id: number
            textbook_id: number
            title: string
            knowledge_points: KnowledgePointDetail[]
          }>(`/academic/chapters/${question.chapter_id}`, { headers: AUTH_HEADERS })
          if (cancelled) return
          const detail = chResp.data
          setTextbookId(detail?.textbook_id)
          setChapterId(question.chapter_id)
          setChapterTitle(detail?.title ?? '')
          setKnowledgePoints(detail?.knowledge_points ?? [])
          await loadChapters(detail?.textbook_id ?? 0)
          if (cancelled) return

          // 预填字段
          setQtype(question.type)
          setDifficulty(question.difficulty)
          setContent(question.content ?? '')
          setPoints(question.points ?? 2)
          setAnswerText(question.answer_text ?? '')
          setKpIds(question.knowledge_point_ids ?? [])
          const existing = question.choices ?? []
          setChoices(
            existing.length > 0
              ? existing.map((c) => newDraft(c.content, c.is_correct))
              : defaultChoices(),
          )
        } else {
          // create：空表单
          setTextbookId(undefined)
          setChapters([])
          setChapterId(undefined)
          setChapterTitle('')
          setKnowledgePoints([])
          setKpIds([])
          setQtype('choice')
          setDifficulty('D')
          setContent('')
          setPoints(2)
          setAnswerText('')
          setChoices(defaultChoices())
        }
      } catch (err) {
        if (!cancelled) setError(errorMessageOf(err, '初始化表单失败'))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void init()
    return () => {
      cancelled = true
    }
  }, [open, mode, question, loadChapters])

  // ──────────────── 交互 ────────────────

  const onTextbookChange = (value: number | undefined) => {
    setTextbookId(value)
    setChapterId(undefined)
    setChapterTitle('')
    setKnowledgePoints([])
    setKpIds([]) // 切章节清空已选知识点（判据 9）
    if (value === undefined) {
      setChapters([])
      return
    }
    void loadChapters(value).catch((err) => {
      setError(errorMessageOf(err, '章节列表加载失败'))
    })
  }

  const onChapterChange = (value: number | undefined) => {
    setChapterId(value)
    setKpIds([]) // 切章节清空已选知识点（判据 9）
    if (value === undefined) {
      setChapterTitle('')
      setKnowledgePoints([])
      return
    }
    const hit = chapters.find((c) => c.id === value)
    setChapterTitle(hit?.title ?? '')
    void loadKnowledgePoints(value).catch((err) => {
      setError(errorMessageOf(err, '知识点加载失败'))
    })
  }

  /** 选项增删改；label 由下标派生 ⇒ 删中间项自动重排，不留 A、C、D 的洞 */
  const updateChoice = (key: string, patch: Partial<ChoiceDraft>) => {
    setChoices((prev) => prev.map((c) => (c.key === key ? { ...c, ...patch } : c)))
  }

  const removeChoice = (key: string) => {
    setChoices((prev) => {
      if (prev.length <= CHOICE_MIN) return prev
      return prev.filter((c) => c.key !== key)
    })
  }

  const addChoice = () => {
    setChoices((prev) => {
      if (prev.length >= CHOICE_MAX) return prev
      return [...prev, newDraft()]
    })
  }

  const choicePayload = useMemo(() => {
    return choices.map((c, i) => ({
      label: LETTERS[i] ?? String(i),
      content: c.content.trim(),
      is_correct: c.is_correct,
      order_index: i,
    }))
  }, [choices])

  // ──────────────── 提交 ────────────────

  const validate = (): string | null => {
    if (chapterId === undefined) return '请选择章节'
    if (content.trim() === '') return '请填写题干'
    if (qtype === 'choice') {
      if (choices.length < CHOICE_MIN) return `选择题至少需要 ${CHOICE_MIN} 个选项`
      if (choices.some((c) => c.content.trim() === '')) return '选项内容不能为空'
      const correct = choices.filter((c) => c.is_correct).length
      if (correct !== 1) return '选择题必须恰好有 1 个正确选项'
    }
    return null
  }

  const handleSubmit = async () => {
    const bad = validate()
    if (bad !== null) {
      message.warning(bad)
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const common = {
        content: content.trim(),
        difficulty,
        type: qtype,
        points,
        answer_text: answerText.trim() === '' ? null : answerText,
        knowledge_point_ids: kpIds,
      }
      // 切到 fill/subjective 时不传 choices（后端不传 = 不动）
      const body = {
        ...common,
        ...(qtype === 'choice' ? { choices: choicePayload } : {}),
      }

      if (mode === 'edit' && question) {
        await apiClient.patch(`/academic/questions/${question.id}`, {
          headers: AUTH_HEADERS,
          data: body,
        })
        message.success('题目已保存')
      } else {
        await apiClient.post('/academic/questions', {
          headers: AUTH_HEADERS,
          data: { chapter_id: chapterId, ...body },
        })
        message.success('题目已创建')
      }
      onSaved()
      onClose()
    } catch (err) {
      setError(errorMessageOf(err, '保存失败'))
    } finally {
      setSubmitting(false)
    }
  }

  // ──────────────── 渲染 ────────────────

  const kpPlaceholder = (() => {
    if (chapterId === undefined) return '先选章节'
    if (knowledgePoints.length === 0) return '本章暂无知识点，请先添加知识点'
    return '全部知识点'
  })()

  return (
    <Drawer
      title={isEdit ? '编辑题目' : '新建题目'}
      width={720}
      open={open}
      onClose={onClose}
      destroyOnClose
      extra={
        <Space>
          <Button onClick={onClose} disabled={submitting}>
            取消
          </Button>
          <Button type="primary" loading={submitting} onClick={() => void handleSubmit()}>
            保存
          </Button>
        </Space>
      }
    >
      {error !== null && (
        <Alert
          type="error"
          showIcon
          message={error}
          style={{ marginBottom: 16 }}
          closable
          onClose={() => setError(null)}
        />
      )}

      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {/* ① 章节：教材→章节 级联。编辑态只读（QuestionUpdate 无 chapter_id） */}
        <div>
          <Text strong>章节</Text>
          <Space.Compact style={{ width: '100%', marginTop: 4 }}>
            <Select
              style={{ width: '50%' }}
              placeholder="选择教材"
              value={textbookId}
              options={textbooks.map((t) => ({ value: t.id, label: t.title }))}
              onChange={onTextbookChange}
              disabled={isEdit || loading}
              loading={loading}
              showSearch
              optionFilterProp="label"
            />
            <Select
              style={{ width: '50%' }}
              placeholder={isEdit ? chapterTitle || '章节（只读）' : '选择章节'}
              value={chapterId}
              options={chapters.map((c) => ({ value: c.id, label: c.title }))}
              onChange={onChapterChange}
              disabled={isEdit || loading || textbookId === undefined}
              loading={loading}
              showSearch
              optionFilterProp="label"
            />
          </Space.Compact>
          {isEdit && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              编辑态不能改章节（后端 QuestionUpdate 无 chapter_id 字段）
            </Text>
          )}
        </div>

        {/* ② 知识点（多选） */}
        <div>
          <Text strong>知识点（可空）</Text>
          <div style={{ marginTop: 4 }}>
            <Select
              mode="multiple"
              allowClear
              style={{ width: '100%' }}
              placeholder={kpPlaceholder}
              value={kpIds}
              options={knowledgePoints.map((kp) => ({ value: kp.id, label: kp.name }))}
              onChange={(v: number[]) => setKpIds(v)}
              disabled={loading || chapterId === undefined}
              loading={loading}
              maxTagCount="responsive"
            />
          </div>
          {chapterId !== undefined && knowledgePoints.length === 0 && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              本章暂无知识点，请先添加知识点
            </Text>
          )}
        </div>

        {/* ③ 题型 */}
        <div>
          <Text strong>题型</Text>
          <div style={{ marginTop: 4 }}>
            <Radio.Group
              optionType="button"
              buttonStyle="solid"
              value={qtype}
              onChange={(e) => setQtype(e.target.value as QuestionRead['type'])}
              options={TYPE_OPTIONS}
              disabled={loading}
            />
          </div>
        </div>

        {/* ④ 难度：只显示中文版本名，不显示字母（决策 10） */}
        <div>
          <Text strong>难度</Text>
          <div style={{ marginTop: 4 }}>
            <Radio.Group
              optionType="button"
              buttonStyle="solid"
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value as QuestionRead['difficulty'])}
              options={DIFFICULTY_OPTIONS_CHINESE}
              disabled={loading}
            />
          </div>
        </div>

        {/* ⑤ 题干 */}
        <div>
          <Text strong>题干</Text>
          <div style={{ marginTop: 4 }}>
            <Input.TextArea
              rows={4}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="题干正文（纯文本，不做富文本）"
              disabled={loading}
            />
          </div>
        </div>

        {/* ⑥ 分值 */}
        <div>
          <Text strong>分值</Text>
          <div style={{ marginTop: 4 }}>
            <InputNumber
              min={0}
              max={999.9}
              step={0.5}
              value={points}
              onChange={(v) => setPoints(typeof v === 'number' ? v : 0)}
              style={{ width: 160 }}
              disabled={loading}
            />
          </div>
        </div>

        {/* ⑦ 参考答案 */}
        <div>
          <Text strong>参考答案</Text>
          <div style={{ marginTop: 4 }}>
            <Input.TextArea
              rows={3}
              value={answerText}
              onChange={(e) => setAnswerText(e.target.value)}
              placeholder="填空题 / 主观题建议填写；选择题可不填"
              disabled={loading}
            />
          </div>
        </div>

        {/* ⑧ 选项（仅 choice 显示；切换题型不丢已填内容） */}
        {showChoices && (
          <div>
            <Text strong>选项</Text>
            <Space direction="vertical" size="small" style={{ width: '100%', marginTop: 4 }}>
              {choices.map((c, i) => (
                <Space key={c.key} style={{ width: '100%' }} align="start">
                  <Text style={{ width: 24, paddingTop: 6 }}>{LETTERS[i] ?? i}</Text>
                  <Input
                    value={c.content}
                    onChange={(e) => updateChoice(c.key, { content: e.target.value })}
                    placeholder={`选项 ${LETTERS[i] ?? i + 1} 内容`}
                    disabled={loading}
                    style={{ flex: 1 }}
                  />
                  <Radio
                    checked={c.is_correct}
                    onChange={() =>
                      // Radio 语义：恰好一个正确 ⇒ 点谁谁正确，其余自动取消
                      setChoices((prev) =>
                        prev.map((x) => ({ ...x, is_correct: x.key === c.key })),
                      )
                    }
                    disabled={loading}
                  >
                    正确
                  </Radio>
                  <Button
                    size="small"
                    danger
                    disabled={loading || choices.length <= CHOICE_MIN}
                    onClick={() => removeChoice(c.key)}
                  >
                    删除
                  </Button>
                </Space>
              ))}
              <Button
                size="small"
                disabled={loading || choices.length >= CHOICE_MAX}
                onClick={addChoice}
              >
                增加选项（最多 {CHOICE_MAX} 个）
              </Button>
            </Space>
          </div>
        )}
      </Space>
    </Drawer>
  )
}
