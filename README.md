# 差异化作业系统（tiered-homework-platform）

> **M1-B B.3 端到端 5 章节验证阶段（2026-09-18）** —— v0.5 §10 M1 范围内的学科知识库 + AI 备课助手 API 端到端就位，含真 PDF 上传 + 真 LLM 5 章节跑通。
> 详见 [`docs/产品定义-v0.5.md`](docs/产品定义-v0.5.md) + [`docs/PROJECT-CHARTER.md`](docs/PROJECT-CHARTER.md)。

## 状态

- **产品定义**：v0.5 §0-§11 全定稿（2026-09-14 收官）
- **工程进度**：**M1-B 实质收官**（B.0/B.1/B.2/B.3 全过，等决策室 commit/push）；M0 准备、M1-A 阶段 1 均已过
- **B.3 收官要点**：
  - `POST /textbooks/upload` 升级为 multipart/form-data + PyMuPDF + pdfplumber 双库 PDF 抽取
  - `backend/scripts/verify_end_to_end_5_chapters.py` 跑通：1 upload + 5 extract + 5 lesson-plan + 5 review = 20 API + 10 真 LLM 调用
  - §7.4 AIAnnotation + §7.5 TeacherReviewStatus OpenAPI schema 可见，8 个端点齐全
  - pytest 146 passed / 8 skipped / ruff + mypy 全过
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

## 镜像源策略

- **国内 build**（家庭 / 公司网络）：Dockerfile 默认用 Aliyun apt + Aliyun PyPI + npmmirror 镜像源（build-time `--index-url` flag 形式，避免污染容器全局 pip 配置）
- **CI / 官方源**（GitHub Actions）：通过 `docker build --build-arg PIP_INDEX_URL=...` 切换，或 Dockerfile 注释里说明 CI 走官方源
- 决策背景：M0 retro 教训——PIP 默认源在国内 ~92kB/s（pymupdf 25.8MB 要 3+ 分钟），Aliyun ~5-10MB/s，build 时间压缩 50-100 倍

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

## 业务 API（M1-B B.2）

业务 API 路由统一挂载在 `/api/v1/academic` 前缀；浏览器 Swagger UI 入口：`http://localhost/docs`。

### 8 个端点（B.2 spec 7 + judgment call 1）

| # | 方法 | 路径 | 用途 | §7.4 / §7.5 |
|---|---|---|---|---|
| 1 | POST | `/api/v1/academic/textbooks/upload` | 上传教材（**B.3 multipart/form-data + PyMuPDF + pdfplumber 双库抽取章节**） | §7.5 pending |
| 2 | GET | `/api/v1/academic/textbooks/{id}/chapters` | 列教材下的章节 | — |
| 3 | POST | `/api/v1/academic/chapters/{id}/extract` | 调 LLM 抽取章节结构化信息（重点 / 难点 / 授课建议） | §7.4 + §7.5 pending |
| 4 | GET | `/api/v1/academic/chapters/{id}` | 章节详情（含 §7.4 AI summary） | §7.4 + §7.5 字段标注 |
| 5 | PATCH | `/api/v1/academic/chapters/{id}/review` | 章节审阅（reviewed / modified + 可改字段） | §7.5 硬约束 |
| 6 | POST | `/api/v1/academic/lesson-plans/generate` | 基于章节 + 学情生成授课建议（chat 真值） | §7.4 + §7.5 pending |
| 7 | GET | `/api/v1/academic/lesson-plans/{id}` | 授课建议详情 | §7.4 + §7.5 字段标注 |
| 8 | PATCH | `/api/v1/academic/lesson-plans/{id}/review` | 授课建议审阅（reviewed / modified + 可改 content） | §7.5 硬约束（**judgment call**） |

> **Judgment call #1**：B.2 spec 端点表只列了 7 个端点，但 §7.5 流程硬约束测试要求 lesson-plan 可 PATCH /review 才能跑端到端流程。本阶段补上第 8 个端点。

### §7.4 AI 生成内容声明（每个 LLM 响应必带字段）

```json
{
  "ai_generated": true,
  "model": "deepseek-chat",
  "generated_at": "2026-09-18T05:02:49.341265Z",
  "requires_teacher_review": true,
  "annotation": "本建议由 AI 生成，需教师审阅"
}
```

> 所有 AI 生成实体（chapter extract / lesson-plan）的 response 都内嵌 `ai: AIAnnotation` 字段。

### §7.5 教师最终审阅（流程节点硬约束）

```json
{
  "review_status": "pending",        // pending / reviewed / modified
  "reviewed_by": null,                 // user_id（B.2 从 X-User-Id header 取）
  "reviewed_at": null,
  "review_notes": null
}
```

> **流程硬约束**：AI 生成的实体（extract / lesson-plan）创建时 `review_status=pending`；必须 PATCH `/review` 标记 `reviewed` 或 `modified` 才能用于下次备课（M1+ 闭环）。
> **不允许**：未先 extract 就 review chapter（→ 409）。

#### §7.5 review_status 流转图

```
                       ┌─────────────────────────────┐
                       │  AI 生成实体创建            │
                       │  (extract / lesson-plan)  │
                       │  review_status = pending  │
                       └──────────────┬──────────────┘
                                      │
                                      ▼
              ┌────────────────────── PATCH /review ──────────────────────┐
              │                                                              │
   status=reviewed                                                  status=modified
              │                                                              │
              ▼                                                              ▼
   review_status = reviewed                                       review_status = modified
   reviewed_by  = user_id                                          reviewed_by   = user_id
   reviewed_at  = now                                              reviewed_at   = now
   review_notes = notes（如提供）                                  review_notes  = notes
   content     = 原 AI 内容                                            content      = 新 content（提供）
                                                                       KP/Difficulty/TeachingSuggestion
                                                                       = 新覆写（如提供）
```

关键点：
- **pending → reviewed**：仅标记；不改 AI 内容
- **pending → modified**：覆写 AI 内容（content / KP / Difficulty / TeachingSuggestion）
- **reviewed → reviewed**（再次提交）：更新 reviewed_at + notes；不改 status
- **不允许**：pending → pending（无意义）；reviewed → pending（回退被禁止；§7.5 硬约束）

### B.3.2 端到端 5 章节真值验证（scripts/verify_end_to_end_5_chapters.py）

`backend/scripts/verify_end_to_end_5_chapters.py` 跑全链路 1 upload + 5 extract + 5 lesson-plan + 5 review = **20 API + 10 真 LLM 调用**（约 80s）：

```bash
# 1. 把真 DEEPSEEK_API_KEY 临时注入 .env（决策室 §7.0 例外条款）
export DEEPSEEK_API_KEY=sk-xxxxxxxx
echo "DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}" > .env
docker compose up -d --force-recreate backend

# 2. 真 PDF 拷到容器内（materials 不在 compose volume 内）
docker cp "materials/textbooks/选择性必修1.pdf" thp-backend:/tmp/选择性必修1.pdf

# 3. 跑端到端
docker exec thp-backend python -m scripts.verify_end_to_end_5_chapters \
  --pdf-path /tmp/选择性必修1.pdf

# 4. 立刻清回 .env 占位符
echo "DEEPSEEK_API_KEY=***" > .env
```

期望输出（节选）：

```
======================================================================
  B.3.2 端到端 5 章节 LLM 真值验证报告
======================================================================
  耗时：79.8s
  教材：id=2 name='B.3.2 端到端验证 - 选择性必修1'
  章节数：5
  授课建议数：5
  错误数：0
----------------------------------------------------------------------
  chapter 6 (id=6): extract ✅ (key_points=5, difficulties=5, suggestions=4) review_id=1
  chapter 7 (id=7): extract ✅ (key_points=5, difficulties=5, suggestions=4) review_id=2
  ...
  lesson-plan 1 (chapter=6 '第一章 地球的运动'): pending → reviewed ✅ (model=deepseek-chat)
  ...
======================================================================
  总结：✅ 全部通过
  API 调用：20 次
  真 LLM 调用：10 次
======================================================================
```

### 简化 Auth（M.2 + M.3 再升级完整 JWT）

- `X-User-Id` header 取 user_id（如 `X-User-Id: 1`）
- 缺失或非正整数 → 401
- 未来：M1+ 接完整 JWT，本阶段简化（subagent 工地的烟测友好）

### 调用示例（curl）

```bash
# 1. 上传教材（B.3 multipart/form-data + 真 PDF）
curl -X POST http://localhost/api/v1/academic/textbooks/upload \
  -H 'X-User-Id: 1' \
  -F "file=@materials/textbooks/选择性必修1.pdf" \
  -F "name=人教版地理选择性必修1" \
  -F "grade_level=senior_high"
# → 201 {"textbook_id": 1, "chapters": [{"id": 1, "chapter_number": 1, "title": "第一章 地球的运动", "page_range_start": 7, "page_range_end": 22, ...}, ...], ...}

# 2. 调 LLM 抽取章节（§7.4 + §7.5 pending）
curl -X POST http://localhost/api/v1/academic/chapters/1/extract \
  -H 'Content-Type: application/json' -H 'X-User-Id: 1' -d '{}'
# → 201 {"ai": {...}, "review": {"review_status": "pending"}, ...}

# 3. 教师审阅（§7.5 流程硬约束）
curl -X PATCH http://localhost/api/v1/academic/chapters/1/review \
  -H 'Content-Type: application/json' -H 'X-User-Id: 5' \
  -d '{"status": "reviewed", "notes": "OK 通过"}'

# 4. 生成授课建议
curl -X POST http://localhost/api/v1/academic/lesson-plans/generate \
  -H 'Content-Type: application/json' -H 'X-User-Id: 1' \
  -d '{"chapter_id": 1, "duration_minutes": 45, "student_count": 50}'
```

## 后续里程碑

详见 `docs/产品定义-v0.5.md §10.2`：
- M1 备课（M1 启动前需读 §2.2 闭环）
- M2 出作业
- M3 上传评分
- M4 学情 + 再备课
- M5-M7 收尾 + 扩展