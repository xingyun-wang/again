#!/usr/bin/env python
"""DeepSeek 真值验证脚本（M1-B B.1.2 验收用）。

用法：
1. 把真 key 注入 docker backend 环境变量（docker-compose.yml 加 DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY}，
   host 上 export DEEPSEEK_API_KEY=sk-xxx，然后 docker compose up -d backend 重启）
   或者直接在容器内 export 后跑
2. 容器内执行：python -m scripts.verify_deepseek_api
3. 输出：响应时间 / HTTP 状态码 / 返回字符数 / 用量

判定：
- status == 200 && response_chars > 0 && 不是 placeholder 错 → 真值成功
- status == 401 / 403 / placeholder → key 未注入或错
- 网络异常 → 网络问题（非 key 问题）

注意：
- 不在 stdout 打印 api_key，避免泄露到日志/抓屏
- 不修改任何状态文件，单纯 GET 一次 API
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.llm.deepseek import DeepSeekProvider  # noqa: E402


def _mask(key: str) -> str:
    """遮蔽 key 前 7 位 + 后 4 位，便于人工核对又不暴露完整值。"""
    if len(key) <= 12:
        return "***"
    return f"{key[:7]}...{key[-4:]}"


def verify_chat(api_key: str) -> tuple[int, int, int]:
    """跑一次最小 chat。返回 (status_code, response_chars, elapsed_ms)。"""
    p = DeepSeekProvider(api_key=api_key)
    messages = [{"role": "user", "content": "回复 'pong' 一个词即可"}]
    t0 = time.monotonic()
    try:
        resp = p.chat(messages, max_tokens=8)
    except RuntimeError as e:
        # RuntimeError 含 HTTP 状态码；提取数字部分
        msg = str(e)
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        # 尝试从 "...HTTP 401: ..." 提取状态码
        import re
        m = re.search(r"HTTP (\d+)", msg)
        status = int(m.group(1)) if m else 0
        print(f"  chat status={status} elapsed={elapsed_ms}ms error={msg[:120]}")
        return (status, 0, elapsed_ms)
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    print(f"  chat status=200 elapsed={elapsed_ms}ms response_chars={len(resp)} content={resp!r}")
    return (200, len(resp), elapsed_ms)


def verify_embedding(api_key: str) -> tuple[int, int, int]:
    """跑一次最小 embedding。"""
    p = DeepSeekProvider(api_key=api_key)
    texts = ["hello world"]
    t0 = time.monotonic()
    try:
        vecs = p.embedding(texts)
    except RuntimeError as e:
        msg = str(e)
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        import re
        m = re.search(r"HTTP (\d+)", msg)
        status = int(m.group(1)) if m else 0
        print(f"  embedding status={status} elapsed={elapsed_ms}ms error={msg[:120]}")
        return (status, 0, elapsed_ms)
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    dim = len(vecs[0]) if vecs else 0
    print(f"  embedding status=200 elapsed={elapsed_ms}ms response_items={len(vecs)} dim={dim}")
    return (200, len(vecs), elapsed_ms)


def main() -> int:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    print(f"DEEPSEEK_API_KEY env present={bool(api_key)} masked={_mask(api_key) if api_key else 'NONE'}")
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY 未设置（容器内 export 或 docker-compose 注入）")
        return 2
    if api_key in ("sk-replace-me", "***", "dummy", ""):
        print("ERROR: DEEPSEEK_API_KEY 是 placeholder，不是真 key")
        return 2

    print("=== chat ===")
    chat_status, chat_chars, chat_ms = verify_chat(api_key)
    print("=== embedding ===")
    emb_status, emb_items, emb_ms = verify_embedding(api_key)

    print()
    print("=== summary ===")
    print(f"chat:     status={chat_status} chars={chat_chars} elapsed={chat_ms}ms")
    print(f"embedding: status={emb_status} items={emb_items} elapsed={emb_ms}ms")

    if chat_status == 200 and chat_chars > 0 and emb_status == 200 and emb_items > 0:
        print("VERDICT: ✅ 真值调用成功（chat + embedding 都返回 200 + 非空内容）")
        return 0
    print("VERDICT: ❌ 真值调用失败（看上方 status 与 error 信息）")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())