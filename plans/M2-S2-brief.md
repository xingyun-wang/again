# M2-S2 brief — 档位管理（v0.5 §3.2 · 范围修订）

> **承接决策**：v0.5 §3.2 + 决策书 §6 启动清单 ⑤ + 2026-10-11 角色边界（D-82 待落字）+ 2026-10-11 范围修订（c 选项，K/M/N 算法延后 M3）
> **本 brief 范围**：S2 = Q2 mapping 函数 + Q3 三端点 + 手动覆盖 service（Student 表加 2 字段 audit）
> **不在范围**：Q1 K/M/N 算法（延后 M3，配 per-student 评分结构 + OMR 接入）
> **最后更新**：2026-10-11 11:55（载曜定稿；审查员 星轨 2026-10-11 核源三定论）
> **承载体**：本文件 `plans/M2-S2-brief.md`

---

## 一、范围

### 1.1 必交付

- Q2 mapping 函数（`tier_to_difficulty`）+ 同构断言测试
- Q3 三端点（GET /students / GET /students/{id} / PATCH /students/{id}）
- 手动覆盖 service（teacher 改 `Student.current_tier` + audit 字段）
- 1 个 migration：`0009_student_tier_audit_fields.py`（Student 表加 2 字段）

### 1.2 不在范围（延后 M3）

- ❌ Q1 K/M/N 算法（per-student 评分结构未建模；M3 才有可能）
- ❌ Assignment ↔ Student/class 绑定（消费侧归 M3）
- ❌ 反马太（S1-A 已实现）

---

## 二、产品定义硬约束（v0.5 §3.2）

```
差异化作业（功能 1）
- 4 档位：D 基础 / C 进阶 / B 挑战 / A 扩展（字母升序 = 难度升序）
- 动态调整：K=5 / M=4（升档）+ N=3（降档）→ M3 实现
- 反马太：D 档强制 20% 拔高（S1-A 已实现）
```

---

## 三、既有模型真值（核源 2026-10-11）

### 3.1 `Student` 模型（`academic.py:220-262`）

```python
class Student(Base):
    """学生。归属一个 Class，有一个 current_tier（v0.5 §3.2）。"""
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    grade_level: Mapped[GradeLevel] = mapped_column(SAEnum(GradeLevel, ...), nullable=False)
    current_tier: Mapped[Tier] = mapped_column(SAEnum(Tier, name="tier_enum", ...), nullable=False)
    created_at / updated_at / class_ / knowledge_points

    # S2 加 2 字段（migration 0009）：
    # tier_changed_by_user_id: Mapped[int | None] = mapped_column(
    #     ForeignKey("users.id", ondelete="RESTRICT"), nullable=True,
    # )
    # tier_changed_at: Mapped[datetime | None] = mapped_column(
    #     DateTime(timezone=True), nullable=True,
    # )
```

### 3.2 `Assignment` 模型（`assignment.py:51-86`）— **S2 不动**

字段：id / owner_user_id / chapter_id / tier / total_count / d_count / c_count / b_count / a_count / seed / created_at / updated_at
关系：items / chapter / owner

⚠️ **粒度说明**（星轨核源）：

- 1 Assignment = 主档（`tier` 字段）+ 反马太 20% 从高一档抽
- 4 个 count 字段（d/c/b/a_count）+ 1 个 tier 字段 — **不是**"一份作业含 4 档"
- Assignment **无 class/student 绑定** — 消费侧归 M3

### 3.3 Q5 真值（`assignment.py:41` + `schemas/assignments.py:26`）

```python
# assignment.py:41 docstring 原文
"""tier: 作业目标档位(D/C/B/A);本笔初始档位 = 老师手动设(v0.5 §3.2);"""

# schemas/assignments.py:26
class AssignmentCreate(BaseModel):
    chapter_id: int
    tier: TierLiteral  # = Literal["D","C","B","A"]
    total_count: int
    seed: int | None
```

⇒ **Q5 = (a) per-tier pool**：`Assignment.tier` = 这份作业的目标档位。

### 3.4 两 enum 同值空间（核源真值）

| enum | 位置 | 含义 | 用途 |
|---|---|---|---|
| `Tier` | `academic.py:63` | 学情层 | `Student.current_tier` |
| `QuestionDifficulty` | `academic.py:656` | 题目难度 | `Question.difficulty` + `Assignment.tier` |

⚠️ 两 enum 独立定义 + 同值空间（D/C/B/A）。**Q2 mapping 函数** = 显式保证（同源真值见 §五）。

---

## 四、API 设计（Q3）

| 方法 | 路径 | 用途 |
|---|---|---|
| `GET` | `/api/v1/students` | 老师本班学生列表 |
| `GET` | `/api/v1/students/{id}` | 单学生详情 |
| `PATCH` | `/api/v1/students/{id}` | 改 `current_tier` |

### 4.1 鉴权

- 复用 `_enforce_owner_or_404`（`academic.py:152-167`）
- 链路：`Student → Class.subject → Subject.owner_user_id`
- **重构**：把 `_enforce_owner_or_404` 从 `academic.py` 模块内私有函数 → `backend/app/api/deps.py` 让 `students.py` 能 import

### 4.2 反向用例（防"恒真"测试）

- 改他人班学生 → 404（防越权）
- 改 current_tier 越界值（非 D/C/B/A）→ 422（Pydantic enum check）

---

## 五、tier_to_difficulty 映射（Q2）

### 5.1 函数（落点：`academic.py` 末尾，紧贴 Tier + QuestionDifficulty 定义）

```python
def tier_to_difficulty(t: Tier) -> QuestionDifficulty:
    """Tier → QuestionDifficulty 显式映射（同值空间恒等映射）。

    同值空间恒等不等于"用 type 强制" —— Pydantic / mypy 都不强制
    Tier == QuestionDifficulty。这是单一来源契约，避免两 enum 漂移。
    """
    return QuestionDifficulty(t.value)
```

### 5.2 同构断言测试

```python
def test_tier_difficulty_value_space_isomorphic():
    """Tier 与 QuestionDifficulty 值空间必须同构（顺序 + 元素 + 唯一）。"""
    tier_values = [e.value for e in Tier]
    qd_values = [e.value for e in QuestionDifficulty]
    assert tier_values == qd_values  # 顺序同
    assert len(set(tier_values)) == len(tier_values)  # 唯一性
```

---

## 六、Migration 0009（S2 唯一 schema 变化）

### 6.1 文件路径

`backend/alembic/versions/0009_student_tier_audit_fields.py`

### 6.2 改动

```python
def upgrade():
    op.add_column(
        "students",
        sa.Column(
            "tier_changed_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.add_column(
        "students",
        sa.Column("tier_changed_at", sa.DateTime(timezone=True), nullable=True),
    )

def downgrade():
    op.drop_column("students", "tier_changed_at")
    op.drop_column("students", "tier_changed_by_user_id")
```

### 6.3 反向回退

- 字段 nullable = True ⇒ 现有 Student 行默认 NULL
- 不破坏 S1-A 任何测试（新增字段不影响 SELECT/INSERT 现有路径）
- 不需要数据回填（NULL = 历史未追踪）

---

## 七、Manual Override Service

### 7.1 service 函数（落点：`backend/app/services/student_tier.py`）

```python
def override_student_tier(
    session: Session,
    current_user_id: int,
    student_id: int,
    new_tier: Tier,
) -> dict:
    """手动覆盖学生档位 + 写 audit 字段。

    Raises:
        HTTPException 404: 学生不存在 / 跨用户隔离
        HTTPException 422: new_tier 不在 D/C/B/A
    """
    student = session.get(Student, student_id)
    if student is None:
        raise HTTPException(404, "Student not found")

    # 链式校验：Student → Class → Subject → owner_user_id
    _enforce_owner_or_404(student.class_.subject, current_user_id)

    old_tier = student.current_tier
    student.current_tier = new_tier
    student.tier_changed_by_user_id = current_user_id
    student.tier_changed_at = datetime.now(timezone.utc)
    session.commit()
    return {"old": old_tier, "new": new_tier, "student_id": student_id}
```

---

## 八、测试判据

### 8.1 tier_to_difficulty

- `test_tier_to_difficulty_identity`：每个 Tier 值都能映射
- `test_tier_difficulty_value_space_isomorphic`：值空间同构

### 8.2 endpoints

- `test_list_own_class_students`：GET 200 + 列表非空
- `test_list_students_cross_teacher_404`：GET 他人班 → 404（反向）
- `test_get_student_detail`：GET 200
- `test_patch_student_tier_success`：PATCH 200 + DB 字段更新
- `test_patch_student_tier_cross_teacher_404`：PATCH 他人班学生 → 404（反向）
- `test_patch_student_tier_invalid_value_422`：PATCH body 非 D/C/B/A → 422（反向）
- `test_patch_student_tier_audit_fields_written`：PATCH 后 audit 字段非 NULL

### 8.3 migration

- `test_migration_0009_upgrade`：跑 upgrade → 字段存在
- `test_migration_0009_downgrade`：跑 downgrade → 字段消失

### 8.4 service

- `test_override_student_tier_happy_path`：DB 字段更新 + audit 写入
- `test_override_student_tier_cross_teacher`：他人班 → 404
- `test_override_student_tier_invalid_tier`：非 D/C/B/A → 422

---

## 九、开工核对项（D-43-X 派生；不立 D-83）

> 本节 = D-43-X "结论性陈述必须自我验证" 在 schema 改动场景的**应用清单**。**不立 D-83**（项目已有元规则通胀教训；同原则已被 D-43-X 覆盖）。

- ☐ 改任何 schema 前：先核**模型粒度**（template / per-instance / per-class）
- ☐ 加字段前：想"这字段语义对应该加在哪张表？"（per-(assignment, student) 不是 field）
- ☐ 改 enum 关系前：想"两 enum 真值同构吗？显式 mapping 函数落地了吗？"
- ☐ 跨 commit 返工前：评估"返工"是不是"结构性返工"
- ☐ 推荐 schema 改动前：grep `mapped_column|ForeignKey|Mapped[` — 不止 grep 字面字段名

---

## 十、工作量估

| 模块 | 行数 |
|---|---|
| model 加 2 字段（Student） | ~10 |
| migration 0009 | ~30 |
| service（manual override） | ~80 |
| API endpoints（3 个 + deps 重构） | ~200 |
| tests（§8.1 + §8.2 + §8.3 + §8.4） | ~150 |
| **合计** | **~470 行** |

---

## 十一、引用

- v0.5 §3.2（差异化作业 / K/M/N / 反马太）
- 决策书 `docs/M2-kickoff-decision.md §6` 启动清单 ⑤（S2 = 档位管理）
- 既有真值：`academic.py:63/152-167/220-262/656` + `assignment.py:41/51-86` + `schemas/assignments.py:26`
- 星轨 review 2026-10-11（Q5 / 审计 / D-83 三项定论）
- D-43-X 协作纪律（"结论性陈述必须自我验证"）
- 2026-10-11 角色边界拍板（待今晚落字 D-82）

---

## 十二、git 操作计划（B 路径）

1. **git add plans/M2-S2-brief.md**
2. **commit**：`docs(M2/S2): 档位管理 brief 定稿（Q5/审计/D-83 三定论）[origin-push]`
3. **ledger_check**：跑 `bash scripts/ledger_check.sh`，10/10 PASS（必须绿才能 push）
4. **push origin**：`git push origin master`
5. **报告**：双 remote SHA + ledger PASS + push 状态

> ⚠️ B 路径跳过 backup.sh（zaiyao-memory 同步）+ memory + STATE 更新 — 按用户授权明确范围。若需补，今晚再收工 8 步全套。

---

> **【brief 元数据 · plans/M2-S2-brief.md】**
>
> **修订范围**：1 项 brief 定稿
> 1. **S2 范围最终 = (c) 修订**：Q2 mapping + Q3 三端点 + manual override service + migration 0009
> 2. **不在范围**：Q1 K/M/N 算法（延后 M3）/ Assignment ↔ Student 绑定（消费侧归 M3）
> 3. **D-83 不立**：D-43-X 已覆盖同原则；降级为 §九开工核对项
>
> **法源依据**：v0.5 §3.2 + 决策书 §6 启动清单 ⑤ + 星轨 review 2026-10-11 + D-43-X 协作纪律 + 2026-10-11 角色边界拍板
>
> **审查员回执**：
> - Q5 → (a) per-tier pool：核源 `assignment.py:41` + `schemas/assignments.py:26`
> - 审计 → A 加 2 字段：migration 0009（**S2 仍有 1 schema 变化**，修正载曜"无 schema 变化"陈述）
> - D-83 → 不立，降级为 brief §九开工核对项
>
> **真值核源**（@HEAD c10c332；取数时刻 2026-10-11 11:55 +0800）：
> - plans/ 已存在 + 命名规则 = `<milestone>-<task>-brief.md`（按 README）
> - alembic 现行 0001-0008；next = 0009（无编号冲突）
> - 双 remote 同步 ecc12cc；本地 ahead 1（c10c332 chore 未推）
> - D-43-X 握手 6-line 已验（toplevel/HEAD/branch/status/remote/ahead）
>
> **来源**：v0.5 §3.2 摘要 `产品定义-v0.5-summary.md:44` + 星轨 review 文件 + D-43-X 协作纪律