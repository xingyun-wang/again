/**
 * 组内小题 · 内联表单（1c-2 commit 2）。
 *
 * 用途：在**题组抽屉里就地**新建 / 编辑一道小题（不是弹窗）。
 *
 * ⭐ 与 1c-1 的 `QuestionDrawer.tsx` 的关系：
 *    题型 / 分值 / 答案 / 选项 的**交互与校验完全照抄**它
 *    （choice 必填选项、type≠choice 不能带选项、恰好 1 个正确选项）。
 *    差别只有三处，且都来自本笔 brief：
 *    ① **不显示章节选择器**（小题继承题组章节）—— 判据 K；
 *    ② **难度只读**（显示题组难度，不给难度选择器）—— 判据 K；
 *    ③ **不显示难度/章节的写入路径**（父组件建题时按题组继承）。
 *
 * 🔴 **state 纪律（1c-1 血泪）**：
 *    本组件**不用 useEffect 清 state**。所有表单 state 用 useState 的
 *    **初始化函数**从 props 取初值（edit 模式预填 / create 模式空表单），
 *    父组件用 `key` 重挂载保证每次展开都是全新会话
 *    （见 QuestionGroupDrawer 的 inlineKey）。
 *
 * 🔴 **图片纪律**：
 *    本表单**只收集文件，不发上传请求** —— create 模式此时还没有 question_id
 *    （上传端点要 question_id）⇒ 上传必须发生在「建题成功之后」
 *    （裁决 ④ 的两段式，顺序不可颠倒）。
 *    edit 模式同理：文件交给父组件，父组件在 PATCH 成功后再上传。
 *    ⇒ 表单里**没有** `<img src="/api/...">`：已有图用 QuestionImages 组件渲染
 *      （内部走 axios blob + createObjectURL）。
 */
import { useState } from 'react'
import {
  Alert,
  Button,
  Input,
  InputNumber,
  Radio,
  Select,
  Space,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd'
import { UploadOutlined } from '@ant-design/icons'

import {
  DIFFICULTY_LABEL,
  TYPE_OPTIONS,
  errorMessageOf,
  type ChoiceInput,
  type KnowledgePointDetail,
  type QuestionDifficulty,
  type QuestionRead,
  type QuestionType,
} from '../api/questionTypes'
import QuestionImages from './QuestionImages'

const { Text } = Typography

/** 选项规则（与 QuestionDrawer 一致：2~8 个，默认 4 个） */
const CHOICE_MIN = 2
const CHOICE_MAX = 8
const CHOICE_DEFAULT = 4

/** label 自动生成 A/B/C…，删中间项后重排，不留洞 */
const LETTERS = 'ABCDEFGH'.split('')

/** 图片限制（对齐后端 routers/academic.py：单题 ≤ 10 张 / 单张 ≤ 5MB） */
const MAX_IMAGE_BYTES = 5 * 1024 * 1024
const MAX_IMAGES_PER_QUESTION = 10
const ALLOWED_IMAGE_EXTS = ['png', 'jpg', 'jpeg', 'webp']

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

/** 表单回传的值（**不含** chapter_id / difficulty / group_order —— 后端从题组继承） */
export interface InlineQuestionFormValues {
  content: string
  type: QuestionType
  points: number
  answer_text: string | null
  /** 仅 choice 题型有；其余题型为 undefined（后端 extra="forbid"，不能带空数组以外的形状） */
  choices: ChoiceInput[] | undefined
  knowledge_point_ids: number[]
}

export interface InlineQuestionFormProps {
  mode: 'create' | 'edit'
  /** edit 模式：被编辑的小题（QuestionRead，含 choices 用来预填选项） */
  question: QuestionRead | null
  /** 题组难度（**只读**展示，判据 K：不给难度选择器） */
  groupDifficulty: QuestionDifficulty
  /** 章节标题（**只读**展示；判据 K：不给章节选择器）。缺省则不显示。 */
  chapterTitle?: string
  /** 本章知识点（多选来源；只列本章，不跨章） */
  knowledgePoints: KnowledgePointDetail[]
  /** create 模式：默认继承题组的知识点 */
  defaultKnowledgePointIds?: number[]
  /** 该题已有图数（单题 ≤ 10 张的上限判定用） */
  existingImageCount?: number
  /** 图片画廊的 key（父组件上传成功后自增 ⇒ 画廊刷新） */
  galleryKey?: number
  disabled?: boolean
  onCancel: () => void
  /** 已有图被删除等变化时回调（父组件据此刷新行上的图数） */
  onImagesChanged?: () => void
  /**
   * 提交回调。
   * - create 模式：**父组件**负责建题（groupId + 继承字段）；
   * - edit 模式：**父组件**负责 PATCH。
   * files = 本次选了、但**还没上传**的图片文件（表单只收集，不上传）。
   */
  onSubmit: (values: InlineQuestionFormValues, files: File[]) => void | Promise<void>
}

export default function InlineQuestionForm({
  mode,
  question,
  groupDifficulty,
  chapterTitle,
  knowledgePoints,
  defaultKnowledgePointIds,
  existingImageCount = 0,
  galleryKey = 0,
  disabled = false,
  onCancel,
  onImagesChanged,
  onSubmit,
}: InlineQuestionFormProps) {
  const isEdit = mode === 'edit'

  // ──────────────── 表单 state（初值来自 props；靠父组件 key 重挂载归零） ────────────────
  const [qtype, setQtype] = useState<QuestionType>(question?.type ?? 'choice')
  const [content, setContent] = useState<string>(question?.content ?? '')
  const [points, setPoints] = useState<number>(question?.points ?? 2)
  const [answerText, setAnswerText] = useState<string>(question?.answer_text ?? '')
  const [kpIds, setKpIds] = useState<number[]>(
    isEdit ? (question?.knowledge_point_ids ?? []) : (defaultKnowledgePointIds ?? []),
  )
  const [choices, setChoices] = useState<ChoiceDraft[]>(() => {
    const existing = question?.choices ?? []
    return existing.length > 0
      ? existing.map((c) => newDraft(c.content, c.is_correct))
      : defaultChoices()
  })
  const [imageFiles, setImageFiles] = useState<File[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const showChoices = qtype === 'choice'
  const busy = submitting || disabled

  // ──────────────── 选项增删改 ────────────────

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

  // ──────────────── 图片（只收集，不上传） ────────────────

  const onFilePicked = (file: File): boolean => {
    const ext = (file.name.split('.').pop() ?? '').toLowerCase()
    if (!ALLOWED_IMAGE_EXTS.includes(ext)) {
      message.warning(`「${file.name}」类型不支持（仅 png / jpg / jpeg / webp）`)
      return false
    }
    if (file.size > MAX_IMAGE_BYTES) {
      message.warning(
        `「${file.name}」超过 5MB（${(file.size / 1024 / 1024).toFixed(1)}MB）`,
      )
      return false
    }
    const total = existingImageCount + imageFiles.length
    if (total + 1 > MAX_IMAGES_PER_QUESTION) {
      message.warning(`单题最多 ${MAX_IMAGES_PER_QUESTION} 张图（当前 ${total} 张）`)
      return false
    }
    setImageFiles((prev) => [...prev, file])
    return false // 阻止 antd 自动上传（本表单不发上传请求）
  }

  const removePendingFile = (index: number) => {
    setImageFiles((prev) => prev.filter((_, i) => i !== index))
  }

  // ──────────────── 校验（照抄 QuestionDrawer 的 validate） ────────────────

  const validate = (): string | null => {
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
    const values: InlineQuestionFormValues = {
      content: content.trim(),
      type: qtype,
      points,
      answer_text: answerText.trim() === '' ? null : answerText.trim(),
      choices:
        qtype === 'choice'
          ? choices.map((c, i) => ({
              label: LETTERS[i] ?? String(i),
              content: c.content.trim(),
              is_correct: c.is_correct,
              order_index: i,
            }))
          : undefined,
      knowledge_point_ids: kpIds,
    }
    try {
      await onSubmit(values, [...imageFiles])
    } catch (err) {
      // 父组件一般自己处理错误并提示；这里是兜底，避免未捕获异常
      setError(errorMessageOf(err, '保存失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const kpPlaceholder =
    knowledgePoints.length === 0 ? '本章暂无知识点，请先添加知识点' : '全部知识点'

  return (
    <div style={{ width: '100%' }}>
      {error !== null && (
        <Alert
          type="error"
          showIcon
          message={error}
          style={{ marginBottom: 12 }}
          closable
          onClose={() => setError(null)}
        />
      )}

      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {/* ① 章节（只读，继承题组）—— 判据 K：不给章节选择器 */}
        <div>
          <Text strong>章节</Text>
          <div style={{ marginTop: 4 }}>
            <Tag color="default" style={{ marginInlineEnd: 8 }}>
              {chapterTitle !== undefined && chapterTitle !== '' ? chapterTitle : '继承题组'}
            </Tag>
            <Text type="secondary" style={{ fontSize: 12 }}>
              小题章节继承题组，不可单独修改
            </Text>
          </div>
        </div>

        {/* ② 难度（只读，继承题组）—— 判据 K：不给难度选择器 */}
        <div>
          <Text strong>难度</Text>
          <div style={{ marginTop: 4 }}>
            <Tag color="geekblue">{DIFFICULTY_LABEL[groupDifficulty] ?? groupDifficulty}</Tag>
            <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
              小题难度继承题组，不可单独修改
            </Text>
          </div>
        </div>

        {/* ③ 知识点（多选；只列本章） */}
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
              disabled={busy}
              maxTagCount="responsive"
            />
          </div>
          {knowledgePoints.length === 0 && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              本章暂无知识点，请先添加知识点
            </Text>
          )}
        </div>

        {/* ④ 题型 */}
        <div>
          <Text strong>题型</Text>
          <div style={{ marginTop: 4 }}>
            <Radio.Group
              optionType="button"
              buttonStyle="solid"
              value={qtype}
              onChange={(e) => setQtype(e.target.value as QuestionType)}
              options={TYPE_OPTIONS}
              disabled={busy}
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
              disabled={busy}
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
              disabled={busy}
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
              disabled={busy}
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
                    disabled={busy}
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
                    disabled={busy}
                  >
                    正确
                  </Radio>
                  <Button
                    size="small"
                    danger
                    disabled={busy || choices.length <= CHOICE_MIN}
                    onClick={() => removeChoice(c.key)}
                  >
                    删除
                  </Button>
                </Space>
              ))}
              <Button
                size="small"
                disabled={busy || choices.length >= CHOICE_MAX}
                onClick={addChoice}
              >
                增加选项（最多 {CHOICE_MAX} 个）
              </Button>
            </Space>
          </div>
        )}

        {/* ⑨ 图片（只收集文件；上传由父组件在「建题/PATCH 成功之后」做） */}
        <div>
          <Text strong>图片</Text>
          <Space direction="vertical" size="small" style={{ width: '100%', marginTop: 4 }}>
            <Upload
              beforeUpload={onFilePicked}
              fileList={[]}
              multiple
              accept=".png,.jpg,.jpeg,.webp"
              showUploadList={false}
              disabled={busy}
            >
              <Button icon={<UploadOutlined />} disabled={busy}>
                选择图片（png/jpg/jpeg/webp，单张 ≤ 5MB，单题 ≤ 10 张）
              </Button>
            </Upload>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {isEdit
                ? '图片在点「保存」后上传（保存成功才传，传失败会标「待补图」）'
                : '图片在小题创建成功后自动上传（创建失败则不会上传）'}
            </Text>

            {imageFiles.length > 0 && (
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <Text type="secondary">
                  待上传 {imageFiles.length} 张（尚未上传，可移除）：
                </Text>
                {imageFiles.map((f, idx) => (
                  <Space key={`${f.name}-${idx}`} size="small">
                    <Text>{f.name}</Text>
                    <Text type="secondary">{(f.size / 1024).toFixed(0)} KB</Text>
                    <Button size="small" danger disabled={busy} onClick={() => removePendingFile(idx)}>
                      移除
                    </Button>
                  </Space>
                ))}
              </Space>
            )}

            {isEdit && question !== null && (
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  已有图片（可删除）：
                </Text>
                <div style={{ marginTop: 4 }}>
                  <QuestionImages
                    key={`${question.id}-${galleryKey}`}
                    questionId={question.id}
                    onChanged={onImagesChanged}
                  />
                </div>
              </div>
            )}
          </Space>
        </div>

        <Space>
          <Button onClick={onCancel} disabled={busy}>
            取消
          </Button>
          <Button type="primary" loading={submitting} onClick={() => void handleSubmit()}>
            保存
          </Button>
        </Space>
      </Space>
    </div>
  )
}
