import { ProTable } from '@ant-design/pro-components'
import type { ProTableProps } from '@ant-design/pro-components'
import type { ProColumns } from './types'

/**
 * ProTable 模板（决策书 §7.1 补丁 A）
 * - 极简：columns + dataSource + 分页（pageSize=10）
 * - 不接 API（dataSource 由父组件传）
 * - search / toolBarRender 关闭 = 骨架期不需要 query / 工具栏
 * - ProTable 数据接入在 S1+（差异化引擎 / 题库等模块各自接入）
 */
export interface ProTableTemplateProps<T = Record<string, unknown>> {
  columns: ProColumns<T>[]
  dataSource: T[]
  loading?: boolean
  onChange?: ProTableProps<T, unknown>['onChange']
}

function ProTableTemplate<T extends Record<string, unknown> = Record<string, unknown>>(
  props: ProTableTemplateProps<T>,
) {
  const { columns, dataSource, loading = false, onChange } = props
  return (
    <ProTable<T>
      columns={columns}
      dataSource={dataSource}
      loading={loading}
      onChange={onChange}
      rowKey="id"
      pagination={{ pageSize: 10 }}
      search={false}
      toolBarRender={false}
    />
  )
}

export default ProTableTemplate
