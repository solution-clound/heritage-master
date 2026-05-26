from __future__ import annotations

"""LLM 抽象基类"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class LLMClient(ABC):
    """LLM 统一接口。所有 Provider 实现此基类。"""

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Optional[str]:
        """调用 LLM 生成回答。

        Args:
            messages: 消息列表，每条含 role 和 content
            temperature: 温度参数
            max_tokens: 最大生成 token 数

        Returns:
            生成的文本，失败返回 None
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider 名称"""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """模型名称"""
        pass
