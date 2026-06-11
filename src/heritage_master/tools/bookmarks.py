"""收藏模块 — 基于 SQLite 的收藏管理

提供收藏的切换、列表查询功能。
"""

from __future__ import annotations

import json
from typing import Optional

from ..data.db import get_conn


def toggle_bookmark(user_id: str, item_type: str, item_id: str,
                    item_name: str = "", item_data: dict = None) -> dict:
    """切换收藏状态，返回 {bookmarked: bool}"""
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM bookmarks WHERE user_id=? AND item_type=? AND item_id=?",
            (user_id, item_type, item_id),
        ).fetchone()
        if existing:
            conn.execute("DELETE FROM bookmarks WHERE id=?", (existing["id"],))
            return {"bookmarked": False}
        else:
            data_json = json.dumps(item_data or {}, ensure_ascii=False)
            conn.execute(
                "INSERT INTO bookmarks (user_id, item_type, item_id, item_name, item_data) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, item_type, item_id, item_name, data_json),
            )
            return {"bookmarked": True}


def list_bookmarks(user_id: str, item_type: Optional[str] = None) -> list[dict]:
    """获取收藏列表"""
    with get_conn() as conn:
        if item_type:
            rows = conn.execute(
                "SELECT * FROM bookmarks WHERE user_id=? AND item_type=? ORDER BY created_at DESC",
                (user_id, item_type),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM bookmarks WHERE user_id=? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item["item_data"] = json.loads(item["item_data"]) if item["item_data"] else {}
            results.append(item)
        return results


def check_bookmarks(user_id: str, items: list[dict]) -> dict:
    """批量检查收藏状态，items 为 [{item_type, item_id}, ...]
    返回 {key: bookmarked} 其中 key 为 "type:id"
    """
    if not items:
        return {}
    with get_conn() as conn:
        result = {}
        for item in items:
            item_type = item.get("item_type", "")
            item_id = item.get("item_id", "")
            key = f"{item_type}:{item_id}"
            row = conn.execute(
                "SELECT 1 FROM bookmarks WHERE user_id=? AND item_type=? AND item_id=?",
                (user_id, item_type, item_id),
            ).fetchone()
            result[key] = row is not None
        return result
