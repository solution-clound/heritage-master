"""旅行路线 API 路由"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import List

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from heritage_master.data.db import get_conn
from heritage_master.tools.route_planner import plan_heritage_route

router = APIRouter()


# ─── 已保存路线 API ─────────────────────────────────────


class TripSaveRequest(BaseModel):
    user_id: str
    name: str = ""
    city: str = ""
    days: int = 1
    interests: List[str] = []
    itinerary: str = ""
    route_data: dict = {}


@router.post("/api/trips/save")
async def api_trip_save(req: TripSaveRequest):
    """保存路线"""
    if not req.user_id:
        return JSONResponse({"error": "需要登录"}, status_code=401)

    def _save():
        route_id = str(uuid.uuid4())
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


@router.get("/api/trips")
async def api_trips_list(user_id: str = Query(...)):
    """获取用户已保存路线列表"""

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


@router.get("/api/trips/{route_id}")
async def api_trip_detail(route_id: str):
    """获取单条路线详情"""

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


@router.delete("/api/trips/{route_id}")
async def api_trip_delete(route_id: str, user_id: str = Query(...)):
    """删除路线（仅作者）"""

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
    return {"ok": True}


# ─── 旅行规划 API ──────────────────────────────────────


class TripRequest(BaseModel):
    city: str
    days: int = 1
    interests: List[str] = []
    start_point: str = None


@router.post("/api/trip")
async def api_trip(req: TripRequest):
    """旅行规划"""
    result = await plan_heritage_route(
        city=req.city,
        days=req.days,
        interests=req.interests,
        start_point=req.start_point,
    )
    return {"result": result["itinerary"], "route_data": result.get("route_data")}
