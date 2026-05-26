from __future__ import annotations

"""LLM 工厂 - 根据配置创建 Provider 实例"""

from typing import Optional

from heritage_master.llm.client import LLMClient
from heritage_master.llm.providers import (
    ClaudeProvider,
    DeepSeekProvider,
    OpenAIProvider,
    QwenProvider,
)

# Provider 默认配置
_PROVIDER_DEFAULTS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
    },
    "claude": {
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-sonnet-4-20250514",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
}

_PROVIDER_CLASSES = {
    "deepseek": DeepSeekProvider,
    "openai": OpenAIProvider,
    "claude": ClaudeProvider,
    "qwen": QwenProvider,
}


def create_llm(
    provider: str = "deepseek",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> Optional[LLMClient]:
    """创建 LLM Provider 实例。

    Args:
        provider: Provider 名称 (deepseek/openai/claude/qwen)
        api_key: API Key（为空则返回 None）
        base_url: API 地址（为空则使用默认值）
        model: 模型名称（为空则使用默认值）

    Returns:
        LLMClient 实例，api_key 为空时返回 None
    """
    if not api_key:
        return None

    provider = provider.lower()
    if provider not in _PROVIDER_CLASSES:
        raise ValueError(f"不支持的 LLM Provider: {provider}，可选: {list(_PROVIDER_CLASSES.keys())}")

    defaults = _PROVIDER_DEFAULTS[provider]
    cls = _PROVIDER_CLASSES[provider]

    return cls(
        api_key=api_key,
        base_url=base_url or defaults["base_url"],
        model=model or defaults["model"],
    )


def create_llm_from_settings() -> Optional[LLMClient]:
    """从全局配置创建 LLM 实例。"""
    from heritage_master.config import settings

    return create_llm(
        provider=getattr(settings, "llm_provider", "deepseek"),
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
    )
