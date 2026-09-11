# 差异化作业工作台 — 前端

W4 完成（2026-09-11）：Ant Design 5 + React 19 + Vite + React Router。

## 启动

```bash
# 前置：dev 服务跑后端
bash scripts/start-dev.sh
bash scripts/verify-dev.sh   # 确认 5173 + 8000 都通

# 启动前端（自动跑在 5173）
cd frontend
npm run dev
```

访问 http://localhost:5173

## 路由

| 路径 | 功能 | 后端端点（W3 已完成） |
|---|---|---|
| `/` | Dashboard（占位） | — |
| `/questions` | 题库 CRUD（5 端点） | W3-T2 |
| `/classes` | 班级/学生管理 + 批量导入 + 改密（5 端点） | W1-T4 |
| `/homeworks` | 作业生成（含反马太）+ 审阅 + 发布（5 端点） | W3-T4 + T5 |
| `/settings` | 占位（W4 后） | — |

## 关键设计

- **API 客户端**：`src/api/client.ts` —— 统一 fetch + `ApiError` 类型化错误处理
- **主布局**：`src/layouts/MainLayout.tsx` —— Ant Design Layout + 侧边导航（题库 / 班级 / 作业 / 设置）
- **页面**：4 个主页面 + Dashboard
- **状态管理**：本地 useState（无 Redux/Zustand，MVP 简单）

## 技术栈

按 CHARTER §7：
- React 19 + TypeScript
- Vite 8 + 极速 dev server
- Ant Design 5（中文 Locale zh_CN）
- React Router 6
