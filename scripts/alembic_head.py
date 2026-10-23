#!/usr/bin/env python3
"""从**仓库工作树**解析 alembic revision 图，求唯一 head。

为什么不用 `alembic heads`（审核员 2026-10-23 指出）：
- `alembic heads` 读的是**当前 alembic 运行环境**的 versions 目录。
- 本项目的 backend 容器 `/app/alembic` 是**镜像里烤进去的副本**（docker-compose
  只 bind mount 了 `data/uploads`）⇒ 在容器里跑 `alembic heads` 读的是**容器副本**，
  **不是仓库工作树**。
- ⇒ 仓库加了新迁移但还没重建容器时，门禁**看不见**（读到旧的 head）⇒ 门禁失守。
- ⇒ 本脚本直接读**仓库工作树**的 `backend/alembic/versions/*.py`，自己解析
  `revision` / `down_revision` 建图求 head。

输出（stdout）：
- 恰好 1 个 head  → 打印该 revision id，exit 0
- 0 个 head        → stderr 打印原因，exit 2
- \>1 个 head（分叉）→ stderr 打印全部，exit 3
- 解析失败        → stderr 打印文件与原因，exit 4

用法：
    python3 scripts/alembic_head.py [versions_dir]
    # 默认 backend/alembic/versions（相对仓库根）
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def _parse_one(path: Path) -> tuple[str, list[str]]:
    """从单个迁移文件解析 (revision, down_revisions)。

    用 ast 而不是正则：down_revision 可能是 None / 字符串 / 元组
    （分支合并时会写成元组），literal_eval 能一次处理干净。
    """
    try:
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise ValueError(f"{path.name}: 读取/解析失败: {exc}") from exc

    revision: str | None = None
    down: list[str] = []

    for node in tree.body:
        # 两种写法都要认：
        #   revision = "0001_initial"              → ast.Assign
        #   revision: str = "0002_academic_models" → ast.AnnAssign（本仓库 0002+ 全用这个）
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            value_node = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target.id] if isinstance(node.target, ast.Name) else []
            value_node = node.value
        else:
            continue
        if not targets:
            continue
        name = targets[0]
        if name not in ("revision", "down_revision"):
            continue
        try:
            value = ast.literal_eval(value_node)
        except (ValueError, SyntaxError):
            # 动态表达式（如变量引用）—— 本仓库不出现，视为解析失败更安全
            raise ValueError(f"{path.name}: {name} 不是字面量，无法静态解析")
        if name == "revision":
            if not isinstance(value, str) or not value:
                raise ValueError(f"{path.name}: revision 不是非空字符串")
            revision = value
        else:
            if value is None:
                down = []
            elif isinstance(value, str):
                down = [value]
            elif isinstance(value, (tuple, list)):
                items = list(value)
                if not all(isinstance(x, str) for x in items):
                    raise ValueError(f"{path.name}: down_revision 元组含非字符串")
                down = items
            else:
                raise ValueError(f"{path.name}: down_revision 类型异常: {type(value)}")

    if revision is None:
        raise ValueError(f"{path.name}: 找不到 revision 赋值")
    return revision, down


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        versions_dir = Path(argv[1]).resolve()
    else:
        repo_root = Path(__file__).resolve().parent.parent
        versions_dir = repo_root / "backend" / "alembic" / "versions"

    if not versions_dir.is_dir():
        print(f"versions 目录不存在: {versions_dir}", file=sys.stderr)
        return 4

    files = sorted(p for p in versions_dir.glob("*.py") if p.name != "__init__.py")
    if not files:
        print(f"versions 目录里没有迁移文件: {versions_dir}", file=sys.stderr)
        return 2

    revisions: dict[str, str] = {}  # revision -> 文件名
    all_down: set[str] = set()
    try:
        for f in files:
            rev, down = _parse_one(f)
            if rev in revisions:
                print(
                    f"revision 重复: {rev}（{revisions[rev]} 与 {f.name}）",
                    file=sys.stderr,
                )
                return 4
            revisions[rev] = f.name
            all_down.update(down)
    except ValueError as exc:
        print(f"解析失败: {exc}", file=sys.stderr)
        return 4

    # head = 没有任何人是它的 down_revision 的那些 revision
    heads = sorted(set(revisions) - all_down)

    if len(heads) == 1:
        print(heads[0])
        return 0
    if not heads:
        print(
            f"没有 head（{len(revisions)} 个迁移全被引用 ⇒ 可能有环）: {versions_dir}",
            file=sys.stderr,
        )
        return 2
    print(
        "revision 图分叉，检出 " + str(len(heads)) + " 个 head: "
        + ", ".join(f"{h} ({revisions[h]})" for h in heads),
        file=sys.stderr,
    )
    return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv))
