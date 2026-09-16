"""LLM Provider 抽象层（v0.5 §9.4）。

设计原则：
- LLMProvider 是 ABC，定义 chat() 和 embedding() 两个核心方法
- 工厂函数 get_llm_provider() 根据配置返回具体实现
- M0 锁定 DeepSeekProvider；M1+ 通过修改配置切换 GPT-4o / Claude / 国产模型
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """LLM Provider 抽象接口。

    所有具体 Provider（DeepSeek / OpenAI / Anthropic / 国产模型）必须实现这两个方法。
    chat 接收 OpenAI 风格 messages 列表（[{"role": ..., "content": ...}]），返回字符串。
    embedding 接收文本列表，返回对应维度的向量列表。
    """

    @abstractmethod
    def chat(self, messages: list[dict[str, object]], **kwargs: object) -> str:
        """对话调用。

        Args:
            messages: OpenAI 风格消息列表
            **kwargs: 模型特定参数（temperature / max_tokens / top_p 等）

        Returns:
            模型回复文本
        """

    @abstractmethod
    def embedding(self, texts: list[str]) -> list[list[float]]:
        """文本向量化。

        Args:
            texts: 待嵌入文本列表

        Returns:
            与 texts 等长的向量列表
        """
