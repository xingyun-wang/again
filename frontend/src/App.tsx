/**
 * App — W4-T1 路由入口
 *
 * - /          → Dashboard
 * - /questions → 题库（W4-T2）
 * - /classes   → 班级 / 学生（W4-T2）
 * - /homeworks → 作业（W4-T3/T4）
 * - /settings  → 设置
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider, App as AntApp } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { MainLayout } from './layouts/MainLayout'
import { Dashboard } from './pages/Dashboard'
import { QuestionList } from './pages/questions/QuestionList'
import { ClassList } from './pages/classes/ClassList'
import { HomeworkList } from './pages/homeworks/HomeworkList'
import { SettingsPlaceholder } from './pages/settings/Placeholder'

function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <AntApp>
        <BrowserRouter>
          <Routes>
            <Route element={<MainLayout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/questions" element={<QuestionList />} />
              <Route path="/classes" element={<ClassList />} />
              <Route path="/homeworks" element={<HomeworkList />} />
              <Route path="/settings" element={<SettingsPlaceholder />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  )
}

export default App
