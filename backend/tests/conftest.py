"""Pytest 共享 fixture。

当前只提供 sys.path 设置，方便 `pytest` 从 backend/ 直接跑。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保 `from app.xxx import ...` 能在 pytest 里直接工作
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
