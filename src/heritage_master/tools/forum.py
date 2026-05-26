"""论坛模块 — 基于 SQLite 的帖子/评论/点赞

提供论坛帖子的 CRUD、点赞切换、评论管理，以及可选的 Redis 缓存层。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

from ..data.db import get_conn

# ─── Redis 缓存层（可选，graceful degradation）──────────────

_redis = None


def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    try:
        from ..config import settings
        if not settings.redis_enabled:
            return None
        import redis
        _redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password or None,
            decode_responses=True,
        )
        _redis.ping()
    except Exception:
        _redis = None
    return _redis


def _cache_get(key: str):
    r = _get_redis()
    if not r:
        return None
    try:
        raw = r.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _cache_set(key: str, value, ttl: int = 60):
    r = _get_redis()
    if not r:
        return
    try:
        r.setex(key, ttl, json.dumps(value, ensure_ascii=False))
    except Exception:
        pass


def _cache_delete(key: str):
    r = _get_redis()
    if not r:
        return
    try:
        r.delete(key)
    except Exception:
        pass


def _cache_delete_pattern(pattern: str):
    r = _get_redis()
    if not r:
        return
    try:
        for key in r.scan_iter(match=pattern):
            r.delete(key)
    except Exception:
        pass


# ─── 内部工具 ─────────────────────────────────────────────

def _parse_post(row) -> dict:
    """将 sqlite3.Row 解析为帖子 dict（JOIN 查询已包含 author_nickname 和 liked）"""
    post = dict(row)
    post["author_nickname"] = post.get("author_nickname") or "未知用户"
    post["images"] = json.loads(post["images"]) if post["images"] else []
    post["route_data"] = json.loads(post["route_data"]) if post.get("route_data") else {}
    post["liked"] = bool(post.get("liked"))
    return post


def _row_to_post(row, conn, viewer_id: str = None) -> dict:
    """将 sqlite3.Row 转为帖子 dict（单条帖子查询，用于 create_post/get_post）"""
    post = dict(row)
    author = conn.execute("SELECT nickname FROM users WHERE id=?", (post["user_id"],)).fetchone()
    post["author_nickname"] = author["nickname"] if author else "未知用户"
    post["images"] = json.loads(post["images"]) if post["images"] else []
    post["route_data"] = json.loads(post["route_data"]) if post.get("route_data") else {}
    if viewer_id:
        liked = conn.execute(
            "SELECT 1 FROM forum_likes WHERE post_id=? AND user_id=?",
            (post["id"], viewer_id),
        ).fetchone()
        post["liked"] = liked is not None
    else:
        post["liked"] = False
    return post


def _parse_comment(row) -> dict:
    """将 sqlite3.Row 解析为评论 dict（JOIN 查询已包含 author_nickname）"""
    c = dict(row)
    c["author_nickname"] = c.get("author_nickname") or "未知用户"
    return c


def _row_to_comment(row, conn) -> dict:
    """将 sqlite3.Row 转为评论 dict（单条评论查询）"""
    c = dict(row)
    author = conn.execute("SELECT nickname FROM users WHERE id=?", (c["user_id"],)).fetchone()
    c["author_nickname"] = author["nickname"] if author else "未知用户"
    return c


# ─── 帖子 CRUD ────────────────────────────────────────────

def create_post(user_id: str, title: str, content: str,
                category: str = "experience", images: list[str] = None,
                route_data: dict = None) -> dict:
    """创建帖子，返回完整帖子 dict"""
    post_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    images_json = json.dumps(images or [], ensure_ascii=False)
    route_json = json.dumps(route_data or {}, ensure_ascii=False)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO forum_posts (id, user_id, title, content, category, images, route_data, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (post_id, user_id, title, content, category, images_json, route_json, now, now),
        )
        row = conn.execute("SELECT * FROM forum_posts WHERE id=?", (post_id,)).fetchone()
        post = _row_to_post(row, conn, user_id)
    _cache_delete_pattern("forum:posts:list:*")
    return post


def get_post(post_id: str, viewer_id: str = None) -> Optional[dict]:
    """获取单帖详情"""
    cache_key = f"forum:posts:detail:{post_id}"
    cached = _cache_get(cache_key) if not viewer_id else None
    if cached:
        return cached
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM forum_posts WHERE id=?", (post_id,)).fetchone()
        if not row:
            return None
        post = _row_to_post(row, conn, viewer_id)
    if not viewer_id:
        _cache_set(cache_key, post, 120)
    return post


def list_posts(category: str = None, user_id: str = None,
               cursor: int = 0, limit: int = 10,
               viewer_id: str = None) -> dict:
    """分页列表，返回 {posts, next_cursor, has_more}"""
    cache_key = f"forum:posts:list:{category or 'all'}:{cursor}:{limit}"
    cached = _cache_get(cache_key) if not viewer_id and not user_id else None
    if cached:
        return cached

    conditions = []
    params = []
    if category:
        conditions.append("p.category=?")
        params.append(category)
    if user_id:
        conditions.append("p.user_id=?")
        params.append(user_id)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    # viewer_id 用于子查询判断点赞状态
    if viewer_id:
        params.append(viewer_id)
    params.extend([limit, cursor])

    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT p.*, u.nickname as author_nickname, "
            f"{'(SELECT 1 FROM forum_likes WHERE post_id=p.id AND user_id=?) as liked' if viewer_id else '0 as liked'} "
            f"FROM forum_posts p LEFT JOIN users u ON p.user_id = u.id "
            f"{where} ORDER BY p.created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        posts = [_parse_post(r) for r in rows]

    result = {
        "posts": posts,
        "next_cursor": cursor + len(posts),
        "has_more": len(posts) == limit,
    }
    if not viewer_id and not user_id:
        _cache_set(cache_key, result, 60)
    return result


def search_posts(keyword: str, limit: int = 10, viewer_id: str = None) -> list[dict]:
    """关键词搜索标题和内容"""
    like = f"%{keyword}%"
    params = [like, like]
    if viewer_id:
        params.append(viewer_id)
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT p.*, u.nickname as author_nickname, "
            f"{'(SELECT 1 FROM forum_likes WHERE post_id=p.id AND user_id=?) as liked' if viewer_id else '0 as liked'} "
            f"FROM forum_posts p LEFT JOIN users u ON p.user_id = u.id "
            f"WHERE p.title LIKE ? OR p.content LIKE ? "
            f"ORDER BY p.created_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [_parse_post(r) for r in rows]


def delete_post(post_id: str, user_id: str) -> bool:
    """删除帖子（仅作者）"""
    with get_conn() as conn:
        row = conn.execute("SELECT user_id FROM forum_posts WHERE id=?", (post_id,)).fetchone()
        if not row or row["user_id"] != user_id:
            return False
        conn.execute("DELETE FROM forum_comments WHERE post_id=?", (post_id,))
        conn.execute("DELETE FROM forum_likes WHERE post_id=?", (post_id,))
        conn.execute("DELETE FROM forum_posts WHERE id=?", (post_id,))
    _cache_delete(f"forum:posts:detail:{post_id}")
    _cache_delete_pattern("forum:posts:list:*")
    return True


# ─── 点赞 ─────────────────────────────────────────────────

def toggle_like(post_id: str, user_id: str) -> dict:
    """点赞/取消，返回 {liked, like_count}"""
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM forum_likes WHERE post_id=? AND user_id=?",
            (post_id, user_id),
        ).fetchone()
        if existing:
            conn.execute("DELETE FROM forum_likes WHERE id=?", (existing["id"],))
            conn.execute(
                "UPDATE forum_posts SET like_count = MAX(0, like_count - 1) WHERE id=?",
                (post_id,),
            )
            liked = False
        else:
            conn.execute(
                "INSERT INTO forum_likes (post_id, user_id) VALUES (?, ?)",
                (post_id, user_id),
            )
            conn.execute(
                "UPDATE forum_posts SET like_count = like_count + 1 WHERE id=?",
                (post_id,),
            )
            liked = True
        row = conn.execute("SELECT like_count FROM forum_posts WHERE id=?", (post_id,)).fetchone()
        like_count = row["like_count"] if row else 0
    _cache_delete(f"forum:posts:detail:{post_id}")
    _cache_delete_pattern("forum:posts:list:*")
    return {"liked": liked, "like_count": like_count}


# ─── 评论 ─────────────────────────────────────────────────

def add_comment(post_id: str, user_id: str, content: str,
                parent_id: int = None) -> dict:
    """发评论，返回评论 dict"""
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO forum_comments (post_id, user_id, content, parent_id, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (post_id, user_id, content, parent_id, now),
        )
        conn.execute(
            "UPDATE forum_posts SET comment_count = comment_count + 1 WHERE id=?",
            (post_id,),
        )
        row = conn.execute(
            "SELECT * FROM forum_comments WHERE id=?", (cursor.lastrowid,)
        ).fetchone()
        comment = _row_to_comment(row, conn)
    _cache_delete(f"forum:posts:detail:{post_id}")
    return comment


def list_comments(post_id: str, limit: int = 50) -> list[dict]:
    """评论列表，按时间正序"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT c.*, u.nickname as author_nickname "
            "FROM forum_comments c LEFT JOIN users u ON c.user_id = u.id "
            "WHERE c.post_id=? ORDER BY c.created_at ASC LIMIT ?",
            (post_id, limit),
        ).fetchall()
        return [_parse_comment(r) for r in rows]


def delete_comment(comment_id: int, user_id: str) -> bool:
    """删除评论（仅作者）"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT user_id, post_id FROM forum_comments WHERE id=?", (comment_id,)
        ).fetchone()
        if not row or row["user_id"] != user_id:
            return False
        post_id = row["post_id"]
        conn.execute("DELETE FROM forum_comments WHERE id=?", (comment_id,))
        conn.execute(
            "UPDATE forum_posts SET comment_count = MAX(0, comment_count - 1) WHERE id=?",
            (post_id,),
        )
    _cache_delete(f"forum:posts:detail:{post_id}")
    return True
