import json
import asyncio
from typing import List, Optional

from fastapi import Query, APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from heritage_master.tools import forum

router = APIRouter()


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


@router.get("/api/forum/posts")
async def api_forum_list(
    category: str = Query(None),
    user_id: str = Query(None),
    cursor: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
    viewer_id: str = Query(None),
):
    """帖子列表"""
    return await asyncio.to_thread(
        forum.list_posts, category=category, user_id=user_id,
        cursor=cursor, limit=limit, viewer_id=viewer_id
    )


@router.get("/api/forum/posts/{post_id}")
async def api_forum_get_post(post_id: str, viewer_id: str = Query(None)):
    """帖子详情"""
    post = await asyncio.to_thread(forum.get_post, post_id, viewer_id=viewer_id)
    if not post:
        return JSONResponse({"error": "帖子不存在"}, status_code=404)
    return {"post": post}


@router.post("/api/forum/posts")
async def api_forum_create(req: ForumCreateRequest):
    """发帖"""
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


@router.delete("/api/forum/posts/{post_id}")
async def api_forum_delete(post_id: str, user_id: str = Query(...)):
    """删帖"""
    ok = await asyncio.to_thread(forum.delete_post, post_id, user_id)
    if not ok:
        return JSONResponse({"error": "删除失败"}, status_code=400)
    return {"ok": True}


@router.post("/api/forum/posts/{post_id}/like")
async def api_forum_like(post_id: str, body: dict = {}):
    """点赞/取消"""
    user_id = body.get("user_id", "")
    if not user_id:
        return JSONResponse({"error": "需要登录"}, status_code=401)
    return await asyncio.to_thread(forum.toggle_like, post_id, user_id)


@router.get("/api/forum/posts/{post_id}/comments")
async def api_forum_comments(post_id: str, limit: int = Query(50, ge=1, le=200)):
    """评论列表"""
    comments = await asyncio.to_thread(forum.list_comments, post_id, limit=limit)
    return {"comments": comments}


@router.post("/api/forum/posts/{post_id}/comments")
async def api_forum_add_comment(post_id: str, req: ForumCommentRequest):
    """发评论"""
    if not req.content.strip():
        return JSONResponse({"error": "内容不能为空"}, status_code=400)
    comment = await asyncio.to_thread(forum.add_comment, post_id, req.user_id, req.content, req.parent_id)
    return {"comment": comment}


@router.delete("/api/forum/comments/{comment_id}")
async def api_forum_delete_comment(comment_id: int, user_id: str = Query(...)):
    """删评论"""
    ok = await asyncio.to_thread(forum.delete_comment, comment_id, user_id)
    if not ok:
        return JSONResponse({"error": "删除失败"}, status_code=400)
    return {"ok": True}


@router.get("/api/forum/search")
async def api_forum_search(keyword: str = Query(...), limit: int = Query(10, ge=1, le=50)):
    """搜索帖子"""
    posts = await asyncio.to_thread(forum.search_posts, keyword, limit=limit)
    return {"posts": posts}
