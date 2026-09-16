# 差异化作业系统 — 前端 (M0 骨架)

React 18 + TypeScript 5 + Vite 5 + Ant Design 5。

## 启动

### 方式一：docker-compose（推荐，含 nginx + backend）
```bash
cd ..
docker compose up -d
# 访问 http://localhost
```

### 方式二：本地 dev（前后端分离）
```bash
# 前置：后端在 8000 跑（docker compose up backend，或本地 uvicorn）
npm install
npm run dev
# 访问 http://localhost:5173
# Vite 已配 /api → http://localhost:8000 的 proxy
```

## 验收

```bash
npm run lint       # ESLint
npm run build      # tsc + vite build
npm run preview    # 预览 build 产物（端口 4173）
```

## 目录

```
src/
  main.tsx         # 入口（React + AntD ConfigProvider + Router）
  App.tsx          # Layout + 路由表
  pages/
    Home.tsx       # 首页：调 /api/health 展示连接状态
  api/
    client.ts      # axios 实例
    health.ts      # /api/health 封装
```
