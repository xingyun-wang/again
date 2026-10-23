/**
 * 材料块 - 表格编辑器（1c-2 commit 1）。
 *
 * 职责：**table_json ↔ 编辑器状态**的双向转换 + 行列增删。
 * 后端只把 table_json 当 dict 存（dict[str, Any]），结构语义由前端定死：
 *   { header: boolean, rows: string[][] }
 *   - header=true ⇒ 首行是表头（渲染成 <thead>）
 *   - rows 是二维字符串数组（每个 cell 一段纯文本）
 *
 * 上限：**7 行 × 4 列**（brief 定稿）。到上限时「+行 / +列」按钮 disabled
 * （不是「点了没反应」——后端不校验这个上限，是前端自己的产品规格）。
 *
 * 为什么不用 antd <Table>：Table 的 dataSource/columns 模型对「二维纯文本矩阵」
 * 太重，还要维护 columns 派生状态；纯 <table> + antd Input 更直白，
 * 也少一份「列定义与 rows 不同步」的状态坑。
 */
import type { CSSProperties } from 'react'
import { Button, Checkbox, Input, Space, Tooltip, Typography } from 'antd'
import { MinusOutlined, PlusOutlined } from '@ant-design/icons'
import type { TableJson } from '../api/questionTypes'

const { Text } = Typography

/** 表格上限（brief：7 行 × 4 列） */
export const MAX_TABLE_ROWS = 7
export const MAX_TABLE_COLS = 4

/** 新建表格块的默认形状：2 行 × 3 列，首行表头 */
export function defaultTableJson(): TableJson {
  return {
    header: true,
    rows: [
      ['', '', ''],
      ['', '', ''],
    ],
  }
}

/**
 * 后端 table_json → 编辑器值。
 *
 * ⚠️ 后端是 `dict[str, Any]` ⇒ 任何形状都可能被存进来（手改库 / 旧版本前端 /
 *    别的客户端写的）⇒ 这里**全量防御**：不是数组就当空表，不是字符串就当空串。
 *    前端崩在这里 = 抽屉打不开 = 用户连编辑都做不了，代价太大。
 */
export function parseTableJson(raw: Record<string, unknown> | null | undefined): TableJson {
  const header = raw?.header === true
  const rowsRaw = Array.isArray(raw?.rows) ? (raw.rows as unknown[]) : []
  const rows = rowsRaw.map((r) =>
    Array.isArray(r) ? r.map((c) => (typeof c === 'string' ? c : String(c ?? ''))) : [],
  )
  if (rows.length === 0) return defaultTableJson()
  // 列数对齐：以最宽行为准，短行补空串（否则渲染时列会错位）
  const cols = rows.reduce((m, r) => Math.max(m, r.length), 0)
  if (cols === 0) return defaultTableJson()
  return {
    header,
    rows: rows.map((r) => (r.length < cols ? [...r, ...Array<string>(cols - r.length).fill('')] : r)),
  }
}

export interface TableBlockEditorProps {
  value: TableJson
  onChange: (next: TableJson) => void
  disabled?: boolean
}

export default function TableBlockEditor({ value, onChange, disabled = false }: TableBlockEditorProps) {
  const rows = value.rows
  const colCount = rows.reduce((m, r) => Math.max(m, r.length), 0)

  const setCell = (r: number, c: number, cell: string) => {
    onChange({
      ...value,
      rows: rows.map((row, ri) =>
        ri === r ? row.map((x, ci) => (ci === c ? cell : x)) : row,
      ),
    })
  }

  const addRow = () => {
    if (rows.length >= MAX_TABLE_ROWS) return
    onChange({
      ...value,
      rows: [...rows, Array<string>(Math.max(colCount, 1)).fill('')],
    })
  }

  const removeRow = () => {
    // 至少留 1 行（最后一行是表头时也留着，空表没法编辑）
    if (rows.length <= 1) return
    onChange({ ...value, rows: rows.slice(0, rows.length - 1) })
  }

  const addCol = () => {
    if (colCount >= MAX_TABLE_COLS) return
    onChange({ ...value, rows: rows.map((r) => [...r, '']) })
  }

  const removeCol = () => {
    if (colCount <= 1) return
    onChange({ ...value, rows: rows.map((r) => r.slice(0, r.length - 1)) })
  }

  const cellStyle: CSSProperties = { padding: 2 }

  return (
    <Space direction="vertical" size="small" style={{ width: '100%' }}>
      <Space wrap>
        <Checkbox
          checked={value.header}
          disabled={disabled}
          onChange={(e) => onChange({ ...value, header: e.target.checked })}
        >
          首行为表头
        </Checkbox>
        <Tooltip title={`最多 ${MAX_TABLE_ROWS} 行`}>
          <Button
            size="small"
            icon={<PlusOutlined />}
            disabled={disabled || rows.length >= MAX_TABLE_ROWS}
            onClick={addRow}
          >
            +行
          </Button>
        </Tooltip>
        <Button
          size="small"
          icon={<MinusOutlined />}
          disabled={disabled || rows.length <= 1}
          onClick={removeRow}
        >
          -行
        </Button>
        <Tooltip title={`最多 ${MAX_TABLE_COLS} 列`}>
          <Button
            size="small"
            icon={<PlusOutlined />}
            disabled={disabled || colCount >= MAX_TABLE_COLS}
            onClick={addCol}
          >
            +列
          </Button>
        </Tooltip>
        <Button
          size="small"
          icon={<MinusOutlined />}
          disabled={disabled || colCount <= 1}
          onClick={removeCol}
        >
          -列
        </Button>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {rows.length} 行 × {colCount} 列（上限 {MAX_TABLE_ROWS}×{MAX_TABLE_COLS}）
        </Text>
      </Space>

      <div style={{ overflowX: 'auto' }}>
        <table
          style={{
            borderCollapse: 'collapse',
            minWidth: '100%',
            tableLayout: 'fixed',
          }}
        >
          {value.header && rows.length > 0 && (
            <thead>
              <tr>
                {rows[0].map((cell, c) => (
                  <th
                    key={`h-${c}`}
                    style={{
                      border: '1px solid #d9d9d9',
                      background: '#fafafa',
                      padding: 2,
                      textAlign: 'center',
                      fontWeight: 600,
                    }}
                  >
                    <Input
                      size="small"
                      value={cell}
                      disabled={disabled}
                      placeholder={`表头 ${c + 1}`}
                      onChange={(e) => setCell(0, c, e.target.value)}
                    />
                  </th>
                ))}
              </tr>
            </thead>
          )}
          <tbody>
            {rows.map((row, r) => {
              // header=true 时第 0 行已在 thead 渲染过 ⇒ body 从第 1 行开始
              if (value.header && r === 0) return null
              return (
                <tr key={`r-${r}`}>
                  {row.map((cell, c) => (
                    <td key={`c-${r}-${c}`} style={{ ...cellStyle, border: '1px solid #d9d9d9' }}>
                      <Input
                        size="small"
                        value={cell}
                        disabled={disabled}
                        placeholder={`第${r + 1}行 第${c + 1}列`}
                        onChange={(e) => setCell(r, c, e.target.value)}
                      />
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Space>
  )
}
