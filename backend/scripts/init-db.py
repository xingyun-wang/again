#!/usr/bin/env python3
"""init-db.py — W1-T2: create_all 落库。

跑法（裸跑，不需 activate venv）：
    cd backend && python3 scripts/init-db.py

依赖通过探测 .venv-backend 自动加载（兼容真 venv + pip --target 两种 layout）。
幂等：表已存在则 no-op（create_all 行为）。
首次跑前请先执行：bash backend/scripts/setup-backend.sh
"""
from __future__ import annotations

import sys
from pathlib import Path

# 把 backend/ 加进 sys.path，让 app.xxx 能 import
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# 把 .venv-backend 的 site-packages 加进 sys.path（兼容两种 layout）
VENV_DIR = BACKEND_DIR / ".venv-backend"
for _candidate in (
    VENV_DIR / "lib" / "python3.8" / "site-packages",  # 真 venv layout
    VENV_DIR,                                          # pip --target 散装 layout
):
    if _candidate.is_dir() and (_candidate / "sqlalchemy").exists():
        sys.path.insert(0, str(_candidate))
        break

from app.database import Base, engine  # noqa: E402
from app import models  # noqa: E402,F401  确保所有 model 注册到 Base.metadata


def main() -> None:
    print(f"[init-db] DATABASE_URL 指向 engine: {engine.url}")
    print("[init-db] 创建/校验表：")
    for tbl_name in Base.metadata.tables:
        print(f"  - {tbl_name}")
    Base.metadata.create_all(engine)
    print("[init-db] done.")


if __name__ == "__main__":
    main()