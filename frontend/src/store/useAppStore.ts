import { create } from 'zustand'

/**
 * App 顶层 zustand store（决策书 §7.1 补丁 A：M2 骨架期极简版）
 * - 仅一个全局 UI 状态：侧边栏收起
 * - 不接持久化（骨架期不必要）
 * - 后续 S 阶段可按需扩展（主题 / 用户 / 全局 loading 等）
 */
interface AppState {
  sidebarCollapsed: boolean
  setSidebarCollapsed: (v: boolean) => void
}

export const useAppStore = create<AppState>((set) => ({
  sidebarCollapsed: false,
  setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
}))
