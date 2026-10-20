/**
 * ErrorBoundary —— 通用单页错误边界（P1 前端健壮性，星轨派工单 2026-10-20 13:40）。
 *
 * 为什么需要：今天出现过「前端新 + 后端旧」镜像不同步，后端少返一个可选展示字段
 * （knowledge_point_names），题库页 render 时 `names.length` 抛
 * TypeError: Cannot read properties of undefined (reading 'length')，
 * React 整棵树不渲染 —— 请求 200 但 #root innerHTML 长度 = 0，用户只看到白屏，
 * 无从判断是「没数据」还是「崩了」。
 *
 * 设计约束（派工单 §二/§五）：
 * - 做成通用组件，后续任何页面都能包，不写死在某个页面里。
 * - 只包「页面级」子树：放在 Layout 之内、路由层逐页包裹 ⇒ 单页崩了侧边导航仍可用、
 *   其他页仍能进（这是派工单验收判据 2 的硬要求）。
 * - 开发环境显示错误详情，生产环境只给一句人话。
 * - 提供「重试」按钮；并支持 resetKey（路由切换后自动清错，不粘住错误页）。
 *
 * 注：React 的 error boundary 必须是 class 组件（没有 hook 版 API）。
 */
import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Button, Result, Space } from 'antd'

interface Props {
  children: ReactNode
  /**
   * 变化时清空已捕获的错误。
   * 路由层传 pathname ⇒ 崩溃后切到别的页再回来，页面会重新正常渲染，
   * 而不必用户手动点「重试」。
   */
  resetKey?: string
}

interface State {
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // 生产也留一条 console：控制台是现场排查的第一手线索
    console.error('[ErrorBoundary] 捕获到渲染错误', error, info.componentStack)
  }

  componentDidUpdate(prevProps: Props): void {
    if (this.state.error !== null && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ error: null })
    }
  }

  private readonly handleRetry = (): void => {
    this.setState({ error: null })
  }

  render(): ReactNode {
    const { error } = this.state
    const { children } = this.props

    if (error === null) {
      return children
    }

    const isDev = import.meta.env.DEV

    return (
      <Result
        status="error"
        title="页面出错了"
        subTitle={
          isDev
            ? String(error.message || error)
            : '该页渲染失败，已停在这一页；侧边导航和其他页面仍可正常使用。'
        }
        extra={
          <Space direction="vertical" align="start" size="middle">
            <Button type="primary" onClick={this.handleRetry}>
              重试
            </Button>
            {isDev && (
              <pre
                style={{
                  maxHeight: 260,
                  overflow: 'auto',
                  whiteSpace: 'pre-wrap',
                  textAlign: 'left',
                  fontSize: 12,
                  color: '#8c8c8c',
                }}
              >
                {error.stack ?? String(error)}
              </pre>
            )}
          </Space>
        }
      />
    )
  }
}
