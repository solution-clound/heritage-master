"""
Agent 状态定义

使用 TypedDict 定义 LangGraph 的状态结构。
所有节点共享此状态，通过 Annotated[list, add_messages] 实现消息追加。
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages


class AgentState(TypedDict):
    """非遗探索助手的图状态。

    Attributes:
        messages: 对话消息列表，使用 add_messages reducer 自动追加
        user_id: 当前用户 ID
        session_id: 当前会话 ID
        panels: 结构化面板数据（项目列表、场馆列表、路线等）
        tool_results_cache: 工具调用结果缓存，key=f"{tool_name}:{args_json}"
        system_prompt: 注入的系统提示词（含个性化上下文）
        final_reply: 最终回复文本（从 messages 中提取）
        metadata: 意图识别、质量校验等元数据
        token_budget: 剩余 token 预算（每次 LLM 调用后递减）
    """

    messages: Annotated[list[AnyMessage], add_messages]
    user_id: str
    session_id: str
    panels: Annotated[list[dict[str, Any]], lambda x, y: x + y]  # 面板数据累加
    tool_results_cache: dict[str, Any]  # 跨轮工具结果缓存
    system_prompt: str
    final_reply: str
    metadata: dict[str, Any]  # 意图识别、质量校验等元数据
    token_budget: int  # 剩余 token 预算（-1=无限制）
