"""LLM 抽象层 - 多模型统一接口"""

from heritage_master.llm.client import LLMClient
from heritage_master.llm.factory import create_llm

__all__ = ["LLMClient", "create_llm"]
