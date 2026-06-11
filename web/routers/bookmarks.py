import asyncio

from fastapi import Query, APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from heritage_master.tools import bookmarks as bookmarks_module

router = APIRouter()


class BookmarkToggleRequest(BaseModel):
    user_id: str
    item_type: str  # 'heritage' | 'venue'
    item_id: str
    item_name: str = ""
    item_data: dict = {}


class BookmarkCheckRequest(BaseModel):
    user_id: str
    items: list  # [{item_type, item_id}, ...]


@router.post("/api/bookmarks/toggle")
async def api_bookmark_toggle(req: BookmarkToggleRequest):
    """切换收藏状态"""
    result = await asyncio.to_thread(
        bookmarks_module.toggle_bookmark,
        req.user_id, req.item_type, req.item_id, req.item_name, req.item_data,
    )
    return result


@router.get("/api/bookmarks")
async def api_bookmarks_list(user_id: str = Query(...), type: str = Query(None)):
    """获取收藏列表"""
    items = await asyncio.to_thread(bookmarks_module.list_bookmarks, user_id, type)
    return {"items": items}


@router.post("/api/bookmarks/check")
async def api_bookmarks_check(req: BookmarkCheckRequest):
    """批量检查收藏状态"""
    result = await asyncio.to_thread(bookmarks_module.check_bookmarks, req.user_id, req.items)
    return result
