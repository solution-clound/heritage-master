"""
上下文管理器 — 会话持久化 + 上下文窗口 + 长期记忆衔接

核心职责：
1. 会话隔离：每个 session_id 对应独立的 LangGraph thread
2. 持久化：通过 LangGraph Checkpointer 将图状态存 SQLite
3. 上下文窗口：自动截断旧消息，防止超 token 限制
4. 长期记忆衔接：每轮自动注入用户画像到 system prompt
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, trim_messages
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from heritage_master.config import settings
from heritage_master.tools.memory import MemoryManager
from heritage_master.tools import user_manager

logger = logging.getLogger("heritage.context")

# 上下文窗口配置
MAX_CONTEXT_MESSAGES = 30       # 最多保留消息数
MAX_CONTEXT_TOKENS = 4000    # 大约的 token 上限（估算）
CONTEXT_WINDOW_TRIM_TO = 20     # 截断后保留的消息数


# ============================================================
# ContextManager — 会话生命周期管理
# ============================================================

class ContextManager:
    """管理 Agent 的会话上下文：持久化、窗口裁剪、记忆注入"""

    def __init__(self):
        self._checkpointer: Optional[AsyncSqliteSaver] = None
        self._conn = None
        self._memory_manager = MemoryManager()
        self._db_path = str(Path(settings.sqlite_path).parent / "heritage_checkpoints.db")

    async def initialize(self) -> None:
        """初始化 checkpointer（在 app lifespan 中调用）"""
        import aiosqlite
        self._conn = await aiosqlite.connect(self._db_path)
        self._checkpointer = AsyncSqliteSaver(self._conn)
        await self._checkpointer.setup()
        logger.info("Checkpointer initialized: %s", self._db_path)

    async def close(self) -> None:
        """关闭 checkpointer"""
        if self._conn:
            await self._conn.close()
            self._checkpointer = None
            logger.info("Checkpointer closed")

    @property
    def checkpointer(self) -> Optional[AsyncSqliteSaver]:
        """获取 LangGraph checkpointer 实例"""
        return self._checkpointer

    # --- 会话管理 ---

    def ensure_session(self, user_id: str, master_id: str, session_id: str) -> str:
        """确保会话存在，返回 session_id

        如果会话不存在则创建。同时确保 user 和 profile 存在。
        """
        existing = user_manager.get_session(session_id)
        if existing:
            return session_id

        # 确保用户存在（外键约束要求 users 表有对应记录）
        now = user_manager.datetime.utcnow().isoformat()
        from heritage_master.data.db import get_conn
        with get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users (id, nickname, password_hash, created_at, last_active_at) VALUES (?, ?, '', ?, ?)",
                (user_id, "u_" + user_id, now, now),
            )
            conn.execute(
                "INSERT OR IGNORE INTO chat_sessions (id, user_id, master_id, started_at) VALUES (?, ?, ?, ?)",
                (session_id, user_id, master_id, now),
            )
            conn.execute(
                "INSERT OR IGNORE INTO user_profiles (user_id, master_id, relationship_stage, question_count, first_met_at, last_talk_at) VALUES (?, ?, '入门期', 0, ?, ?)",
                (user_id, master_id, now, now),
            )
        return session_id

    # --- 上下文构建 ---

    def build_messages(
        self,
        user_id: str,
        master_id: str,
        session_id: str,
        new_message: str,
        system_prompt: str,
    ) -> list:
        """构建完整的上下文消息列表

        流程：
        1. 从 SQLite 加载历史消息
        2. 注入用户画像到 system prompt
        3. 拼接历史 + 新消息
        4. 如果超长则截断
        """
        messages = []

        # 1. System prompt + 用户画像
        profile_context = self._build_profile_context(user_id, master_id)
        full_system = system_prompt
        if profile_context:
            full_system += "\n\n" + profile_context
        messages.append(SystemMessage(content=full_system))

        # 2. 加载历史消息
        history = user_manager.get_recent_messages(session_id, limit=MAX_CONTEXT_MESSAGES)
        for h in history:
            role = h.get("role", "")
            content = h.get("content", "")
            if role == "user" and content:
                messages.append(HumanMessage(content=content))
            elif role == "assistant" and content:
                messages.append(AIMessage(content=content))

        # 3. 添加新消息
        messages.append(HumanMessage(content=new_message))

        # 4. 上下文窗口裁剪
        messages = self._trim_context(messages)

        return messages

    def _build_profile_context(self, user_id: str, master_id: str) -> str:
        """从长期记忆构建用户画像上下文"""
        try:
            memory = self._memory_manager.load_memory(master_id, user_id)
            if not memory:
                return ""

            profile = memory.get("profile", {})
            teaching = memory.get("teaching_progress", {})
            core_memories = memory.get("core_memories", [])

            parts = []

            # 基本画像
            stage = profile.get("relationship_stage", "入门期")
            interests = profile.get("interest_tags", [])
            notes = profile.get("personality_notes", "")
            q_count = profile.get("question_count", 0)

            parts.append(f"【学徒画像】阶段: {stage}，提问次数: {q_count}")
            if interests:
                parts.append(f"兴趣标签: {', '.join(interests)}")
            if notes:
                parts.append(f"性格特点: {notes}")

            # 教学进度
            completed = teaching.get("completed_topics", [])
            if completed:
                parts.append(f"已学内容: {', '.join(completed[-5:])}")

            # 核心记忆（最近3条）
            if core_memories:
                recent = sorted(core_memories, key=lambda m: m.get("created_at", ""), reverse=True)[:3]
                memory_texts = [m.get("content", "") for m in recent if m.get("content")]
                if memory_texts:
                    parts.append(f"重要记忆: {'; '.join(memory_texts)}")

            return "\n".join(parts)
        except Exception as e:
            logger.warning("构建用户画像失败: %s", e)
            return ""

    def _trim_context(self, messages: list) -> list:
        """上下文窗口裁剪

        策略：
        - 保留 SystemMessage（第一条）
        - 如果消息数超过限制，从中间截断
        - 保留最近的 CONTEXT_WINDOW_TRIM_TO 条消息
        """
        if len(messages) <= MAX_CONTEXT_MESSAGES:
            return messages

        # 分离 system prompt 和对话消息
        system_msg = messages[0] if isinstance(messages[0], SystemMessage) else None
        conversation = messages[1:] if system_msg else messages

        # 截断对话：保留最近的 N 条
        trimmed = conversation[-CONTEXT_WINDOW_TRIM_TO:]

        if system_msg:
            result = [system_msg] + trimmed
        else:
            result = trimmed

        logger.info(
            "上下文裁剪: %d -> %d 条消息",
            len(messages), len(result),
        )
        return result

    # --- 消息持久化 ---

    def save_message(self, session_id: str, role: str, content: str) -> None:
        """保存一条消息到 SQLite"""
        try:
            user_manager.add_message(session_id, role, content)
        except Exception as e:
            logger.warning("保存消息失败: %s", e)

    def save_conversation_pair(
        self, session_id: str, user_message: str, assistant_reply: str
    ) -> None:
        """保存一轮对话（用户问题 + 助手回复）"""
        self.save_message(session_id, "user", user_message)
        self.save_message(session_id, "assistant", assistant_reply)


# --- 全局单例 ---

_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """获取全局 ContextManager 实例"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
