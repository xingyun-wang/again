/**
 * 题组新建 / 编辑抽屉（1c-2 commit 1 · 纯前端材料层）。
 *
 * 范围（brief 1c-2 commit 1）：
 * - 题组 CRUD（新建 / 编辑）、章节+难度+知识点
 * - **材料层**：文字 / 图片 / 表格三种块，可增删、可上下移、可改图片宽度档位
 * - 小题区**只留空壳**（内联新建小题、列表页题组行 = commit 2）
 *
 * 🔴 三个必须记住的取舍（都是 brief 定稿，不是实现偷懒）：
 *
 * ① **新建即落库**：新建模式下选好章节+难度点「创建题组」⇒ POST /question-groups
 *    拿到 id ⇒ **转成编辑态**继续编辑材料。
 *    理由：材料图必须有 group_id 才能上传（上传端点要 /question-groups/{id}/images），
 *    纯前端草稿做不了。
 *    代价：中途关掉会**留下一个空题组**（已知并接受，抽屉里也提示了）。
 *
 * ② **保存 = 一次 PUT**（`{difficulty, knowledge_point_ids, blocks[]}`），
 *    blocks 是**整体替换**（后端按数组下标重建 order_index）⇒
 *    前端必须传**完整**块数组，**顺序即数组顺序**（= 顺序持久化的机制）。
 *
 * ③ **state 不靠 useEffect 清**：父组件用 `key={groupDrawerKey}` 让抽屉
 *    「每次打开 = 一次全新会话」（1c-1 的血泪：漏清一个 state 就复现上一题的数据）。
 *    本组件内部只用 useEffect **加载**数据，不用它**清理**状态。
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Drawer,
  Empty,
  Popconfirm,
  Select,
  Space,
  Tag,
  Tooltip,
  Typography,
  Upload,
  message,
} from 'antd'
import { PlusOutlined, UploadOutlined } from '@ant-design/icons'

import { apiClient } from '../api/client'
import {
  createQuestionGroup,
  createGroupQuestion,
  deleteGroupImage,
  getQuestionGroup,
  listGroupImages,
  updateQuestionGroup,
  uploadQuestionImage,
  type GroupQuestionCreateBody,
  type QuestionGroupUpdateBody,
} from '../api/questionGroups'
import {
  AUTH_HEADERS,
  DIFFICULTY_OPTIONS_CHINESE,
  TYPE_LABEL,
  errorMessageOf,
  type ChapterSummary,
  type ChoiceInput,
  type ChoiceRead,
  type GroupQuestionRead,
  type KnowledgePointDetail,
  type QuestionDifficulty,
  type QuestionRead,
  type TextbookSummary,
} from '../api/questionTypes'
import ContentBlockEditor, {
  MAX_MATERIAL_IMAGES,
  blockFromRead,
  blockToInput,
  createImageBlock,
  createTableBlock,
  createTextBlock,
  uploadMaterialImage,
  type BlockDraft,
} from './ContentBlockEditor'
import InlineQuestionForm, {
  type InlineQuestionFormValues,
} from './InlineQuestionForm'

const { Text } = Typography

/** 题干摘要长度（列表行展示用） */
const CONTENT_PREVIEW_LEN = 50

function previewOf(content: string): string {
  return content.length > CONTENT_PREVIEW_LEN
    ? `${content.slice(0, CONTENT_PREVIEW_LEN)}…`
    : content
}

/**
 * 组内小题排序。
 *
 * ⚠️ 后端 GET /question-groups/{id} 已按 group_order 升序返回；
 *    但 **QuestionRead 响应模型里没有 group_order**（brief 说有，实际没有）
 *    ⇒ 拿不到 order 时保持服务端顺序（数组下标兜底），拿到才排。
 */
function sortQuestions(list: QuestionRead[]): QuestionRead[] {
  const allHaveOrder = list.every(
    (q) => typeof (q as GroupQuestionRead).group_order === 'number',
  )
  if (!allHaveOrder) return list
  return [...list].sort(
    (a, b) =>
      ((a as GroupQuestionRead).group_order ?? 0) - ((b as GroupQuestionRead).group_order ?? 0),
  )
}

/** 题序展示：**从 1 起**（库里是 0 起）；拿不到 group_order 时用数组下标兜底 */
function questionOrderOf(q: QuestionRead, index: number): number {
  const g = q as GroupQuestionRead
  return (typeof g.group_order === 'number' ? g.group_order : index) + 1
}

/** 知识点 id 集合是否相同（忽略顺序） */
function sameIdSet(a: number[], b: number[]): boolean {
  if (a.length !== b.length) return false
  const sa = [...a].sort((x, y) => x - y)
  const sb = [...b].sort((x, y) => x - y)
  return sa.every((v, i) => v === sb[i])
}

/**
 * 选项是否语义相同。
 *
 * ⚠️ 只比 content + is_correct + 数量：**label / order_index 由下标派生**
 *    （删中间项后重排）⇒ 不能拿来当“有没有改”的判据。
 */
function sameChoices(a: ChoiceInput[], b: ChoiceRead[]): boolean {
  if (a.length !== b.length) return false
  return a.every((c, i) => {
    const o = b[i]
    return o !== undefined && o.content === c.content && o.is_correct === c.is_correct
  })
}


export interface QuestionGroupDrawerProps {
  open: boolean
  mode: 'create' | 'edit'
  /** edit 模式：题组 id（commit 1 只有新建入口，编辑态由 commit 2 的列表行触发） */
  groupId: number | null
  onClose: () => void
  /** 保存成功回调（列表页据此刷新） */
  onSaved?: () => void
}

export default function QuestionGroupDrawer({
  open,
  mode,
  groupId,
  onClose,
  onSaved,
}: QuestionGroupDrawerProps) {
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [uploadingImage, setUploadingImage] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [textbooks, setTextbooks] = useState<TextbookSummary[]>([])
  const [textbookId, setTextbookId] = useState<number | undefined>(undefined)
  const [chapters, setChapters] = useState<ChapterSummary[]>([])
  const [chapterId, setChapterId] = useState<number | undefined>(undefined)
  const [knowledgePoints, setKnowledgePoints] = useState<KnowledgePointDetail[]>([])
  const [kpIds, setKpIds] = useState<number[]>([])
  const [difficulty, setDifficulty] = useState<QuestionDifficulty>('D')

  const [blocks, setBlocks] = useState<BlockDraft[]>([])
  /** 组内小题（来自 GET /question-groups/{id} 的 detail.questions）；小题数 = questions.length */
  const [questions, setQuestions] = useState<QuestionRead[]>([])
  /**
   * 内联小题表单的展开状态。
   *
   * 🔴 **不许用 useEffect 清 state**（1c-1 血泪）⇒ 每次展开内联表单都
   *    **自增 inlineKey** ⇒ 父组件用 key 让表单整体重挂载 ⇒ 21 个 state 一次性归零。
   *    （`inlineMode` 决定展开哪个表单，`editingQuestion` 是被编辑的那一行）
   */
  const [inlineMode, setInlineMode] = useState<'closed' | 'create' | 'edit'>('closed')
  const [inlineKey, setInlineKey] = useState(0)
  const [editingQuestion, setEditingQuestion] = useState<QuestionRead | null>(null)
  const [creatingQuestion, setCreatingQuestion] = useState(false)
  const [savingQuestion, setSavingQuestion] = useState(false)
  const [deletingQuestionId, setDeletingQuestionId] = useState<number | null>(null)
  /** 正在传图的小题 id（行内「重传图片」） */
  const [uploadingImageQuestionId, setUploadingImageQuestionId] = useState<number | null>(null)
  /**
   * 「待补图」的小题 id（建题成功但图片上传失败 ⇒ 题目**保留**，等用户重传）。
   *
   * 🔴 这是**客户端状态**（服务端不知道「上传失败」这回事）⇒
   *    重传成功后才清掉；重载题组也不清（用户可能还没传）。
   */
  const [pendingImageIds, setPendingImageIds] = useState<number[]>([])
  /** 每个「待补图」小题的失败原因（行内展示，便于用户知道怎么修） */
  const [pendingImageReasons, setPendingImageReasons] = useState<Record<number, string>>({})
  /** 图片画廊 key（编辑态上传成功后自增 ⇒ QuestionImages 重挂载重载） */
  const [questionGalleryKey, setQuestionGalleryKey] = useState(0)
  /**
   * 当前题组 id：null = 还没落库（create 模式初始）；
   * 创建成功后 = 新 id（此时章节/教材变只读：后端 QuestionGroupUpdate 没有 chapter_id）。
   */
  const [currentGroupId, setCurrentGroupId] = useState<number | null>(
    mode === 'edit' ? groupId : null,
  )
  /** 服务端已存在的材料图数（10 张上限判定用） */
  const [serverImageCount, setServerImageCount] = useState(0)
  /** 本次会话新传的图数 */
  const [sessionImageCount, setSessionImageCount] = useState(0)
  /**
   * 待删图片 id 队列。
   *
   * 🔴 为什么不在删块/换图时**立刻** DELETE 图片：
   *    后端 content_blocks.image_id 上有 FK CASCADE ⇒ 先删图会把**已落库的块**
   *    连带删掉（用户还没点保存，库里就少了一块材料，且不可恢复）。
   *    ⇒ 顺序必须是：先 PUT（整体替换块）→ 再删图。
   */
  const [pendingDeleteImageIds, setPendingDeleteImageIds] = useState<number[]>([])
  /**
   * 本次会话**新上传**成功的材料图 id（取消/关闭时用来回收孤儿图）。
   *
   * 🔴 星轨 OUTBOX #5 · T1（P1）：上传图后点「取消」⇒ 图留在库里
   *    ⇒ 反复「选图→取消」能吃满 10 张配额 ⇒ 这组再也传不了图，
   *      且块编辑器没有「未引用图」入口 ⇒ 用户看不见也删不掉。
   *
   * ⭐ 用 **ref** 而不是 state：回收是异步的，回收期间组件可能已卸载
   *    ⇒ 不能依赖 state 读「最新值」（state 会是闭包里的旧值）。
   *    父组件每次打开用 key 重挂载 ⇒ ref 天然按会话归零。
   */
  const sessionUploadedImageIdsRef = useRef<number[]>([])
  /** 回收中（关闭前先回收孤儿图，期间锁住交互） */
  const [cleaning, setCleaning] = useState(false)
  /** 最近一次成功保存的时刻（T3：显示「已保存 HH:MM」，免得用户反复点） */
  const [savedAtLabel, setSavedAtLabel] = useState<string | null>(null)

  const imageCountTotal = serverImageCount + sessionImageCount
  /** 题组已落库 ⇒ 章节/教材只读（后端 PUT 不接受 chapter_id） */
  const chapterLocked = currentGroupId !== null

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

  /**
   * 打开抽屉时加载。**只加载，不清状态** —— 状态归零靠父组件的 key 重挂载
   * （1c-1 血泪：靠 useEffect 清 state 一定会漏）。
   */
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
        setTextbooks(tbResp.data ?? [])

        if (mode !== 'edit' || groupId === null) return

        // 编辑态：取详情（材料块 + 小题）
        const detail = await getQuestionGroup(groupId)
        if (cancelled) return
        setCurrentGroupId(detail.id)
        setChapterId(detail.chapter_id)
        setDifficulty(detail.difficulty)
        setKpIds(detail.knowledge_point_ids ?? [])
        // ⚠️ 块顺序按后端返回的 order_index 升序（后端已排序，这里再排一次不亏）
        setBlocks(
          [...(detail.blocks ?? [])]
            .sort((a, b) => a.order_index - b.order_index)
            .map(blockFromRead),
        )
        setQuestions(sortQuestions(detail.questions ?? []))

        // 反查教材 + 章节列表 + 知识点
        const chResp = await apiClient.get<{
          id: number
          textbook_id: number
          title: string
          knowledge_points: KnowledgePointDetail[]
        }>(`/academic/chapters/${detail.chapter_id}`, { headers: AUTH_HEADERS })
        if (cancelled) return
        setTextbookId(chResp.data?.textbook_id)
        setKnowledgePoints(chResp.data?.knowledge_points ?? [])
        await loadChapters(chResp.data?.textbook_id ?? 0)
        if (cancelled) return

        const imgs = await listGroupImages(detail.id)
        if (cancelled) return
        setServerImageCount(imgs.length)
      } catch (err) {
        if (!cancelled) setError(errorMessageOf(err, '初始化失败'))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void init()
    return () => {
      cancelled = true
    }
  }, [open, mode, groupId, loadChapters])

  // ──────────────── 章节 / 难度 / 知识点 ────────────────

  const onTextbookChange = (value: number | undefined) => {
    setTextbookId(value)
    setChapterId(undefined)
    setKnowledgePoints([])
    setKpIds([])
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
    setKpIds([])
    if (value === undefined) {
      setKnowledgePoints([])
      return
    }
    void loadKnowledgePoints(value).catch((err) => {
      setError(errorMessageOf(err, '知识点加载失败'))
    })
  }

  // ──────────────── 材料块 ────────────────

  const updateBlock = (key: string, patch: Partial<BlockDraft>) => {
    setBlocks((prev) => prev.map((b) => (b.key === key ? { ...b, ...patch } : b)))
  }

  /** 上移 / 下移：只改数组顺序 ⇒ 保存时后端按数组下标重建 order_index */
  const moveBlock = (key: string, delta: number) => {
    setBlocks((prev) => {
      const i = prev.findIndex((b) => b.key === key)
      const j = i + delta
      if (i < 0 || j < 0 || j >= prev.length) return prev
      const next = [...prev]
      const tmp = next[i]
      next[i] = next[j]
      next[j] = tmp
      return next
    })
  }

  /** 登记「本次会话新上传的图」（取消/关闭时按它算孤儿） */
  const registerSessionImage = useCallback((imageId: number) => {
    sessionUploadedImageIdsRef.current = sessionUploadedImageIdsRef.current.includes(imageId)
      ? sessionUploadedImageIdsRef.current
      : [...sessionUploadedImageIdsRef.current, imageId]
  }, [])

  /**
   * 删除「本次会话上传、但服务端已无块引用」的图。
   *
   * @param referenced 服务端当前仍被块引用的 image_id 集合
   */
  const deleteSessionImagesNotIn = useCallback(
    async (gid: number, referenced: Set<number>): Promise<void> => {
      const ids = sessionUploadedImageIdsRef.current
      if (ids.length === 0) return
      for (const imageId of ids) {
        if (referenced.has(imageId)) continue
        try {
          await deleteGroupImage(gid, imageId)
        } catch (err) {
          // 404 = 已被别处删掉（如保存后清 pendingDelete 队列）⇒ 不算失败
          const status = (err as { response?: { status?: number } })?.response?.status
          if (status !== 404) {
            message.warning(`材料图 #${imageId} 回收失败：${errorMessageOf(err, '删除失败')}`)
          }
        }
      }
      // 只留下仍被服务端引用的（其余已回收或已不存在）
      sessionUploadedImageIdsRef.current = ids.filter((id) => referenced.has(id))
    },
    [],
  )

  /**
   * 回收「本次会话上传、但服务端已无块引用」的孤儿图。
   *
   * 🔴 **判据是「服务端当前有没有块引用它」，不是「本次有没有保存成功」** ——
   *    字面口径（未成功保存 ⇒ 全删）会**误删已落库的材料**：
   *    上传 A → 保存（落库）→ 本地删掉 A 的块（还没再保存）→ 取消
   *    ⇒ 服务端那块仍引用 A，此时删 A 会被 `content_blocks.image_id` 的
   *      **FK CASCADE 连带删掉已保存的材料块** ⇒ 数据丢失。
   *    逐张图按服务端真值判断 ⇒ 既清得掉真孤儿，又不碰已落库材料。
   *
   * ⚠️ 读不到服务端真值时**不删**（宁可留孤儿，也不误删已落库材料）。
   */
  const cleanupOrphanSessionImages = useCallback(
    async (gid: number): Promise<void> => {
      if (sessionUploadedImageIdsRef.current.length === 0) return
      let referenced = new Set<number>()
      try {
        const detail = await getQuestionGroup(gid)
        referenced = new Set(
          (detail.blocks ?? [])
            .map((b) => b.image_id)
            .filter((x): x is number => typeof x === 'number'),
        )
      } catch (err) {
        message.warning(
          `材料图回收已跳过（无法确认服务端状态）：${errorMessageOf(err, '读取题组失败')}`,
        )
        return
      }
      await deleteSessionImagesNotIn(gid, referenced)
    },
    [deleteSessionImagesNotIn],
  )

  /** 排入待删图片（不立刻删，理由见 pendingDeleteImageIds 注释） */
  const scheduleImageDelete = (imageId: number) => {
    setPendingDeleteImageIds((prev) => (prev.includes(imageId) ? prev : [...prev, imageId]))
  }

  const removeBlock = (key: string) => {
    const target = blocks.find((b) => b.key === key)
    if (target !== undefined && target.image_id !== null) {
      scheduleImageDelete(target.image_id)
    }
    setBlocks((prev) => prev.filter((b) => b.key !== key))
  }

  const addTextBlock = () => {
    setBlocks((prev) => [...prev, createTextBlock()])
  }

  const addTableBlock = () => {
    setBlocks((prev) => [...prev, createTableBlock()])
  }

  /** 「+ 图片」：直接开文件选择器 ⇒ 选中即上传 ⇒ 拿到 image_id 才建块
   *  （上传失败**不留半块**：块是在上传成功后才追加的）。 */
  const onAddImagePicked = async (file: File): Promise<boolean> => {
    if (currentGroupId === null) {
      message.warning('请先创建题组（材料图必须挂在已存在的题组下）')
      return false
    }
    if (imageCountTotal + 1 > MAX_MATERIAL_IMAGES) {
      message.warning(
        `单组最多 ${MAX_MATERIAL_IMAGES} 张材料图（当前 ${imageCountTotal} 张）`,
      )
      return false
    }
    setUploadingImage(true)
    try {
      const imageId = await uploadMaterialImage(currentGroupId, file, imageCountTotal)
      setSessionImageCount((c) => c + 1)
      // ⭐ 登记本次会话上传的图 ⇒ 取消/关闭时可回收（星轨 OUTBOX #5 · T1 P1）
      registerSessionImage(imageId)
      setBlocks((prev) => [...prev, createImageBlock(imageId)])
      message.success('图片已上传')
    } catch (err) {
      message.error(errorMessageOf(err, '图片上传失败'))
    } finally {
      setUploadingImage(false)
    }
    return false
  }

  /**
   * 关闭抽屉（取消按钮 / 右上角 X / 遮罩点击都走这里）。
   *
   * 🔴 **先回收孤儿图，再关闭**（星轨 OUTBOX #5 · T1 P1）：
   *    上传图后直接点「取消」⇒ 图已落库但没有任何块引用它 ⇒ 留在库里吃配额，
   *    且块编辑器没有「未引用图」入口 ⇒ 用户看不见也删不掉。
   */
  const handleClose = useCallback(async () => {
    if (cleaning) return
    setCleaning(true)
    try {
      if (currentGroupId !== null) {
        await cleanupOrphanSessionImages(currentGroupId)
      }
    } finally {
      setCleaning(false)
      onClose()
    }
  }, [cleaning, currentGroupId, cleanupOrphanSessionImages, onClose])

  // ──────────────── 提交 ────────────────

  /** 新建即落库：POST 拿到 id ⇒ 转编辑态（材料才能传图） */
  const handleCreate = async () => {
    if (chapterId === undefined) {
      message.warning('请选择章节')
      return
    }
    setCreating(true)
    setError(null)
    try {
      const resp = await createQuestionGroup({
        chapter_id: chapterId,
        difficulty,
        knowledge_point_ids: kpIds,
      })
      setCurrentGroupId(resp.id)
      setServerImageCount(0)
      // ⭐ 建组即落库 ⇒ 列表页必须知道多了一个组（否则用户看不到 ⇒ 重做一遍 ⇒ 重复组）
      //   （星轨 1c-2 欠账 P2：内联建题不刷新的同族根因，这里一并堵住）
      onSaved?.()
      message.success(`题组 #${resp.id} 已创建，可继续编辑材料`)
    } catch (err) {
      setError(errorMessageOf(err, '创建题组失败'))
    } finally {
      setCreating(false)
    }
  }

  /**
   * 保存 = 一次 PUT（整体替换）。
   *
   * 顺序铁律：**先 PUT（替换块）→ 再删待删图片**。
   * 反过来（先删图）会被 content_blocks.image_id 的 FK CASCADE 把块一起带走，
   * 刚 PUT 进去的块就没了。
   */
  const handleSave = async () => {
    const gid = currentGroupId
    if (gid === null) {
      message.warning('请先创建题组')
      return
    }
    // ⭐⭐ 保存前的硬闸门：**未知 block_type 绝不能被写回**。
    //   PUT 的 blocks 是**整体替换** ⇒ 把认不出来的块当普通块写回
    //   = 静默改写那块数据（原内容不可恢复），而用户完全不知情。
    //   ⇒ 拦住 + 指名道姓告诉用户是哪一块，别让「保存」变成无声的数据破坏。
    const unsupported = blocks.find((b) => b.unsupportedType !== null)
    if (unsupported !== undefined) {
      setError(
        `材料块 #${blocks.indexOf(unsupported) + 1} 的类型「${unsupported.unsupportedType}」不受支持，` +
          '已阻止保存（材料块是整体替换，写回会覆盖原内容且不可恢复）。' +
          '请先删除该块，或由后端修正该块类型后再保存。',
      )
      message.error('存在无法识别的材料块类型，已阻止保存')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const body: QuestionGroupUpdateBody = {
        difficulty,
        knowledge_point_ids: kpIds,
        blocks: blocks.map(blockToInput),
      }
      await updateQuestionGroup(gid, body)

      // PUT 成功 ⇒ 块已落库 ⇒ 现在删图才安全
      const pending = pendingDeleteImageIds
      for (const imgId of pending) {
        try {
          await deleteGroupImage(gid, imgId)
        } catch (err) {
          // 单张删失败不阻塞整次保存（块已经存好了）；如实提示
          message.warning(`材料图 #${imgId} 清理失败：${errorMessageOf(err, '删除失败')}`)
        }
      }
      if (pending.length > 0) {
        setPendingDeleteImageIds([])
      }
      // 图数重新拉一次（不用算术扣减：待删队列里可能含本次会话新传的图，算术会漂）
      try {
        const imgs = await listGroupImages(gid)
        setServerImageCount(imgs.length)
        setSessionImageCount(0)
      } catch {
        // 计数刷新失败不阻塞保存（块与图都已经落库了）
      }

      message.success('题组已保存')
      // T3：保存成功显示时刻（**不改按钮文案**，避免打断验收脚本的选择器）
      const now = new Date()
      setSavedAtLabel(
        `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`,
      )
      onSaved?.()
      // ⚠️ **保存后不自动关闭抽屉**（与 QuestionDrawer 不同）：
      //    新建即落库 ⇒ 这个抽屉本来就是「建组 → 编辑材料 → 保存」的连续工作区；
      //    关闭了就没法点「重新加载」回读服务端验证顺序/宽度是否落库。
      //    需要离开时点「取消」。
    } catch (err) {
      setError(errorMessageOf(err, '保存失败'))
    } finally {
      setSaving(false)
    }
  }

  /**
   * 从服务端重新加载题组（块 / 难度 / 知识点 / 图数）。
   *
   * 为什么需要它（1c-2 commit 1）：
   *   列表页的题组行 = commit 2 ⇒ 本笔页面上**没有**重新打开已有题组的入口，
   *   而验收点是「刷新后顺序与宽度档位都在」⇒ 需要一个能验证**服务端真值**的按钮。
   *   点它 ⇒ GET /question-groups/{id} ⇒ 屏幕上显示的顺序与宽度就**只可能**来自服务端。
   *   （纯本地 state 回显证明不了任何持久化。）
   */
  const handleReload = async () => {
    const gid = currentGroupId
    if (gid === null) return
    setLoading(true)
    setError(null)
    try {
      const detail = await getQuestionGroup(gid)
      setDifficulty(detail.difficulty)
      setKpIds(detail.knowledge_point_ids ?? [])
      setBlocks(
        [...(detail.blocks ?? [])].sort((a, b) => a.order_index - b.order_index).map(blockFromRead),
      )
      setQuestions(sortQuestions(detail.questions ?? []))
      const imgs = await listGroupImages(detail.id)
      setServerImageCount(imgs.length)
      setSessionImageCount(0)
      setPendingDeleteImageIds([])
      // ⭐ 「重新加载」= **丢弃本地草稿** ⇒ 本次会话新传、但没落库的图同样变孤儿
      //    ⇒ 同源清理（否则「传图→重新加载」也是一条漏路）。
      await deleteSessionImagesNotIn(
        detail.id,
        new Set(
          (detail.blocks ?? [])
            .map((b) => b.image_id)
            .filter((x): x is number => typeof x === 'number'),
        ),
      )
      message.success('已从服务端重新加载')
    } catch (err) {
      setError(errorMessageOf(err, '重新加载失败'))
    } finally {
      setLoading(false)
    }
  }

  // ──────────────── 小题区（1c-2 commit 2） ────────────────

  /** 只刷新小题（**不动本地材料块草稿**）⇒ 小题增删改后调用 */
  const refreshQuestions = useCallback(async (gid: number): Promise<void> => {
    try {
      const detail = await getQuestionGroup(gid)
      setQuestions(sortQuestions(detail.questions ?? []))
    } catch (err) {
      message.warning(`小题列表刷新失败：${errorMessageOf(err, '读取题组失败')}`)
    }
  }, [])

  /** 展开内联表单（create / edit）：**自增 key ⇒ 整体重挂载 ⇒ state 一次性归零** */
  const openInlineCreate = () => {
    setInlineMode('create')
    setEditingQuestion(null)
    setInlineKey((k) => k + 1)
  }

  const openInlineEdit = (q: QuestionRead) => {
    setInlineMode('edit')
    setEditingQuestion(q)
    setInlineKey((k) => k + 1)
  }

  const closeInline = () => {
    setInlineMode('closed')
    setEditingQuestion(null)
  }

  /** 标「待补图」 / 清「待补图」 */
  const markPendingImage = (questionId: number, reason: string) => {
    setPendingImageIds((prev) => (prev.includes(questionId) ? prev : [...prev, questionId]))
    setPendingImageReasons((prev) => ({ ...prev, [questionId]: reason }))
  }

  const clearPendingImage = (questionId: number) => {
    setPendingImageIds((prev) => prev.filter((id) => id !== questionId))
    setPendingImageReasons((prev) => {
      const next = { ...prev }
      delete next[questionId]
      return next
    })
  }

  /**
   * 逐张上传小题图。
   *
   * 🔴 **必须在「题已存在」之后调用**（上传端点要 question_id）——
   *    这就是裁决 ④ 的两段式：**建题成功 → 才传图**。
   *
   * @param baseOrder 新图的 order_index 起点（已有图数 ⇒ 不与旧图撞序号）
   * @returns 成功 true / 失败 false（失败时 reason 里带后端 message）
   */
  const uploadImagesToQuestion = async (
    questionId: number,
    files: File[],
    baseOrder = 0,
  ): Promise<{ ok: boolean; reason: string | null }> => {
    for (let i = 0; i < files.length; i += 1) {
      const f = files[i]
      const ext = (f.name.split('.').pop() ?? 'png').toLowerCase()
      try {
        await uploadQuestionImage(questionId, f, ext, baseOrder + i)
      } catch (err) {
        return { ok: false, reason: errorMessageOf(err, '上传失败') }
      }
    }
    return { ok: true, reason: null }
  }

  /**
   * 新建小题（**两段式，顺序不可颠倒**，裁决 ④）。
   *
   * ① POST /question-groups/{id}/questions 建题
   * ② **成功之后**才 POST /academic/questions/{id}/images 传图
   * ③ 图失败 ⇒ **保留该题**（行留在组内 + 标「待补图」+ 给「重传图片」入口）
   *    并弹 `小题已创建（第 N 题），仅图片上传失败`
   * ④ **建题本身失败 ⇒ 不插入任何行**
   */
  const handleCreateQuestion = async (
    values: InlineQuestionFormValues,
    files: File[],
  ): Promise<void> => {
    const gid = currentGroupId
    if (gid === null) {
      message.warning('请先创建题组（小题必须挂在已存在的题组下）')
      return
    }
    const body: GroupQuestionCreateBody = {
      content: values.content,
      type: values.type,
      points: values.points,
      // answer_text 空 ⇒ **不传该键**（后端 extra="forbid" + 默认 None）
      ...(values.answer_text !== null ? { answer_text: values.answer_text } : {}),
      // choices 只在 choice 题型传；非 choice **不能带**（后端 extra="forbid"）
      ...(values.choices !== undefined ? { choices: values.choices } : {}),
      knowledge_point_ids: values.knowledge_point_ids,
      // ⚠️ **不传** group_order（后端 max+1 分配）/ chapter_id / difficulty（后端从组继承）
    }
    setCreatingQuestion(true)
    try {
      // ① 建题
      let created: QuestionRead
      try {
        created = await createGroupQuestion(gid, body)
      } catch (err) {
        // ④ 建题失败 ⇒ **不插入任何行**；错误信息取后端 message（不是 detail）
        message.error(errorMessageOf(err, '新建小题失败'))
        return
      }
      // ② 建题成功 ⇒ 题目已落库（**不因图失败而回滚**）
      const n = questions.length + 1
      setQuestions((prev) => sortQuestions([...prev, created]))
      closeInline()
      // ③ 然后才传图
      if (files.length > 0) {
        const { ok, reason } = await uploadImagesToQuestion(created.id, files)
        if (!ok) {
          markPendingImage(created.id, reason ?? '上传失败')
          message.error(`小题已创建（第 ${n} 题），仅图片上传失败`)
        } else {
          message.success(`小题已创建（第 ${n} 题）`)
        }
      } else {
        message.success(`小题已创建（第 ${n} 题）`)
      }
      // 回读服务端（题序 / 图数以服务端为准）
      await refreshQuestions(gid)
      // ⭐ 小题已落库 ⇒ 通知列表页刷新（题组行的「N 小题」计数变了）
      //   （星轨 1c-2 欠账 P2：数据已落库但列表看不到 ⇒ 用户以为没建成 ⇒ 重做 ⇒ 重复题组）
      onSaved?.()
    } finally {
      setCreatingQuestion(false)
    }
  }

  /** 编辑小题：PATCH /academic/questions/{id}（只传改动字段；**无 chapter_id**）⇒ 然后才传图 */
  const handleEditQuestion = async (
    values: InlineQuestionFormValues,
    files: File[],
  ): Promise<void> => {
    const target = editingQuestion
    if (target === null) return
    setSavingQuestion(true)
    try {
      const body: Record<string, unknown> = {}
      // ⚠️ **只传改动字段**（brief §3.2）
      //   choices 传则**完全替换**（删旧建新 + cascade）⇒ 没改就别传。
      if (values.content !== target.content) body.content = values.content
      if (values.type !== target.type) body.type = values.type
      if (values.points !== target.points) body.points = values.points
      if ((values.answer_text ?? null) !== (target.answer_text ?? null)) {
        body.answer_text = values.answer_text
      }
      if (!sameIdSet(values.knowledge_point_ids, target.knowledge_point_ids ?? [])) {
        body.knowledge_point_ids = values.knowledge_point_ids
      }
      if (values.choices !== undefined && !sameChoices(values.choices, target.choices ?? [])) {
        body.choices = values.choices
      }
      if (Object.keys(body).length === 0 && files.length === 0) {
        message.info('没有改动，无需保存')
        return
      }
      // 有字段改动才 PATCH（只传改动字段）；只选了图 ⇒ 跳过 PATCH，直接传图
      if (Object.keys(body).length > 0) {
        try {
          await apiClient.patch(`/academic/questions/${target.id}`, body, {
            headers: AUTH_HEADERS,
          })
        } catch (err) {
          message.error(errorMessageOf(err, '保存小题失败'))
          return
        }
      }
      closeInline()
      if (files.length > 0) {
        const { ok, reason } = await uploadImagesToQuestion(
          target.id,
          files,
          target.image_count ?? 0,
        )
        if (!ok) {
          markPendingImage(target.id, reason ?? '上传失败')
          message.error('题目已保存，仅图片上传失败')
        } else {
          message.success('题目已保存')
        }
      } else {
        message.success('题目已保存')
      }
      setQuestionGalleryKey((k) => k + 1)
      const gid = currentGroupId
      if (gid !== null) await refreshQuestions(gid)
      // ⭐ 小题已改 ⇒ 通知列表页刷新（同上；题组行的计数/摘要可能变了）
      onSaved?.()
    } finally {
      setSavingQuestion(false)
    }
  }

  /** 删除小题：DELETE /academic/questions/{id} */
  const handleDeleteQuestion = async (questionId: number): Promise<void> => {
    setDeletingQuestionId(questionId)
    try {
      await apiClient.delete(`/academic/questions/${questionId}`, {
        headers: AUTH_HEADERS,
      })
      message.success('小题已删除')
      clearPendingImage(questionId)
      const gid = currentGroupId
      if (gid !== null) await refreshQuestions(gid)
      // ⭐ 小题已删 ⇒ 通知列表页刷新（题组行的「N 小题」计数变了）
      onSaved?.()
    } catch (err) {
      message.error(errorMessageOf(err, '删除小题失败'))
    } finally {
      setDeletingQuestionId(null)
    }
  }

  /** 行内「重传图片」：待补图的小题重新传图（成功 ⇒ 清「待补图」标记） */
  const handleRetryImage = async (
    question: QuestionRead,
    file: File,
  ): Promise<boolean> => {
    const ext = (file.name.split('.').pop() ?? 'png').toLowerCase()
    if (!['png', 'jpg', 'jpeg', 'webp'].includes(ext)) {
      message.warning(`「${file.name}」类型不支持（仅 png / jpg / jpeg / webp）`)
      return false
    }
    setUploadingImageQuestionId(question.id)
    try {
      await uploadQuestionImage(question.id, file, ext, question.image_count ?? 0)
      clearPendingImage(question.id)
      message.success('图片已上传')
      const gid = currentGroupId
      if (gid !== null) await refreshQuestions(gid)
    } catch (err) {
      const reason = errorMessageOf(err, '上传失败')
      markPendingImage(question.id, reason)
      message.error(`图片上传失败：${reason}`)
    } finally {
      setUploadingImageQuestionId(null)
    }
    return false
  }

  // ──────────────── 渲染 ────────────────

  const kpPlaceholder = (() => {
    if (chapterId === undefined) return '先选章节'
    if (knowledgePoints.length === 0) return '本章暂无知识点'
    return '全部知识点'
  })()

  /** 内联表单标题（编辑态带题序，避免用户不知道在改哪一道） */
  const inlineFormTitle = (() => {
    if (inlineMode === 'create') return '新建小题'
    if (editingQuestion === null) return '编辑小题'
    const idx = questions.findIndex((q) => q.id === editingQuestion.id)
    return `编辑小题（第 ${questionOrderOf(editingQuestion, idx < 0 ? 0 : idx)} 题）`
  })()

  const busy = loading || saving || creating || cleaning
  /** 小题区的忙碌态（建题/改题进行中 ⇒ 锁住行操作，避免并发） */
  const questionBusy = creatingQuestion || savingQuestion

  return (
    <Drawer
      title={mode === 'edit' ? '编辑题组' : '新建题组'}
      width={880}
      open={open}
      onClose={() => void handleClose()}
      destroyOnClose
      extra={
        <Space>
          <Button onClick={() => void handleClose()} disabled={busy}>
            取消
          </Button>
          {currentGroupId === null ? (
            <Button
              type="primary"
              loading={creating}
              disabled={busy || chapterId === undefined}
              onClick={() => void handleCreate()}
            >
              创建题组
            </Button>
          ) : (
            <Space>
              <Button type="primary" loading={saving} disabled={busy} onClick={() => void handleSave()}>
                保存
              </Button>
              {/* T3（星轨 OUTBOX #5）：保存成功后显示时刻 ⇒ 用户知道存没存，不用反复点。
                  ⚠️ **不改按钮文案**（「保存」→「已保存 15:23」会打断验收脚本的选择器）。 */}
              {savedAtLabel !== null && (
                <Tag color="green">已保存 {savedAtLabel}</Tag>
              )}
            </Space>
          )}
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
        {/* ① 章节（教材→章节 级联）+ 难度 */}
        <div>
          <Text strong>章节</Text>
          <Space.Compact style={{ width: '100%', marginTop: 4 }}>
            <Select
              style={{ width: '50%' }}
              placeholder="选择教材"
              value={textbookId}
              options={textbooks.map((t) => ({ value: t.id, label: t.title }))}
              onChange={onTextbookChange}
              disabled={busy || chapterLocked}
              loading={loading}
              showSearch
              optionFilterProp="label"
            />
            <Select
              style={{ width: '50%' }}
              placeholder="选择章节"
              value={chapterId}
              options={chapters.map((c) => ({ value: c.id, label: c.title }))}
              onChange={onChapterChange}
              disabled={busy || chapterLocked || textbookId === undefined}
              loading={loading}
              showSearch
              optionFilterProp="label"
            />
          </Space.Compact>
          {chapterLocked && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              题组已落库，章节不可改（后端 QuestionGroupUpdate 无 chapter_id 字段）
            </Text>
          )}
        </div>

        {/* ② 难度（下拉；与题目抽屉口径一致，只显示中文名） */}
        <div>
          <Text strong>难度</Text>
          <Space wrap style={{ marginTop: 4 }}>
            <Select
              style={{ width: 200 }}
              value={difficulty}
              options={DIFFICULTY_OPTIONS_CHINESE}
              disabled={busy}
              onChange={(v: QuestionDifficulty) => setDifficulty(v)}
            />
            <Tag color="geekblue">当前：{difficulty}</Tag>
          </Space>
        </div>

        {/* ③ 知识点（多选；多对多，保存时整体替换 knowledge_point_ids） */}
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
              disabled={busy || chapterId === undefined}
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

        {/* ④ 材料块 */}
        <Card
          size="small"
          title={
            <Space size="small">
              <Text strong>材料</Text>
              <Tag color="blue">{blocks.length} 块</Tag>
            </Space>
          }
          extra={
            currentGroupId !== null ? (
              <Popconfirm
                title="从服务端重新加载？"
                description="会丢弃未保存的本地修改，屏幕内容将完全来自服务端。"
                okText="重新加载"
                cancelText="取消"
                onConfirm={() => void handleReload()}
              >
                <Button size="small" disabled={busy}>
                  重新加载
                </Button>
              </Popconfirm>
            ) : null
          }
        >
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            {currentGroupId === null ? (
              <Alert
                type="info"
                showIcon
                message="先创建题组，才能编辑材料"
                description="材料图必须挂在已存在的题组下（上传端点要 group_id）⇒ 请先点右上角「创建题组」。中途关闭会留下一个空题组（brief 已接受该代价）。"
              />
            ) : (
              <>
                {blocks.length === 0 ? (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="还没有材料块，用下面的按钮添加"
                  />
                ) : (
                  blocks.map((b, i) => (
                    <ContentBlockEditor
                      key={b.key}
                      block={b}
                      index={i}
                      total={blocks.length}
                      groupId={currentGroupId}
                      disabled={busy}
                      imageCountTotal={imageCountTotal}
                      orderIndex={imageCountTotal}
                      onChange={(patch) => updateBlock(b.key, patch)}
                      onMoveUp={() => moveBlock(b.key, -1)}
                      onMoveDown={() => moveBlock(b.key, 1)}
                      onRemove={() => removeBlock(b.key)}
                      onScheduleImageDelete={scheduleImageDelete}
                      onImageUploaded={(imageId: number) => {
                        setSessionImageCount((c) => c + 1)
                        // ⭐ 换图也会新上传一张 ⇒ 同样要登记（否则取消时漏回收）
                        registerSessionImage(imageId)
                      }}
                    />
                  ))
                )}

                <Space wrap>
                  <Button icon={<PlusOutlined />} disabled={busy} onClick={addTextBlock}>
                    + 文字
                  </Button>
                  <Upload
                    beforeUpload={onAddImagePicked}
                    fileList={[]}
                    showUploadList={false}
                    accept=".png,.jpg,.jpeg,.webp"
                    disabled={busy || uploadingImage}
                  >
                    <Button icon={<UploadOutlined />} disabled={busy || uploadingImage}>
                      + 图片
                    </Button>
                  </Upload>
                  <Button icon={<PlusOutlined />} disabled={busy} onClick={addTableBlock}>
                    + 表格
                  </Button>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    顺序 = 上下移顺序，保存后按数组顺序落库（order_index）
                  </Text>
                </Space>

                {currentGroupId !== null && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    保存后抽屉保持打开；点「重新加载」可从服务端回读，核对顺序与图片宽度档位是否真的落库。
                  </Text>
                )}
              </>
            )}
          </Space>
        </Card>

        {/* ⑤ 小题区（1c-2 commit 2：内联新建 / 编辑 + 删除 + 待补图重传） */}
        <Card
          size="small"
          title={
            <Space size="small">
              <Text strong>小题</Text>
              <Tag color="blue">{questions.length}</Tag>
            </Space>
          }
          extra={
            <Button
              icon={<PlusOutlined />}
              disabled={busy || questionBusy || currentGroupId === null}
              onClick={openInlineCreate}
            >
              + 新建小题
            </Button>
          }
        >
          {currentGroupId === null ? (
            <Alert
              type="info"
              showIcon
              message="先创建题组，才能新建小题"
              description="小题必须挂在已存在的题组下 ⇒ 请先点右上角「创建题组」。"
            />
          ) : (
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              {questions.length === 0 ? (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description="还没有小题，点右上角「+ 新建小题」"
                />
              ) : (
                questions.map((q, idx) => {
                  const pending = pendingImageIds.includes(q.id)
                  const kpNames = q.knowledge_point_names ?? []
                  return (
                    <div
                      key={q.id}
                      role="button"
                      style={{
                        border: '1px solid #f0f0f0',
                        borderRadius: 6,
                        padding: '8px 12px',
                        cursor: 'pointer',
                      }}
                      // 点已有小题行 ⇒ 内联展开编辑表单（操作按钮除外）
                      onClick={() => openInlineEdit(q)}
                    >
                      <Space wrap size="small">
                        <Tag color="blue">第 {questionOrderOf(q, idx)} 题</Tag>
                        <Tooltip title={q.content}>
                          <Text style={{ maxWidth: 320 }} ellipsis>
                            {previewOf(q.content)}
                          </Text>
                        </Tooltip>
                        <Tag>{TYPE_LABEL[q.type] ?? q.type}</Tag>
                        <Text type="secondary">{q.points} 分</Text>
                        {kpNames.length > 0 ? (
                          <Space size={[4, 4]} wrap>
                            {kpNames.map((n) => (
                              <Tag key={n} color="geekblue">
                                {n}
                              </Tag>
                            ))}
                          </Space>
                        ) : (
                          <Text type="secondary">无知识点</Text>
                        )}
                        <Text type="secondary">{q.image_count ?? 0} 图</Text>
                        {pending && <Tag color="warning">待补图</Tag>}
                        <Space size="small" onClick={(e) => e.stopPropagation()}>
                          <Button
                            size="small"
                            disabled={busy || questionBusy}
                            onClick={() => openInlineEdit(q)}
                          >
                            编辑
                          </Button>
                          <Upload
                            beforeUpload={(file: File) => handleRetryImage(q, file)}
                            fileList={[]}
                            showUploadList={false}
                            accept=".png,.jpg,.jpeg,.webp"
                            disabled={busy || questionBusy || uploadingImageQuestionId === q.id}
                          >
                            <Button
                              size="small"
                              loading={uploadingImageQuestionId === q.id}
                              disabled={busy || questionBusy}
                            >
                              重传图片
                            </Button>
                          </Upload>
                          <Popconfirm
                            title="删除这道小题？"
                            description="删除后不可恢复（其图片一并级联清理）。"
                            okText="删除"
                            cancelText="取消"
                            okButtonProps={{ danger: true }}
                            onConfirm={() => void handleDeleteQuestion(q.id)}
                          >
                            <Button
                              size="small"
                              danger
                              loading={deletingQuestionId === q.id}
                              disabled={busy || questionBusy}
                            >
                              删除
                            </Button>
                          </Popconfirm>
                        </Space>
                      </Space>
                      {pending && pendingImageReasons[q.id] !== undefined && (
                        <Text type="danger" style={{ fontSize: 12 }}>
                          图片上传失败原因：{pendingImageReasons[q.id]}（题目已保留，点「重传图片」补传）
                        </Text>
                      )}
                    </div>
                  )
                })
              )}

              {inlineMode !== 'closed' && (
                <Card
                  size="small"
                  style={{ marginTop: 8 }}
                  title={inlineFormTitle}
                >
                  <InlineQuestionForm
                    key={inlineKey}
                    mode={inlineMode}
                    question={editingQuestion}
                    groupDifficulty={difficulty}
                    chapterTitle={chapters.find((c) => c.id === chapterId)?.title}
                    knowledgePoints={knowledgePoints}
                    defaultKnowledgePointIds={kpIds}
                    existingImageCount={editingQuestion?.image_count ?? 0}
                    galleryKey={questionGalleryKey}
                    disabled={creatingQuestion || savingQuestion}
                    onCancel={closeInline}
                    onImagesChanged={() => {
                      const gid = currentGroupId
                      if (gid !== null) void refreshQuestions(gid)
                    }}
                    onSubmit={
                      inlineMode === 'create'
                        ? handleCreateQuestion
                        : handleEditQuestion
                    }
                  />
                </Card>
              )}
            </Space>
          )}
        </Card>
      </Space>
    </Drawer>
  )
}
