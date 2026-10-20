/**
 * 题目图片展示（1c-1c 裁决，2026-10-20 14:48）。
 *
 * 作用：把某题的图片按 order_index 展示成缩略图，可删。
 *
 * 两条硬约束（1c-1c 派工单）：
 * ① **禁止** `<img src="/api/...">` —— <img> 发不出 X-User-Id ⇒ 401。
 *    这里走 axios(`responseType: 'blob'`) + `URL.createObjectURL`，
 *    <img> 的 src 拿到的是 `blob:` URL，不是 /api 路径。
 * ② objectURL 不会自动回收 ⇒ 必须 revokeObjectURL。
 *    本组件用 urlsRef 持有全部 objectURL，并在 **卸载 / questionId 切换 / 重新加载** 时统一回收。
 *
 * 刷新方式：父组件改 `key` 即可强制重挂载重载（不用加 reloadToken prop ——
 * 那会触发 react-hooks/exhaustive-deps 的「多余依赖」警告，而 lint 是
 * --max-warnings 0）。
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, Button, Empty, Space, Spin, Tag, Typography, message } from 'antd'
import { apiClient } from '../api/client'
import { fetchImageObjectUrl, listQuestionImages } from '../api/images'
import {
  AUTH_HEADERS,
  errorMessageOf,
  type QuestionImageSummary,
} from '../api/questionTypes'

const { Text } = Typography

interface LoadedImage {
  summary: QuestionImageSummary
  /** objectURL；null = 该图字节加载失败 */
  url: string | null
  error: string | null
}

export interface QuestionImagesProps {
  questionId: number
  /** 图片增删后回调（列表页用来刷新 image_count） */
  onChanged?: () => void
}

export default function QuestionImages({ questionId, onChanged }: QuestionImagesProps) {
  const [items, setItems] = useState<LoadedImage[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  /** 持有全部 objectURL，供统一 revoke */
  const urlsRef = useRef<string[]>([])

  const revokeAll = useCallback(() => {
    urlsRef.current.forEach((u) => URL.revokeObjectURL(u))
    urlsRef.current = []
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    revokeAll()
    try {
      const summaries = await listQuestionImages(questionId)
      const loaded: LoadedImage[] = []
      for (const s of summaries) {
        try {
          const url = await fetchImageObjectUrl(questionId, s.id)
          urlsRef.current.push(url)
          loaded.push({ summary: s, url, error: null })
        } catch (err) {
          // 单张失败不拖垮整个列表
          loaded.push({
            summary: s,
            url: null,
            error: errorMessageOf(err, '图片加载失败'),
          })
        }
      }
      setItems(loaded)
    } catch (err) {
      setError(errorMessageOf(err, '图片列表加载失败'))
    } finally {
      setLoading(false)
    }
  }, [questionId, revokeAll])

  useEffect(() => {
    void load()
    // 卸载 / questionId 变化 ⇒ 回收 objectURL
    return () => {
      revokeAll()
    }
  }, [load, revokeAll])

  const handleDelete = async (img: QuestionImageSummary) => {
    setDeletingId(img.id)
    try {
      await apiClient.delete(`/academic/questions/${questionId}/images/${img.id}`, {
        headers: AUTH_HEADERS,
      })
      message.success('图片已删除')
      await load()
      onChanged?.()
    } catch (err) {
      setError(errorMessageOf(err, '删除图片失败'))
    } finally {
      setDeletingId(null)
    }
  }

  if (loading && items.length === 0) {
    return (
      <Space>
        <Spin size="small" />
        <Text type="secondary">加载图片…</Text>
      </Space>
    )
  }

  if (error !== null) {
    return <Alert type="error" showIcon message={error} />
  }

  if (items.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="该题暂无图片" />
  }

  return (
    <Space direction="vertical" size="small" style={{ width: '100%' }}>
      {items.map((it) => (
        <Space key={it.summary.id} size="small" align="start" style={{ width: '100%' }}>
          <Tag color="blue">#{it.summary.order_index + 1}</Tag>
          {it.url !== null ? (
            <img
              src={it.url}
              alt={`图片 ${it.summary.id}`}
              style={{
                width: 96,
                height: 96,
                objectFit: 'cover',
                borderRadius: 4,
                border: '1px solid #f0f0f0',
              }}
            />
          ) : (
            <div
              style={{
                width: 96,
                height: 96,
                borderRadius: 4,
                border: '1px dashed #d9d9d9',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#8c8c8c',
                fontSize: 12,
                textAlign: 'center',
                padding: 4,
              }}
            >
              {it.error ?? '加载失败'}
            </div>
          )}
          <Space direction="vertical" size={2}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {it.summary.file_ext} · {new Date(it.summary.uploaded_at).toLocaleString('zh-CN')}
            </Text>
            <Button
              size="small"
              danger
              loading={deletingId === it.summary.id}
              disabled={deletingId !== null}
              onClick={() => void handleDelete(it.summary)}
            >
              删除
            </Button>
          </Space>
        </Space>
      ))}
    </Space>
  )
}
