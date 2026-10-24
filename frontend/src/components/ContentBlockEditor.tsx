/**
 * 材料块编辑器（1c-2 commit 1）—— 一个块 = 一行（[↑][↓][🗑] + 类型化编辑区）。
 *
 * 覆盖 3 种块：
 * - text  → TextArea 编辑 text_content（新建时默认空串）
 * - image → 缩略图 + 宽度档位（meta.image_width = 50/75/100）+ [换图][删除]
 * - table → TableBlockEditor（table_json ↔ 编辑器双向转换）
 *
 * 🔴 两条硬约束（1c-1 血泪，1c-2 继续沿用）：
 * ① **禁止** `<img src="/api/...">` —— <img> 发不出 X-User-Id ⇒ 401。
 *    缩略图走 axios(responseType:'blob') + URL.createObjectURL，
 *    <img> 的 src 只能是 blob: URL（范式见 QuestionImages.tsx 的 urlsRef 思路，
 *    这里是**每个块一个** effect，卸载/换图时 revoke）。
 * ② 图片字节只走 `/question-groups/{id}/images/{image_id}/content`，
 *    不许 nginx 静态挂 /uploads（会绕过 owner 校验）。
 *
 * ⚠️ 换图 / 删块**不立刻删服务器图片**：
 *    后端 content_blocks.image_id 上挂了 FK CASCADE ⇒ 先删图会把**已落库的块**
 *    连带删掉（用户还没保存，库里就少了一块材料）。
 *    ⇒ 这里只把旧 image_id 交给上层排进「待删队列」，
 *      等 PUT（整体替换块）成功之后再删（见 QuestionGroupDrawer）。
 */
import { useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Input,
  Popconfirm,
  Radio,
  Space,
  Tag,
  Tooltip,
  Typography,
  Upload,
  message,
} from 'antd'
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  DeleteOutlined,
  UploadOutlined,
} from '@ant-design/icons'

import { fetchGroupImageObjectUrl, uploadGroupImage } from '../api/images'
import {
  DEFAULT_IMAGE_WIDTH,
  IMAGE_WIDTH_OPTIONS,
  errorMessageOf,
  isKnownBlockType,
  type ContentBlockInput,
  type ContentBlockRead,
  type ContentBlockType,
  type ImageWidthPercent,
  type TableJson,
} from '../api/questionTypes'
import TableBlockEditor, { defaultTableJson, parseTableJson } from './TableBlockEditor'

const { Text } = Typography

/** 图片限制（对齐后端 routers/academic.py：MAX_IMAGES_PER_GROUP / _ALLOWED_FILE_EXTS） */
export const MAX_MATERIAL_IMAGE_BYTES = 5 * 1024 * 1024
export const MAX_MATERIAL_IMAGES = 10
export const ALLOWED_MATERIAL_EXTS = ['png', 'jpg', 'jpeg', 'webp']

/** 块类型显示名 */
export const BLOCK_TYPE_LABEL: Record<ContentBlockType, string> = {
  text: '文字',
  image: '图片',
  table: '表格',
}

// ──────────────── 前端草稿态 ────────────────

/**
 * 一个材料块的前端草稿。
 *
 * 为什么是「草稿」而不是直接用后端的 ContentBlockRead：
 * - 后端块有 id / order_index（**保存前不存在**），前端要先能排版才能保存；
 * - table_json 是 dict[string, any]，编辑期要的是强类型二维数组
 *   （TableJson）⇒ 编辑期用强类型、保存时再转回 dict。
 */
export interface BlockDraft {
  /** 前端唯一 key（React key + 定位）；后端 id 保存后才有 ⇒ 不能用 id 当 key */
  key: string
  block_type: ContentBlockType
  text_content: string
  image_id: number | null
  table: TableJson
  /** 图片宽度档位（百分数）；只对 image 块有意义 */
  image_width: ImageWidthPercent
  /**
   * 服务端返回的**未知** block_type 原值（非 null ⇒ 这块认不出来）。
   *
   * ⭐ 为什么必须有这个字段（**不是防御性编程的洁癖，是数据安全问题**）：
   *   后端读取 schema 的 block_type 是裸 str，库里可能有历史脏值。
   *   认不出来时若「顺手当成 text」⇒ PUT 的 blocks 是**整体替换**
   *   ⇒ **保存一次就把那块数据改写成文本块**（原内容丢失，且用户毫不知情）。
   *   ⇒ 认不出来就**显式标出来 + 阻断保存**（见 QuestionGroupDrawer.handleSave），
   *     让用户显式删掉它（或后端修数据）再保存。
   */
  unsupportedType: string | null
}

let blockSeq = 0
function nextBlockKey(prefix: string): string {
  blockSeq += 1
  return `${prefix}-${blockSeq}`
}

/** 新建文字块（text_content 默认空串） */
export function createTextBlock(): BlockDraft {
  return {
    key: nextBlockKey('text'),
    block_type: 'text',
    text_content: '',
    image_id: null,
    table: defaultTableJson(),
    image_width: DEFAULT_IMAGE_WIDTH,
    unsupportedType: null,
  }
}

/** 新建表格块（默认 2 行 × 3 列、首行表头） */
export function createTableBlock(): BlockDraft {
  return {
    key: nextBlockKey('table'),
    block_type: 'table',
    text_content: '',
    image_id: null,
    table: defaultTableJson(),
    image_width: DEFAULT_IMAGE_WIDTH,
    unsupportedType: null,
  }
}

/** 新建图片块（image_id 已由上传拿到；宽度默认 100） */
export function createImageBlock(imageId: number): BlockDraft {
  return {
    key: nextBlockKey('image'),
    block_type: 'image',
    text_content: '',
    image_id: imageId,
    table: defaultTableJson(),
    image_width: DEFAULT_IMAGE_WIDTH,
    unsupportedType: null,
  }
}

/**
 * 后端 ContentBlockRead → 前端草稿。
 *
 * meta.image_width 口径：只认 50 / 75 / 100，其余一律当 100
 * （后端 meta 是 dict[str, Any] ⇒ 可能是脏值；脏值不能把渲染搞崩）。
 */
export function blockFromRead(block: ContentBlockRead): BlockDraft {
  const raw = block.meta?.image_width
  const width: ImageWidthPercent =
    typeof raw === 'number' && (raw === 50 || raw === 75 || raw === 100) ? raw : DEFAULT_IMAGE_WIDTH
  // ⚠️ 类型守卫**直接写在内联三元里** —— 存进 boolean 变量后
  //    TS 的收窄信息就丢了（block_type 会退回 string ⇒ TS2322）。
  const unsupportedType = isKnownBlockType(block.block_type) ? null : block.block_type
  return {
    key: nextBlockKey(`b${block.id}`),
    // ⚠️ 未知类型时**不当成 text**（那会悄悄改写数据）⇒ 标记 unsupportedType，
    //    block_type 暂用 'text' 仅供渲染分支不崩，保存前会被拦住。
    block_type: isKnownBlockType(block.block_type) ? block.block_type : 'text',
    unsupportedType,
    text_content: block.text_content ?? '',
    image_id: block.image_id ?? null,
    table: parseTableJson(block.table_json),
    image_width: width,
  }
}

/**
 * 前端草稿 → PUT 的 ContentBlockInput。
 *
 * ⚠️ 只带该类型真正用到的字段（后端 ContentBlockInput 是 extra="forbid"，
 *    多带字段直接 422）。
 * - image 块必须带 meta.image_width ⇒ **宽度档位就是靠这个字段持久化的**；
 * - table 块必须带 table_json（{header, rows}）；
 * - text 块必须带 text_content。
 */
export function blockToInput(block: BlockDraft): ContentBlockInput {
  // ⭐ 兜底闸门：未知类型块**绝不能**被写回（PUT 整体替换 ⇒ 写回=覆盖=丢数据）。
  //   正常路径下 handleSave 已提前拦截并 return；这里是最后一道，
  //   保证任何绕过 handleSave 的调用也**不会**静默改写数据。
  if (block.unsupportedType !== null) {
    throw new Error(`材料块类型「${block.unsupportedType}」不受支持，无法保存`)
  }
  if (block.block_type === 'text') {
    return { block_type: 'text', text_content: block.text_content }
  }
  if (block.block_type === 'image') {
    return {
      block_type: 'image',
      image_id: block.image_id,
      meta: { image_width: block.image_width },
    }
  }
  return {
    block_type: 'table',
    table_json: { header: block.table.header, rows: block.table.rows },
  }
}

/**
 * 上传一张材料图（本地预校验 + 调后端），返回新的 image_id。
 *
 * 为什么前端也要预校验：判据要求「当场拦（不发请求）」；
 * 而且后端的 5MB/10 张限制报错信息是英文 detail，前端拦体验更好。
 */
export async function uploadMaterialImage(
  groupId: number,
  file: File,
  orderIndex: number,
): Promise<number> {
  const ext = (file.name.split('.').pop() ?? '').toLowerCase()
  if (!ALLOWED_MATERIAL_EXTS.includes(ext)) {
    throw new Error(`「${file.name}」类型不支持（仅 png / jpg / jpeg / webp）`)
  }
  if (file.size > MAX_MATERIAL_IMAGE_BYTES) {
    throw new Error(
      `「${file.name}」超过 5MB（${(file.size / 1024 / 1024).toFixed(1)}MB）`,
    )
  }
  const img = await uploadGroupImage(groupId, file, ext, orderIndex)
  if (img?.id === undefined) {
    throw new Error('后端未返回图片 id')
  }
  return img.id
}

export interface ContentBlockEditorProps {
  block: BlockDraft
  /** 该块在序列中的下标（0 起） */
  index: number
  /** 块总数 */
  total: number
  /** 所属题组 id；null = 题组还没建（此时不能传图） */
  groupId: number | null
  disabled: boolean
  /** 服务端已有图数 + 本次会话已传数（用于 10 张上限判断） */
  imageCountTotal: number
  /** 新图的 order_index 建议值 */
  orderIndex: number
  onChange: (patch: Partial<BlockDraft>) => void
  onMoveUp: () => void
  onMoveDown: () => void
  onRemove: () => void
  /** 换图：把旧 image_id 交给上层排「待删队列」（保存成功后由上层删） */
  onScheduleImageDelete: (imageId: number) => void
  /**
   * 上传成功回调（上层用来累加本次会话图数 + 登记新图 id）。
   *
   * ⚠️ **必须回传 imageId**：换图也会新上传一张图，
   *    上层要靠它登记「本次会话新传的图」⇒ 取消时才能回收（星轨 OUTBOX #5 T1）。
   */
  onImageUploaded: (imageId: number) => void
}

export default function ContentBlockEditor({
  block,
  index,
  total,
  groupId,
  disabled,
  imageCountTotal,
  orderIndex,
  onChange,
  onMoveUp,
  onMoveDown,
  onRemove,
  onScheduleImageDelete,
  onImageUploaded,
}: ContentBlockEditorProps) {
  const [thumbUrl, setThumbUrl] = useState<string | null>(null)
  const [thumbError, setThumbError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  // ── 缩略图：blob → objectURL（禁止 <img src="/api/...">，见文件头注释）──
  useEffect(() => {
    if (groupId === null || block.image_id === null) {
      setThumbUrl(null)
      return
    }
    let cancelled = false
    let url: string | null = null
    const load = async () => {
      try {
        const u = await fetchGroupImageObjectUrl(groupId, block.image_id as number)
        if (cancelled) {
          URL.revokeObjectURL(u)
          return
        }
        url = u
        setThumbUrl(u)
        setThumbError(null)
      } catch (err) {
        if (!cancelled) setThumbError(errorMessageOf(err, '图片加载失败'))
      }
    }
    void load()
    return () => {
      cancelled = true
      // revoke 必须在 cleanup 里做：objectURL 不会自动回收（1c-1 血泪）
      if (url !== null) URL.revokeObjectURL(url)
    }
  }, [groupId, block.image_id])

  // ── 上传（首次传图 / 换图共用）──
  const pickImage = (replace: boolean) => async (file: File): Promise<boolean> => {
    if (groupId === null) {
      message.warning('请先创建题组（材料图必须挂在已存在的题组下）')
      return false
    }
    if (!replace && imageCountTotal + 1 > MAX_MATERIAL_IMAGES) {
      message.warning(`单组最多 ${MAX_MATERIAL_IMAGES} 张材料图（当前 ${imageCountTotal} 张）`)
      return false
    }
    setUploading(true)
    try {
      const newId = await uploadMaterialImage(groupId, file, orderIndex)
      if (replace && block.image_id !== null) {
        // 旧图不立即删（会 CASCADE 掉已落库的块）⇒ 排待删队列
        onScheduleImageDelete(block.image_id)
      }
      onChange({ image_id: newId })
      onImageUploaded(newId)
      message.success(replace ? '图片已替换' : '图片已上传')
    } catch (err) {
      message.error(errorMessageOf(err, '图片上传失败'))
    } finally {
      setUploading(false)
    }
    return false
  }

  return (
    <Card
      size="small"
      style={{ marginBottom: 8 }}
      title={
        <Space size="small">
          <Tag color="blue">#{index + 1}</Tag>
          <Text strong>
            {block.unsupportedType !== null
              ? `未知类型（${block.unsupportedType}）`
              : BLOCK_TYPE_LABEL[block.block_type]}
          </Text>
        </Space>
      }
      extra={
        <Space size={4}>
          <Tooltip title="上移">
            <Button
              size="small"
              icon={<ArrowUpOutlined />}
              disabled={disabled || index === 0}
              onClick={onMoveUp}
            />
          </Tooltip>
          <Tooltip title="下移">
            <Button
              size="small"
              icon={<ArrowDownOutlined />}
              disabled={disabled || index === total - 1}
              onClick={onMoveDown}
            />
          </Tooltip>
          <Popconfirm
            title="删除这块材料？"
            description="删除后保存即可生效（图片在保存成功后一并清理）。"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={onRemove}
          >
            <Button size="small" danger icon={<DeleteOutlined />} disabled={disabled} />
          </Popconfirm>
        </Space>
      }
    >
      {block.unsupportedType !== null && (
        <Alert
          type="error"
          showIcon
          message={`无法识别的材料块类型「${block.unsupportedType}」`}
          description={
            <Text>
              服务端返回的 block_type 不在 text/image/table 白名单内。
              <b>保存已被阻止</b>：材料块是整体替换的，若把这个块当作普通块写回，
              原内容会被改写覆盖且不可恢复。请先删除该块（或由后端修正该块类型）再保存。
            </Text>
          }
          style={{ marginBottom: 8 }}
        />
      )}

      {block.unsupportedType === null && block.block_type === 'text' && (
        <Input.TextArea
          rows={3}
          value={block.text_content}
          disabled={disabled}
          placeholder="材料文字（纯文本）"
          onChange={(e) => onChange({ text_content: e.target.value })}
        />
      )}

      {block.block_type === 'table' && (
        <TableBlockEditor
          value={block.table}
          disabled={disabled}
          onChange={(table) => onChange({ table })}
        />
      )}

      {block.block_type === 'image' && (
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          {block.image_id === null ? (
            <Upload
              beforeUpload={pickImage(false)}
              fileList={[]}
              showUploadList={false}
              accept=".png,.jpg,.jpeg,.webp"
              disabled={disabled || uploading}
            >
              <Button icon={<UploadOutlined />} disabled={disabled || uploading}>
                上传图片（png/jpg/jpeg/webp，单张 ≤ 5MB，单组 ≤ 10 张）
              </Button>
            </Upload>
          ) : (
            <>
              {/* 宽度预览：容器宽度 = 当前档位 ⇒ 切换档位立刻能看到比例变化 */}
              <div style={{ width: `${block.image_width}%`, minWidth: 120 }}>
                {thumbUrl !== null ? (
                  <img
                    src={thumbUrl}
                    alt={`材料图 ${block.image_id ?? ''}`}
                    style={{
                      width: '100%',
                      maxHeight: 220,
                      objectFit: 'contain',
                      border: '1px solid #f0f0f0',
                      borderRadius: 4,
                      background: '#fafafa',
                    }}
                  />
                ) : (
                  <div
                    style={{
                      height: 96,
                      border: '1px dashed #d9d9d9',
                      borderRadius: 4,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#8c8c8c',
                      fontSize: 12,
                    }}
                  >
                    {thumbError ?? '加载中…'}
                  </div>
                )}
              </div>

              <Space wrap>
                <Text type="secondary">宽度</Text>
                <Radio.Group
                  optionType="button"
                  size="small"
                  buttonStyle="solid"
                  value={block.image_width}
                  disabled={disabled}
                  options={IMAGE_WIDTH_OPTIONS}
                  onChange={(e) => onChange({ image_width: e.target.value as ImageWidthPercent })}
                />
                <Upload
                  beforeUpload={pickImage(true)}
                  fileList={[]}
                  showUploadList={false}
                  accept=".png,.jpg,.jpeg,.webp"
                  disabled={disabled || uploading}
                >
                  <Button size="small" disabled={disabled || uploading}>
                    换图
                  </Button>
                </Upload>
                <Popconfirm
                  title="删除这张材料图？"
                  description="保存后图片与磁盘文件一并清理。"
                  okText="删除"
                  cancelText="取消"
                  okButtonProps={{ danger: true }}
                  onConfirm={onRemove}
                >
                  <Button size="small" danger disabled={disabled || uploading}>
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            </>
          )}
        </Space>
      )}
    </Card>
  )
}
