"""CSV 批量导入 — W1-T4 服务层。

职责：
- 解析 CSV 字节流（编码双探测：UTF-8(含 BOM) → GBK）
- 把行 dict 落库到指定班级
- 行级 try/except：单行失败 → failed 列表，不中断批量
- 学号重复 → 依赖 DB UniqueConstraint + savepoint 捕获

关键设计：
- 用 db.begin_nested()（SAVEPOINT）包住每行 insert。
  IntegrityError 触发 savepoint 回滚，外层事务不受影响，
  后续行不会被"株连"。这是 SQLAlchemy 2.0 处理"部分批量"的标准做法。
- 失败原因分两类：
    1. 客户端错：name / student_no 缺失 → failed（不写库）
    2. DB 约束：UniqueConstraint 冲突 → failed（已 rollback）

风险（已记录在 STATE.md 风险表 #1-3）：
- 编码异常：双探测都失败 → ValueError 上抛，HTTP 500
- 大量行（50+）：SAVEPOINT 性能可接受（CHARTER §3 单班 50 人上限）
"""
from __future__ import annotations

import csv
import io
from typing import Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Student


def parse_csv_text(raw: bytes) -> Tuple[list[dict], str]:
    """解析 CSV 字节流 → (行 dict 列表, 实际编码)。

    编码双探测：
        1. utf-8-sig：自动剥 UTF-8 BOM（Excel 导出常见）
        2. gbk：Windows 中文环境常见 fallback
    """
    last_err: Exception | None = None
    for enc in ("utf-8-sig", "gbk"):
        try:
            text = raw.decode(enc)
            reader = csv.DictReader(io.StringIO(text))
            rows: list[dict] = []
            for r in reader:
                # 标准化：键 strip；空值统一成 ""；忽略空键
                rows.append(
                    {
                        (k or "").strip(): (v.strip() if isinstance(v, str) else (v or ""))
                        for k, v in r.items()
                        if k
                    }
                )
            return rows, enc
        except (UnicodeDecodeError, csv.Error) as e:
            last_err = e
            continue
    raise ValueError(f"CSV 编码/格式无法解析（utf-8-sig / gbk 均失败）：{last_err}")


def bulk_import_students(db: Session, class_id: int, raw: bytes) -> dict:
    """把 CSV 字节流批量写入 class_id 班级。

    返回 dict：
        {
            "inserted": int,
            "failed": [{"row": int, "name": str, "reason": str}, ...]
        }
    """
    rows, encoding = parse_csv_text(raw)

    inserted = 0
    failed: list[dict] = []

    # 行号从 2 起：CSV 行 1 = 表头，数据行从 2 开始（方便老师对 CSV 行号定位）
    for idx, row in enumerate(rows, start=2):
        name = row.get("name", "")
        student_no = row.get("student_no", "")
        # initial_password 可选；缺省 = student_no（学号做初始密码方便记忆）
        initial_password = row.get("initial_password", "") or student_no

        # ----- 客户端校验（不写库） -----
        if not name:
            failed.append({"row": idx, "name": "", "reason": "name 为空"})
            continue
        if not student_no:
            failed.append({"row": idx, "name": name, "reason": "student_no 为空"})
            continue

        # ----- DB 写入（SAVEPOINT 行级隔离） -----
        try:
            with db.begin_nested():
                student = Student(
                    name=name,
                    student_no=student_no,
                    class_id=class_id,
                    # TODO(W3+): 改用 passlib + bcrypt hash 存储
                    initial_password=initial_password,
                )
                db.add(student)
            # SAVEPOINT 成功 release → 计入 inserted
            inserted += 1
        except IntegrityError as e:
            # 学号重复 / FK 约束等 → savepoint 已回滚，外层事务安全
            orig = getattr(e, "orig", None)
            reason = f"约束冲突：{orig}" if orig else "约束冲突（学号重复？）"
            failed.append({"row": idx, "name": name, "reason": reason})
        except Exception as e:  # noqa: BLE001 — 行级兜底，绝不中断批量
            # 未知异常 → 也记 failed，不抛
            failed.append({"row": idx, "name": name, "reason": f"未知错误：{e}"})

    # 整批提交（成功行此时都在事务里）
    db.commit()
    return {"inserted": inserted, "failed": failed}