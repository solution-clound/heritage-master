"""用户管理系统

提供用户CRUD、会话管理、消息存取、画像读写、对话摘要等功能。
"""

import hashlib
import json
import secrets
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from ..data.db import get_conn


# ============================================================
# 密码工具
# ============================================================

def _hash_password(password: str, salt: str = None) -> tuple:
    """哈希密码，返回 (hash, salt)"""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}${h}", salt


def _verify_password(password: str, stored_hash: str) -> bool:
    """验证密码"""
    if "$" not in stored_hash:
        return False
    salt, _ = stored_hash.split("$", 1)
    computed, _ = _hash_password(password, salt)
    return secrets.compare_digest(computed, stored_hash)


# ============================================================
# 用户 CRUD
# ============================================================

def create_user(nickname: str, password: str) -> Dict[str, Any]:
    """创建新用户，返回用户信息"""
    user_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    password_hash, _ = _hash_password(password)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (id, nickname, password_hash, created_at, last_active_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, nickname, password_hash, now, now),
        )
    return {"id": user_id, "nickname": nickname, "created_at": now}


def login_user(nickname: str, password: str) -> Optional[Dict[str, Any]]:
    """用户登录，验证昵称和密码。成功返回用户信息，失败返回 None"""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE nickname=? COLLATE UTF8", (nickname,)).fetchone()
        if row is None:
            return None
        user = dict(row)
        if not _verify_password(password, user.get("password_hash", "")):
            return None
        # 更新活跃时间
        now = datetime.utcnow().isoformat()
        conn.execute("UPDATE users SET last_active_at=? WHERE id=?", (now, user["id"]))
        return {"id": user["id"], "nickname": user["nickname"], "created_at": user["created_at"]}


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    """获取用户信息"""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if row is None:
            return None
        return dict(row)


def update_user_active(user_id: str) -> None:
    """更新用户最后活跃时间"""
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute("UPDATE users SET last_active_at=? WHERE id=?", (now, user_id))


# ============================================================
# 会话管理
# ============================================================

def start_session(user_id: str, master_id: str) -> str:
    """开始一个新的对话会话，返回 session_id

    按日复用：同一天、同一用户、同一大师共用一个会话。
    如果今天已有会话，直接返回该 session_id。
    """
    today = datetime.utcnow().date().isoformat()
    with get_conn() as conn:
        # 检查今天是否已有该大师的会话
        existing = conn.execute(
            """SELECT id FROM chat_sessions
               WHERE user_id=? AND master_id=? AND DATE(started_at)=?
               ORDER BY started_at DESC LIMIT 1""",
            (user_id, master_id, today),
        ).fetchone()
        if existing:
            return existing["id"]

        # 创建新会话
        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO chat_sessions (id, user_id, master_id, started_at) VALUES (?, ?, ?, ?)",
            (session_id, user_id, master_id, now),
        )
        # 确保用户画像存在
        _ensure_profile(conn, user_id, master_id)
    update_user_active(user_id)
    return session_id


def end_session(session_id: str) -> None:
    """结束对话会话

    按日会话模式下，不设置 ended_at（保持当天可复用）。
    """
    # 不再设置 ended_at，保持会话当天活跃
    pass


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """获取会话信息"""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM chat_sessions WHERE id=?", (session_id,)).fetchone()
        return dict(row) if row else None


# ============================================================
# 消息存取
# ============================================================

def add_message(session_id: str, role: str, content: str) -> int:
    """添加一条消息，返回消息ID"""
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, now),
        )
        # 更新用户画像中的问题计数
        session = conn.execute("SELECT user_id, master_id FROM chat_sessions WHERE id=?", (session_id,)).fetchone()
        if session and role == "user":
            conn.execute(
                "UPDATE user_profiles SET question_count = question_count + 1, last_talk_at=? WHERE user_id=? AND master_id=?",
                (now, session["user_id"], session["master_id"]),
            )
        return cursor.lastrowid


def delete_session(session_id: str) -> bool:
    """删除一个会话及其所有消息"""
    with get_conn() as conn:
        conn.execute("DELETE FROM chat_messages WHERE session_id=?", (session_id,))
        cursor = conn.execute("DELETE FROM chat_sessions WHERE id=?", (session_id,))
        return cursor.rowcount > 0


def get_recent_messages(session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """获取会话中最近的消息"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM chat_messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


def get_user_messages(user_id: str, master_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """获取用户与某大师的所有对话消息（跨会话）"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT m.role, m.content, m.created_at, s.id as session_id
               FROM chat_messages m
               JOIN chat_sessions s ON m.session_id = s.id
               WHERE s.user_id=? AND s.master_id=?
               ORDER BY m.id DESC LIMIT ?""",
            (user_id, master_id, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


def get_user_sessions(user_id: str, master_id: str = "", limit: int = 20) -> List[Dict[str, Any]]:
    """获取用户的对话会话列表（含消息数和首条用户消息作为标题）

    按日模式下，每个会话对应一天，返回时附带日期信息。
    """
    with get_conn() as conn:
        if master_id:
            rows = conn.execute(
                """SELECT s.id, s.master_id, s.started_at, s.ended_at, s.topic_summary,
                          DATE(s.started_at) as talk_date,
                          (SELECT COUNT(*) FROM chat_messages WHERE session_id=s.id) as msg_count,
                          (SELECT content FROM chat_messages WHERE session_id=s.id AND role='user' ORDER BY id ASC LIMIT 1) as first_msg
                   FROM chat_sessions s
                   WHERE s.user_id=? AND s.master_id=?
                   ORDER BY s.started_at DESC LIMIT ?""",
                (user_id, master_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT s.id, s.master_id, s.started_at, s.ended_at, s.topic_summary,
                          DATE(s.started_at) as talk_date,
                          (SELECT COUNT(*) FROM chat_messages WHERE session_id=s.id) as msg_count,
                          (SELECT content FROM chat_messages WHERE session_id=s.id AND role='user' ORDER BY id ASC LIMIT 1) as first_msg
                   FROM chat_sessions s
                   WHERE s.user_id=?
                   ORDER BY s.started_at DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]


# ============================================================
# 用户画像
# ============================================================

def get_user_profile(user_id: str, master_id: str) -> Optional[Dict[str, Any]]:
    """获取大师对学徒的画像"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM user_profiles WHERE user_id=? AND master_id=?",
            (user_id, master_id),
        ).fetchone()
        if row is None:
            return None
        profile = dict(row)
        # 解析 JSON 字段
        profile["interest_tags"] = json.loads(profile["interest_tags"]) if profile["interest_tags"] else []
        return profile


def update_user_profile(user_id: str, master_id: str, **kwargs) -> None:
    """更新用户画像字段

    可更新字段: relationship_stage, interest_tags, aesthetic_pref, personality_notes
    """
    allowed = {"relationship_stage", "interest_tags", "aesthetic_pref", "personality_notes"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return

    # JSON 序列化
    if "interest_tags" in updates and isinstance(updates["interest_tags"], list):
        updates["interest_tags"] = json.dumps(updates["interest_tags"], ensure_ascii=False)

    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [user_id, master_id]
    with get_conn() as conn:
        conn.execute(
            f"UPDATE user_profiles SET {set_clause} WHERE user_id=? AND master_id=?",
            values,
        )


def auto_update_profile(user_id: str, master_id: str, updates: dict) -> None:
    """自动更新画像字段（合并式写入，不覆盖已有值）

    Args:
        updates: 可包含 new_interests(列表), personality_notes(追加), aesthetic_pref
    """
    profile = get_user_profile(user_id, master_id)
    if not profile:
        return

    merged = {}

    # 兴趣标签：去重追加
    if "new_interests" in updates and updates["new_interests"]:
        existing = set(profile.get("interest_tags", []))
        existing.update(updates["new_interests"])
        merged["interest_tags"] = list(existing)

    # 性格观察：追加不覆盖
    if "personality_notes" in updates and updates["personality_notes"]:
        existing_notes = profile.get("personality_notes", "")
        new_note = updates["personality_notes"]
        if existing_notes:
            merged["personality_notes"] = f"{existing_notes}; {new_note}"
        else:
            merged["personality_notes"] = new_note

    # 审美偏好：直接更新
    if "aesthetic_pref" in updates and updates["aesthetic_pref"]:
        merged["aesthetic_pref"] = updates["aesthetic_pref"]

    if merged:
        update_user_profile(user_id, master_id, **merged)


def get_all_profiles(user_id: str) -> List[Dict[str, Any]]:
    """获取用户在所有大师处的画像"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM user_profiles WHERE user_id=?", (user_id,)
        ).fetchall()
        result = []
        for row in rows:
            profile = dict(row)
            profile["interest_tags"] = json.loads(profile["interest_tags"]) if profile["interest_tags"] else []
            result.append(profile)
        return result


# ============================================================
# 对话摘要（用于注入prompt）
# ============================================================

def get_conversation_summary(user_id: str, master_id: str, limit: int = 10) -> str:
    """获取用户与大师的近期对话摘要，用于注入prompt上下文

    返回格式化的对话历史字符串。
    """
    messages = get_user_messages(user_id, master_id, limit=limit)
    if not messages:
        return ""

    lines = ["【近期对话记录】"]
    for msg in messages:
        role_label = "学徒" if msg["role"] == "user" else "大师"
        # 截断过长的消息
        content = msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"]
        lines.append(f"{role_label}: {content}")
    return "\n".join(lines)


def get_profile_context(user_id: str, master_id: str) -> str:
    """将用户画像格式化为prompt上下文字符串"""
    profile = get_user_profile(user_id, master_id)
    if profile is None:
        return ""

    lines = ["【学徒画像】"]
    lines.append(f"- 关系阶段: {profile['relationship_stage']}")
    lines.append(f"- 提问次数: {profile['question_count']}")
    if profile["interest_tags"]:
        lines.append(f"- 兴趣标签: {', '.join(profile['interest_tags'])}")
    if profile["aesthetic_pref"]:
        lines.append(f"- 审美偏好: {profile['aesthetic_pref']}")
    if profile["personality_notes"]:
        lines.append(f"- 性格观察: {profile['personality_notes']}")
    return "\n".join(lines)


# ============================================================
# 内部辅助
# ============================================================

def _ensure_profile(conn, user_id: str, master_id: str) -> None:
    """确保用户在某大师处有画像记录"""
    existing = conn.execute(
        "SELECT id FROM user_profiles WHERE user_id=? AND master_id=?",
        (user_id, master_id),
    ).fetchone()
    if existing is None:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO user_profiles (user_id, master_id, first_met_at, last_talk_at) VALUES (?, ?, ?, ?)",
            (user_id, master_id, now, now),
        )
        # 同时创建阶段进度记录
        conn.execute(
            "INSERT OR IGNORE INTO stage_progress (user_id, master_id, stage) VALUES (?, ?, '入门期')",
            (user_id, master_id),
        )
