"""TWAIN 扫描桥 schemas（M2 S0-4：D-M2-4 拍板 + 3 补丁 A/B/C）。

职责：
- 定义 ``POST /scan/omr`` 的请求/响应契约
- 契约稳定 = M3 替换 mock 为真 HTTP 桥实现时零返工（决策书 §7.3 补丁 A）

设计要点：
- 4 档位难度（D 基础 / C 进阶 / B 挑战 / A 扩展；v0.5 §3.2）
- 答案列表长度 = ``question_count``，其中 5 个位置填涂，其余为 None（未填涂/未识别）
- metadata 显式标注 ``bridge_layer``（mock vs 未来真 HTTP 桥），方便 M3 替换时验证
- 不收集 PII（CHARTER §6 + v0.5 §6.5）：响应只回传 chapter_id / 档位 / 文件路径，无学生姓名学号
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# v0.5 §3.2：4 档位（D 基础 / C 进阶 / B 挑战 / A 扩展；字母升序 = 难度升序）
# A 扩展最难 → D 基础最易
TierLevel = Literal["D", "C", "B", "A"]

# 答案字母：OMR 答题卡每题 4 个填涂位（A/B/C/D）
ANSWER_CHOICES: tuple[str, ...] = ("A", "B", "C", "D")

# 每档固定 5 个"已填涂"位置（与"每档生成 5 个不同位置的答案"对齐）
# 位置 = 0-indexed 题目序号；mock 永远填这 5 个槽
TIER_DETECTED_POSITIONS: dict[str, tuple[int, ...]] = {
    "D": (0, 1, 2, 3, 4),        # 基础：前 5 题
    "C": (0, 2, 4, 6, 8),        # 进阶：每隔 1 题
    "B": (1, 3, 5, 7, 9),        # 挑战：错位 5 题
    "A": (0, 3, 6, 9, 12),       # 扩展：跨 3 题间隔
}

# 答案卡的最小题数（必须 >= 5 才能放下 5 个填涂位）
MIN_QUESTION_COUNT = 5

# 最大题数（防 OOM / 恶意请求）
MAX_QUESTION_COUNT = 200

# HTTP 桥抽象层标识（mock 阶段 = "mock"；M3 替换为 "http_bridge_windows_host"）
BRIDGE_LAYER_MOCK = "http_bridge_mock"


class ScanOMRResponse(BaseModel):
    """``POST /scan/omr`` 响应契约。

    Attributes:
        answers: 长度 = ``question_count``；5 个位置填涂答案（A/B/C/D），
            其余为 None（未填涂/未识别）。索引 = 0-based 题目序号。
        metadata: 扫描元数据（bridge_layer / level / chapter_id / question_count /
            detected_count / file_path / file_size / content_type / timestamp）。
            显式标注 bridge_layer = "http_bridge_mock"：M3 替换为真实现时
            只需改这一个字段，测试可断言契约稳定。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "answers": ["A", "B", "C", "D", "A", None, None, None, None, None],
                "metadata": {
                    "bridge_layer": "http_bridge_mock",
                    "level": "D",
                    "chapter_id": "ch-001",
                    "question_count": 10,
                    "detected_count": 5,
                    "file_path": "/app/data/uploads/scans/abc123.pdf",
                    "file_size": 12345,
                    "content_type": "application/pdf",
                    "timestamp": "2026-10-08T15:30:00+08:00",
                },
            }
        }
    )

    answers: list[str | None] = Field(
        ...,
        description=(
            "OMR 识别答案列表；长度 = question_count。5 个位置为 A/B/C/D 之一，"
            "其余为 null（未填涂/未识别）。"
        ),
    )
    metadata: dict[str, object] = Field(
        ...,
        description="扫描元数据；显式含 bridge_layer 字段标识抽象层（mock vs 真实现）。",
    )
