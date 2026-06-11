"""
共享依赖 — Web 层的公共实例和服务

所有 router 从这里导入共享的 LLM、记忆管理器、用户管理器等，
避免在每个 router 中重复创建。
"""

from __future__ import annotations

from heritage_master.llm.factory import create_llm_from_settings
from heritage_master.tools.memory import MemoryManager
from heritage_master.tools import user_manager

# 记忆系统单例
_memory_manager: MemoryManager | None = None


def get_memory_manager() -> MemoryManager:
    """获取记忆管理器单例（带 Redis 缓存）"""
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


def get_llm():
    """获取 LLM 实例"""
    return create_llm_from_settings()


def llm_available() -> bool:
    """检查 LLM 是否可用"""
    return get_llm() is not None
