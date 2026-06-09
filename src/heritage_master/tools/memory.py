"""
长期记忆系统 — 大师对学徒的跨会话记忆

提供三个核心类：
- MemoryManager: 记忆文件 CRUD + Redis 缓存
- MemoryExtractor: 从对话中提取记忆（LLM + 规则兜底）
- GreetingGenerator: 个性化问候生成

记忆文件结构：memory/{master_id}/{user_id}.json
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from heritage_master.config import settings

# 记忆文件根目录
MEMORY_DIR = Path(settings.memory_dir)

# 记忆类型枚举
MEMORY_TYPES = ("interest", "milestone", "preference", "personality", "event", "feedback")

# 阶段名称规范化
_STAGE_ALIASES = {"试探期": "入门期", "初期": "入门期", "初识": "入门期"}
_VALID_STAGES = {"入门期", "成长期", "精进期", "传承期"}


def _normalize_stage(stage: str) -> str:
    """将非标准阶段名映射到标准四阶段"""
    if stage in _VALID_STAGES:
        return stage
    return _STAGE_ALIASES.get(stage, "入门期")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_memory(user_id: str, master_id: str) -> dict:
    """创建空白记忆模板"""
    return {
        "version": "1.0",
        "user_id": user_id,
        "master_id": master_id,
        "profile": {
            "relationship_stage": "入门期",
            "interest_tags": [],
            "personality_notes": "",
            "aesthetic_pref": "",
            "question_count": 0,
            "first_met_at": _now_iso(),
            "last_talk_at": _now_iso(),
        },
        "core_memories": [],
        "data_records": {
            "practice_history": [],
            "conversation_topics": [],
            "visit_log": [],
        },
        "teaching_progress": {
            "current_stage": "入门期",
            "completed_topics": [],
            "next_topics": [],
            "total_practice_days": 0,
            "total_questions": 0,
            "mastery_scores": {},
        },
        "meta": {
            "last_consolidated_at": None,
            "memory_count": 0,
            "consolidation_count": 0,
        },
    }


# ============================================================
# MemoryManager — 文件 CRUD + Redis 缓存
# ============================================================

class MemoryManager:
    """管理用户长期记忆的读写、缓存和整理"""

    def __init__(self, redis_client=None):
        self.redis = redis_client

    # --- 文件路径 ---

    def _get_memory_path(self, master_id: str, user_id: str) -> Path:
        return MEMORY_DIR / master_id / f"{user_id}.json"

    def _ensure_dir(self, master_id: str) -> None:
        (MEMORY_DIR / master_id).mkdir(parents=True, exist_ok=True)

    # --- 缓存层 ---

    def _cache_key(self, master_id: str, user_id: str) -> str:
        return f"heritage:memory:{master_id}:{user_id}"

    def _cache_get(self, key: str) -> Optional[dict]:
        if not self.redis:
            return None
        try:
            raw = self.redis.get(key)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    def _cache_set(self, key: str, value: dict, ttl: int = 600) -> None:
        if not self.redis:
            return
        try:
            self.redis.setex(key, ttl, json.dumps(value, ensure_ascii=False))
        except Exception:
            pass

    def invalidate_cache(self, master_id: str, user_id: str) -> None:
        if self.redis:
            try:
                self.redis.delete(self._cache_key(master_id, user_id))
            except Exception:
                pass

    # --- 核心读写 ---

    def load_memory(self, master_id: str, user_id: str) -> dict:
        """加载用户记忆（读穿透：Redis → 文件 → 回填）"""
        cache_key = self._cache_key(master_id, user_id)

        # 1. 尝试 Redis
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        # 2. 读文件
        path = self._get_memory_path(master_id, user_id)
        if path.exists():
            try:
                memory = json.loads(path.read_text(encoding="utf-8"))
                self._cache_set(cache_key, memory, settings.memory_cache_ttl)
                return memory
            except Exception:
                pass

        # 3. 不存在则创建空白
        memory = _empty_memory(user_id, master_id)
        self.save_memory(master_id, user_id, memory)
        return memory

    def save_memory(self, master_id: str, user_id: str, memory: dict) -> None:
        """保存用户记忆（写穿透：文件 → Redis）"""
        self._ensure_dir(master_id)
        path = self._get_memory_path(master_id, user_id)
        path.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")
        self._cache_set(self._cache_key(master_id, user_id), memory, settings.memory_cache_ttl)

    # --- 核心记忆 CRUD ---

    def add_core_memory(self, master_id: str, user_id: str, memory_entry: dict) -> str:
        """追加一条核心记忆，返回分配的 id"""
        memory = self.load_memory(master_id, user_id)
        mem_id = f"mem_{uuid.uuid4().hex[:8]}"
        entry = {
            "id": mem_id,
            "type": memory_entry.get("type", "event"),
            "content": memory_entry.get("content", ""),
            "importance": memory_entry.get("importance", 5),
            "created_at": _now_iso(),
            "last_referenced": None,
            "reference_count": 0,
            "source": memory_entry.get("source", "conversation"),
            "tags": memory_entry.get("tags", []),
        }
        memory["core_memories"].append(entry)
        memory["meta"]["memory_count"] = len(memory["core_memories"])
        self.save_memory(master_id, user_id, memory)
        return mem_id

    def get_core_memories(self, master_id: str, user_id: str,
                          memory_type: Optional[str] = None,
                          limit: int = 20) -> list[dict]:
        """查询核心记忆"""
        memory = self.load_memory(master_id, user_id)
        memories = memory.get("core_memories", [])
        if memory_type:
            memories = [m for m in memories if m.get("type") == memory_type]
        # 按重要度降序
        memories.sort(key=lambda m: m.get("importance", 0), reverse=True)
        return memories[:limit]

    def update_memory_reference(self, master_id: str, user_id: str, memory_id: str) -> None:
        """更新记忆的引用计数"""
        memory = self.load_memory(master_id, user_id)
        for m in memory.get("core_memories", []):
            if m["id"] == memory_id:
                m["last_referenced"] = _now_iso()
                m["reference_count"] = m.get("reference_count", 0) + 1
                break
        self.save_memory(master_id, user_id, memory)

    # --- 画像同步 ---

    def sync_profile_from_db(self, master_id: str, user_id: str, db_profile: dict) -> None:
        """从数据库同步画像到记忆文件"""
        memory = self.load_memory(master_id, user_id)
        profile = memory["profile"]
        profile["relationship_stage"] = db_profile.get("relationship_stage", profile["relationship_stage"])
        profile["interest_tags"] = db_profile.get("interest_tags", profile["interest_tags"])
        profile["personality_notes"] = db_profile.get("personality_notes", profile["personality_notes"])
        profile["aesthetic_pref"] = db_profile.get("aesthetic_pref", profile["aesthetic_pref"])
        profile["question_count"] = db_profile.get("question_count", profile["question_count"])
        if db_profile.get("first_met_at"):
            profile["first_met_at"] = db_profile["first_met_at"]
        if db_profile.get("last_talk_at"):
            profile["last_talk_at"] = db_profile["last_talk_at"]
        self.save_memory(master_id, user_id, memory)

    # --- 话题记录 ---

    def add_conversation_topic(self, master_id: str, user_id: str, topic: str) -> None:
        """记录一次对话话题"""
        memory = self.load_memory(master_id, user_id)
        topics = memory["data_records"]["conversation_topics"]
        today = datetime.now(timezone.utc).date().isoformat()
        for t in topics:
            if t["topic"] == topic:
                t["count"] += 1
                t["last_discussed"] = today
                self.save_memory(master_id, user_id, memory)
                return
        topics.append({"topic": topic, "count": 1, "last_discussed": today})
        self.save_memory(master_id, user_id, memory)

    def add_visit_log(self, master_id: str, user_id: str,
                      session_id: str, topic_summary: str = "") -> None:
        """记录一次来访"""
        memory = self.load_memory(master_id, user_id)
        memory["data_records"]["visit_log"].append({
            "date": datetime.now(timezone.utc).date().isoformat(),
            "session_id": session_id,
            "topic_summary": topic_summary,
        })
        memory["profile"]["last_talk_at"] = _now_iso()
        self.save_memory(master_id, user_id, memory)

    def update_visit_topic_summary(self, master_id: str, user_id: str,
                                   session_id: str, topic_summary: str) -> None:
        """更新来访记录的话题摘要"""
        memory = self.load_memory(master_id, user_id)
        for log in reversed(memory["data_records"]["visit_log"]):
            if log["session_id"] == session_id:
                log["topic_summary"] = topic_summary
                break
        self.save_memory(master_id, user_id, memory)

    # --- 教学进度 ---

    def update_teaching_progress(self, master_id: str, user_id: str, **kwargs) -> None:
        """更新教学进度"""
        memory = self.load_memory(master_id, user_id)
        tp = memory["teaching_progress"]
        for k, v in kwargs.items():
            if k in tp:
                if k == "completed_topics" and isinstance(v, str):
                    if v not in tp[k]:
                        tp[k].append(v)
                elif k == "mastery_scores" and isinstance(v, dict):
                    tp[k].update(v)
                else:
                    tp[k] = v
        self.save_memory(master_id, user_id, memory)

    # --- 整理检查 ---

    def check_consolidation(self, master_id: str, user_id: str) -> bool:
        """检查是否需要整理记忆"""
        memory = self.load_memory(master_id, user_id)
        return len(memory.get("core_memories", [])) >= settings.memory_consolidation_threshold

    async def consolidate_memories(self, master_id: str, user_id: str,
                                   llm_func: Callable) -> None:
        """调用 LLM 整理压缩记忆"""
        memory = self.load_memory(master_id, user_id)
        memories = memory.get("core_memories", [])
        if len(memories) < settings.memory_consolidation_threshold:
            return

        memory_text = "\n".join(
            f"- [{m['type']}] {m['content']} (重要度:{m['importance']}, 引用:{m['reference_count']}次)"
            for m in memories
        )

        prompt = (
            f"你是非遗大师助手的记忆整理模块。请将以下{len(memories)}条记忆整理合并。\n\n"
            f"{memory_text}\n\n"
            "要求：\n"
            "1. 合并相似记忆（如多条关于同一话题的兴趣记录）\n"
            "2. 保留高重要度和高引用次数的记忆\n"
            "3. 去除过时或重复的信息\n"
            "4. 输出精简后的JSON数组，每条保留原有字段格式（id/type/content/importance/created_at/last_referenced/reference_count/source/tags）\n"
            "5. 目标：压缩到20-25条核心记忆\n"
            "只返回JSON数组，不要其他文字。"
        )

        try:
            result = await llm_func(prompt)
            # 提取 JSON
            text = result.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            consolidated = json.loads(text)
            if isinstance(consolidated, list):
                memory["core_memories"] = consolidated
                memory["meta"]["last_consolidated_at"] = _now_iso()
                memory["meta"]["memory_count"] = len(consolidated)
                memory["meta"]["consolidation_count"] += 1
                self.save_memory(master_id, user_id, memory)
        except Exception as e:
            print(f"[memory] 整理记忆失败: {e}")

    # --- Prompt 上下文生成 ---

    def get_memory_context(self, master_id: str, user_id: str) -> str:
        """将记忆格式化为 prompt 注入文本"""
        memory = self.load_memory(master_id, user_id)
        lines = ["【你对这个学徒的记忆】"]

        # 核心记忆（取最重要的 5 条）
        core = memory.get("core_memories", [])
        if core:
            top = sorted(core, key=lambda m: m.get("importance", 0), reverse=True)[:5]
            lines.append("- 核心记忆：")
            for m in top:
                lines.append(f"  · {m['content']}（重要度{m.get('importance', 5)}）")

        # 近期话题
        topics = memory["data_records"].get("conversation_topics", [])
        if topics:
            recent = sorted(topics, key=lambda t: t.get("last_discussed", ""), reverse=True)[:3]
            topic_str = "、".join(f"{t['topic']}({t['count']}次)" for t in recent)
            lines.append(f"- 近期话题：{topic_str}")

        # 教学进度
        tp = memory.get("teaching_progress", {})
        stage = tp.get("current_stage", "")
        if stage:
            completed = tp.get("completed_topics", [])
            next_topics = tp.get("next_topics", [])
            progress_str = f"- 修行进度：{stage}"
            if completed:
                progress_str += f"，已学「{'」「'.join(completed[-3:])}」"
            if next_topics:
                progress_str += f"，建议下一步「{'」「'.join(next_topics[:2])}」"
            lines.append(progress_str)

        # 上次来访
        last_talk = memory["profile"].get("last_talk_at", "")
        if last_talk:
            try:
                last_dt = datetime.fromisoformat(last_talk)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                days = (datetime.now(timezone.utc) - last_dt).days
                if days == 0:
                    lines.append("- 上次来访：今天")
                elif days == 1:
                    lines.append("- 上次来访：昨天")
                else:
                    lines.append(f"- 上次来访：{days}天前")
            except Exception:
                pass

        return "\n".join(lines)

    def get_greeting_context(self, master_id: str, user_id: str) -> dict:
        """返回问候所需的结构化数据"""
        memory = self.load_memory(master_id, user_id)

        # 计算缺席天数
        absence_days = 0
        last_talk = memory["profile"].get("last_talk_at", "")
        if last_talk:
            try:
                last_dt = datetime.fromisoformat(last_talk)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                absence_days = (datetime.now(timezone.utc) - last_dt).days
            except Exception:
                pass

        # 最近话题
        topics = memory["data_records"].get("conversation_topics", [])
        recent_topics = sorted(topics, key=lambda t: t.get("last_discussed", ""), reverse=True)[:3]

        # 最近高重要度记忆
        core = memory.get("core_memories", [])
        recent_memory = sorted(core, key=lambda m: m.get("importance", 0), reverse=True)[:2] if core else []

        # 教学进度
        tp = memory.get("teaching_progress", {})

        # 是否首次见面
        is_first = len(memory["data_records"].get("visit_log", [])) <= 1

        return {
            "absence_days": absence_days,
            "recent_topics": recent_topics,
            "recent_memory": recent_memory,
            "teaching_progress": tp,
            "is_first": is_first,
            "relationship_stage": memory["profile"].get("relationship_stage", "试探期"),
            "question_count": memory["profile"].get("question_count", 0),
        }


# ============================================================
# MemoryExtractor — 记忆提取（LLM + 规则兜底）
# ============================================================

# 规则匹配的关键词映射
_RULE_PATTERNS = {
    "interest": [
        "我想学", "我想了解", "能教我", "怎么", "什么是", "为什么",
        "有什么区别", "哪个好", "推荐", "介绍一下",
    ],
    "preference": [
        "我喜欢", "我不喜欢", "我觉得", "更喜欢", "偏爱",
        "好喝", "好看", "好听", "不错",
    ],
    "personality": [
        "太难了", "不懂", "明白了", "原来如此", "厉害",
        "佩服", "谢谢", "好的",
    ],
    "milestone": [
        "第一次", "学会了", "终于", "做到了", "完成了",
    ],
}


class MemoryExtractor:
    """从对话中提取值得记忆的信息"""

    def __init__(self, llm_func: Optional[Callable] = None):
        self.llm_func = llm_func

    async def extract_from_conversation(
        self,
        user_message: str,
        master_reply: str,
        master_id: str,
        existing_memory: dict,
    ) -> list[dict]:
        """LLM 提取记忆，失败时降级为规则匹配"""
        if self.llm_func:
            try:
                return await self._llm_extract(user_message, master_reply, master_id, existing_memory)
            except Exception as e:
                print(f"[memory] LLM 提取失败，降级为规则: {e}")

        return self.extract_by_rules(user_message, master_reply, master_id)

    async def _llm_extract(
        self,
        user_message: str,
        master_reply: str,
        master_id: str,
        existing_memory: dict,
    ) -> list[dict]:
        """LLM 提取"""
        # 构建已有记忆摘要
        core = existing_memory.get("core_memories", [])
        summary_parts = []
        for m in core[-10:]:
            summary_parts.append(f"- [{m['type']}] {m['content']}")
        existing_summary = "\n".join(summary_parts) if summary_parts else "（暂无）"

        prompt = (
            "你是非遗大师助手的记忆提取模块。根据以下对话，提取值得记住的信息。\n\n"
            f"用户消息：{user_message}\n"
            f"大师回复：{master_reply[:300]}\n"
            f"已有记忆摘要：\n{existing_summary}\n\n"
            "请提取以下类型的记忆（JSON数组）：\n"
            "- interest: 用户表现出兴趣的话题\n"
            "- preference: 审美或风格偏好\n"
            "- personality: 性格观察\n"
            "- milestone: 学习里程碑\n"
            "- event: 重要交互事件（如长时间缺席后回来）\n"
            "- feedback: 用户的反馈或反应\n\n"
            "每条记忆包含：type, content(一句话描述), importance(1-10), tags(关键词列表)\n"
            "如果没有值得记忆的信息，返回空数组 []\n"
            "只返回JSON，不要其他文字。"
        )

        result = await self.llm_func(prompt)
        text = result.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        extracted = json.loads(text)
        if not isinstance(extracted, list):
            return []

        # 验证格式
        valid = []
        for item in extracted:
            if isinstance(item, dict) and "type" in item and "content" in item:
                item.setdefault("importance", 5)
                item.setdefault("tags", [])
                item.setdefault("source", "conversation")
                if item["type"] in MEMORY_TYPES:
                    valid.append(item)
        return valid

    def extract_by_rules(
        self,
        user_message: str,
        master_reply: str,
        master_id: str,
    ) -> list[dict]:
        """规则兜底提取"""
        results = []
        msg = user_message.strip()

        if not msg or len(msg) < 4:
            return results

        for mem_type, patterns in _RULE_PATTERNS.items():
            for pattern in patterns:
                if pattern in msg:
                    results.append({
                        "type": mem_type,
                        "content": f"用户说：{msg[:80]}",
                        "importance": 6 if mem_type == "interest" else 4,
                        "tags": [],
                        "source": "rule",
                    })
                    break  # 每种类型只匹配一次

        return results

    async def infer_profile_updates(
        self,
        conversation_history: list[dict],
        current_profile: dict,
    ) -> dict:
        """从对话历史推断画像更新"""
        if not self.llm_func:
            return {}

        history_text = "\n".join(
            f"{'用户' if m['role'] == 'user' else '大师'}: {m['content'][:150]}"
            for m in conversation_history[-10:]
        )

        current_tags = current_profile.get("interest_tags", [])
        current_notes = current_profile.get("personality_notes", "")

        prompt = (
            "你是非遗大师助手的画像分析模块。根据以下对话历史，推断用户的兴趣和性格特征。\n\n"
            f"对话历史：\n{history_text}\n\n"
            f"已知兴趣标签：{', '.join(current_tags) if current_tags else '无'}\n"
            f"已知性格观察：{current_notes if current_notes else '无'}\n\n"
            "请返回JSON对象，包含以下可选字段（只包含需要更新的）：\n"
            '- "new_interests": 新发现的兴趣标签列表（与已有标签去重）\n'
            '- "personality_notes": 新的性格观察（一句话，会追加到已有观察后）\n'
            '- "aesthetic_pref": 审美偏好描述\n'
            "如果没有需要更新的，返回空对象 {}。只返回JSON。"
        )

        try:
            result = await self.llm_func(prompt)
            text = result.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            updates = json.loads(text)
            return updates if isinstance(updates, dict) else {}
        except Exception as e:
            print(f"[memory] 画像推断失败: {e}")
            return {}

    def extract_topics(self, text: str, master_id: str) -> list[str]:
        """从文本中提取话题关键词"""
        # 非遗术语词典
        heritage_terms = [
            "凤凰单丛", "鸭屎香", "工夫茶", "潮州", "盖碗", "紫砂壶",
            "醒狮", "采青", "狮头", "鼓乐", "武术",
            "香型", "山韵", "火候", "冲泡", "品鉴",
            "传承", "非遗", "文化", "技艺", "工艺",
        ]
        found = []
        for term in heritage_terms:
            if term in text:
                found.append(term)
        return found[:5]


# ============================================================
# GreetingGenerator — 个性化问候生成
# ============================================================

class GreetingGenerator:
    """根据记忆生成个性化开场白"""

    def generate_greeting(
        self,
        master_id: str,
        memory: dict,
        persona_data: Optional[dict] = None,
    ) -> str:
        """生成个性化问候"""
        profile = memory.get("profile", {})
        stage = profile.get("relationship_stage", "试探期")
        core = memory.get("core_memories", [])
        tp = memory.get("teaching_progress", {})
        topics = memory["data_records"].get("conversation_topics", [])
        visit_log = memory["data_records"].get("visit_log", [])
        is_first = len(visit_log) <= 1

        # 计算缺席天数
        absence_days = 0
        last_talk = profile.get("last_talk_at", "")
        if last_talk:
            try:
                last_dt = datetime.fromisoformat(last_talk)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                absence_days = (datetime.now(timezone.utc) - last_dt).days
            except Exception:
                pass

        parts = []

        # 1. 首次见面
        if is_first:
            if stage == "试探期":
                return "坐。——先喝杯茶，喝完再说。"
            return "来了？随便坐。你想聊什么？"

        # 2. 缺席问候
        if absence_days >= 7:
            parts.append(f"好久不见了，{absence_days}天没来了吧？最近忙？")
        elif absence_days >= 3:
            parts.append(f"来了？{absence_days}天没见你了。")

        # 3. 引用最近高重要度记忆
        if core and not parts:
            top_mem = max(core, key=lambda m: m.get("importance", 0))
            if top_mem.get("importance", 0) >= 7:
                content = top_mem["content"]
                # 简化引用
                if "鸭屎香" in content:
                    parts.append("来了？上次说的鸭屎香，后来自己泡了没有？")
                elif "泡茶" in content or "练习" in content:
                    parts.append("嗯，上次练习的感觉还记得吗？")
                elif "香型" in content:
                    parts.append("来了？上次聊的香型，今天咱们接着说。")

        # 4. 教学进度推进
        if not parts and tp:
            next_topics = tp.get("next_topics", [])
            if next_topics:
                parts.append(f"嗯，今天该学{next_topics[0]}了。")

        # 5. 话题延续
        if not parts and topics:
            recent = sorted(topics, key=lambda t: t.get("last_discussed", ""), reverse=True)
            if recent:
                parts.append(f"来了？上次聊的{recent[0]['topic']}，想继续吗？")

        # 6. 默认
        if not parts:
            if stage == "试探期":
                parts.append("坐。")
            elif stage == "信任期":
                parts.append("来了？今天想聊什么？")
            else:
                parts.append("来了？准备好了吗？")

        return "".join(parts)
