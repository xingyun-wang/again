"""业务 API schemas（M1-B B.2：§7.4 AI 声明 + §7.5 教师审阅硬约束）。

设计要点：
- AIAnnotation / TeacherReviewStatus 抽成独立可复用 mixin，方便 endpoint response_model 组合
- Request / Response 拆分：Request 走业务字段校验；Response 走 §7.4/§7.5 标注
- Pydantic v2（pyproject 锁 pydantic>=2.9.0），用 model_config / model_dump
"""

from __future__ import annotations

# 占位：当前仅 academic 业务，后续 M2/M3 加题库 / 答题卡 schemas 时再拆分模块。