# -*- coding: utf-8 -*-
"""
LangGraph 图节点 - 增强版
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from heritage_master.agent.state import AgentState
from heritage_master.agent.tools import HERITAGE_TOOLS

logger = logging.getLogger("heritage.agent")

class Intent(str, Enum):
    SEARCH = "search"
    VENUE = "venue"
    TRIP = "trip"
    KNOWLEDGE = "knowledge"
    EVENT = "event"
    CHAT = "chat"
    HANDOFF = "handoff"  # 转人工


_INTENT_PATTERNS = [
    (Intent.TRIP, ["旅行", "旅游", "路线", "行程", "几天", "攻略", "去.*玩", "怎么玩", "规划.*之旅", "玩.*天", "游.*天"]),
    (Intent.VENUE, ["场馆", "博物馆", "文化馆", "体验馆", "在哪", "哪里有", "附近", "地址"]),
    (Intent.EVENT, ["活动", "展览", "演出", "工作坊", "讲座", "什么时候", "最近有"]),
    (Intent.KNOWLEDGE, ["传承人", "大师", "谁是", "师承", "历史", "起源", "流派", "代表作", "知识图谱", "谱系", "技法", "工艺", "了解.*功夫茶", "了解.*技艺", "了解.*文化"]),
    (Intent.SEARCH, ["搜索", "查", "找", "有哪些", "什么项目", "名录", "分类", "类别", "帮我了解.*并", "介绍一下"]),
    (Intent.HANDOFF, ["转人工", "人工客服", "真人", "找人问", "转接", "客服"]),
]

# 上下文感知：指代消解词（当用户说这些词时，需要结合上下文理解）
_CONTEXTUAL_PATTERNS = [
    r"[他她它]的",
    r"那[个些位]",
    r"这个",
    r"还有[什么吗]",
    r"[还再]有呢",
    r"继续",
    r"然后呢",
    r"详细[说讲聊]",
    r"更多",
    r"类似的",
    r"之前[说聊提]",
    r"刚才",
]


@dataclass
class IntentResult:
    intent: Intent
    confidence: float
    method: str


def _extract_conversation_context(messages: list) -> dict:
    """从对话历史中提取上下文信息

    Returns:
        {
            "last_intent": str,       # 上一轮意图
            "recent_topics": list,    # 最近讨论的话题关键词
            "last_tool": str,         # 上次调用的工具
            "last_entities": list,    # 最近提到的实体（人名、项目名等）
            "turn_count": int,        # 对话轮次
            "is_followup": bool,      # 当前是否是追问
        }
    """
    ctx = {
        "last_intent": "",
        "recent_topics": [],
        "last_tool": "",
        "last_entities": [],
        "turn_count": 0,
        "is_followup": False,
    }

    user_msgs = []
    ai_msgs = []
    tool_msgs = []

    for msg in messages:
        if isinstance(msg, HumanMessage):
            user_msgs.append(msg.content)
        elif isinstance(msg, AIMessage):
            ai_msgs.append(msg.content or "")
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    ctx["last_tool"] = tc["name"]
        elif isinstance(msg, ToolMessage):
            tool_msgs.append(msg.content[:200])

    ctx["turn_count"] = len(user_msgs)

    # 提取最近的用户消息
    if len(user_msgs) >= 2:
        prev_msg = user_msgs[-2]
        # 从上一轮用户消息中提取实体（简单规则）
        entities = _extract_entities(prev_msg)
        if entities:
            ctx["recent_topics"] = entities
            ctx["last_entities"] = entities

    # 判断当前消息是否是追问
    if user_msgs:
        current = user_msgs[-1]
        for pattern in _CONTEXTUAL_PATTERNS:
            if re.search(pattern, current):
                ctx["is_followup"] = True
                break

    return ctx


def _extract_entities(text: str) -> list:
    """从文本中提取非遗相关实体（人名、项目名等）"""
    entities = []
    # 已知项目名
    known_projects = [
        "昆曲", "京剧", "粤剧", "古琴", "广绣", "苏绣", "湘绣", "蜀绣",
        "剪纸", "太极拳", "中医针灸", "春节", "端午", "皮影戏",
        "景德镇陶瓷", "相声", "凉茶", "醒狮", "南狮", "工夫茶",
        "凤凰单丛", "潮州", "佛山",
    ]
    for p in known_projects:
        if p in text:
            entities.append(p)

    # 已知人名
    known_people = ["叶汉钟", "黄钦添", "蔡正仁", "王秀英", "高凤莲"]
    for p in known_people:
        if p in text:
            entities.append(p)

    return entities


def classify_intent_rule(message: str, context: dict = None) -> IntentResult | None:
    """规则意图分类（支持上下文感知）"""
    # 先检查转人工
    for kw in _INTENT_PATTERNS[-1][1]:  # HANDOFF patterns
        if re.search(kw, message):
            return IntentResult(intent=Intent.HANDOFF, confidence=0.95, method="rule")

    # 标准规则匹配
    for intent, keywords in _INTENT_PATTERNS[:-1]:  # 排除 HANDOFF
        for kw in keywords:
            if re.search(kw, message):
                return IntentResult(intent=intent, confidence=0.85, method="rule")

    # 上下文感知：如果是追问，继承上一轮意图
    if context and context.get("is_followup"):
        last_intent = context.get("last_intent", "")
        if last_intent:
            for it in Intent:
                if it.value == last_intent and it != Intent.CHAT:
                    return IntentResult(intent=it, confidence=0.75, method="context_followup")

    return None


async def classify_intent_llm(message: str, context: dict = None) -> IntentResult:
    """LLM 意图分类（带上下文）"""
    try:
        from heritage_master.config import settings
        llm = ChatOpenAI(model=settings.llm_model, api_key=settings.llm_api_key, base_url=settings.llm_base_url, temperature=0, max_tokens=30)

        # 构建带上下文的 prompt
        ctx_hint = ""
        if context:
            topics = context.get("recent_topics", [])
            last_intent = context.get("last_intent", "")
            if topics:
                ctx_hint += f"\n最近讨论的话题：{', '.join(topics)}"
            if last_intent:
                ctx_hint += f"\n上一轮意图：{last_intent}"
            if context.get("is_followup"):
                ctx_hint += "\n当前消息是追问，大概率延续上一轮意图。"

        prompt = (
            "你是意图分类器。根据用户消息和上下文，只输出一个意图标签：\n"
            "search/venue/trip/knowledge/event/chat/handoff\n"
            f"{ctx_hint}\n\n"
            f"用户消息：{message}\n意图标签："
        )
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        label = resp.content.strip().lower()
        for intent in Intent:
            if intent.value in label:
                return IntentResult(intent=intent, confidence=0.7, method="llm")
    except Exception as e:
        logger.warning("[intent] LLM 分类失败: %s", e)
    return IntentResult(intent=Intent.CHAT, confidence=0.5, method="fallback")


def _build_llm() -> ChatOpenAI:
    from heritage_master.config import settings
    return ChatOpenAI(model=settings.llm_model, api_key=settings.llm_api_key, base_url=settings.llm_base_url, temperature=0.7, max_tokens=2000)

_llm_with_tools = None

def _get_llm_with_tools() -> ChatOpenAI:
    global _llm_with_tools
    if _llm_with_tools is None:
        _llm_with_tools = _build_llm().bind_tools(HERITAGE_TOOLS)
    return _llm_with_tools

def reset_llm():
    global _llm_with_tools
    _llm_with_tools = None


_PLANNABLE_INTENTS = {Intent.TRIP, Intent.VENUE, Intent.KNOWLEDGE}
_PLANNABLE_INTENTS_SET = {i.value for i in _PLANNABLE_INTENTS}
_PLANNER_MIN_COMPLEXITY = 2


async def classify_and_plan(state: AgentState) -> dict[str, Any]:
    import time as _time
    from heritage_master.observability.tracer import collector
    messages = state["messages"]
    user_id = state.get("user_id", "")
    session_id = state.get("session_id", "")
    metadata = dict(state.get("metadata", {}))
    trace_id = metadata.get("trace_id") or f"tr_{int(_time.time())}_{id(state) % 10000:04d}"
    metadata["trace_id"] = trace_id
    metadata["started_at"] = _time.time()
    collector.start_trace(trace_id, user_id=user_id, session_id=session_id)

    user_msg = ""
    for msg in messages:
        if isinstance(msg, HumanMessage):
            user_msg = msg.content; break
    if not user_msg:
        metadata.update({"intent": Intent.CHAT.value, "confidence": 0.5, "method": "empty", "plan": None, "plan_step": 0})
        return {"metadata": metadata}

    # 提取对话上下文
    ctx = _extract_conversation_context(messages)
    metadata["context"] = ctx

    # 检查是否是转人工意图
    rule_result = classify_intent_rule(user_msg, context=ctx)
    if rule_result and rule_result.intent == Intent.HANDOFF:
        metadata.update({"intent": Intent.HANDOFF.value, "confidence": rule_result.confidence, "method": rule_result.method, "plan": None, "plan_step": 0})
        collector.add_step(trace_id, "intent_classify", {"intent": "handoff", "confidence": rule_result.confidence, "method": rule_result.method})
        return {"metadata": metadata}

    if rule_result:
        intent = rule_result.intent.value
        metadata.update({"intent": intent, "confidence": rule_result.confidence, "method": "rule"})
        collector.add_step(trace_id, "intent_classify", {"intent": intent, "confidence": rule_result.confidence, "method": "rule"})
        if intent not in _PLANNABLE_INTENTS_SET:
            metadata["plan"] = None; metadata["plan_step"] = 0
            return {"metadata": metadata}
        plan = await _generate_plan_for_intent(user_msg, intent)
        metadata["plan"] = plan; metadata["plan_step"] = 0
        if plan:
            collector.add_step(trace_id, "task_plan", {"steps": len(plan), "tools": [s.get("tool") for s in plan]})
        return {"metadata": metadata}
    token_budget = state.get("token_budget", -1)
    from heritage_master.agent.token_budget import check_budget, deduct
    if not check_budget(token_budget, "classify_and_plan"):
        metadata.update({"intent": Intent.CHAT.value, "confidence": 0.5, "method": "budget_skip", "plan": None, "plan_step": 0})
        return {"metadata": metadata}
    try:
        from heritage_master.config import settings
        llm = ChatOpenAI(model=settings.llm_model, api_key=settings.llm_api_key, base_url=settings.llm_base_url, temperature=0, max_tokens=500)

        # 构建带上下文的 prompt
        ctx_hint = ""
        topics = ctx.get("recent_topics", [])
        last_intent = ctx.get("last_intent", "")
        if topics:
            ctx_hint += f"\n最近讨论的话题：{', '.join(topics)}"
        if last_intent:
            ctx_hint += f"\n上一轮意图：{last_intent}"
        if ctx.get("is_followup"):
            ctx_hint += "\n当前消息是追问，大概率延续上一轮意图。"

        prompt = ("你是意图分类器兼任务规划器。输出JSON: "
                  '{"intent": "标签", "plan": [数组或null]}\n\n'
                  "意图标签：search/venue/trip/knowledge/event/chat/handoff\n"
                  "plan：多工具时输出数组，否则null\n"
                  f"{ctx_hint}\n\n"
                  "用户消息：" + user_msg + "\n输出JSON：")
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        text = resp.content.strip()
        if "```" in text: text = text.split("```")[1]
        if text.startswith("json"): text = text[4:]
        data = json.loads(text.strip())
        intent_label = data.get("intent", "chat").lower()
        raw_plan = data.get("plan")
        matched = Intent.CHAT
        for it in Intent:
            if it.value in intent_label: matched = it; break
        metadata["intent"] = matched.value; metadata["confidence"] = 0.7; metadata["method"] = "llm_merged"
        collector.add_step(trace_id, "intent_classify", {"intent": matched.value, "confidence": 0.7, "method": "llm"})
        if isinstance(raw_plan, list) and len(raw_plan) >= _PLANNER_MIN_COMPLEXITY:
            vp = [{"step": i+1, "tool": s["tool"], "args": s.get("args",{}), "purpose": s.get("purpose","")} for i,s in enumerate(raw_plan) if isinstance(s,dict) and "tool" in s]
            metadata["plan"] = vp if len(vp) >= _PLANNER_MIN_COMPLEXITY else None
        else:
            metadata["plan"] = None
        metadata["plan_step"] = 0
        if metadata.get("plan"):
            collector.add_step(trace_id, "task_plan", {"steps": len(metadata["plan"]), "tools": [s.get("tool") for s in metadata["plan"]]})
        token_budget = deduct(token_budget, "classify_and_plan")
    except Exception as e:
        logger.warning("[classify_and_plan] LLM 失败: %s", e)
        metadata.update({"intent": Intent.CHAT.value, "confidence": 0.5, "method": "fallback", "plan": None, "plan_step": 0})
    return {"metadata": metadata, "token_budget": token_budget}


async def _generate_plan_for_intent(user_msg, intent):
    try:
        from heritage_master.config import settings
        llm = ChatOpenAI(model=settings.llm_model, api_key=settings.llm_api_key, base_url=settings.llm_base_url, temperature=0, max_tokens=500)
        prompt = f"用户意图：{intent}\\n用户消息：{user_msg}\\n\\n生成执行计划(JSON数组，每个含step/tool/args/purpose)。只需一个工具则返回[]。只输出JSON。"
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        text = resp.content.strip()
        if "```" in text: text = text.split("```")[1]
        plan = json.loads(text.strip().replace("json", ""))
        if not isinstance(plan, list): return None
        valid = [{"step": i+1, "tool": s["tool"], "args": s.get("args",{}), "purpose": s.get("purpose","")} for i,s in enumerate(plan) if isinstance(s,dict) and "tool" in s]
        return valid if len(valid) >= _PLANNER_MIN_COMPLEXITY else None
    except Exception as e:
        logger.warning("[_generate_plan] 失败: %s", e); return None


TOOL_HINTS = {
    Intent.SEARCH: "优先使用 search_heritage 工具搜索非遗项目。",
    Intent.VENUE: "优先使用 find_venues 工具查找场馆。",
    Intent.TRIP: "优先使用 plan_trip 工具规划旅行路线。",
    Intent.KNOWLEDGE: "优先使用 query_knowledge_graph 或 get_inheritance_chain 工具查询知识。",
    Intent.EVENT: "优先使用 find_events 工具查找活动信息。",
    Intent.CHAT: "直接回复，不需要调用工具。",
    Intent.HANDOFF: "用户要求转人工，请表示理解并告知已记录需求，会有专人联系。",
}


async def agent_node(state: AgentState) -> dict[str, Any]:
    import time as _time
    from heritage_master.observability.tracer import collector
    messages = state["messages"]
    system_prompt = state.get("system_prompt", "")
    metadata = dict(state.get("metadata", {}))
    trace_id = metadata.get("trace_id", "")
    intent = metadata.get("intent", "")
    plan = metadata.get("plan")
    plan_step = metadata.get("plan_step", 0)

    # 转人工意图：直接返回转接提示，不走 LLM
    if intent == Intent.HANDOFF.value:
        handoff_msg = AIMessage(content=(
            "好的，我理解您希望与真人沟通。我已记录您的需求，"
            "我们的工作人员会尽快与您联系。\n\n"
            "您也可以通过以下方式联系我们：\n"
            "• 在论坛发帖，社区志愿者会帮您解答\n"
            "• 前往当地文化馆/非遗中心咨询\n\n"
            "在等待期间，如果还有其他问题，我随时在这里。"
        ))
        if trace_id:
            collector.add_step(trace_id, "handoff", {"intent": "handoff", "method": "direct"})
        return {"messages": [handoff_msg], "final_reply": handoff_msg.content, "metadata": metadata}
    if plan and plan_step < len(plan):
        step = plan[plan_step]
        import uuid
        tcid = f"plan_{plan_step}_{uuid.uuid4().hex[:8]}"
        ai_msg = AIMessage(content="", tool_calls=[{"id": tcid, "name": step["tool"], "args": step.get("args", {})}])
        metadata["plan_step"] = plan_step + 1
        if trace_id:
            collector.add_step(trace_id, "plan_execute", {"step": plan_step + 1, "tool": step["tool"], "args": step.get("args", {})})
        return {"messages": [ai_msg], "metadata": metadata}
    if plan and plan_step >= len(plan):
        metadata["plan"] = None
    token_budget = state.get("token_budget", -1)
    from heritage_master.agent.token_budget import check_budget, deduct as bd
    if not check_budget(token_budget, "agent"):
        fb = AIMessage(content="抱歉，本轮对话已达到处理上限。")
        return {"messages": [fb], "final_reply": fb.content, "metadata": metadata, "token_budget": 0}
    full = []
    if system_prompt:
        hint = TOOL_HINTS.get(Intent(intent), "") if intent else ""
        enhanced = system_prompt
        if hint: enhanced += "\\n\\n【意图提示】" + hint
        if plan_step > 0 and not plan: enhanced += "\\n\\n【执行完成】请基于工具结果生成总结回复。"
        full.append(SystemMessage(content=enhanced))
    full.extend(messages)
    llm = _get_llm_with_tools()
    try:
        t_start = _time.time()
        resp = await llm.ainvoke(full)
        t_ms = int((_time.time() - t_start) * 1000)
        token_budget = bd(token_budget, "agent")
        if trace_id:
            has_tools = bool(resp.tool_calls)
            collector.add_step(trace_id, "llm_generate", {"duration_ms": t_ms, "has_tool_calls": has_tools, "reply_len": len(resp.content) if resp.content else 0})
        return {"messages": [resp], "metadata": metadata, "token_budget": token_budget}
    except Exception as e:
        logger.error("[agent_node] LLM 失败: %s", e)
        if trace_id:
            collector.add_step(trace_id, "llm_generate", {"status": "error", "error": str(e)})
        err = AIMessage(content="抱歉，我暂时无法处理这个请求。")
        return {"messages": [err], "final_reply": err.content, "metadata": metadata, "token_budget": token_budget}


async def tool_node(state: AgentState) -> dict[str, Any]:
    import time as _time
    from heritage_master.observability.tracer import collector
    messages = state["messages"]
    metadata = state.get("metadata", {})
    trace_id = metadata.get("trace_id", "")
    cache = dict(state.get("tool_results_cache", {}))
    panels = []
    last_ai = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.tool_calls: last_ai = msg; break
    if not last_ai: return {}
    tool_msgs = []
    tmap = {t.name: t for t in HERITAGE_TOOLS}
    for tc in last_ai.tool_calls:
        tn, ta, tid = tc["name"], tc["args"], tc["id"]
        ck = f"{tn}:{json.dumps(ta, sort_keys=True, ensure_ascii=False)}"
        t_start = _time.time()
        if ck in cache:
            rt = cache[ck]
            t_ms = int((_time.time() - t_start) * 1000)
            if trace_id:
                collector.add_step(trace_id, "tool_call", {"tool": tn, "args": ta, "cached": True, "duration_ms": t_ms})
        else:
            fn = tmap.get(tn)
            if fn is None:
                rt = f"未知工具: {tn}"
                if trace_id:
                    collector.add_step(trace_id, "tool_call", {"tool": tn, "args": ta, "status": "unknown_tool"})
            else:
                rt = await _exec_retry(fn, tn, ta)
                t_ms = int((_time.time() - t_start) * 1000)
                success = bool(rt and rt.strip() and not rt.startswith("暂无") and not rt.startswith("抱歉"))
                if trace_id:
                    collector.add_step(trace_id, "tool_call", {"tool": tn, "args": ta, "success": success, "duration_ms": t_ms, "result_len": len(rt) if rt else 0})
                if not rt or not rt.strip(): rt = _degrade(tn, ta)
                cache[ck] = rt
            p = _extract_panel(tn, ta, rt)
            if p: panels.append(p)
        tool_msgs.append(ToolMessage(content=rt, tool_call_id=tid, name=tn))
    return {"messages": tool_msgs, "panels": panels, "tool_results_cache": cache}

MAX_RETRIES = 2

async def _exec_retry(fn, name, args):
    for attempt in range(MAX_RETRIES + 1):
        try:
            r = await fn.ainvoke(args)
            if r and r.strip(): return r
        except Exception as e:
            logger.warning("[tool] %s attempt=%d error=%s", name, attempt, e)
        if attempt < MAX_RETRIES: await asyncio.sleep(1.0 * (2 ** attempt))
    return _degrade(name, args)

def _degrade(name, args, error=None):
    s = ", ".join(f"{k}={v}" for k, v in args.items() if v)
    if error: return f"抱歉，查询{name}时遇到问题（{s}）。建议稍后再试。"
    return f"暂无匹配结果（{s}），建议换个关键词。"

def _extract_panel(name, args, text):
    if name == "find_venues" and "找到" in text: return {"type": "venue_list", "city": args.get("city","")}
    if name == "plan_trip" and "Day" in text: return {"type": "trip_plan", "city": args.get("city","")}
    return None


CONSECUTIVE_FAILURE_THRESHOLD = 3

async def validate_node(state: AgentState) -> dict[str, Any]:
    from heritage_master.observability.tracer import collector
    messages = state["messages"]
    metadata = dict(state.get("metadata", {}))
    trace_id = metadata.get("trace_id", "")
    final_reply = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls and msg.content:
            final_reply = msg.content; break
    issues = []
    if not final_reply or len(final_reply.strip()) < 5: issues.append("empty_reply")
    errs = ["抱歉", "无法", "失败", "错误", "稍后再试"]
    if final_reply and all(p in final_reply for p in errs[:2]) and len(final_reply) < 50: issues.append("error_only")
    tc_count = sum(1 for m in messages if isinstance(m, AIMessage) and m.tool_calls)
    if tc_count > 0 and len(final_reply) < 30: issues.append("short_reply_with_tools")
    cf = metadata.get("consecutive_failures", 0)
    if issues:
        cf += 1
        metadata["quality_issues"] = issues
        metadata["consecutive_failures"] = cf
        if cf >= CONSECUTIVE_FAILURE_THRESHOLD: metadata["should_handoff"] = True
    else:
        metadata["consecutive_failures"] = 0
        metadata.pop("quality_issues", None)
    if trace_id:
        collector.add_step(trace_id, "validate", {"passed": not bool(issues), "issues": issues})
    return {"metadata": metadata}


async def memory_node(state: AgentState) -> dict[str, Any]:
    import time as _time
    from heritage_master.observability.tracer import collector
    messages = state["messages"]
    user_id = state.get("user_id", "")
    session_id = state.get("session_id", "")
    metadata = state.get("metadata", {})
    trace_id = metadata.get("trace_id", "")
    final_reply = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls and msg.content:
            final_reply = msg.content; break
    if not final_reply: final_reply = "抱歉，我暂时无法生成回复。"
    metadata = state.get("metadata", {})
    if metadata.get("should_handoff"):
        final_reply += (
            "\n\n---\n看起来我连续几次都没能帮到您。"
            "如果您愿意，可以回复「转人工」，我会为您记录需求，"
            "我们的工作人员会尽快与您联系。"
        )
        if trace_id:
            collector.add_step(trace_id, "auto_handoff_trigger", {"consecutive_failures": metadata.get("consecutive_failures", 0)})
    if user_id and session_id:
        try:
            from heritage_master.tools import user_manager
            for msg in messages:
                if isinstance(msg, HumanMessage): user_manager.add_message(session_id, "user", msg.content[:500]); break
            user_manager.add_message(session_id, "assistant", final_reply[:2000])
        except Exception as e: logger.warning("[memory] 保存会话失败: %s", e)
    token_budget = state.get("token_budget", -1)
    if user_id:
        try:
            from heritage_master.agent.token_budget import check_budget
            use_llm = check_budget(token_budget, "memory_extract")
            await _extract_memories(messages, user_id, final_reply, use_llm=use_llm)
        except Exception as e: logger.warning("[memory] 提取失败: %s", e)
        try: await _maybe_consolidate(user_id, session_id)
        except Exception as e: logger.warning("[memory] 整理失败: %s", e)
    if trace_id:
        collector.add_step(trace_id, "memory_extract", {"user_id": user_id[:8] if user_id else ""})
    try: _record_metrics(state, final_reply)
    except Exception as e: logger.warning("[memory] 指标失败: %s", e)
    return {"final_reply": final_reply}


def _record_metrics(state, final_reply):
    from heritage_master.observability.metrics import metrics, RequestMetric
    from heritage_master.observability.tracer import collector
    import time as _t
    md = state.get("metadata", {})
    msgs = state["messages"]
    tc = sum(len(m.tool_calls) for m in msgs if isinstance(m, AIMessage) and m.tool_calls)
    ts = sum(1 for m in msgs if isinstance(m, ToolMessage) and not m.content.startswith("抱歉"))
    st = "failed" if md.get("quality_issues") else "success"
    metric = RequestMetric(trace_id=md.get("trace_id",""), user_id=state.get("user_id",""), session_id=state.get("session_id",""), intent=md.get("intent",""), started_at=md.get("started_at",_t.time()), finished_at=_t.time(), status=st, tool_calls=tc, tool_successes=ts, tool_failures=tc-ts, reply_len=len(final_reply))
    metrics.record_request(metric)
    tid = md.get("trace_id","")
    if tid: collector.end_trace(tid, status=st, reply_len=len(final_reply), total_ms=int((_t.time()-metric.started_at)*1000))


async def _extract_memories(messages, user_id, reply, use_llm=True):
    from heritage_master.tools.memory import MemoryManager, MemoryExtractor
    user_msg = ""
    for msg in messages:
        if isinstance(msg, HumanMessage): user_msg = msg.content; break
    if not user_msg: return
    mm = MemoryManager()
    ext = MemoryExtractor()
    mems = ext.extract_by_rules(user_msg, reply, "explorer")
    if mems:
        for m in mems: mm.add_memory("explorer", user_id, m)
    if not use_llm: return
    try:
        lm = await ext.extract_from_conversation([{"role":"user","content":user_msg},{"role":"assistant","content":reply}], "explorer", user_id)
        if lm:
            for m in lm: mm.add_memory("explorer", user_id, m)
    except: pass


async def _maybe_consolidate(user_id, session_id):
    from heritage_master.config import settings
    from heritage_master.tools.memory import MemoryManager
    mm = MemoryManager()
    mem = mm.load_memory("explorer", user_id)
    if not mem: return
    core = mem.get("core_memories", [])
    if len(core) < settings.memory_consolidation_threshold: return
    recent = sorted(core, key=lambda m: m.get("created_at",""), reverse=True)[:20]
    old = sorted(core, key=lambda m: m.get("created_at",""), reverse=True)[20:]
    if not old: return
    try:
        from langchain_openai import ChatOpenAI as C
        from langchain_core.messages import HumanMessage as H
        llm = C(model=settings.llm_model, api_key=settings.llm_api_key, base_url=settings.llm_base_url, temperature=0.3, max_tokens=500)
        txt = chr(10).join(f"- [{m.get('type','')}] {m.get('content','')}" for m in old[:30])
        resp = await llm.ainvoke([H(content=f"将以下{len(old)}条记忆合并为3-5条摘要：\\n{txt}\\n每条一行以- 开头")])
        lines = [l.strip().lstrip("- ") for l in resp.content.strip().split(chr(10)) if l.strip().startswith("-")]
        if lines:
            from datetime import datetime, timezone
            new = [{"type":"consolidated","content":l,"created_at":datetime.now(timezone.utc).isoformat()} for l in lines]
            mem["core_memories"] = recent + new
            mm.save_memory("explorer", user_id, mem)
    except Exception as e: logger.warning("[memory] 整理失败: %s", e)
