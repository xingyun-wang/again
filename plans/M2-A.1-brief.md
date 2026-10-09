# M2-A.1 brief — 出题引擎 + 题库 CRUD + S1 前置债 1（题目图片承载）

> **承接决策**：`docs/M2-kickoff-decision.md §7.2 拍板记录（D-M2-2 · 2026-10-08 14:56）`
> **本 brief 范围**：M2 子任务 S1 出题引擎 + 题库 CRUD（含 S1 前置债 1 题目图片承载）
> **承载体**：本文件 `plans/M2-A.1-brief.md`（per `plans/README.md` 命名规则 + 决策书 §6 启动清单）
> **最后更新**：2026-10-08 15:41（commit dc246aa 新建；§7.2 瘦身 12 列 schema/关系/路径/API/存储；D-79 唯一真值源落地）

---

## 一、范围

### 1.1 S1 出题引擎（决策书 §3）

- 4 档（D 基础 / C 进阶 / B 挑战 / A 扩展，字母升序 = 难度升序）
- 反马太（D 档强制 20% 拔高，**只从 C 抽** —— v0.5 §3.5）
- 教师手动覆盖档位（v0.5 §3.2 初始档位）

### 1.2 S1 前置债 1 · 题目图片承载（决策书 §7.2）

- 图像密集学科（地理等）题干必须为图片（地图 / 等值线 / 示意图）预留 image / asset 承载
- 实现走独立 `question_images` 表（1:N，与 `choices` 同构），不混在 `questions` 表内

## 二、产品定义硬约束（v0.5 §3.4）

> 图像密集学科（地理等）的题干必须为图片（地图 / 等值线 / 示意图）预留 image / asset 承载——实现走独立 `question_images` 表（1:N，与 `choices` 同构），不混在 `questions` 表内

## 三、模型设计

### 3.1 `QuestionImage` 表（1:N 与 `Question` 同构）

```python
class QuestionImage(Base):
    """题目图片承载（地理等图像密集学科；v0.5 §3.4 硬约束）。
    与 Question 是 1 对多（与 Choice 同构）；删 Question 时 cascade 自动清空。
    """
    __tablename__ = "question_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    file_ext: Mapped[str] = mapped_column(String(8), nullable=False)  # png/jpg/webp/svg
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    source: Mapped[QuestionImageSource] = mapped_column(SAEnum(...))  # self_built | external_imported
    desensitization_status: Mapped[DesensitizationStatus] = mapped_column(
        SAEnum(...), nullable=False, default="pending"
    )
    desensitized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    uploaded_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True,
    )
    oss_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)  # M3 预留
    oss_uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)  # M3 预留

    question: Mapped[Question] = relationship("Question", back_populates="images")

# Question 端加：
images: Mapped[list[QuestionImage]] = relationship(
    "QuestionImage", back_populates="question",
    cascade="all, delete-orphan", lazy="selectin",
    order_by="QuestionImage.order_index",
)
```

### 3.2 12 列字段摘要

| 字段 | 类型 | 含义 |
|---|---|---|
| `id` | PK | 自增 |
| `question_id` | FK | → `questions.id` (CASCADE) |
| `order_index` | Integer | 排序（与 `Choice.order_index` 同款） |
| `file_ext` | String(8) | png/jpg/webp/svg |
| `storage_path` | String(512) | 本地相对路径 |
| `source` | enum | `self_built` / `external_imported` |
| `desensitization_status` | enum | `pending` / `done` / `skipped` |
| `desensitized_at` | DateTime? | 脱敏完成时刻（M3 实际用） |
| `uploaded_at` | DateTime | 上传时刻 |
| `uploaded_by_user_id` | FK | → `users.id` (RESTRICT) |
| `oss_object_key` | String? | **M3 预留**；S1/M2 阶段 NULL |
| `oss_uploaded_at` | DateTime? | **M3 预留**；S1/M2 阶段 NULL |

### 3.3 1:N vs ARRAY 优势真值（决策已落；本段仅记录判据）

| 维度 | ARRAY(String) | 1:N QuestionImage |
|---|---|---|
| SQLite 测试栈 | ❌ 失败（无原生类型） | ✅ 标准 String/Integer/DateTime |
| 排序 | ❌ | ✅ `order_index` |
| 单图删除 | ❌ UPDATE 全列 | ✅ DELETE WHERE id |
| 脱敏标记 | ❌ | ✅ `desensitized_at` + status |
| 来源追溯 | ❌ | ✅ `source` enum per-row |
| OSS 状态 | ❌ | ✅ `oss_object_key` + `oss_uploaded_at` per-row |
| 上传者追溯 | ❌ | ✅ `uploaded_by_user_id`（§1.4 用户题库个人资产） |

## 四、路径设计

### 4.1 模板

```
${UPLOAD_ROOT}/{chapter_id}/{question_id}/{image_id}.{ext}
```

### 4.2 默认值（既有配置真值）

- **UPLOAD_ROOT 环境变量**：未设置时 = `DEFAULT_UPLOADS_DIR = "/app/data/uploads"`（`backend/app/services/textbook_upload.py:58` 已落）
- 容器内 = `/app/data/uploads/{chapter_id}/{question_id}/{image_id}.{ext}`
- 本机测试 = `./data/uploads/{chapter_id}/...`（按 `textbook_upload.py:57` compose 挂载 `./data/uploads:/app/data/uploads`）

### 4.3 三级目录原因

- 1 chapter × ~50 questions × N images = 单目录不爆
- `image_id` = QuestionImage.id (PK) 稳定，reorder / delete 不触发重命名

### 4.4 历史失实（D-43-X 留痕）

旧 `{chapter_uuid}/{question_uuid}_{n}.{ext}` = **D-43-X**（uuid 列不存在；`academic.py:720-790` Question 列定义无）；改用真 FK 列 `chapter_id` + `question_id` + `image_id`（PK）

## 五、API 设计

### 5.1 接口

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/questions/{id}/images` | 上传图片（multipart + checksum） |
| `GET` | `/questions/{id}/images/{image_id}` | 获取图片（鉴权 = owner_user_id） |
| `DELETE` | `/questions/{id}/images/{image_id}` | 删除图片 |

### 5.2 鉴权

- 上传 / 删除 = 必须 `owner_user_id = current_user.id`
- 获取 = 同上

### 5.3 约束

- 单题最多 N 张图（按性能 / 存储决定；默认 50）
- 单图最大 size = 5MB（与 nginx `client_max_body_size` 同步）
- 支持 MIME：`image/png` / `image/jpeg` / `image/webp` / `image/svg+xml`

## 六、存储设计

### 6.1 本地（UPLOAD_ROOT-based）

- 路径：`${UPLOAD_ROOT}/{chapter_id}/{question_id}/{image_id}.{ext}`
- 容器内默认：`/app/data/uploads/...`
- Compose 挂载：`./data/uploads:/app/data/uploads`
- 环境变量覆盖：`UPLOAD_ROOT=/custom/path`

### 6.2 云端 OSS —— **M3 范围**

- 决策书 §7.2 修订（v0.5 §10.2 行 509「§6.5 本地存储+云端备份（脱敏）」列在 M3）
- **S1/M2 阶段**：仅预留字段 `oss_object_key + oss_uploaded_at`，**不实际触发上传**
- **M3 实现**：阿里云 OSS bucket `thp-images-{env}` + 脱敏后上传

### 6.3 脱敏 —— **M3 范围**

- 决策书 §7.2 修订：脱敏逻辑 = M3 工作
- **S1/M2 阶段**：`desensitization_status` 字段默认 `pending`，无实际脱敏处理
- **M3 实现**：上传前脱敏（题目图片通常不含 PII；v0.5 §6.5）

## 七、测试判据

### 7.1 SQLite 兼容

- `QuestionImage` 表结构与 SQLite 兼容（无 ARRAY）
- 测试 fixture：每题 3 张图（png/jpg/webp 各 1）= 验证 create / read / update / delete

### 7.2 pytest 桩

- `tests/models/test_question_image.py`：
  - 7.2.1 创建 + 查询
  - 7.2.2 排序（order_index）
  - 7.2.3 删除（cascade）
  - 7.2.4 字段约束（NOT NULL / FK）

### 7.3 引用完整性判据（S1-0 必修；防 FK 解析不到）

- **C1**：pool 每行 `chapter_ref` ∈ `demo.chapters[].ref`（FK 解析可达）
- **C2**：pool 每行每个 `knowledge_points[*]` ∈ `demo.knowledge_points[].ref`
- **C3**：`grep -c 'CP-DEMO' backend/tests/fixtures/questions_pool.jsonl` = 0（typo 清零）
- **C4**：`backend/tests/test_question_pool_fixture.py` 引用完整性断言已替换（line 41 升级为集合成员测试）
- **fixture 改造**：`conftest.py question_pool_fixtures` 增 `demo_chapter_refs` + `demo_kp_refs` 两个集合键
- **数据规模**（真值 @2026-10-09 10:00 +0800）：demo = 22 章 / 44 KP；pool = 200 行 / 20 unique 章节 / 40 unique KP；pool ⊆ demo
- **B1 备注**：demo 22 章 / 44 KP 名称是**数学占位**（如「一次不等式」挂在「函数入门」下）⇒ **仅作 loader 引用完整性测试用**，不可作"章节拓扑/分布"样本。S0-5 人工精录时换真实章节名 + 拓扑。

### 7.4 测量点核对（避免 commit message 错位）

- **本笔测量点（@3727ba0）**：builder 镜像 `sha256:a2681646...` + dirty 树（**不含** `backend/tests/test_academic_api.py` 6 修法）。
- 任何人照 `git checkout 3727ba0` 跑 **拿不到 233 passed**（缺 6 test 修法 + dirty 不在 commit 里）。
- **下一笔 commit** 落 6 test 修法后才真值。
- 法源：commit message 报"233 passed" + conftest 提"6 test 补救" ⇒ 引用了 dirty 树 ⇒ 违反 D-74 §1（环境/commit/run 三项标注）；本节为落字补救。

### 7.5 容器 pytest 用独立测试库（防 A3 清 dev 库）

- **危险**：`conftest` teardown `drop_all`（:115）+ `test_academic_models.py:646` 也 `drop_all`+`stamp base`；容器 `DATABASE_URL` 指向 **dev 库 `tiered_homework`**。
- **禁止**：`docker exec thp-backend pytest ...`（会 drop dev 库，毁数据）。
- **安全**：`docker build` 内的 builder stage pytest 走 **SQLite in-memory**，**不碰** dev 库。
- **CI 安全**：CI 用独立库 `tiered_homework_test`（ci.yml:53），**与 dev 库隔离**。
- **本地 dev box 想跑 PG 路径**：必须临时 `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/tiered_homework_test` + 跑 `alembic upgrade head` + 跑完即清（测试库性质）。

## 八、工作量估

- Backend：~250 行（model 80 行 + API 100 行 + 测试 70 行）
- Model migration：~50 行（Alembic）
- 前端上传组件：~30 行

## 九、引用

- **决策书**：`docs/M2-kickoff-decision.md §7.2 拍板记录（D-M2-2 · 2026-10-08 14:56）`
- **memory**：`memory/2026-10-08.md §十三 · D-M2-2 拍板`
- **产品定义 v0.5**：`docs/产品定义-v0.5.md §3.4`（图像密集学科 image / asset 承载）
- **既有 UPLOAD_ROOT**：`backend/app/services/textbook_upload.py:58` + `backend/app/api/v1/routers/academic.py:103`