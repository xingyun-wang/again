# 差异化作业系统（tiered-homework-platform）

> **M0 骨架阶段（2026-09-16）** —— v0.5 产品定义全定稿后的工程起点。
> 详见 [`docs/产品定义-v0.5.md`](docs/产品定义-v0.5.md) + [`docs/PROJECT-CHARTER.md`](docs/PROJECT-CHARTER.md)。

## 状态

- **产品定义**：v0.5 §0-§11 全定稿（2026-09-14 收官）
- **工程进度**：M0 准备（基础设施骨架）已完成，M1-M7 见 `docs/产品定义-v0.5.md §10.2`
- **技术栈**：PostgreSQL 15 + FastAPI (Python 3.11) + React 18 + TS 5 + Vite 5 + Ant Design 5 + Docker Compose

## 目录结构

```
.
├── backend/                # Python 3.11 + FastAPI
│   ├── app/
│   │   ├── core/          # config + LLM provider (抽象 + DeepSeek 实现 + 工厂)
│   │   ├── api/           # health + v1 (v1 留空，M1 才有)
│   │   ├── pdf/           # PyMuPDF + pdfplumber 双库封装
│   │   ├── db/            # SQLAlchemy base + session
│   │   └── models/        # M1+ 才有真实 ORM
│   ├── tests/             # health + LLM provider + PDF extractor
│   ├── alembic/           # migrations（M0 占位）
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── .env.example
├── frontend/               # React 18 + TS 5 + Vite 5 + AntD 5
│   ├── src/
│   │   ├── pages/         # Home（健康检查）
│   │   ├── api/           # axios client + health 封装
│   │   ├── App.tsx        # Layout + Router
│   │   └── main.tsx       # 入口
│   ├── nginx.conf         # /api → backend:8000
│   ├── Dockerfile
│   └── .env.example
├── docker-compose.yml     # postgres + backend + frontend（nginx serve）一键起
├── .github/workflows/ci.yml
├── docs/                   # 产品定义 / 宪法 / 决策 / 开放问题
└── memory/                 # 决策室 daily logs
```

## 一键启动（验收标准）

```bash
# 1. 起服务
docker compose up -d

# 2. 验证
curl http://localhost/api/health
# 期望返回：{"status":"ok","version":"0.1.0"}

# 浏览器打开 http://localhost
# 首页应显示 "✅ 后端连接成功" + status/version tags
```

### 验收标准全清单

| # | 命令 | 期望 |
|---|---|---|
| 1 | `docker compose up -d` | postgres + backend + frontend 全部 healthy |
| 2 | `cd frontend && npm run dev` | vite 在 5173 起来（可选，仅本地开发） |
| 3 | `curl http://localhost/api/health` | `{"status":"ok","version":"0.1.0"}` |
| 4 | 浏览器首页 | "✅ 后端连接成功" |
| 5 | `docker compose exec backend ruff check .` | exit 0 |
| 6 | `docker compose exec backend mypy app` | exit 0 |
| 7 | `docker compose exec backend pytest` | 全过 |
| 8 | `cd frontend && npm run lint` | exit 0 |
| 9 | `cd frontend && npm run build` | exit 0 |

## 本地开发（不依赖 docker）

### 后端（venv）

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"   # 或直接 pip install -r requirements（如有）
cp .env.example .env      # 改 DEEPSEEK_API_KEY
uvicorn app.main:app --reload --port 8000
```

### 前端（npm）

```bash
cd frontend
npm install
npm run dev    # 5173 端口，已配 /api → localhost:8000
```

## 技术决策摘要

- **PDF 解析**：PyMuPDF + pdfplumber 双库（v0.5 §9.1 已定）
  - PyMuPDF 处理文本/图像/坐标
  - pdfplumber 处理表格
  - 不选 unstructured / markitdown（抽象层重 / 损失结构）
- **LLM 抽象层**：DeepSeek-V3 + Provider 抽象层 + 工厂（v0.5 §9.4 已定）
  - `LLMProvider.ABC.chat() / embedding()`
  - `DeepSeekProvider` 实现
  - `get_llm_provider()` 工厂按配置返回
  - 未来加 GPT-4o / Claude / 国产模型零重构

## 国内镜像源（build-time 优化）

中国网络下默认 pypi.org / npm registry / Debian apt 源速度慢或不可达（pypi.org 实测 ~92kB/s；pymupdf 25.8MB 要 3+ 分钟）。Dockerfile 已硬编码国内镜像源：

- **后端**：`backend/Dockerfile` —— Aliyun apt + Aliyun PyPI（`pip install --index-url https://mirrors.aliyun.com/pypi/simple/`）。清华 PyPI 不稳定（fastapi 0.115+ 拿不到），Aliyun 镜像在家庭网络下稳。Aliyun 镜像 ~5-10MB/s，build 时间压缩 50-100 倍
- **前端**：`frontend/Dockerfile` —— `NPM_CONFIG_REGISTRY=https://registry.npmmirror.com`

**作用域**：仅 build-time 生效。CI（GitHub Actions）走官方源——Dockerfile flag/ENV 在 GitHub Actions runner 上不生效（境外网络默认官方源 OK）。

**M1+ 模板默认带这些镜像源 + 注释**——避免每个 subagent 重新踩坑。

## 后续里程碑

详见 `docs/产品定义-v0.5.md §10.2`：
- M1 备课（M1 启动前需读 §2.2 闭环）
- M2 出作业
- M3 上传评分
- M4 学情 + 再备课
- M5-M7 收尾 + 扩展
