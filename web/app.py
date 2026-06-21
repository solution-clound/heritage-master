from __future__ import annotations

from typing import List, Optional

"""
非遗大师 Web 应用 - FastAPI 后端

提供 JSON API 并托管 Vue 前端静态文件。
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# 将 src 目录加入 sys.path，以便导入 heritage_master 包
_project_root = Path(__file__).resolve().parent.parent
_src_dir = str(_project_root / "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from heritage_master.data.crawler import (
    CATEGORIES,
    crawl_baike,
    get_heritage_detail,
    search_heritage_data,
)
from heritage_master.data.realtime import get_heritage_news, get_heritage_events, get_news_for_context
from heritage_master.tools.venue_finder import search_venues_amap, get_venue_detail
from heritage_master.tools.knowledge_base import ask_heritage_expert, get_knowledge
from heritage_master.tools.route_planner import plan_heritage_route
from heritage_master.tools.agent_tools import AGENT_SYSTEM_PROMPT, AGENT_TOOLS
from heritage_master.tools import forum
from heritage_master.data.db import init_db as _init_db
from heritage_master.tools import user_manager
from heritage_master.tools.memory import MemoryManager, MemoryExtractor, GreetingGenerator

app = FastAPI(title="非遗大师", version="1.0.0")

# 初始化 SQLite 数据库
_init_db()

# 记忆系统单例
_memory_manager: MemoryManager | None = None


def get_memory_manager() -> MemoryManager:
    global _memory_manager
    if _memory_manager is None:
        redis_client = None
        try:
            from heritage_master.config import settings
            if settings.redis_enabled:
                import redis
                redis_client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db,
                    password=settings.redis_password or None,
                    decode_responses=True,
                )
                redis_client.ping()
        except Exception:
            redis_client = None
        _memory_manager = MemoryManager(redis_client=redis_client)
    return _memory_manager

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── LLM 配置 ───────────────────────────────────────────
import os
import httpx as _httpx

_LLM_API_KEY = os.getenv("HERITAGE_LLM_API_KEY", "")
_LLM_BASE_URL = os.getenv("HERITAGE_LLM_BASE_URL", "https://api.deepseek.com/v1")
_LLM_MODEL = os.getenv("HERITAGE_LLM_MODEL", "deepseek-chat")

# 大师人设（从 master_prompt 模块导入，MCP 和 Web 共用）
from heritage_master.tools.master_prompt import (
    MASTER_SYSTEM_PROMPT,
    build_qa_prompt as _build_qa_prompt,
    build_adaptive_prompt as _build_adaptive_prompt,
    get_adaptive_greeting as _get_adaptive_greeting,
    list_masters as _list_masters,
    get_master_prompt as _get_master_prompt,
)

_LLM_SYSTEM_PROMPT = MASTER_SYSTEM_PROMPT


async def _ask_llm(question: str, context: str = "", messages: list = None) -> str | None:
    """调用 LLM 生成回答。支持传入自定义 messages 或自动构建。"""
    if not _LLM_API_KEY:
        return None

    if messages is None:
        user_msg = f"参考资料：\n{context}\n\n用户问题：{question}" if context else question
        messages = [
            {"role": "system", "content": _LLM_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

    try:
        async with _httpx.AsyncClient(timeout=60, trust_env=False) as client:
            resp = await client.post(
                f"{_LLM_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {_LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _LLM_MODEL,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 2000,
                },
            )
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[LLM] 调用失败: {e}")
        return None


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


async def _ask_llm_with_tools(messages: list, tools: list) -> dict:
    """调用 LLM 支持 function calling，返回原始 response dict。

    返回 DeepSeek/OpenAI 格式的 response JSON。
    """
    if not _LLM_API_KEY:
        return {}

    try:
        async with _httpx.AsyncClient(timeout=60, trust_env=False) as client:
            resp = await client.post(
                f"{_LLM_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {_LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": _LLM_MODEL,
                    "messages": messages,
                    "tools": tools,
                    "temperature": 0.7,
                    "max_tokens": 2000,
                },
            )
            return resp.json()
    except Exception as e:
        print(f"[LLM-Tools] 调用失败: {e}")
        return {}


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
            city=arguments["city"],
            keyword=arguments.get("keyword", "非遗"),
            limit=10,
        )
        from heritage_master.tools.venue_finder import format_venue_list
        text = format_venue_list(venues, arguments["city"])
        return venues, "venue_list", text

    elif tool_name == "plan_trip":
        result = await plan_heritage_route(
            city=arguments["city"],
            days=arguments.get("days", 2),
            interests=arguments.get("interests"),
        )
        text = result["itinerary"]
        route_data = result.get("route_data")
        return {"city": arguments["city"], "days": arguments.get("days", 2), "itinerary": text, "route_data": route_data}, "trip_plan", text

    elif tool_name == "query_knowledge_graph":
        from heritage_master.data.knowledge_graph import search_nodes, get_node, get_neighbors
        results = search_nodes(
            arguments["query"],
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
        person_name = arguments["person_name"]
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

    return None, None, "工具调用失败"


class AgentRequest(BaseModel):
    message: str
    history: list = []
    user_id: str = ""
    session_id: str = ""


def _merge_panels(panels: list) -> list:
    """合并同类型面板，避免多个 venue_list、heritage_list 等。"""
    if not panels:
        return panels

    merged = {}
    order = []
    for p in panels:
        ptype = p.get("type", "")
        if ptype in ("venue_list", "heritage_list"):
            if ptype not in merged:
                merged[ptype] = []
                order.append(ptype)
            data = p.get("data", [])
            if isinstance(data, list):
                merged[ptype].extend(data)
        else:
            # 其他类型面板保持不变
            key = f"{ptype}_{id(p)}"
            merged[key] = p
            order.append(key)

    result = []
    for key in order:
        if key in merged:
            val = merged[key]
            if isinstance(val, list):
                # 去重（按 id 字段）
                seen = set()
                deduped = []
                for item in val:
                    item_id = item.get("id", "") if isinstance(item, dict) else ""
                    if item_id and item_id in seen:
                        continue
                    if item_id:
                        seen.add(item_id)
                    deduped.append(item)
                result.append({"type": key, "data": deduped})
            else:
                result.append(val)

    return result


@app.post("/api/agent")
async def api_agent(req: AgentRequest):
    """非遗探索助手 — 对话式 Agent，自动路由到搜索/场馆/旅行工具。"""
    import time as _time
    import uuid as _uuid
    from heritage_master.observability.tracer import collector

    started_at = _time.time()
    trace_id = f"tr_{int(started_at)}_{_uuid.uuid4().hex[:8]}"
    collector.start_trace(trace_id, user_id=req.user_id or "", session_id=req.session_id or "")

    if not _LLM_API_KEY:
        collector.end_trace(trace_id, status="failed")
        return JSONResponse({"error": "LLM 未配置"}, status_code=503)

    # 组装 messages — 注入个性化上下文（聚合所有大师的画像）
    system_prompt = AGENT_SYSTEM_PROMPT
    if req.user_id:
        try:
            mm = get_memory_manager()
            # 聚合画像（兴趣标签去重、提问次数累加、性格观察拼接、阶段取最高）
            agg_ctx = user_manager.get_aggregated_profile_context(req.user_id)
            agg_profile = user_manager.get_aggregated_profile(req.user_id)
            memory_ctx = mm.get_memory_context("explorer", req.user_id)
            if memory_ctx:
                system_prompt += "\n\n" + memory_ctx
            if agg_ctx:
                system_prompt += "\n\n" + agg_ctx
            system_prompt += "\n\n" + _build_agent_personalization(agg_profile or {})
        except Exception:
            pass

    messages = [{"role": "system", "content": system_prompt}]
    for h in req.history:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": req.message})

    # 保存用户消息到会话
    if req.user_id and req.session_id:
        try:
            user_manager.add_message(req.session_id, "user", req.message)
        except Exception:
            pass

    panels = []
    max_rounds = 5  # 防止无限循环
    llm_call_count = 0
    tool_call_count = 0

    for _ in range(max_rounds):
        t0 = _time.time()
        resp_data = await _ask_llm_with_tools(messages, AGENT_TOOLS)
        llm_ms = int((_time.time() - t0) * 1000)
        llm_call_count += 1

        if not resp_data or "choices" not in resp_data:
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

        # 如果有 tool_calls，执行工具
        if has_tools:
            # 先把 assistant 消息（含 tool_calls）加入 messages
            messages.append(msg)

            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                try:
                    arguments = __import__("json").loads(fn.get("arguments", "{}"))
                except Exception:
                    arguments = {}

                raw_data, panel_type, tool_text = await _execute_agent_tool(tool_name, arguments)
                tool_ms = int((_time.time() - t0) * 1000) if 't0' in dir() else 0
                tool_call_count += 1

                # 添加 tool result 到 messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_text or "未找到相关结果",
                })

                # 记录工具调用
                collector.add_step(trace_id, "tool_call", {
                    "tool": tool_name,
                    "args": arguments,
                    "duration_ms": tool_ms,
                    "result_len": len(tool_text) if tool_text else 0,
                })

                # 收集面板数据
                if panel_type and raw_data:
                    panels.append({"type": panel_type, "data": raw_data})

            # 继续循环，让 LLM 根据工具结果生成回复
            continue

        # 没有 tool_calls，拿到最终文本回复
        reply = msg.get("content", "")
        break
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

    # 合并同类型面板（避免多个 venue_list、heritage_list）
    merged_panels = _merge_panels(panels)

    return {"reply": reply, "panels": merged_panels, "trace_id": trace_id}


@app.get("/api/agent/greeting")
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
        # 构建临时 memory 结构供 GreetingGenerator 使用
        profile = user_manager.get_user_profile(user_id, "explorer") or {}
        memory_data = {
            "profile": {
                "relationship_stage": ctx.get("relationship_stage", "试探期"),
                "last_talk_at": "",
                "interest_tags": profile.get("interest_tags", []),
                "question_count": ctx.get("question_count", 0),
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


@app.get("/api/agent/conversations")
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


@app.get("/api/agent/conversations/{session_id}")
async def api_agent_conversation_detail(session_id: str):
    """获取单个会话的完整消息列表"""
    try:
        messages = user_manager.get_recent_messages(session_id, limit=100)
        return {"session_id": session_id, "messages": messages}
    except Exception as e:
        print(f"[agent] 获取会话详情失败: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ─── API 路由 ───────────────────────────────────────────

@app.get("/api/categories")
async def api_categories():
    """返回非遗十大类别"""
    return {"categories": CATEGORIES}


@app.get("/api/search")
async def api_search(
    query: str = Query("", description="搜索关键词"),
    category: str = Query("", description="非遗类别"),
    region: str = Query("", description="地区"),
    limit: int = Query(10, ge=1, le=50),
    enrich: bool = Query(False, description="是否用 LLM 增强内容"),
):
    """搜索非遗项目"""
    items = await search_heritage_data(query=query, category=category, region=region, limit=limit)

    # 如果开启增强，用 LLM 为每个项目生成丰富描述
    if enrich and items and _LLM_API_KEY:
        enriched = await _enrich_search_results(items, query, region)
        return {"items": enriched, "total": len(enriched)}

    return {"items": items, "total": len(items)}


async def _enrich_search_results(items: list[dict], query: str, region: str) -> list[dict]:
    """用 LLM 增强搜索结果的内容"""
    import asyncio

    async def enrich_one(item: dict) -> dict:
        name = item.get("name", "")
        # 收集上下文：知识库 + 元数据
        knowledge = await get_knowledge(name, "overview")
        meta_parts = []
        if item.get("category"):
            meta_parts.append(f"类别：{item['category']}")
        if item.get("region"):
            meta_parts.append(f"地区：{item['region']}")
        if item.get("batch"):
            meta_parts.append(f"批次：{item['batch']}")
        meta_text = " | ".join(meta_parts)

        prompt = f"""基于以下真实资料，用 2-3 句话介绍「{name}」这个非遗项目。
要求：语言自然流畅，突出特色和价值。不要编造信息，只基于提供的资料整理。

项目元数据：{meta_text}
知识库资料：{knowledge[:500] if knowledge else '无'}

请用中文回答，2-3句话即可："""

        answer = await _ask_llm(prompt)
        if answer:
            item["description"] = answer
            item["enriched"] = True
        return item

    # 并发处理，但限制并发数
    semaphore = asyncio.Semaphore(3)

    async def limited_enrich(item):
        async with semaphore:
            return await enrich_one(item)

    results = await asyncio.gather(*[limited_enrich(item) for item in items])
    return list(results)


@app.get("/api/search/enriched")
async def api_search_enriched(
    query: str = Query("", description="搜索关键词"),
    category: str = Query("", description="非遗类别"),
    region: str = Query("", description="地区"),
    limit: int = Query(8, ge=1, le=20),
):
    """组合接口：返回项目搜索结果 + 相关活动 + 路径规划建议"""
    # 1. 搜索非遗项目
    items = await search_heritage_data(query=query, category=category, region=region, limit=limit)

    # 2. 用 LLM 增强描述
    if items and _LLM_API_KEY:
        items = await _enrich_search_results(items, query, region)

    # 3. 获取相关活动
    events = await get_heritage_events(keyword=query, region=region, limit=5)

    # 4. 获取相关场馆（如果有城市信息）
    venues = []
    if region:
        try:
            venues = await search_venues_amap(city=region, keyword=query or "非遗", limit=5)
        except Exception:
            pass

    # 5. 构建路线建议提示
    route_hint = None
    if venues and len(venues) >= 2:
        route_hint = {
            "message": f"找到 {len(venues)} 个相关场馆，可规划参观路线",
            "venues": [v.get("name", "") for v in venues[:5]],
            "city": region,
            "suggestion": "使用 /api/trip 接口规划详细路线",
        }

    return {
        "items": items,
        "events": events,
        "venues": venues,
        "route_hint": route_hint,
        "total_projects": len(items),
        "total_events": len(events),
        "note": "项目数据来自中国非遗网，活动数据可能因网站改版而受限",
    }


@app.get("/api/project/{name}")
async def api_project_detail(name: str):
    """获取非遗项目详情"""
    detail = await get_heritage_detail(name)
    return {"project": detail}


@app.get("/api/venues")
async def api_venues(
    city: str = Query(..., description="城市名"),
    keyword: str = Query("非遗", description="搜索关键词"),
    limit: int = Query(10, ge=1, le=25),
):
    """查找非遗场馆"""
    from heritage_master.config import settings
    venues = await search_venues_amap(city=city, keyword=keyword, limit=limit)
    # 为没有照片的场馆生成静态地图图片 URL
    amap_key = settings.amap_key
    for v in venues:
        if not v.get("photos") and v.get("lng") and v.get("lat") and amap_key:
            v["map_img"] = (
                f"https://restapi.amap.com/v3/staticmap?"
                f"location={v['lng']},{v['lat']}&zoom=15&size=400*200"
                f"&markers=mid,0xFF0000:{v['lng']},{v['lat']}&key={amap_key}"
            )
    return {"venues": venues, "city": city}


@app.get("/api/venue/detail")
async def api_venue_detail(
    poi_id: str = Query(..., description="高德 POI ID"),
):
    """获取场馆详情"""
    detail = await get_venue_detail(poi_id)
    # 添加静态地图图片
    if detail and not detail.get("photos") and detail.get("lng") and detail.get("lat"):
        from heritage_master.config import settings
        if settings.amap_key:
            detail["map_img"] = (
                f"https://restapi.amap.com/v3/staticmap?"
                f"location={detail['lng']},{detail['lat']}&zoom=16&size=600*300"
                f"&markers=mid,0xFF0000:{detail['lng']},{detail['lat']}&key={settings.amap_key}"
            )
    return {"detail": detail}


@app.get("/api/masters")
async def api_masters():
    """列出所有可选的非遗大师"""
    masters = _list_masters()
    return {"masters": masters}


@app.get("/api/masters/{master_id}/greeting")
async def api_master_greeting(master_id: str, user_id: str = Query("")):
    """获取大师问候语（围绕每日功课展开）

    优先使用每日功课问候，降级为记忆增强问候。
    """
    if user_id:
        # 优先：每日功课问候
        daily = await cultivation.get_daily_greeting(user_id, master_id)
        if daily and daily.get("greeting"):
            return {
                "greeting": daily["greeting"],
                "today_practice": daily.get("today_practice", ""),
                "practice_date": daily.get("practice_date", ""),
            }

        # 降级：记忆增强问候
        mm = get_memory_manager()
        memory = mm.load_memory(master_id, user_id)
        gg = GreetingGenerator()
        greeting = gg.generate_greeting(master_id, memory)
        stage = memory["profile"].get("relationship_stage", "试探期")
        return {"greeting": greeting, "stage": stage}

    stage = "试探期"
    greeting = _get_adaptive_greeting(master_id, stage)
    return {"greeting": greeting, "stage": stage}


class AskRequest(BaseModel):
    question: str
    master_id: str = ""
    user_id: str = ""
    session_id: str = ""


import re as _re


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


@app.post("/api/ask")
async def api_ask(req: AskRequest):
    """知识问答 - 搜索数据 + LLM 生成回答"""
    # 0. 保存用户消息到会话
    if req.user_id and req.session_id:
        user_manager.add_message(req.session_id, "user", req.question)
        # 更新修行系统中的提问计数
        cultivation.increment_question_count(req.user_id, req.master_id or "chagongfu")

    # 1. 搜索相关非遗数据作为上下文（并行搜索关键词）
    import asyncio as _asyncio
    keywords = _extract_keywords(req.question)

    if keywords:
        search_tasks = [search_heritage_data(query=kw, limit=5) for kw in keywords]
        search_results = await _asyncio.gather(*search_tasks, return_exceptions=True)
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

    # 1.5 搜索论坛帖子作为补充上下文
    forum_context = ""
    try:
        from heritage_master.tools.forum import search_posts, list_posts
        import re as _re

        # 从问题中提取搜索词：先提取完整中文段，再用 2-gram 切词
        full_segments = _re.findall(r'[\u4e00-\u9fff]+', req.question)
        stops = {"什么", "怎么", "可以", "有人", "论坛", "讨论", "有没有", "一下",
                 "知道", "想问", "请问", "帮我", "看看", "里有", "人讨", "论昆",
                 "曲吗", "坛里", "吗", "呢", "吧", "啊", "呀"}
        search_terms = []
        for seg in full_segments:
            for i in range(len(seg) - 1):
                w = seg[i:i+2]
                if w not in stops and w not in search_terms:
                    search_terms.append(w)
        # 也加上 _extract_keywords 提取的关键词
        if keywords:
            for kw in keywords:
                if kw not in search_terms and len(kw) >= 2:
                    search_terms.append(kw)
        search_terms = search_terms[:8]  # 最多搜 8 个词

        forum_posts = []
        for term in search_terms:
            posts = search_posts(keyword=term, limit=3)
            if posts:
                forum_posts.extend(posts)
                break  # 命中就停

        if forum_posts:
            seen_ids = set()
            unique_posts = []
            for p in forum_posts:
                pid = p.get("id", "")
                if pid not in seen_ids:
                    seen_ids.add(pid)
                    unique_posts.append(p)
            forum_lines = []
            for p in unique_posts[:5]:
                title = p.get("title", "")
                content = p.get("content", "")[:80]
                category = p.get("category", "讨论")
                author = p.get("author_nickname", "匿名")
                forum_lines.append(f"【{category}】{title} — {content}（作者：{author}）")
            forum_context = "相关论坛讨论：\n" + "\n".join(forum_lines)
        else:
            # 没搜到，明确告诉 LLM 论坛中暂无相关讨论
            query_hint = req.question[:20]
            forum_context = f"论坛中暂无关于「{query_hint}」的讨论帖子。"
    except Exception as e:
        # 论坛搜索出错，记录但不影响主流程
        forum_context = ""
        import logging
        logging.getLogger("heritage").warning("[ask] 论坛搜索异常: %s", e)

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
    if forum_context:
        context = context + "\n\n" + forum_context

    # 3. 获取实时新闻/活动数据
    news = get_news_for_context(req.question, limit=5)

    # 4. 构建 prompt（有用户画像时使用自适应 prompt，否则使用静态 prompt）
    master_id = req.master_id or "chagongfu"

    # 论坛数据直接追加到问题中（确保 LLM 一定能看到）
    effective_question = req.question
    if forum_context and "相关论坛讨论" in forum_context:
        effective_question = req.question + "\n\n[论坛相关数据]\n" + forum_context

    if req.user_id:
        user_profile = user_manager.get_user_profile(req.user_id, master_id)
        conversation_summary = user_manager.get_conversation_summary(req.user_id, master_id, limit=10)
        # 加载长期记忆上下文
        mm = get_memory_manager()
        memory_context = mm.get_memory_context(master_id, req.user_id)
        messages = _build_adaptive_prompt(
            master_id=master_id,
            question=effective_question,
            user_profile=user_profile,
            conversation_summary=conversation_summary,
            context_items=context_items or None,
            news=news,
            memory_context=memory_context,
        )
    else:
        messages = _build_qa_prompt(effective_question, context_items or None, news=news, master_id=req.master_id)

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
                # 用关键词再搜一次
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


@app.get("/api/knowledge")
async def api_knowledge(
    name: str = Query(..., description="项目名称"),
    aspect: str = Query("overview", description="方面"),
):
    """获取项目知识"""
    content = await get_knowledge(name=name, aspect=aspect)
    return {"content": content, "name": name, "aspect": aspect}


@app.get("/api/baike/{keyword}")
async def api_baike(keyword: str):
    """百度百科信息"""
    data = await crawl_baike(keyword)
    return {"data": data}


# ─── 论坛 API（SQLite）─────────────────────────────────────

class ForumCreateRequest(BaseModel):
    title: str
    content: str
    category: str = "experience"
    images: List[str] = []
    route_id: str = ""
    user_id: str


class ForumCommentRequest(BaseModel):
    user_id: str
    content: str
    parent_id: Optional[int] = None


@app.get("/api/forum/posts")
async def api_forum_list(
    category: str = Query(None),
    user_id: str = Query(None),
    cursor: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
    viewer_id: str = Query(None),
):
    """帖子列表"""
    import asyncio
    return await asyncio.to_thread(
        forum.list_posts, category=category, user_id=user_id,
        cursor=cursor, limit=limit, viewer_id=viewer_id
    )


@app.get("/api/forum/posts/{post_id}")
async def api_forum_get_post(post_id: str, viewer_id: str = Query(None)):
    """帖子详情"""
    import asyncio
    post = await asyncio.to_thread(forum.get_post, post_id, viewer_id=viewer_id)
    if not post:
        return JSONResponse({"error": "帖子不存在"}, status_code=404)
    return {"post": post}


@app.post("/api/forum/posts")
async def api_forum_create(req: ForumCreateRequest):
    """发帖"""
    import asyncio
    if not req.title.strip() or not req.content.strip():
        return JSONResponse({"error": "标题和内容不能为空"}, status_code=400)

    def _create():
        # 如果附加了路线，从 saved_routes 查出数据
        route_data = {}
        if req.route_id:
            from heritage_master.data.db import get_conn as _get_conn
            with _get_conn() as conn:
                row = conn.execute("SELECT * FROM saved_routes WHERE id=?", (req.route_id,)).fetchone()
                if row:
                    route_data = {
                        "route_id": row["id"],
                        "name": row["name"],
                        "city": row["city"],
                        "days": row["days"],
                        "itinerary": row["itinerary"],
                    }
                    try:
                        route_data.update(json.loads(row["route_data"]) if row["route_data"] else {})
                    except Exception:
                        pass
        return forum.create_post(user_id=req.user_id, title=req.title.strip(),
                                 content=req.content, category=req.category,
                                 images=req.images, route_data=route_data or None)
    post = await asyncio.to_thread(_create)
    return {"post": post}


@app.delete("/api/forum/posts/{post_id}")
async def api_forum_delete(post_id: str, user_id: str = Query(...)):
    """删帖"""
    import asyncio
    ok = await asyncio.to_thread(forum.delete_post, post_id, user_id)
    if not ok:
        return JSONResponse({"error": "删除失败"}, status_code=400)
    return {"ok": True}


@app.post("/api/forum/posts/{post_id}/like")
async def api_forum_like(post_id: str, body: dict = {}):
    """点赞/取消"""
    import asyncio
    user_id = body.get("user_id", "")
    if not user_id:
        return JSONResponse({"error": "需要登录"}, status_code=401)
    return await asyncio.to_thread(forum.toggle_like, post_id, user_id)


@app.get("/api/forum/posts/{post_id}/comments")
async def api_forum_comments(post_id: str, limit: int = Query(50, ge=1, le=200)):
    """评论列表"""
    import asyncio
    comments = await asyncio.to_thread(forum.list_comments, post_id, limit=limit)
    return {"comments": comments}


@app.post("/api/forum/posts/{post_id}/comments")
async def api_forum_add_comment(post_id: str, req: ForumCommentRequest):
    """发评论"""
    import asyncio
    if not req.content.strip():
        return JSONResponse({"error": "内容不能为空"}, status_code=400)
    comment = await asyncio.to_thread(forum.add_comment, post_id, req.user_id, req.content, req.parent_id)
    return {"comment": comment}


@app.delete("/api/forum/comments/{comment_id}")
async def api_forum_delete_comment(comment_id: int, user_id: str = Query(...)):
    """删评论"""
    import asyncio
    ok = await asyncio.to_thread(forum.delete_comment, comment_id, user_id)
    if not ok:
        return JSONResponse({"error": "删除失败"}, status_code=400)
    return {"ok": True}


@app.get("/api/forum/search")
async def api_forum_search(keyword: str = Query(...), limit: int = Query(10, ge=1, le=50)):
    """搜索帖子"""
    import asyncio
    posts = await asyncio.to_thread(forum.search_posts, keyword, limit=limit)
    return {"posts": posts}


# ─── 图片上传 API ───────────────────────────────────────

import uuid as _uuid
import hashlib as _hashlib
from fastapi import File, UploadFile

_UPLOAD_DIR = Path(__file__).parent / "static" / "uploads"
_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_MAX_SIZE = 5 * 1024 * 1024  # 5MB


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    """上传图片，返回可访问的 URL"""
    if file.content_type not in _ALLOWED_TYPES:
        return JSONResponse({"error": "仅支持 jpg/png/gif/webp 格式"}, status_code=400)
    data = await file.read()
    if len(data) > _MAX_SIZE:
        return JSONResponse({"error": "文件大小不能超过 5MB"}, status_code=400)
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    unique = _hashlib.md5(data[:1024]).hexdigest()[:8] + "_" + _uuid.uuid4().hex[:8]
    filename = f"{unique}.{ext}"
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (_UPLOAD_DIR / filename).write_bytes(data)
    return {"url": f"/static/uploads/{filename}"}


# ─── 已保存路线 API ─────────────────────────────────────

from heritage_master.data.db import get_conn


class TripSaveRequest(BaseModel):
    user_id: str
    name: str = ""
    city: str = ""
    days: int = 1
    interests: List[str] = []
    itinerary: str = ""
    route_data: dict = {}


@app.post("/api/trips/save")
async def api_trip_save(req: TripSaveRequest):
    """保存路线"""
    import asyncio
    if not req.user_id:
        return JSONResponse({"error": "需要登录"}, status_code=401)

    def _save():
        route_id = str(_uuid.uuid4())
        name = req.name or f"{req.city} {req.days}日游" if req.city else "我的路线"
        interests_json = json.dumps(req.interests, ensure_ascii=False)
        route_json = json.dumps(req.route_data, ensure_ascii=False)
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO saved_routes (id, user_id, name, city, days, interests, itinerary, route_data) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (route_id, req.user_id, name, req.city, req.days, interests_json, req.itinerary, route_json),
            )
        return {"id": route_id, "name": name}

    return await asyncio.to_thread(_save)


@app.get("/api/trips")
async def api_trips_list(user_id: str = Query(...)):
    """获取用户已保存路线列表"""
    import asyncio

    def _list():
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM saved_routes WHERE user_id=? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            return [{
                "id": r["id"], "name": r["name"], "city": r["city"],
                "days": r["days"],
                "interests": json.loads(r["interests"]) if r["interests"] else [],
                "created_at": r["created_at"],
            } for r in rows]

    return {"routes": await asyncio.to_thread(_list)}


@app.get("/api/trips/{route_id}")
async def api_trip_detail(route_id: str):
    """获取单条路线详情"""
    import asyncio

    def _detail():
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM saved_routes WHERE id=?", (route_id,)).fetchone()
            if not row:
                return None
            return {
                "id": row["id"], "user_id": row["user_id"], "name": row["name"],
                "city": row["city"], "days": row["days"],
                "interests": json.loads(row["interests"]) if row["interests"] else [],
                "itinerary": row["itinerary"],
                "route_data": json.loads(row["route_data"]) if row["route_data"] else {},
                "created_at": row["created_at"],
            }

    route = await asyncio.to_thread(_detail)
    if not route:
        return JSONResponse({"error": "路线不存在"}, status_code=404)
    return {"route": route}


@app.delete("/api/trips/{route_id}")
async def api_trip_delete(route_id: str, user_id: str = Query(...)):
    """删除路线（仅作者）"""
    import asyncio

    def _delete():
        with get_conn() as conn:
            row = conn.execute("SELECT user_id FROM saved_routes WHERE id=?", (route_id,)).fetchone()
            if not row or row["user_id"] != user_id:
                return False
            conn.execute("DELETE FROM saved_routes WHERE id=?", (route_id,))
            return True

    ok = await asyncio.to_thread(_delete)
    if not ok:
        return JSONResponse({"error": "无权删除"}, status_code=403)
        conn.execute("DELETE FROM saved_routes WHERE id=?", (route_id,))
    return {"ok": True}


class TripRequest(BaseModel):
    city: str
    days: int = 1
    interests: List[str] = []
    start_point: str = None


@app.post("/api/trip")
async def api_trip(req: TripRequest):
    """旅行规划"""
    result = await plan_heritage_route(
        city=req.city,
        days=req.days,
        interests=req.interests,
        start_point=req.start_point,
    )
    return {"result": result["itinerary"], "route_data": result.get("route_data")}


@app.get("/api/news")
async def api_news(limit: int = Query(8, ge=1, le=20)):
    """获取最新非遗新闻和活动（仅真实数据）"""
    news = await get_heritage_news(limit=limit)
    return {
        "news": news,
        "source": "中国非遗网 (ihchina.cn)" if news else None,
        "note": "数据来自中国非遗网实时爬取" if news else "暂未获取到实时新闻，请稍后再试",
    }


@app.get("/api/events")
async def api_events(
    keyword: str = Query("", description="搜索关键词（如茶文化、刺绣）"),
    region: str = Query("", description="地区（如广东）"),
    limit: int = Query(10, ge=1, le=30),
):
    """获取非遗活动（展览、工作坊、演出等）"""
    events = await get_heritage_events(keyword=keyword, region=region, limit=limit)
    return {
        "events": events,
        "total": len(events),
        "source": "中国非遗网 (ihchina.cn)" if events else None,
        "note": "数据来自中国非遗网实时爬取，活动链接以来源为准"
        if events
        else "暂未获取到相关活动，请稍后再试或查看其他地区",
    }


@app.get("/api/data-status")
async def api_data_status():
    """返回数据源状态，让用户知道哪些数据是实时的"""
    from heritage_master.data.realtime import get_data_status
    status = get_data_status()
    return {
        "sources": status,
        "summary": {
            "project_search": "ihchina.cn JSON API（实时）",
            "venues": "高德地图 API（实时）",
            "knowledge": "本地知识库（静态，需手动更新）",
            "news": "ihchina.cn HTML 爬取（可能因改版失效）",
        },
    }


@app.get("/api/map-config")
async def api_map_config():
    """返回前端地图所需的高德 JS API 配置"""
    from heritage_master.config import settings
    js_key = settings.amap_js_key or settings.amap_key
    return {
        "key": js_key,
        "security_code": settings.amap_security_code,
        "available": bool(js_key),
    }


# ─── 用户系统 API ───────────────────────────────────────

class RegisterRequest(BaseModel):
    nickname: str
    password: str


class LoginRequest(BaseModel):
    nickname: str
    password: str


class SessionRequest(BaseModel):
    user_id: str
    master_id: str


@app.post("/api/user/register")
async def api_user_register(req: RegisterRequest):
    """注册新用户"""
    if not req.nickname.strip():
        return JSONResponse({"error": "昵称不能为空"}, status_code=400)
    if len(req.password) < 4:
        return JSONResponse({"error": "密码至少4位"}, status_code=400)
    try:
        user = user_manager.create_user(req.nickname.strip(), req.password)
        return user
    except Exception as e:
        if "UNIQUE" in str(e):
            return JSONResponse({"error": "该昵称已被注册"}, status_code=409)
        return JSONResponse({"error": "注册失败"}, status_code=500)


@app.post("/api/user/login")
async def api_user_login(req: LoginRequest):
    """用户登录"""
    if not req.nickname.strip() or not req.password:
        return JSONResponse({"error": "昵称和密码不能为空"}, status_code=400)
    user = user_manager.login_user(req.nickname.strip(), req.password)
    if user is None:
        return JSONResponse({"error": "昵称或密码错误"}, status_code=401)
    return user


@app.get("/api/user/{user_id}")
async def api_user_get(user_id: str):
    """获取用户信息"""
    user = user_manager.get_user(user_id)
    if user is None:
        return JSONResponse({"error": "用户不存在"}, status_code=404)
    # 不返回密码哈希
    user.pop("password_hash", None)
    return user


@app.post("/api/user/session/start")
async def api_session_start(req: SessionRequest):
    """开始对话会话"""
    user = user_manager.get_user(req.user_id)
    if user is None:
        return JSONResponse({"error": "用户不存在"}, status_code=404)
    session_id = user_manager.start_session(req.user_id, req.master_id)

    # 加载记忆 + 生成个性化问候
    mm = get_memory_manager()
    master_id = req.master_id

    # 同步画像到记忆文件
    db_profile = user_manager.get_user_profile(req.user_id, master_id)
    if db_profile:
        mm.sync_profile_from_db(master_id, req.user_id, db_profile)

    # 记录来访
    mm.add_visit_log(master_id, req.user_id, session_id)

    # 生成个性化问候
    memory = mm.load_memory(master_id, req.user_id)
    gg = GreetingGenerator()
    greeting = gg.generate_greeting(master_id, memory)

    return {"session_id": session_id, "greeting": greeting}


@app.post("/api/user/session/end")
async def api_session_end(session_id: str = Query(...)):
    """结束对话会话"""
    session = user_manager.get_session(session_id)
    if session:
        master_id = session["master_id"]
        user_id = session["user_id"]
        # 生成本次会话话题摘要
        try:
            messages = user_manager.get_recent_messages(session_id, limit=30)
            if messages:
                mm = get_memory_manager()
                me = MemoryExtractor()
                all_text = " ".join(m["content"][:100] for m in messages if m["role"] == "user")
                topics = me.extract_topics(all_text, master_id)
                summary = "、".join(topics) if topics else "日常对话"
                mm.update_visit_topic_summary(master_id, user_id, session_id, summary)
        except Exception as e:
            print(f"[memory] 会话摘要生成失败: {e}")

    user_manager.end_session(session_id)
    return {"ok": True}


@app.get("/api/user/{user_id}/history")
async def api_user_history(user_id: str, master_id: str = Query(""), limit: int = Query(50, ge=1, le=200)):
    """获取用户对话历史"""
    if master_id:
        messages = user_manager.get_user_messages(user_id, master_id, limit=limit)
    else:
        messages = []
    return {"messages": messages}


@app.get("/api/user/{user_id}/sessions")
async def api_user_sessions(user_id: str, master_id: str = Query(""), limit: int = Query(20, ge=1, le=50)):
    """获取用户的对话会话列表"""
    sessions = user_manager.get_user_sessions(user_id, master_id=master_id, limit=limit)
    return {"sessions": sessions}


@app.get("/api/session/{session_id}/messages")
async def api_session_messages(session_id: str, limit: int = Query(50, ge=1, le=200)):
    """获取指定会话的消息列表"""
    messages = user_manager.get_recent_messages(session_id, limit=limit)
    return {"messages": messages}


@app.delete("/api/session/{session_id}")
async def api_session_delete(session_id: str):
    """删除指定会话及其消息"""
    ok = user_manager.delete_session(session_id)
    if not ok:
        return JSONResponse({"error": "会话不存在"}, status_code=404)
    return {"ok": True}


@app.get("/api/user/{user_id}/profile/{master_id}")
async def api_user_profile(user_id: str, master_id: str):
    """获取大师视角的用户画像"""
    profile = user_manager.get_user_profile(user_id, master_id)
    if profile is None:
        return JSONResponse({"error": "画像不存在"}, status_code=404)
    return profile


@app.get("/api/user/{user_id}/profiles")
async def api_user_all_profiles(user_id: str):
    """获取用户在所有大师处的画像"""
    profiles = user_manager.get_all_profiles(user_id)
    return {"profiles": profiles}


# ─── 修行系统 API ───────────────────────────────────────

from heritage_master.tools import cultivation

class PracticeSubmitRequest(BaseModel):
    user_id: str
    master_id: str
    content: str

class PracticeAssignRequest(BaseModel):
    user_id: str
    master_id: str

class StageTransitionRequest(BaseModel):
    user_id: str
    master_id: str


@app.post("/api/cultivation/practice/assign")
async def api_practice_assign(req: PracticeAssignRequest):
    """获取今日功课"""
    result = await cultivation.assign_daily_practice(req.user_id, req.master_id)
    return result


@app.post("/api/cultivation/practice/submit")
async def api_practice_submit(req: PracticeSubmitRequest):
    """提交练习记录"""
    result = await cultivation.submit_practice(req.user_id, req.master_id, req.content)
    return result


@app.get("/api/cultivation/practice/history")
async def api_practice_history(user_id: str = Query(...), master_id: str = Query(...), limit: int = Query(20)):
    """获取练习历史"""
    history = cultivation.get_practice_history(user_id, master_id, limit=limit)
    return {"history": history}


@app.get("/api/cultivation/map")
async def api_cultivation_map(user_id: str = Query(...), master_id: str = Query(...)):
    """获取修行地图数据"""
    data = cultivation.get_cultivation_map(user_id, master_id)
    return data


@app.get("/api/cultivation/stage")
async def api_cultivation_stage(user_id: str = Query(...), master_id: str = Query(...)):
    """获取当前阶段信息"""
    info = cultivation.get_stage_info(user_id, master_id)
    return info


@app.post("/api/cultivation/stage/transition")
async def api_stage_transition(req: StageTransitionRequest):
    """执行阶段转换"""
    result = cultivation.do_stage_transition(req.user_id, req.master_id)
    return result


@app.get("/api/cultivation/daily-greeting")
async def api_daily_greeting(user_id: str = Query(...), master_id: str = Query(...)):
    """获取每日问候（含今日功课 + 昨日收获提醒）"""
    result = await cultivation.get_daily_greeting(user_id, master_id)
    return result


class HarvestRequest(BaseModel):
    user_id: str
    master_id: str
    content: str


@app.post("/api/cultivation/harvest")
async def api_record_harvest(req: HarvestRequest):
    """记录每日收获"""
    if not req.content.strip():
        return JSONResponse({"error": "收获内容不能为空"}, status_code=400)
    result = cultivation.record_daily_harvest(
        user_id=req.user_id,
        master_id=req.master_id,
        content=req.content.strip(),
    )
    return result


@app.get("/api/cultivation/harvest/history")
async def api_harvest_history(
    user_id: str = Query(...), master_id: str = Query(...), limit: int = Query(10)
):
    """获取收获历史"""
    history = cultivation.get_harvest_history(user_id, master_id, limit)
    return {"harvests": history}


# ─── 知识图谱 API ───────────────────────────────────────

from heritage_master.data import knowledge_graph

@app.get("/api/graph/search")
async def api_graph_search(q: str = Query(""), type: str = Query(""), limit: int = Query(20)):
    """搜索图谱节点"""
    if not q:
        return {"nodes": [], "total": 0}
    results = knowledge_graph.search_nodes(q, node_type=type or None, limit=limit)
    return {"nodes": results, "total": len(results)}


@app.get("/api/graph/node/{node_id:path}")
async def api_graph_node(node_id: str):
    """获取节点详情及邻居"""
    node = knowledge_graph.get_node(node_id)
    if not node:
        return JSONResponse({"error": "节点不存在"}, status_code=404)
    neighbors = knowledge_graph.get_neighbors(node_id)
    return {"node": {"node_id": node_id, **node}, "neighbors": neighbors}


@app.get("/api/graph/path")
async def api_graph_path(from_id: str = Query(...), to_id: str = Query(...)):
    """查找两个节点之间的路径"""
    paths = knowledge_graph.find_path(from_id, to_id)
    return {"paths": paths}


@app.get("/api/graph/chain")
async def api_graph_chain(person: str = Query(...)):
    """获取师承链"""
    person_id = person if ":" in person else f"person:{person}"
    chain = knowledge_graph.get_inheritance_chain(person_id)
    return {"chain": chain}


@app.get("/api/graph/stats")
async def api_graph_stats():
    """获取图谱统计"""
    return knowledge_graph.get_graph_stats()


@app.get("/api/graph/explore")
async def api_graph_explore(node_id: str = Query(...), depth: int = Query(2, ge=1, le=3)):
    """从某节点探索图谱"""
    result = knowledge_graph.explore_node(node_id, depth=depth)
    return result


@app.get("/api/graph/by-type")
async def api_graph_by_type(type: str = Query(...), limit: int = Query(50)):
    """获取指定类型的所有节点"""
    results = knowledge_graph.get_nodes_by_type(type, limit=limit)
    return {"nodes": results, "total": len(results)}


# ─── 调试 / 可观测 API ──────────────────────────────────

@app.get("/api/debug/traces")
async def api_debug_traces(limit: int = Query(20, ge=1, le=100)):
    """获取最近的请求追踪记录（含每步详情）"""
    from heritage_master.observability.tracer import collector
    traces = collector.get_recent(limit)
    result = []
    for t in traces:
        result.append({
            "trace_id": t.trace_id,
            "user_id": t.user_id,
            "session_id": t.session_id,
            "status": t.status,
            "total_ms": t.total_ms,
            "reply_len": t.reply_len,
            "started_at": t.started_at,
            "steps": [
                {"event": s.event, "data": s.data, "duration_ms": s.duration_ms, "timestamp": s.timestamp}
                for s in t.steps
            ],
        })
    return {"traces": result, "total": len(result)}


@app.get("/api/debug/trace/{trace_id}")
async def api_debug_trace_detail(trace_id: str):
    """获取单个请求的完整追踪详情"""
    from heritage_master.observability.tracer import collector
    trace = collector.get_trace(trace_id)
    if not trace:
        return JSONResponse({"error": "追踪记录不存在"}, status_code=404)
    return {
        "trace_id": trace.trace_id,
        "user_id": trace.user_id,
        "session_id": trace.session_id,
        "status": trace.status,
        "total_ms": trace.total_ms,
        "reply_len": trace.reply_len,
        "started_at": trace.started_at,
        "steps": [
            {"event": s.event, "data": s.data, "duration_ms": s.duration_ms, "timestamp": s.timestamp}
            for s in trace.steps
        ],
    }


@app.get("/api/debug/metrics")
async def api_debug_metrics(limit: int = Query(50, ge=1, le=200)):
    """获取最近的请求指标"""
    from heritage_master.observability.metrics import metrics
    data = metrics.get_recent(limit)
    return {"metrics": data, "total": len(data)}


@app.post("/api/handoff")
async def api_handoff(user_id: str = Query(""), master_id: str = Query(""), reason: str = Query("")):
    """用户请求转人工

    记录转人工请求到数据库，供后台查看。
    """
    from heritage_master.data.db import get_conn
    from datetime import datetime
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        # 复用 cultivation_records 表存储转人工记录
        conn.execute(
            """INSERT INTO cultivation_records (user_id, master_id, practice_type, content, created_at)
               VALUES (?, ?, 'handoff_request', ?, ?)""",
            (user_id, master_id, reason or "用户请求转人工", now),
        )
    return {"ok": True, "message": "已记录您的转人工请求，工作人员会尽快联系您。"}


@app.get("/api/handoff/pending")
async def api_handoff_pending(limit: int = Query(20)):
    """获取待处理的转人工请求（管理员用）"""
    from heritage_master.data.db import get_conn
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, user_id, master_id, content, created_at
               FROM cultivation_records
               WHERE practice_type='handoff_request'
               ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return {"requests": [dict(r) for r in rows]}


# ─── 静态文件服务 ───────────────────────────────────────

_static_dir = Path(__file__).parent / "frontend" / "dist"

# 挂载上传文件静态目录
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory=str(_UPLOAD_DIR)), name="uploads")

if _static_dir.exists():
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA fallback: 所有非 API 路径返回 index.html"""
        file_path = _static_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_static_dir / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
