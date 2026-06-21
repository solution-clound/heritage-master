"""
非遗探索助手 / 知识问答 / LangGraph Agent 路由

包含：
- POST /api/agent          — 对话式 Agent（function calling 循环）
- GET  /api/agent/greeting — 个性化问候
- GET  /api/agent/conversations — 对话历史列表
- GET  /api/agent/conversations/{session_id} — 会话详情
- POST /api/ask            — 大师知识问答
- POST /api/agent/graph    — LangGraph Agent
- POST /api/agent/graph/stream — LangGraph SSE 流式
"""
from __future__ import annotations

import json as _json
import re
import asyncio
import uuid
from typing import List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from heritage_master.data.crawler import CATEGORIES, search_heritage_data
from heritage_master.data.realtime import get_platforms_for_region, get_all_platforms
from heritage_master.tools.venue_finder import search_venues_amap
from heritage_master.tools.knowledge_base import ask_heritage_expert, get_knowledge
from heritage_master.tools.route_planner import plan_heritage_route
from heritage_master.tools.agent_tools import AGENT_SYSTEM_PROMPT, AGENT_TOOLS
from heritage_master.tools import user_manager, cultivation
from heritage_master.tools.memory import MemoryManager, MemoryExtractor, GreetingGenerator
from heritage_master.tools.master_prompt import (
    MASTER_SYSTEM_PROMPT,
    build_qa_prompt as _build_qa_prompt,
    build_adaptive_prompt as _build_adaptive_prompt,
    list_masters as _list_masters,
    get_master_prompt as _get_master_prompt,
    get_adaptive_greeting as _get_adaptive_greeting,
)

from deps import get_memory_manager, get_llm, llm_available

router = APIRouter()

_LLM_SYSTEM_PROMPT = MASTER_SYSTEM_PROMPT


# ─── LLM 调用辅助 ─────────────────────────────────────────

async def _ask_llm(question: str, context: str = "", messages: list = None) -> str | None:
    """调用 LLM 生成回答。支持传入自定义 messages 或自动构建。"""
    llm = get_llm()
    if not llm:
        return None

    if messages is None:
        user_msg = f"参考资料：\n{context}\n\n用户问题：{question}" if context else question
        messages = [
            {"role": "system", "content": _LLM_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

    return await llm.chat_completion(messages, temperature=0.7, max_tokens=2000)


async def _ask_llm_with_tools(messages: list, tools: list) -> dict:
    """调用 LLM 支持 function calling，返回原始 response dict。"""
    llm = get_llm()
    if not llm:
        return {}

    result = await llm.chat_completion_with_tools(messages, tools, temperature=0.7, max_tokens=2000)
    return result if result else {}


# ─── Agent 辅助函数 ────────────────────────────────────────

def _build_agent_personalization(profile: dict) -> str:
    """根据用户画像生成探索助手的个性化行为指令"""
    parts = []
    if not profile:
        return ""

    tags = profile.get("interest_tags", [])
    if tags:
        parts.append(f"该用户对以下非遗话题感兴趣：{'、'.join(tags)}。推荐内容时优先匹配这些兴趣。")

    question_count = profile.get("question_count", 0)
    if question_count <= 3:
        parts.append("这是新用户，回复要简洁易懂，避免过多专业术语，多用生活化的例子。")
    elif question_count <= 15:
        parts.append("这是有一定了解的用户，可以适当深入，但仍需解释专业概念。")
    else:
        parts.append("这是资深用户，可以直接使用专业术语，回复可以更深入详细。")

    personality = profile.get("personality_notes", "")
    if personality:
        parts.append(f"用户性格观察：{personality}。据此调整语气风格。")

    return "\n".join(parts)


async def _execute_agent_tool(tool_name: str, arguments: dict) -> tuple:
    """执行 agent 工具调用，返回 (raw_data, panel_type, formatted_text)。"""
    if tool_name == "search_heritage":
        items = await search_heritage_data(
            query=arguments.get("query", ""),
            category=arguments.get("category", ""),
            region=arguments.get("region", ""),
            limit=10,
        )
        from heritage_master.tools.heritage_search import format_heritage_list
        text = format_heritage_list(items)
        return items, "heritage_list", text

    elif tool_name == "find_venues":
        venues = await search_venues_amap(
            city=arguments.get("city", ""),
            keyword=arguments.get("keyword", "非遗"),
            limit=10,
        )
        from heritage_master.tools.venue_finder import format_venue_list
        text = format_venue_list(venues, arguments.get("city", ""))
        return venues, "venue_list", text

    elif tool_name == "plan_trip":
        print(f"[agent] plan_trip 调用: city={arguments.get('city')}, days={arguments.get('days', 2)}")
        try:
            result = await plan_heritage_route(
                city=arguments.get("city", ""),
                days=arguments.get("days", 2),
                interests=arguments.get("interests"),
            )
            text = result["itinerary"]
            route_data = result.get("route_data")
            print(f"[agent] plan_trip 完成: itinerary_len={len(text)}, route_data={'有' if route_data else '无'}")
            return {"city": arguments.get("city", ""), "days": arguments.get("days", 2), "itinerary": text, "route_data": route_data}, "trip_plan", text
        except Exception as e:
            print(f"[agent] plan_trip 失败: {e}")
            return None, None, f"路线规划失败: {e}"

    elif tool_name == "query_knowledge_graph":
        from heritage_master.data.knowledge_graph import search_nodes, get_node, get_neighbors
        results = search_nodes(
            arguments.get("query", ""),
            node_type=arguments.get("node_type") or None,
            limit=10,
        )
        if not results:
            return None, None, "未找到相关的图谱节点"
        lines = [f"找到 {len(results)} 个相关节点："]
        for r in results:
            ntype = r.get("type", "")
            name = r.get("name", r.get("node_id", ""))
            desc = r.get("description", "")
            title = r.get("title", "")
            specialty = r.get("specialty", "")
            line = f"- [{ntype}] {name}"
            if title:
                line += f"（{title}）"
            if specialty:
                line += f" — {specialty}"
            if desc:
                line += f"\n  {desc[:100]}"
            lines.append(line)
        text = "\n".join(lines)
        return results, "knowledge_graph", text

    elif tool_name == "get_inheritance_chain":
        from heritage_master.data.knowledge_graph import get_inheritance_chain as _get_chain
        person_name = arguments.get("person_name", "")
        person_id = person_name if ":" in person_name else f"person:{person_name}"
        chain = _get_chain(person_id)
        if not chain:
            return None, None, f"未找到「{person_name}」的师承记录"
        lines = [f"「{person_name}」的师承链："]
        for i, c in enumerate(chain):
            name = c.get("name", "")
            title = c.get("title", "")
            prefix = "  " * i + ("└─ " if i > 0 else "")
            lines.append(f"{prefix}{name}" + (f"（{title}）" if title else ""))
        text = "\n".join(lines)
        return chain, "inheritance_chain", text

    elif tool_name == "find_events":
        keyword = arguments.get("keyword", "")
        region = arguments.get("region", "")

        platforms = get_platforms_for_region(region)

        if not platforms:
            # 没有指定地区或未知地区，返回所有平台列表
            all_platforms = get_all_platforms()
            lines = [f"未找到指定地区的文化平台。以下是全国主要省级文化服务平台（共 {len(all_platforms)} 个）："]
            for prov, p in list(all_platforms.items())[:10]:
                lines.append(f"- {prov}：{p['name']}（{p['type']}）— {p['search_hint']}")
            lines.append("\n请告诉我你所在的地区，我可以推荐对应的文化平台来查找活动。")
            return None, None, "\n".join(lines)

        hint = f"（{region}）" if region else ""
        lines = [
            f"🔍 {hint}非遗活动查询",
            "",
            f"以下是{region or ''}查非遗活动的官方渠道，点击直达👇",
            "",
        ]

        type_icons = {"小程序": "📱", "公众号": "📣", "网站": "🌐", "线下体验": "🏘️"}
        for i, p in enumerate(platforms, 1):
            icon = type_icons.get(p.get("type", ""), "🔗")
            lines.append(f"{i}️⃣ {icon} {p['name']}（{p.get('type', '')}）")
            lines.append(f"   🔗 {p['url']}")
            if p.get("desc"):
                lines.append(f"   {p['desc']}")
            lines.append("")

        lines.append("以上平台会发布最新的非遗活动、展览、工作坊等信息，可直接访问查看并报名。")
        return None, None, "\n".join(lines)

    return None, None, "工具调用失败"


def _detect_selection(message: str, history: list) -> str | None:
    """检测用户是否在选择之前的方案，返回增强后的消息。"""
    msg = message.strip()

    # 匹配选择模式
    selection_patterns = [
        r'(第[一二三四五六七八九十\d]+[个条方案路线])',
        r'(方案[一二三四五六七八九十\d])',
        r'(选项[一二三四五六七八九十\d])',
        r'(就(这个|那个))',
        r'(选(这个|那个))',
        r'(更好|更喜欢|更合适)',
    ]

    is_selection = any(re.search(p, msg) for p in selection_patterns)
    if not is_selection or not history:
        return None

    # 从历史中找到最后一个助手消息
    last_assistant = None
    for h in reversed(history):
        if h.get("role") == "assistant" and h.get("content"):
            last_assistant = h["content"]
            break

    if not last_assistant:
        return None

    # 增强消息，明确告诉 LLM 需要调用工具
    enhanced = f"{msg}\n\n[系统提示：用户正在选择你之前提供的方案。请根据用户的选择，调用 plan_trip 工具重新规划路线，确保画布能展示用户选择的具体方案。请在 interests 参数中体现用户选择的方案主题。]"
    return enhanced


def _extract_keywords(question: str) -> list[str]:
    """从自然语言问题中提取非遗相关关键词"""
    # 已知项目名和非遗相关关键词
    known = [
        # 戏曲/戏剧
        "昆曲", "京剧", "粤剧", "潮剧", "藏戏", "雷剧", "皮影戏", "相声",
        "龙舟说唱",
        # 音乐
        "古琴", "南音", "花儿", "木卡姆", "长调",
        # 美术/技艺
        "广绣", "苏绣", "蜀绣", "湘绣", "四大名绣",
        "剪纸", "篆刻", "书法", "木雕", "年画", "热贡",
        "景德镇", "陶瓷", "宣纸", "广彩",
        # 体育/杂技
        "太极拳", "醒狮", "龙舟",
        # 医药
        "针灸", "诊法", "凉茶",
        # 民俗
        "春节", "端午", "妈祖",
        # 通用关键词
        "刺绣", "戏曲", "非遗", "曲艺", "民俗", "戏剧",
        "传统技艺", "传统美术", "传统音乐", "传统舞蹈",
        "传统医药", "民间文学", "传统体育",
        "四大名绣", "名绣", "绣",
        "传承人", "非物质文化遗产",
    ]
    found = [k for k in known if k in question]
    # 去重并按长度降序（优先匹配更长的词）
    return sorted(set(found), key=len, reverse=True)


def _build_answer(question: str, keywords: list[str], items: list[dict]) -> str:
    """根据问题和搜索到的项目，组织成有意义的回答"""
    # 如果问题提到具体项目（>=2个），做对比回答
    project_names = [kw for kw in keywords if len(kw) >= 2 and kw not in (
        "非遗", "戏曲", "刺绣", "戏剧", "民俗", "曲艺", "名绣", "绣",
        "传统技艺", "传统美术", "传统音乐", "传统舞蹈", "传统医药",
        "民间文学", "传统体育", "传承人", "非物质文化遗产",
    )]

    if len(project_names) >= 2:
        # 对比模式
        lines = [f"关于「{'」和「'.join(project_names)}」的区别：\n"]
        for name in project_names:
            matched = [i for i in items if name in i.get("name", "")]
            if not matched:
                continue
            proj = matched[0]
            lines.append(f"### {proj['name']}")
            if proj.get("category"):
                lines.append(f"- **类别**：{proj['category']}")
            if proj.get("region"):
                lines.append(f"- **流传地区**：{proj['region']}")
            if proj.get("batch"):
                lines.append(f"- **批次**：{proj['batch']}")
            if proj.get("unesco"):
                lines.append(f"- **UNESCO**：人类非物质文化遗产代表作（{proj.get('unesco_year', '')}年）")
            if proj.get("description"):
                lines.append(f"\n{proj['description']}")
            lines.append("")

        # 如果找到了两个以上项目，补充总结
        matched_items = [i for i in items if any(n in i.get("name", "") for n in project_names)]
        if len(matched_items) >= 2:
            cats = set(i.get("category", "") for i in matched_items if i.get("category"))
            if len(cats) > 1:
                lines.append(f"\n**主要区别**：两者属于不同类别，「{project_names[0]}」属于{matched_items[0].get('category', '')}，"
                             f"「{project_names[1]}」属于{matched_items[1].get('category', '')}。")

        lines.append("\n点击项目名称可查看更详细的信息。")
        return "\n".join(lines)

    # 单项目或多项目展示模式
    lines = []
    if len(project_names) == 1:
        name = project_names[0]
        matched = [i for i in items if name in i.get("name", "")]
        if matched:
            proj = matched[0]
            lines.append(f"关于「{name}」：\n")
            if proj.get("category"):
                lines.append(f"- **类别**：{proj['category']}")
            if proj.get("region"):
                lines.append(f"- **流传地区**：{proj['region']}")
            if proj.get("batch"):
                lines.append(f"- **批次**：{proj['batch']}")
            if proj.get("unesco"):
                lines.append(f"- **UNESCO**：人类非物质文化遗产代表作（{proj.get('unesco_year', '')}年）")
            if proj.get("description"):
                lines.append(f"\n{proj['description']}")
            # 列出其他相关项目
            others = [i for i in items if i["name"] != proj["name"]][:3]
            if others:
                lines.append(f"\n**相关项目**：{'、'.join(i['name'] for i in others)}")
            lines.append("\n点击项目名称可查看更详细的信息。")
            return "\n".join(lines)

    # 通用展示
    lines = ["以下是中国非物质文化遗产的相关信息：\n"]
    for item in items:
        name = item.get("name", "")
        cat = item.get("category", "")
        desc = item.get("description", "")
        region = item.get("region", "")
        unesco = " ★UNESCO" if item.get("unesco") else ""
        line = f"**{name}**{unesco}"
        if cat:
            line += f" [{cat}]"
        if region:
            line += f" · 流传地区：{region}"
        if desc:
            line += f"\n{desc[:200]}"
        lines.append(line)
    lines.append("\n点击项目名称可查看详细信息，或前往「搜索」页面按类别、地区筛选。")
    return "\n".join(lines)


# ─── 请求模型 ──────────────────────────────────────────────

class AgentRequest(BaseModel):
    message: str
    history: list = []
    user_id: str = ""
    session_id: str = ""


class AskRequest(BaseModel):
    question: str
    master_id: str = ""
    user_id: str = ""
    session_id: str = ""


class GraphAgentRequest(BaseModel):
    """LangGraph Agent 请求"""
    message: str
    history: list = []
    user_id: str = ""
    session_id: str = ""


# ─── Agent 端点 ─────────────────────────────────────────────

@router.post("/api/agent")
async def api_agent(req: AgentRequest):
    """非遗探索助手 — 对话式 Agent，自动路由到搜索/场馆/旅行工具。"""
    import time as _time
    from heritage_master.observability.tracer import collector

    started_at = _time.time()
    trace_id = f"tr_{int(started_at)}_{uuid.uuid4().hex[:8]}"
    collector.start_trace(trace_id, user_id=req.user_id or "", session_id=req.session_id or "")

    if not get_llm():
        collector.end_trace(trace_id, status="failed")
        return JSONResponse({"error": "LLM 未配置"}, status_code=503)

    # 组装 messages — 注入个性化上下文（聚合所有大师的画像和记忆）
    system_prompt = AGENT_SYSTEM_PROMPT
    if req.user_id:
        try:
            mm = get_memory_manager()
            # 加载所有大师的独立记忆上下文
            all_profiles = user_manager.get_all_profiles(req.user_id)
            for p in all_profiles:
                mid = p.get("master_id", "")
                if mid == "explorer":
                    continue
                mem_ctx = mm.get_memory_context(mid, req.user_id)
                if mem_ctx:
                    system_prompt += "\n\n" + mem_ctx
            # 聚合画像（兴趣标签去重、提问次数累加、性格观察拼接、阶段取最高）
            agg_ctx = user_manager.get_aggregated_profile_context(req.user_id)
            if agg_ctx:
                system_prompt += "\n\n" + agg_ctx
            agg_profile = user_manager.get_aggregated_profile(req.user_id)
            system_prompt += "\n\n" + _build_agent_personalization(agg_profile or {})
        except Exception as e:
            print(f"[agent] 加载用户画像失败: {e}")

    messages = [{"role": "system", "content": system_prompt}]
    for h in req.history:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": h["content"]})

    # 检测用户是否在选择方案，如果是则增强消息
    enhanced_msg = _detect_selection(req.message, req.history)
    user_msg_content = enhanced_msg if enhanced_msg else req.message
    messages.append({"role": "user", "content": user_msg_content})

    # 保存用户消息到会话
    if req.user_id and req.session_id:
        try:
            user_manager.add_message(req.session_id, "user", req.message)
        except Exception:
            pass
        # 探索助手也触发阶段检查（用 explorer 作为 master_id）
        try:
            cultivation.increment_question_count(req.user_id, "explorer")
            _check = cultivation.check_stage_transition(req.user_id, "explorer")
            if _check.get("can_transition"):
                cultivation.do_stage_transition(req.user_id, "explorer")
                print(f"[cultivation] 用户 {req.user_id[:8]} 自动升级(explorer): {_check['current_stage']} -> {_check['next_stage']}")
        except Exception:
            pass

    panels = []
    max_rounds = 8  # 防止无限循环
    # 跨轮去重：记录已执行过的工具调用，避免重复调用同名同参数的工具
    global_seen_tools: dict[str, tuple] = {}  # tool_key -> (raw_data, panel_type, tool_text)
    llm_call_count = 0
    tool_call_count = 0

    for _ in range(max_rounds):
        t0 = _time.time()
        resp_data = await _ask_llm_with_tools(messages, AGENT_TOOLS)
        llm_ms = int((_time.time() - t0) * 1000)
        llm_call_count += 1

        if not resp_data or "choices" not in resp_data:
            print(f"[agent] LLM 返回异常: {str(resp_data)[:300]}")
            collector.add_step(trace_id, "llm_call", {"round": llm_call_count, "status": "error", "duration_ms": llm_ms})
            break

        choice = resp_data["choices"][0]
        msg = choice.get("message", {})
        finish_reason = choice.get("finish_reason", "")

        # 记录 LLM 调用
        has_tools = bool(msg.get("tool_calls"))
        collector.add_step(trace_id, "llm_call", {
            "round": llm_call_count,
            "has_tool_calls": has_tools,
            "finish_reason": finish_reason,
            "duration_ms": llm_ms,
        })

        # 调试日志
        if has_tools:
            tool_names = [tc.get("function",{}).get("name","?") for tc in msg["tool_calls"]]
            print(f"[agent] LLM 调用工具: {tool_names}")
        else:
            print(f"[agent] LLM 直接回复 (无工具调用), finish_reason={finish_reason}")

        # 如果有 tool_calls，执行工具
        if has_tools:
            # 先把 assistant 消息（含 tool_calls）加入 messages
            messages.append(msg)

            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                try:
                    arguments = _json.loads(fn.get("arguments", "{}"))
                except Exception:
                    arguments = {}

                tool_key = f"{tool_name}:{_json.dumps(arguments, sort_keys=True, ensure_ascii=False)}"

                if tool_key in global_seen_tools:
                    # 跨轮或同轮重复，复用已有结果
                    raw_data, panel_type, tool_text = global_seen_tools[tool_key]
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_text or "未找到相关结果",
                    })
                    collector.add_step(trace_id, "tool_call", {"tool": tool_name, "cached": True})
                else:
                    # 首次调用，正常执行
                    tool_call_count += 1
                    t1 = _time.time()
                    raw_data, panel_type, tool_text = await _execute_agent_tool(tool_name, arguments)
                    tool_ms = int((_time.time() - t1) * 1000)
                    global_seen_tools[tool_key] = (raw_data, panel_type, tool_text)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": tool_text or "未找到相关结果",
                    })
                    collector.add_step(trace_id, "tool_call", {
                        "tool": tool_name,
                        "args": arguments,
                        "duration_ms": tool_ms,
                        "result_len": len(tool_text) if tool_text else 0,
                    })

                # 收集面板数据（重复调用不重复收集）
                if panel_type and raw_data and tool_key in global_seen_tools:
                    # 只有首次执行时才添加面板（跨轮重复调用不添加）
                    already_has_panel = any(p["data"] is raw_data for p in panels)
                    if not already_has_panel:
                        panels.append({"type": panel_type, "data": raw_data})

            # 继续循环，让 LLM 根据工具结果生成回复
            continue

        # 没有 tool_calls，拿到最终文本回复
        reply = msg.get("content", "")
        break
    else:
        # 循环用完了但 LLM 还在调用工具，根据已有 panels 生成默认回复
        if panels:
            reply = "已为你规划好路线，请查看上方的行程卡片和地图。如需调整路线或了解更多详情，请告诉我！"
        else:
            reply = "抱歉，我暂时无法处理这个请求。"

    # 保存助手回复 + 记忆提取
    if req.user_id and req.session_id:
        try:
            user_manager.add_message(req.session_id, "assistant", reply)
        except Exception:
            pass

    if req.user_id:
        try:
            mm = get_memory_manager()
            me = MemoryExtractor(llm_func=_ask_llm)
            master_id = "explorer"  # 探索助手统一用 explorer 作为 master_id
            existing_memory = mm.load_memory(master_id, req.user_id)

            # 提取核心记忆
            new_memories = await me.extract_from_conversation(
                req.message, reply, master_id, existing_memory
            )
            for mem in new_memories:
                mm.add_core_memory(master_id, req.user_id, mem)

            # 提取话题
            topics = me.extract_topics(req.message + " " + reply, master_id)
            for topic in topics:
                mm.add_conversation_topic(master_id, req.user_id, topic)

            # 记录来访
            if req.session_id:
                mm.add_visit_log(master_id, req.user_id, req.session_id, req.message[:50])

            # 每 5 个问题推断画像更新
            profile = user_manager.get_user_profile(req.user_id, master_id) if req.session_id else None
            if profile and profile.get("question_count", 0) % 5 == 0:
                history = user_manager.get_user_messages(req.user_id, master_id, limit=20)
                updates = await me.infer_profile_updates(history, profile)
                if updates:
                    user_manager.auto_update_profile(req.user_id, master_id, updates)
                    db_profile = user_manager.get_user_profile(req.user_id, master_id)
                    if db_profile:
                        mm.sync_profile_from_db(master_id, req.user_id, db_profile)
        except Exception as e:
            print(f"[memory] 探索助手记忆提取失败: {e}")

    # 结束 trace
    total_ms = int((_time.time() - started_at) * 1000)
    collector.add_step(trace_id, "agent_complete", {
        "llm_calls": llm_call_count,
        "tool_calls": tool_call_count,
        "reply_len": len(reply) if reply else 0,
        "panels_count": len(panels),
    })
    collector.end_trace(trace_id, status="completed", reply_len=len(reply) if reply else 0, total_ms=total_ms)

    return {"reply": reply, "panels": panels, "trace_id": trace_id}


@router.get("/api/agent/greeting")
async def api_agent_greeting(user_id: str = ""):
    """探索助手个性化问候"""
    default_greeting = "你好，我是非遗探索助手，可以帮你发现、了解和体验中国非物质文化遗产。"
    if not user_id:
        return {"greeting": default_greeting, "interests": [], "recent_topic": ""}

    try:
        mm = get_memory_manager()
        ctx = mm.get_greeting_context("explorer", user_id)

        from heritage_master.tools.memory import GreetingGenerator
        gg = GreetingGenerator()
        # 构建临时 memory 结构供 GreetingGenerator 使用（使用聚合画像）
        profile = user_manager.get_aggregated_profile(user_id) or {}
        memory_data = {
            "profile": {
                "relationship_stage": profile.get("relationship_stage", ctx.get("relationship_stage", "入门期")),
                "last_talk_at": "",
                "interest_tags": profile.get("interest_tags", []),
                "question_count": profile.get("question_count", ctx.get("question_count", 0)),
            },
            "core_memories": ctx.get("recent_memory", []),
            "data_records": {
                "conversation_topics": ctx.get("recent_topics", []),
                "visit_log": [] if ctx.get("is_first") else [{"date": ""}],
            },
            "teaching_progress": ctx.get("teaching_progress", {}),
        }
        greeting = gg.generate_greeting("explorer", memory_data)

        # 提取兴趣和近期话题供前端使用
        interests = profile.get("interest_tags", [])
        recent_topic = ""
        if ctx.get("recent_topics"):
            recent_topic = ctx["recent_topics"][0].get("topic", "")

        return {"greeting": greeting, "interests": interests, "recent_topic": recent_topic}
    except Exception as e:
        print(f"[agent] 问候生成失败: {e}")
        return {"greeting": default_greeting, "interests": [], "recent_topic": ""}


@router.get("/api/agent/conversations")
async def api_agent_conversations(user_id: str = ""):
    """获取用户的探索助手对话历史列表"""
    if not user_id:
        return JSONResponse({"error": "缺少 user_id"}, status_code=400)

    try:
        sessions = user_manager.get_user_sessions(user_id, "explorer")
        result = []
        for s in sessions:
            messages = user_manager.get_recent_messages(s["id"], limit=100)
            result.append({
                "session_id": s["id"],
                "topic_summary": s.get("topic_summary", ""),
                "started_at": s.get("started_at", ""),
                "message_count": len(messages),
            })
        return {"conversations": result}
    except Exception as e:
        print(f"[agent] 获取对话历史失败: {e}")
        return {"conversations": []}


@router.get("/api/agent/conversations/{session_id}")
async def api_agent_conversation_detail(session_id: str):
    """获取单个会话的完整消息列表"""
    try:
        messages = user_manager.get_recent_messages(session_id, limit=100)
        return {"session_id": session_id, "messages": messages}
    except Exception as e:
        print(f"[agent] 获取会话详情失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── 知识问答 ──────────────────────────────────────────────

@router.post("/api/ask")
async def api_ask(req: AskRequest):
    """知识问答 - 搜索数据 + LLM 生成回答"""
    # 0. 保存用户消息到会话
    if req.user_id and req.session_id:
        user_manager.add_message(req.session_id, "user", req.question)
        # 更新修行系统中的提问计数
        master_id_for_cultivation = req.master_id or "chagongfu"
        cultivation.increment_question_count(req.user_id, master_id_for_cultivation)
        # 自动检查阶段升级（满足条件时静默升级）
        try:
            _check = cultivation.check_stage_transition(req.user_id, master_id_for_cultivation)
            if _check.get("can_transition"):
                cultivation.do_stage_transition(req.user_id, master_id_for_cultivation)
                print(f"[cultivation] 用户 {req.user_id[:8]} 自动升级: {_check['current_stage']} -> {_check['next_stage']}")
        except Exception as _e:
            print(f"[cultivation] 阶段检查异常: {_e}")

    # 1. 搜索相关非遗数据作为上下文（并行搜索关键词）
    keywords = _extract_keywords(req.question)

    if keywords:
        search_tasks = [search_heritage_data(query=kw, limit=5) for kw in keywords]
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        seen_names = set()
        context_items = []
        for r in search_results:
            if isinstance(r, list):
                for item in r:
                    if item["name"] not in seen_names:
                        seen_names.add(item["name"])
                        context_items.append(item)
    else:
        context_items = []

    if not context_items:
        for cat in CATEGORIES:
            if cat in req.question:
                context_items = await search_heritage_data(category=cat, limit=5)
                break

    if not context_items:
        context_items = await search_heritage_data(limit=8)

    # 2. 构建上下文文本
    context_parts = []
    for item in context_items:
        parts = [f"项目：{item.get('name', '')}"]
        if item.get("category"):
            parts.append(f"类别：{item['category']}")
        if item.get("region"):
            parts.append(f"地区：{item['region']}")
        if item.get("batch"):
            parts.append(f"批次：{item['batch']}")
        if item.get("description"):
            parts.append(f"简介：{item['description']}")
        context_parts.append(" | ".join(parts))
    context = "\n".join(context_parts)

    # 3. 构建 prompt（有用户画像时使用自适应 prompt，否则使用静态 prompt）
    master_id = req.master_id or "chagongfu"
    if req.user_id:
        user_profile = user_manager.get_user_profile(req.user_id, master_id)
        conversation_summary = user_manager.get_conversation_summary(req.user_id, master_id, limit=10)
        # 加载长期记忆上下文
        mm = get_memory_manager()
        memory_context = mm.get_memory_context(master_id, req.user_id)
        messages = _build_adaptive_prompt(
            master_id=master_id,
            question=req.question,
            user_profile=user_profile,
            conversation_summary=conversation_summary,
            context_items=context_items or None,
            news=[],
            memory_context=memory_context,
        )
    else:
        messages = _build_qa_prompt(req.question, context_items or None, news=[], master_id=req.master_id)
    llm_answer = await _ask_llm(req.question, context, messages=messages)
    if llm_answer:
        # 保存大师回复到会话
        if req.user_id and req.session_id:
            user_manager.add_message(req.session_id, "assistant", llm_answer)

        # 5. 提取记忆（异步，不阻塞响应）
        if req.user_id:
            try:
                mm = get_memory_manager()
                me = MemoryExtractor(llm_func=_ask_llm)
                existing_memory = mm.load_memory(master_id, req.user_id)
                new_memories = await me.extract_from_conversation(
                    req.question, llm_answer, master_id, existing_memory
                )
                for mem in new_memories:
                    mm.add_core_memory(master_id, req.user_id, mem)

                # 提取话题
                topics = me.extract_topics(req.question + " " + llm_answer, master_id)
                for topic in topics:
                    mm.add_conversation_topic(master_id, req.user_id, topic)

                # 每 5 个问题推断画像更新
                if user_profile and user_profile.get("question_count", 0) % 5 == 0:
                    history = user_manager.get_user_messages(req.user_id, master_id, limit=20)
                    updates = await me.infer_profile_updates(history, user_profile or {})
                    if updates:
                        user_manager.auto_update_profile(req.user_id, master_id, updates)
                        db_profile = user_manager.get_user_profile(req.user_id, master_id)
                        if db_profile:
                            mm.sync_profile_from_db(master_id, req.user_id, db_profile)

                # 检查是否需要整理记忆
                if mm.check_consolidation(master_id, req.user_id):
                    await mm.consolidate_memories(master_id, req.user_id, _ask_llm)
            except Exception as e:
                print(f"[memory] 记忆提取失败: {e}")

        return {"answer": llm_answer}

    # 5. LLM 不可用时，降级为知识库 + 搜索结果展示
    answer = await ask_heritage_expert(req.question)
    if "暂未找到" in answer and context_items:
        answer = _build_answer(req.question, keywords, context_items)

    # 保存大师回复到会话
    if req.user_id and req.session_id:
        user_manager.add_message(req.session_id, "assistant", answer)

    return {"answer": answer}


# ─── LangGraph Agent ──────────────────────────────────────

@router.post("/api/agent/graph")
async def api_agent_graph(req: GraphAgentRequest):
    """LangGraph Agent — 基于 StateGraph 的探索助手。

    与 /api/agent 功能相同，但使用 LangGraph 编排引擎：
    - 自动路由到搜索/场馆/路线/图谱/活动工具
    - 支持多轮工具调用（最多5轮）
    - 自动提取记忆和个性化
    - 结构化面板数据（供前端渲染卡片/地图）
    """
    if not get_llm():
        return JSONResponse({"error": "LLM 未配置"}, status_code=503)

    try:
        from heritage_master.agent.graph import run_heritage_agent

        # 构建系统提示词（含个性化，聚合所有大师的画像和记忆）
        system_prompt = AGENT_SYSTEM_PROMPT
        if req.user_id:
            try:
                mm = get_memory_manager()
                # 加载所有大师的独立记忆上下文
                all_profiles = user_manager.get_all_profiles(req.user_id)
                for p in all_profiles:
                    mid = p.get("master_id", "")
                    if mid == "explorer":
                        continue
                    mem_ctx = mm.get_memory_context(mid, req.user_id)
                    if mem_ctx:
                        system_prompt += "\n\n" + mem_ctx
                # 聚合画像（兴趣标签去重、提问次数累加、性格观察拼接、阶段取最高）
                agg_ctx = user_manager.get_aggregated_profile_context(req.user_id)
                if agg_ctx:
                    system_prompt += "\n\n" + agg_ctx
                agg_profile = user_manager.get_aggregated_profile(req.user_id)
                system_prompt += "\n\n" + _build_agent_personalization(agg_profile or {})
            except Exception as e:
                print(f"[agent] 加载用户画像失败: {e}")

        result = await run_heritage_agent(
            message=req.message,
            history=req.history,
            user_id=req.user_id,
            session_id=req.session_id,
            system_prompt=system_prompt,
        )

        return {"reply": result["reply"], "panels": result["panels"], "trace_id": result.get("trace_id", "")}

    except ImportError as e:
        print(f"[langgraph] 模块导入失败: {e}")
        return JSONResponse({"error": "LangGraph 模块未安装，请执行: pip install langgraph langchain-openai"}, status_code=503)
    except Exception as e:
        print(f"[langgraph] Agent 执行失败: {e}")
        return JSONResponse({"error": f"Agent 执行失败: {e}"}, status_code=500)


@router.post("/api/agent/graph/stream")
async def api_agent_graph_stream(req: GraphAgentRequest):
    """LangGraph Agent 流式版本 — SSE 逐事件推送。

    事件类型：
    - tool_start: 工具开始执行
    - tool_end: 工具执行完成
    - text_delta: 文本增量
    - done: 完成（含 reply 和 panels）
    """
    if not get_llm():
        return JSONResponse({"error": "LLM 未配置"}, status_code=503)

    async def event_generator():
        try:
            from heritage_master.agent.graph import run_heritage_agent_stream

            system_prompt = AGENT_SYSTEM_PROMPT
            if req.user_id:
                try:
                    mm = get_memory_manager()
                    # 加载所有大师的独立记忆上下文
                    all_profiles = user_manager.get_all_profiles(req.user_id)
                    for p in all_profiles:
                        mid = p.get("master_id", "")
                        if mid == "explorer":
                            continue
                        mem_ctx = mm.get_memory_context(mid, req.user_id)
                        if mem_ctx:
                            system_prompt += "\n\n" + mem_ctx
                    # 聚合画像（兴趣标签去重、提问次数累加、性格观察拼接、阶段取最高）
                    agg_ctx = user_manager.get_aggregated_profile_context(req.user_id)
                    if agg_ctx:
                        system_prompt += "\n\n" + agg_ctx
                    agg_profile = user_manager.get_aggregated_profile(req.user_id)
                    system_prompt += "\n\n" + _build_agent_personalization(agg_profile or {})
                except Exception as e:
                    print(f"[agent] 加载用户画像失败: {e}")
                    pass

            async for event in run_heritage_agent_stream(
                message=req.message,
                history=req.history,
                user_id=req.user_id,
                session_id=req.session_id,
                system_prompt=system_prompt,
            ):
                yield f"data: {_json.dumps(event, ensure_ascii=False)}\n\n"

        except ImportError as e:
            yield f"data: {_json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
