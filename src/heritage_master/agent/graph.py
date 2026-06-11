"""
LangGraph StateGraph — 非遗探索助手主图

构建并编译 Agent 工作流图：

  ┌─────────────────────────────────────────────────┐
  │                                                 │
  │  START ──→ [agent] ──→ route_after_agent ──→ [tools] ──→──┘
  │                  │            │                              │
  │                  │         reply                             │
  │                  │            │                              │
  │                  │       [memory]                            │
  │                  │            │                              │
  │                  └──────────→END                            │
  │                                                 │
  └─────────────────────────────────────────────────┘

关键设计：
- agent_node: LLM 决策节点，绑定工具，返回 AIMessage（可能含 tool_calls）
- route_after_agent: 条件路由，检查最后一条消息是否有 tool_calls
- tool_node: 执行工具，将结果作为 ToolMessage 追加
- memory_node: 提取记忆、保存会话、提取 final_reply
- 支持最大循环次数限制（防止无限循环）
- 支持流式输出 (astream / astream_events)
- 支持 checkpointer 会话持久化（thread_id = session_id）
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver

from heritage_master.agent.nodes import (
    agent_node, memory_node, tool_node, classify_and_plan, validate_node
)
from heritage_master.agent.state import AgentState

logger = logging.getLogger("heritage.agent")

# 最大工具调用轮数（只统计自由模式，不包括计划步骤）
MAX_AGENT_LOOPS = 8


# ─── 条件路由 ───────────────────────────────────────────────


def route_after_agent(state: AgentState) -> str:
    """条件路由 — 根据 LLM 回复决定下一步。

    检查最后一条 AIMessage：
    - 有 tool_calls → "tools"（执行工具）
    - 无 tool_calls → "validate"（结果校验）

    循环次数只统计自由模式的 AIMessage（有 content 的），
    计划步骤（content 为空的 tool_call）不计入。
    """
    messages = state["messages"]

    # 只统计自由模式的 AIMessage（content 非空的，排除计划步骤的空 content）
    # 计划步骤: AIMessage(content="", tool_calls=[...])  → 不计入
    # 自由模式: AIMessage(content="...", tool_calls=[...]) 或 AIMessage(content="...")  → 计入
    free_ai_count = sum(
        1 for m in messages
        if isinstance(m, AIMessage) and m.content
    )
    if free_ai_count > MAX_AGENT_LOOPS:
        logger.warning("[route] 达到最大自由模式次数 %d，强制结束", MAX_AGENT_LOOPS)
        return "memory"

    # 检查最后一条消息
    last_msg = messages[-1] if messages else None
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        logger.info("[route] LLM 请求调用 %d 个工具", len(last_msg.tool_calls))
        return "tools"

    logger.info("[route] LLM 直接回复，进入结果校验")
    return "validate"


# ─── 图构建 ────────────────────────────────────────────────


def build_graph() -> StateGraph:
    """构建增强版 LangGraph StateGraph。

    流程：
    START → classify_intent → planner → agent → route_after_agent → tools → agent (loop)
                                                              → validate → memory → END

    节点职责：
    - classify_intent: 意图识别（规则+LLM）
    - planner: 任务规划（复杂任务生成多步计划）
    - agent: 按计划执行或自由决策
    - tools: 工具执行（带重试+降级）
    - validate: 结果质量校验+连续失败追踪
    - memory: 记忆提取+会话保存+指标记录
    """
    graph = StateGraph(AgentState)

    # 添加节点（意图识别+规划合并为单节点，减少一次 LLM 调用）
    graph.add_node("classify_and_plan", classify_and_plan)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("validate", validate_node)
    graph.add_node("memory", memory_node)

    # 添加边
    graph.add_edge(START, "classify_and_plan")
    graph.add_edge("classify_and_plan", "agent")
    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {
            "tools": "tools",
            "validate": "validate",
        },
    )
    graph.add_edge("tools", "agent")  # 工具执行后回到 agent 决策
    graph.add_edge("validate", "memory")
    graph.add_edge("memory", END)

    return graph


def build_heritage_agent(checkpointer: Optional[BaseCheckpointSaver] = None):
    """构建并编译非遗探索助手 Agent。

    Args:
        checkpointer: LangGraph checkpointer 实例，用于会话持久化。
                     传入 None 则不持久化（兼容旧模式）。

    Returns:
        CompiledGraph 实例

    Usage:
        agent = build_heritage_agent(checkpointer)
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content="广州有什么非遗？")], ...},
            config={"configurable": {"thread_id": "session_123"}},
        )
    """
    graph = build_graph()
    return graph.compile(checkpointer=checkpointer)


# ─── 便捷运行函数（带上下文管理） ───────────────────────────


async def run_heritage_agent(
    message: str,
    history: list[dict] = None,
    user_id: str = "",
    session_id: str = "",
    system_prompt: str = "",
    master_id: str = "explorer",
) -> dict[str, Any]:
    """运行非遗探索助手（高层接口，带上下文管理）。

    流程：
    1. 通过 ContextManager 确保会话存在
    2. 构建上下文消息（历史 + 用户画像 + 新消息）
    3. 通过 checkpointer 持久化图状态（thread_id = session_id）
    4. 运行 Agent 图
    5. 保存对话消息到 SQLite

    Args:
        message: 用户消息
        history: 对话历史（兼容旧接口，优先使用 checkpointer 中的历史）
        user_id: 用户 ID
        session_id: 会话 ID
        system_prompt: 系统提示词
        master_id: 大师 ID

    Returns:
        {
            "reply": str,           # 最终回复文本
            "panels": list[dict],   # 结构化面板数据
            "messages": list,       # 完整消息列表（含工具调用）
        }
    """
    from heritage_master.tools.agent_tools import AGENT_SYSTEM_PROMPT
    from heritage_master.agent.context import get_context_manager

    ctx = get_context_manager()

    # 确保会话存在
    if session_id:
        ctx.ensure_session(user_id, master_id, session_id)

    # 使用传入的 system_prompt 或默认的
    if not system_prompt:
        system_prompt = AGENT_SYSTEM_PROMPT

    # 构建上下文消息（含历史 + 用户画像）
    if session_id and not history:
        # 有 session_id 且无手动 history → 从 DB 加载历史
        messages = ctx.build_messages(
            user_id=user_id,
            master_id=master_id,
            session_id=session_id,
            new_message=message,
            system_prompt=system_prompt,
        )
    else:
        # 兼容旧模式：手动传入 history
        messages = []
        if history:
            for h in history:
                role = h.get("role", "")
                content = h.get("content", "")
                if role == "user" and content:
                    messages.append(HumanMessage(content=content))
                elif role == "assistant" and content:
                    messages.append(AIMessage(content=content))
        messages.append(HumanMessage(content=message))

        # 注入用户个性化上下文
        if user_id:
            try:
                system_prompt = _enrich_system_prompt(user_id, system_prompt)
            except Exception as e:
                logger.debug("[run] 个性化注入失败: %s", e)

    # 构建初始状态
    from heritage_master.agent.token_budget import DEFAULT_BUDGET
    initial_state: AgentState = {
        "messages": messages,
        "user_id": user_id,
        "session_id": session_id,
        "panels": [],
        "tool_results_cache": {},
        "system_prompt": system_prompt,
        "final_reply": "",
        "metadata": {},
        "token_budget": DEFAULT_BUDGET,
    }
    checkpointer = ctx.checkpointer if session_id else None
    agent = build_heritage_agent(checkpointer=checkpointer)

    # 运行图
    config = {}
    if session_id and checkpointer:
        config = {"configurable": {"thread_id": session_id}}

    result = await agent.ainvoke(initial_state, config=config)

    # 保存对话消息到 SQLite
    reply = result.get("final_reply", "")
    if session_id and reply:
        ctx.save_conversation_pair(session_id, message, reply)

    return {
        "reply": reply,
        "panels": result.get("panels", []),
        "messages": [
            {"role": type(m).__name__.replace("Message", "").lower(), "content": m.content}
            for m in result.get("messages", [])
            if hasattr(m, "content")
        ],
    }


async def run_heritage_agent_stream(
    message: str,
    history: list[dict] = None,
    user_id: str = "",
    session_id: str = "",
    system_prompt: str = "",
    master_id: str = "explorer",
) -> AsyncIterator[dict[str, Any]]:
    """流式运行非遗探索助手（SSE 友好，带上下文管理）。

    产出事件类型：
    - {"type": "agent_thinking"} — LLM 正在思考
    - {"type": "tool_start", "tool": "...", "args": {...}} — 开始执行工具
    - {"type": "tool_end", "tool": "...", "result": "..."} — 工具执行完成
    - {"type": "text_delta", "content": "..."} — 文本增量
    - {"type": "done", "reply": "...", "panels": [...]} — 完成
    """
    from heritage_master.tools.agent_tools import AGENT_SYSTEM_PROMPT
    from heritage_master.agent.context import get_context_manager

    ctx = get_context_manager()

    if session_id:
        ctx.ensure_session(user_id, master_id, session_id)

    if not system_prompt:
        system_prompt = AGENT_SYSTEM_PROMPT

    # 构建上下文消息
    if session_id and not history:
        messages = ctx.build_messages(
            user_id=user_id,
            master_id=master_id,
            session_id=session_id,
            new_message=message,
            system_prompt=system_prompt,
        )
    else:
        messages = []
        if history:
            for h in history:
                role = h.get("role", "")
                content = h.get("content", "")
                if role == "user" and content:
                    messages.append(HumanMessage(content=content))
                elif role == "assistant" and content:
                    messages.append(AIMessage(content=content))
        messages.append(HumanMessage(content=message))

        if user_id:
            try:
                system_prompt = _enrich_system_prompt(user_id, system_prompt)
            except Exception:
                pass

    initial_state: AgentState = {
        "messages": messages,
        "user_id": user_id,
        "session_id": session_id,
        "panels": [],
        "tool_results_cache": {},
        "system_prompt": system_prompt,
        "final_reply": "",
        "metadata": {},
    }

    checkpointer = ctx.checkpointer if session_id else None
    agent = build_heritage_agent(checkpointer=checkpointer)

    config = {}
    if session_id and checkpointer:
        config = {"configurable": {"thread_id": session_id}}

    final_reply = ""

    # 使用 astream 按节点流式输出
    async for event in agent.astream(initial_state, stream_mode="updates", config=config):
        for node_name, node_output in event.items():
            if node_name == "agent":
                ai_msg = None
                for m in node_output.get("messages", []):
                    if isinstance(m, AIMessage):
                        ai_msg = m
                        break

                if ai_msg:
                    if ai_msg.tool_calls:
                        for tc in ai_msg.tool_calls:
                            yield {
                                "type": "tool_start",
                                "tool": tc["name"],
                                "args": tc["args"],
                            }
                    elif ai_msg.content:
                        yield {"type": "text_delta", "content": ai_msg.content}

            elif node_name == "tools":
                for m in node_output.get("messages", []):
                    if hasattr(m, "name") and m.name:
                        yield {
                            "type": "tool_end",
                            "tool": m.name,
                            "result": m.content[:200],
                        }

            elif node_name == "memory":
                reply = node_output.get("final_reply", "")
                panels = node_output.get("panels", [])
                final_reply = reply
                yield {"type": "done", "reply": reply, "panels": panels}

    # 保存对话消息
    if session_id and final_reply:
        ctx.save_conversation_pair(session_id, message, final_reply)


# ─── 辅助函数 ──────────────────────────────────────────────


def _enrich_system_prompt(user_id: str, base_prompt: str) -> str:
    """注入用户画像和记忆上下文到系统提示词（聚合所有大师处的数据）"""
    from heritage_master.tools import user_manager
    from heritage_master.tools.memory import MemoryManager
    from heritage_master.tools.master_prompt import MASTERS

    parts = [base_prompt]

    # 聚合用户在所有大师处的画像
    all_profiles = user_manager.get_all_profiles(user_id)
    if all_profiles:
        merged_tags = []
        total_questions = 0
        merged_personality = ""
        merged_aesthetic = ""
        highest_stage_val = 0
        stage_order = {"入门期": 0, "成长期": 1, "精进期": 2, "传承期": 3}
        masters_visited = []

        for p in all_profiles:
            mid = p.get("master_id", "")
            if mid == "explorer":
                continue
            master_info = MASTERS.get(mid, {})
            master_name = master_info.get("name", mid)
            master_title = master_info.get("title", "")
            display = f"{master_name}（{master_title}）" if master_title else master_name
            masters_visited.append(display)

            tags = p.get("interest_tags", [])
            if isinstance(tags, str):
                import json as _json
                try:
                    tags = _json.loads(tags)
                except Exception:
                    tags = []
            for t in tags:
                if t not in merged_tags:
                    merged_tags.append(t)
            total_questions += p.get("question_count", 0)
            notes = p.get("personality_notes", "")
            if notes and notes not in merged_personality:
                merged_personality = f"{merged_personality}; {notes}" if merged_personality else notes
            aesthetic = p.get("aesthetic_pref", "")
            if aesthetic:
                merged_aesthetic = aesthetic
            stage = p.get("relationship_stage", "入门期")
            s_val = stage_order.get(stage, 0)
            if s_val > highest_stage_val:
                highest_stage_val = s_val

        if merged_tags:
            parts.append(f"该用户对以下非遗话题感兴趣：{'、'.join(merged_tags)}。推荐内容时优先匹配这些兴趣。")

        if total_questions <= 3:
            parts.append("这是新用户，回复要简洁易懂，避免过多专业术语。")
        elif total_questions <= 15:
            parts.append("这是有一定了解的用户，可以适当深入。")
        else:
            parts.append("这是资深用户，可以直接使用专业术语。")

        if merged_personality:
            parts.append(f"用户性格观察：{merged_personality}。据此调整语气风格。")
        if merged_aesthetic:
            parts.append(f"用户审美偏好：{merged_aesthetic}。推荐内容时参考此偏好。")
        if masters_visited:
            parts.append(f"该用户已在平台跟随以下非遗大师学习过：{'、'.join(masters_visited)}。当用户提到相关大师时，说明他们已有师徒互动经历，不要说用户没有拜访过。")

    # 聚合所有大师的长期记忆
    mm = MemoryManager()
    for p in all_profiles:
        mid = p.get("master_id", "")
        if not mid or mid == "explorer":
            continue
        memory_ctx = mm.get_memory_context(mid, user_id)
        if memory_ctx and "暂无" not in memory_ctx:
            master_info = MASTERS.get(mid, {})
            master_name = master_info.get("name", mid)
            parts.append(f"【用户与{master_name}大师的互动记忆】\n{memory_ctx}")

    # explorer 自身的画像上下文
    profile_ctx = user_manager.get_profile_context(user_id, "explorer")
    if profile_ctx:
        parts.append(profile_ctx)

    return "\n\n".join(parts)
