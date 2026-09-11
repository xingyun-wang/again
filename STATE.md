# STATE.md — 差异化作业工作台进度

> **最后更新**：2026-09-11（W1 + W2 + W3 全部 6 个子阶段完成）
> **重启原则**：按"一标签一标签"节奏推进（教训 #35 精神 + 教训 #9）

---

## 0. 重置精神（2026-09-10 王星云拍板）

W3.1.15 批量入库现状不满意 → 工程成果全部清空，从 W1 开始重启。

**重启原则**：
- 按"一标签一标签"节奏推进，**不批量**
- 情绪驱动的"全部重来"先拦，再问状态（教训 #35）
- 教训沉淀保留（精简版），工程代码不留

**硬约束**（来自 PROJECT-CHARTER.md，不变）：
- MVP：高中地理选必 1 全 5 章
- 档位：D 基础 / C 进阶 / B 挑战 / A 扩展（字母升序 = 难度升序）
- 反马太：D 档强制 20% 拔高
- 共建题库愿景（MEMORY §A）

---

## 1. 一句话定位

e卷通是"题库 + 报告工具"，我们是"老师主导的教学闭环操作系统"。详见 [PROJECT-CHARTER.md](docs/PROJECT-CHARTER.md)。

---

## 2. 进度（2026-09-11 W1/W2/W3-T1）

| 阶段 | 状态 | 备注 |
|---|---|---|
| W1 基础架构 + 班级/学生/档位 + 批量导入 + 改密 | ✅ 完成 | T3 / T1 / T2 / T2b / T4 全完成 |
| W2 (CHARTER §8 标的) | ✅ **提前完成** | W2 范围已被 W1 覆盖（基础架构 + 班级/学生 + 批量导入 + 改密） |
| W3 老师自建题库 CRUD + 作业生成引擎 | 🔄 进行中 | T1 完成；T2-T6 待 |
| W4-W12 MVP 联调 | ⏳ 待重启 | |

**W1 详细**：

| W | 子阶段 | 状态 | commit |
|---|---|---|---|
| W1-T3 | 目录结构 + dev 脚本（保活） | ✅ | acdbc56 |
| W1-T1 | 前后端 hello world 互 ping | ✅ | acdbc56 |
| W1-T2 | 数据库 schema 初版（teacher/class/student/level） | ✅ | acdbc56 |
| W1-T2b | venv 持久化修复（T2 验收假阳性） | ✅ | acdbc56 |
| W1-T4 | 批量导入学生 + 改密接口 | ✅ | 2b0bb3a |

**W3 详细**：

| W | 子阶段 | 状态 | commit |
|---|---|---|---|
| W3-T1 | 题目数据模型（Question + Chapter + QuestionType） | ✅ | 09b048b |
| W3-T2 | 题目 CRUD API（6 端点 + 3 坑对策） | ✅ | 68025b8 |
| W3-T3 | 作业数据模型（Homework + HomeworkQuestion + HomeworkStatus） | ✅ | d14d3ab |
| W3-T4 | 作业生成引擎（核心：反马太，D 档 20% 拔高） | ✅ | 9cebeaa |
| W3-T5 | 老师审阅 + 手动调整档位 + 发布 | ✅ | 9cebeaa |
| W3-T6 | 端到端集成测试（12 Step 全 PASS） | ✅ | 本次 |

---

## 5. 决策记录（重大决策按时间倒序）

### D-2026-09-11-01 主会话 = 决策室，工作 = 外派

**来源**：王星云 2026-09-11 07:58
**原文**：「这个地方是我们的决策室，工作要去外派工作干，避免上下文太冗长。」

**分工定义**：

| 边界 | 范围 |
|---|---|
| **主会话（决策室）** | 拍板、定规则、判断优先级、读 STATE/CHARTER/memory、回星云消息 |
| **外派（subagent）** | 工程实现、配置、文档草稿、一次性研究、批量内容生成、跑得动的验证 |

**触发条件**：
- 派：写代码、跑命令、批量产出、做调研
- 不派：定方向、问问题、改规则、做判断

**与 CHARTER §9 的关系**：
- CHARTER §9.1 旧："session 启动载曜先读 STATE + 3 篇 memory + CHARTER（≤3 分钟）"
- 本决策补充："读完之后，**只做判断**；体力活派 subagent（`context:"isolated"`），任务描述里附 STATE/CHARTER 路径"

**subagent 沟通约定**：
- `context:"isolated"` 干净启动
- 任务描述自包含（附文件路径 + 期望产出格式）
- subagent 完成后给"摘要 + 证据 + 路径"，不灌长输出回主会话
- 不确定项 subagent 回主会话拍板，不让它自己拍

---

### D-2026-09-11-04 主会话破例写代码（W3-T4）

**来源**：王星云 2026-09-11 10:52
**原文**：「A」（选项 A：主会话自己写）

**背景**：W3-T4 是 W3 核心（反马太算法 + 作业生成）。subagent 报「5/5 全过」，独立 verify 发现：
- `backend/app/api/homeworks.py` 未创建
- `backend/app/services/anti_matthew.py` 未创建
- `backend/scripts/test-homeworks-generate.sh` 未创建
- `main.py` 没 include_router
- API 端点总数 10（应是 11）
- uvicorn log 5 次 POST 都是 404

**这是 W3 第二次 subagent 假阳性**（第一次是 T2 端点不足）。**连续两次后决策不再赌 subagent**。

**破例范围**：仅 W3-T4 一个文件集（anti_matthew.py / homeworks.py / schemas 追加 / main.py 追加 / test-homeworks-generate.sh）。

**今后默认**：subagent 连续 2 次假阳性 → 主会话直接接手，不重复派；保留事后复盘（为什么 prompt 不够死、是否有新机制该加）。

---

### D-W3-01～03 W3 题型 / 作业生成 / 反马太 三连拍板（A+A+A）

**来源**：王星云 2026-09-11 10:11
**原文**：「A+A+A」（3 个决策点都选 A）

**三个决策**：

| 编号 | 决策 | 选项 | 选定 | 理由 |
|---|---|---|---|---|
| **D-W3-01** | 题型范围 | A 只客观 / B + 填空 / C +主观 | **A. 只客观题** | MVP 简化；主观题 W5+ 再加（CHARTER §5 OMR 主路径） |
| **D-W3-02** | 作业生成策略 | A 老师指定每档 / B 引擎自动分配 | **A. 老师指定每档题数** | MVP 老师主导（CHARTER §2 "老师主导"） |
| **D-W3-03** | 反马太实现位置 | A 实时计算 / B 预生成缓存 | **A. 实时计算** | MVP 灵活，方便 T5 老师手动调整档位时重算 |

**题型枚举范围**（D-W3-01）：

| QuestionType | 说明 |
|---|---|
| `single_choice` | 单选 |
| `multiple_choice` | 多选 |
| `true_false` | 判断（options=["对","错"]） |

**作业生成接口形状**（D-W3-02 + D-W3-03 预约定）：

```
POST /api/classes/{class_id}/homeworks/generate
body: {
  "title": "...",
  "questions_per_level": { "D": 10, "C": 8, "B": 5, "A": 3 },
  "chapters": ["ch1_...", "ch2_..."],   // 可选，默认全 5 章
  "anti_matthew": true                   // D 档强制 20% 拔高（默认 true）
}
response: HomeworkOut（含 questions 列表，D 档里 20% 是 C 档题）
```

**反马太算法核心**（D-W3-03 预约定）：

```python
# 作业生成时，D 档的题 20% 必须从 C 档题库挑（拔高）
# 逻辑：拿 D 档题池中的题，其中 20% 的位置用 C 档题替换
# 老师手动调整档位时（POST /homeworks/{id}/review），重算反马太
```

---

### D-2026-09-11-02 技术决策权 = 载曜，执行前出计划 + 星云确认

**来源**：王星云 2026-09-11 08:01
**原文**：「技术我不懂，载曜决定。所有决定落实到执行端之前都需要载曜制定计划，然后分布执行，我确认后再继续，避免跑偏。」

**三层工作流**（与 D-2026-09-11-01 互锁）：

| 阶段 | 责任方 | 动作 | 输出 |
|---|---|---|---|
| **1. 计划** | 载曜（主会话） | 定方向、选技术、拆任务、估工作量、点风险 | 主会话可见的计划文本 |
| **2. 确认** | 王星云 | 看计划，过 / 打回 / 改方向 | 显式确认信号 |
| **3. 执行** | 载曜派 subagent | 按计划实现，跑验证，回报告 | 摘要 + 证据 + 路径 |

**强制约束**：
- **不“心里想完直接干”**：任何执行前必须有主会话可见的计划文本
- **技术拍板 = 载曜**：不再问“用什么技术”“怎么实现”，那是浪费上下文
- **只问“方向对不对 / 优先级对不对 / 范围对不对”**：不问“代码怎么写”

**避免跑偏三检**：
1. 计划是否与 STARTER §0 重启原则一致（不批量、不越 W 阶段）
2. 计划是否破坏 CHARTER 硬约束（档位、反马太、不做项）
3. 计划是否超出当前标签范围（scope creep，教训 #9）

---

## 7. 已知 bug

### B-2026-09-11-W1T1-CWD start-dev.sh CWD 分裂

**状态**：✅ T4 修复（commit 2b0bb3a）
**现象**：T1 start-dev.sh 后端段未 `(cd backend && ...)`，API 写入项目根 `dev.db`，seed 写入 `backend/dev.db`，分裂成两个数据库。
**修复**：T4 subagent 主动暴露 + 加子壳包。
**教训**：启动脚本必须明确 `cd backend` 上下文，不能凭相对路径跨目录。

### B-2026-09-11-W1T2b-DEP python-multipart 未写 requirements.txt

**状态**：⏳ W2 顺手补
**现象**：FastAPI `UploadFile` 需要 `python-multipart`，W1-T4 装在 venv 里但 `requirements.txt` 没写。下次 setup-backend.sh 重建 venv 会撞。
**教训**：装依赖后必查 requirements.txt，不依赖 venv 持久化。

---

## 8. TODO（按 W 阶段排序）

### W2 (CHARTER §8)
- B-DEP 修复 `requirements.txt` 补 python-multipart（5min）

### W3-T2 题目 CRUD API
- 包含 3 个 T1 报告的工程坑：
  1. `answer` 字段多选反序列化（Pydantic 出参时 `json.loads`）
  2. `Question.teacher` relationship 补上（~10 行）
  3. `teacher_id` 不允许 body 传入，从 session/当前老师注入（CHARTER §6 合规边界）

---

## 8. TODO（按 W 阶段排序）

（重启后空）

---

## 11. 教训索引（精简保留，详见 zaiyao-memory/MEMORY.md §B/§C/§D）

### §B 主会话专属 8 条
- **#24** 默认不复述上下文
- **#32** reset 前先沉淀
- **#34** 工作流变革是行为约束（hard check）
- **#35** 情绪驱动"全部重来"先拦
- **#36** 工作疲劳信号识别
- **#9** scope creep 是 token 浪费最大头
- **#19** debug 黑洞 3 次换思路
- **#21** sed 禁用

### §C 工程哲学 3 条
- **#11** 凌晨不开 milestone
- **#13** 用用户语言
- **#22** 工作量估算 ×1.5-2

### §D W1 重启后沉淀 3 条（新增）

- **#37** **verifier 不信被验对象**：T2 subagent 报"5 条全过"，主会话独立 verify 时 dev 服务已挂、venv 已失效。**独立 verify 永远跑一遍**，不信 subagent 报告。
- **#38** **环境基线写进 prompt，不要让 subagent 自己探**：T1 subagent 卡在 PyPI 下载 ×15min（PyPI 官方 8s 卡边界），重派写明"必换 aliyun"后 30 秒装完。**网络/工具路径/版本 在 prompt 顶部写死**。
- **#39** **诚实报告 > 静默掩盖**：T4 subagent 主动暴露 T1 遗留 CWD bug。**奖励诚实，惩罚隐藏**。

---

## 完整历史

- 本地备份：`~/tiered-homework-platform.bak.2026-09-10/`（674MB）
- zaiyao-memory 远端：`archive/2026-09-10-pre-reset` 分支（创建后）