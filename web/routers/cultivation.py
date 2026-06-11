"""
修行 / 用户 / 大师 路由

从 web/app.py 提取的大师列表、问候、用户画像、修行系统等端点。
"""
from __future__ import annotations

from fastapi import Query, APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import json

from heritage_master.tools import user_manager, cultivation
from heritage_master.tools.master_prompt import (
    list_masters as _list_masters,
    get_master_prompt as _get_master_prompt,
    get_adaptive_greeting as _get_adaptive_greeting,
)
from deps import get_memory_manager
from heritage_master.tools.memory import GreetingGenerator

router = APIRouter()


# ─── 内部辅助 ────────────────────────────────────────────


def _get_llm():
    """获取 LLM 实例"""
    from deps import get_llm
    return get_llm()


async def _ask_llm(question: str, context: str = "", messages: list = None) -> str | None:
    """调用 LLM 生成回答。"""
    llm = _get_llm()
    if not llm:
        return None

    if messages is None:
        user_msg = f"参考资料：\n{context}\n\n用户问题：{question}" if context else question
        messages = [
            {"role": "system", "content": "你是非遗大师助手。"},
            {"role": "user", "content": user_msg},
        ]

    return await llm.chat_completion(messages, temperature=0.7, max_tokens=2000)


# ─── 请求模型 ────────────────────────────────────────────


class UpdateProfileRequest(BaseModel):
    user_id: str
    master_id: str
    interest_tags: List[str] = []
    personality_notes: Optional[str] = None
    question_count: Optional[int] = None


class SubmitPractice(BaseModel):
    user_id: str
    master_id: str
    content: str


class StageTransitionRequest(BaseModel):
    user_id: str
    master_id: str


# ─── 大师路由 ────────────────────────────────────────────


@router.get("/api/masters")
async def api_masters():
    """列出所有可选的非遗大师"""
    masters = _list_masters()
    return {"masters": masters}


@router.get("/api/masters/{master_id}/greeting")
async def api_master_greeting(master_id: str, user_id: str = Query("")):
    """获取大师问候语（围绕每日功课展开）

    每次进入大师房间，都以当日功课为中心：
    - 新一天首次访问：分配今日功课并围绕功课展开问候
    - 同一天再次访问：仍然以今日功课为中心（可能追问昨日收获）
    """
    if user_id:
        # 始终使用每日功课问候 — 每天第一句话围绕功课展开
        daily = cultivation.get_daily_greeting(user_id, master_id)
        if daily and daily.get("greeting"):
            stage = cultivation._get_stage(user_id, master_id)
            return {
                "greeting": daily["greeting"],
                "stage": stage,
                "today_practice": daily.get("today_practice", ""),
                "practice_date": daily.get("practice_date", ""),
            }

        # 降级：记忆增强问候
        mm = get_memory_manager()
        memory = mm.load_memory(master_id, user_id)
        gg = GreetingGenerator()
        greeting = gg.generate_greeting(master_id, memory)
        stage = memory["profile"].get("relationship_stage", "入门期")
        return {"greeting": greeting, "stage": stage}

    stage = "入门期"
    greeting = _get_adaptive_greeting(master_id, stage)
    return {"greeting": greeting, "stage": stage}


# ─── 用户路由 ────────────────────────────────────────────


@router.get("/api/user/profile")
async def api_user_profile(
    user_id: str = Query(..., description="用户 ID"),
    master_id: str = Query(..., description="大师 ID"),
):
    """获取大师视角的用户画像"""
    profile = user_manager.get_user_profile(user_id, master_id)
    if profile is None:
        return JSONResponse({"error": "画像不存在"}, status_code=404)
    return profile


@router.post("/api/user/profile")
async def api_update_user_profile(req: UpdateProfileRequest):
    """更新用户画像"""
    try:
        kwargs = {}
        if req.interest_tags:
            kwargs["interest_tags"] = json.dumps(req.interest_tags, ensure_ascii=False)
        if req.personality_notes is not None:
            kwargs["personality_notes"] = req.personality_notes
        if req.question_count is not None:
            kwargs["question_count"] = req.question_count
        user_manager.update_user_profile(req.user_id, req.master_id, **kwargs)
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/user/messages")
async def api_user_messages(
    user_id: str = Query(..., description="用户 ID"),
    master_id: str = Query(..., description="大师 ID"),
    limit: int = Query(50, ge=1, le=200),
):
    """获取用户消息历史"""
    messages = user_manager.get_user_messages(user_id, master_id, limit=limit)
    return {"messages": messages}


# ─── 修行系统路由 ────────────────────────────────────────


@router.get("/api/cultivation/daily-practice")
async def api_cultivation_daily_practice(
    user_id: str = Query(..., description="用户 ID"),
    master_id: str = Query(..., description="大师 ID"),
):
    """获取今日功课（支持 LLM 动态生成）"""
    result = await cultivation.assign_daily_practice(user_id, master_id, llm_func=_ask_llm)
    return result


@router.post("/api/cultivation/submit")
async def api_cultivation_submit(req: SubmitPractice):
    """提交练习记录（LLM 点评 + LLM 评分）"""
    result = await cultivation.submit_practice(req.user_id, req.master_id, req.content, llm_func=_ask_llm)
    return result


@router.get("/api/cultivation/history")
async def api_cultivation_history(
    user_id: str = Query(..., description="用户 ID"),
    master_id: str = Query(..., description="大师 ID"),
    limit: int = Query(20, ge=1, le=100),
):
    """获取练习历史"""
    history = cultivation.get_practice_history(user_id, master_id, limit=limit)
    return {"history": history}


@router.get("/api/cultivation/evaluation")
async def api_cultivation_evaluation(
    user_id: str = Query(..., description="用户 ID"),
    master_id: str = Query(..., description="大师 ID"),
):
    """获取修行评估（阶段 + 修行地图 + 近期练习）"""
    stage_info = cultivation.get_stage_info(user_id, master_id)
    cultivation_map = cultivation.get_cultivation_map(user_id, master_id)
    recent = cultivation.get_practice_history(user_id, master_id, limit=5)
    return {
        "stage": stage_info,
        "map": cultivation_map,
        "recent_practices": recent,
    }


@router.get("/api/cultivation/progress")
async def api_cultivation_progress(
    user_id: str = Query(..., description="用户 ID"),
    master_id: str = Query(..., description="大师 ID"),
):
    """获取修行进度（地图数据）"""
    data = cultivation.get_cultivation_map(user_id, master_id)
    return data


@router.get("/api/cultivation/stage")
async def api_cultivation_stage(
    user_id: str = Query(..., description="用户 ID"),
    master_id: str = Query(..., description="大师 ID"),
):
    """获取当前阶段信息"""
    info = cultivation.get_stage_info(user_id, master_id)
    return info


@router.post("/api/cultivation/stage/transition")
async def api_stage_transition(req: StageTransitionRequest):
    """执行阶段转换"""
    result = cultivation.do_stage_transition(req.user_id, req.master_id)
    return result


# ─── 每日功课流程 API ───────────────────────────────────

@router.get("/api/cultivation/daily-greeting")
async def api_daily_greeting(
    user_id: str = Query(..., description="用户 ID"),
    master_id: str = Query(..., description="大师 ID"),
):
    """获取每日问候（含今日功课 + 昨日收获提醒）

    返回：
    - greeting: 师父的问候语（含今日功课介绍）
    - today_practice: 今日功课内容
    - ask_harvest: 是否需要问昨天的收获
    - yesterday_practice: 昨天的功课（如果有）
    """
    result = cultivation.get_daily_greeting(user_id, master_id)
    return result


class HarvestRequest(BaseModel):
    user_id: str
    master_id: str
    content: str


@router.post("/api/cultivation/harvest")
async def api_record_harvest(req: HarvestRequest):
    """记录每日收获

    用户分享今日学习收获，师父点评并打分。
    """
    if not req.content.strip():
        return JSONResponse({"error": "收获内容不能为空"}, status_code=400)

    result = cultivation.record_daily_harvest(
        user_id=req.user_id,
        master_id=req.master_id,
        content=req.content.strip(),
    )
    return result


@router.get("/api/cultivation/harvest/history")
async def api_harvest_history(
    user_id: str = Query(..., description="用户 ID"),
    master_id: str = Query(..., description="大师 ID"),
    limit: int = Query(10, ge=1, le=50),
):
    """获取收获历史"""
    history = cultivation.get_harvest_history(user_id, master_id, limit)
    return {"harvests": history}
