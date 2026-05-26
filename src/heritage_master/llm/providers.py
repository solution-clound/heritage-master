from __future__ import annotations

"""LLM Provider 实现"""

from typing import Dict, List, Optional

import httpx

from heritage_master.llm.client import LLMClient


class DeepSeekProvider(LLMClient):
    """DeepSeek API (OpenAI 兼容格式)"""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[LLM:DeepSeek] 调用失败: {e}")
            return None

    @property
    def provider_name(self) -> str:
        return "deepseek"

    @property
    def model_name(self) -> str:
        return self._model


class OpenAIProvider(LLMClient):
    """OpenAI API"""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[LLM:OpenAI] 调用失败: {e}")
            return None

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model


class ClaudeProvider(LLMClient):
    """Anthropic Claude API (Messages API)"""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Optional[str]:
        try:
            # Claude Messages API: system 从 messages 中提取
            system_text = ""
            claude_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system_text = msg["content"]
                else:
                    claude_messages.append(msg)

            body = {
                "model": self._model,
                "messages": claude_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if system_text:
                body["system"] = system_text

            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self._base_url}/messages",
                    headers={
                        "x-api-key": self._api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                data = resp.json()
                return data["content"][0]["text"]
        except Exception as e:
            print(f"[LLM:Claude] 调用失败: {e}")
            return None

    @property
    def provider_name(self) -> str:
        return "claude"

    @property
    def model_name(self) -> str:
        return self._model


class QwenProvider(LLMClient):
    """通义千问 API (OpenAI 兼容格式)"""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[LLM:Qwen] 调用失败: {e}")
            return None

    @property
    def provider_name(self) -> str:
        return "qwen"

    @property
    def model_name(self) -> str:
        return self._model
