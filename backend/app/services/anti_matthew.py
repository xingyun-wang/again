"""反马太算法（D-W3-03 MVP，CHARTER §4 硬约束）。

规则：
- 仅 D 档触发
- 每 5 道 D 题插 1 道 C 题（20%）
- D 档题数 < 5：不插，warning 但不报错
- C 档题库不足：能插几道插几道，剩余位置保留 D 档原题 + warning
- 替换位置：随机（D-W3-03 实时计算，不固定位置）

V0.1 设计决策：
- 接受 Question ORM 对象（不是 id），由调用方决定怎么写入 HomeworkQuestion
- 返回 (题, 当前档位) 元组列表，方便调用方直接写入 HomeworkQuestion.level
"""
import random
from typing import List, Tuple


def anti_matthew_substitute(
    d_questions: list,
    c_questions: list,
) -> Tuple[List[Tuple], List[str]]:
    """反马太核心算法。

    Args:
        d_questions: D 档题（已抽好 N 道），Question ORM 列表
        c_questions: C 档题池，Question ORM 列表

    Returns:
        (results, warnings):
        - results: [(Question, current_level), ...] 列表，长度 = len(d_questions)
          current_level 是替换后的档位（C 或 D）
        - warnings: 反马太相关警告（D 档不足 5 / C 档题库不足 等）

    算法：
    1. N = len(d_questions)
    2. N < 5: warning，不替换，返回 [(q, "D") for q in d_questions]
    3. need = N // 5
    4. len(c_questions) < need: warning, need = len(c_questions)
    5. need == 0: 直接返回原题
    6. 随机选 need 个位置 + 随机选 need 道 C 题
    7. 替换：result[i] = (c_q, "C") if i in positions else (q, "D")
    """
    warnings: List[str] = []
    n = len(d_questions)

    # Case 1: D 档题数 < 5
    if n < 5:
        warnings.append(
            f"D 档题数 {n} < 5，反马太不生效（每 5 道才有 1 道 C 档，少于 5 不插）"
        )
        return ([(q, "D") for q in d_questions], warnings)

    need = n // 5

    # Case 2: C 档题库不足
    if len(c_questions) < need:
        warnings.append(
            f"C 档题库不足 {need} 道，实际 {len(c_questions)} 道；"
            f"能插几道插几道，剩余位置保留 D 档原题"
        )
        need = len(c_questions)

    if need == 0:
        return ([(q, "D") for q in d_questions], warnings)

    # Case 3: 正常替换
    positions = set(random.sample(range(n), need))
    selected_c = random.sample(c_questions, need)
    selected_c_iter = iter(selected_c)

    result = []
    for i, q in enumerate(d_questions):
        if i in positions:
            c_q = next(selected_c_iter)
            result.append((c_q, "C"))
        else:
            result.append((q, "D"))

    return (result, warnings)
