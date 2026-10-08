"""TWAIN 扫描桥 schemas（M2 S0-4：D-M2-4 拍板 + 3 补丁 A/B/C）。

职责：
- 定义 ``POST /scan/omr`` 的请求/响应契约
- 契约稳定 = M3 替换 mock 为真 HTTP 桥实现时零返工（决策书 §7.3 补丁 A）

设计要点：
- 桥的职责 = 「图像 → 填涂位」；不包含出题侧概念（档位 / 题目索引等）
- 答案列表长度 = ``question_count``；前 5 个位置填涂，其余 None
- 答案字母 A/B/C/D（OMR 答题卡 4 选项）
- mock deterministic：seed = chapter_id
- metadata 显式标注 ``bridge_layer``（mock vs 未来真 HTTP 桥），方便 M3 替换时验证
- 响应只回 scan_id，不暴露内部目录结构（file_path 泄漏风险）
- 不收集 PII（CHARTER §6 + v0.5 §6.5）
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# 答案字母：OMR 答题卡每题 4 个填涂位（A/B/C/D）
ANSWER_CHOICES: tuple[str, ...] = ("A", "B", "C", "D")

# 答案卡的最小题数（必须 >= 5 才能放下 5 个填涂位）
MIN_QUESTION_COUNT = 5

# 最大题数（防 OOM / 恶意请求）
MAX_QUESTION_COUNT = 200

# mock 阶段填涂位置（前 5 题；0-based 索引；与真 OMR 答题卡视觉一致）
MOCK_DETECTED_POSITIONS: tuple[int, ...] = (0, 1, 2, 3, 4)

# HTTP 桥抽象层标识（mock 阶段 = "mock"；M3 替换为 "http_bridge_windows_host"）
BRIDGE_LAYER_MOCK = "http_bridge_mock"


class ScanOMRResponse(BaseModel):
    """``POST /scan/omr`` 响应契约。

    Attributes:
        answers: 长度 = ``question_count``；前 5 个位置为 A/B/C/D 之一，
            其余为 None（未填涂/未识别）。索引 = 0-based 题目序号。
        metadata: 扫描元数据。显式含 bridge_layer 字段标识抽象层（mock vs 真实现）；
            scan_id 用于客户端后续取文件（不暴露内部目录 file_path）。
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "answers": ["A", "B", "C", "D", "A", None, None, None, None, None],
                "metadata": {
                    "bridge_layer": "http_bridge_mock",
                    "chapter_id": "ch-001",
                    "question_count": 10,
                    "detected_count": 5,
                    "scan_id": "abc123def456789012345678901234ab",
                    "file_size": 12345,
                    "content_type": "application/pdf",
                    "magic_kind": "pdf",
                    "timestamp": "2026-10-08T15:30:00+08:00",
                },
            }
        }
    )

    answers: list[str | None] = Field(
        ...,
        description=(
            "OMR 识别答案列表；长度 = question_count。前 5 个位置为 A/B/C/D 之一，"
            "其余为 null（未填涂/未识别）。"
        ),
    )
    metadata: dict[str, object] = Field(
        ...,
        description="扫描元数据；显式含 bridge_layer 字段标识抽象层（mock vs 真实现）。",
    )
