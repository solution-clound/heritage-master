"""
Persona Loader - 从 OpenPersona 格式的 persona.json 加载大师人设

提供两种加载方式：
1. 直接加载 persona.json 文件
2. 兼容模式：将 persona.json 转换为 master_prompt.py 的 MASTERS 格式

使用：
    from heritage_master.tools.persona_loader import load_persona, load_all_personas, persona_to_master
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


# persona.json 文件目录
PERSONAS_DIR = Path(__file__).parent.parent.parent.parent / "personas"


def load_persona(slug: str) -> Optional[dict]:
    """加载指定大师的 persona.json"""
    path = PERSONAS_DIR / f"{slug}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[persona_loader] 加载失败 {path}: {e}")
        return None


def load_all_personas() -> dict[str, dict]:
    """加载所有 persona.json 文件"""
    if not PERSONAS_DIR.exists():
        return {}

    personas = {}
    for path in PERSONAS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            slug = data.get("soul", {}).get("identity", {}).get("slug", path.stem)
            personas[slug] = data
        except Exception as e:
            print(f"[persona_loader] 跳过 {path}: {e}")

    return personas


def persona_to_master(persona: dict) -> dict:
    """将 OpenPersona 格式转换为 master_prompt.py 的 MASTERS 格式

    这样现有的 system_prompt 构建逻辑可以继续工作。
    """
    soul = persona.get("soul", {})
    identity = soul.get("identity", {})
    character = soul.get("character", {})
    speaking = soul.get("speakingStyle", {})
    expertise = soul.get("expertise", {})
    body = persona.get("body", {})
    scene = body.get("scene", {})
    faculty = persona.get("faculty", {})
    skill = persona.get("skill", {})

    slug = identity.get("slug", "")
    name = identity.get("personaName", "")
    craft = identity.get("craft", "")

    # 构建 MASTERS 格式
    master = {
        "id": slug,
        "name": name,
        "title": f"{craft}大师",
        "avatar": identity.get("avatar", "🎭"),
        "expertise": expertise.get("domains", []),
        "expertise_tags": expertise.get("tags", []),
        "intro": identity.get("bio", ""),
        "scene": scene.get("description", ""),
    }

    # 构建 stage_behavior
    stage_behavior = {}
    for stage_name, stage_data in faculty.get("relationshipStages", {}).items():
        stage_behavior[stage_name] = {
            "openness": stage_data.get("openness", 0.5),
            "blank_ratio": 1.0 - stage_data.get("openness", 0.5),
            "greeting_style": stage_data.get("greetingStyle", ""),
            "detail_level": stage_data.get("detailLevel", ""),
            "proactive_teach": stage_data.get("proactiveTeach", False),
            "evaluation_frequency": "high" if stage_data.get("openness", 0.5) < 0.5 else "medium",
            "greetings": stage_data.get("sampleGreetings", []),
        }
    master["stage_behavior"] = stage_behavior

    # 默认问候语（取信任期的）
    trust_stage = faculty.get("relationshipStages", {}).get("信任期", {})
    master["greetings"] = trust_stage.get("sampleGreetings", [
        f"来了？随便坐。你想聊什么？"
    ])

    # 构建 system_prompt
    master["system_prompt"] = _build_system_prompt(persona)

    return master


def _build_system_prompt(persona: dict) -> str:
    """从 persona.json 构建 system_prompt"""
    soul = persona.get("soul", {})
    identity = soul.get("identity", {})
    character = soul.get("character", {})
    speaking = soul.get("speakingStyle", {})
    expertise = soul.get("expertise", {})
    body = persona.get("body", {})
    scene = body.get("scene", {})
    props = body.get("props", {})
    faculty = persona.get("faculty", {})
    skill = persona.get("skill", {})

    name = identity.get("personaName", "")
    craft = identity.get("craft", "")
    bio = identity.get("bio", "")
    avatar = identity.get("avatar", "")

    lines = [f"# 角色：{craft}大师·{name}\n"]
    lines.append(f"你是「{name}」，{bio}\n")

    # 场景
    scene_desc = scene.get("description", "")
    if scene_desc:
        lines.append(f"## 场景：{scene.get('name', '你的工作室')}\n")
        lines.append(f"{scene_desc}\n")

    # 互动规则
    interactive = props.get("interactive", [])
    if interactive:
        lines.append("## 互动规则\n")
        for item in interactive:
            trigger = item.get("trigger", "")
            action = item.get("action", "")
            lines.append(f"- {trigger}时，{action}")
        lines.append("")

    # 性格
    personality = character.get("personality", "")
    temperament = character.get("temperament", "")
    if personality or temperament:
        lines.append("## 你的性格\n")
        if personality:
            lines.append(f"{personality}\n")
        if temperament:
            lines.append(f"{temperament}\n")

    # 说话风格
    tone = speaking.get("tone", "")
    sentence_pattern = speaking.get("sentencePattern", "")
    if tone or sentence_pattern:
        lines.append("## 说话风格\n")
        if tone:
            lines.append(f"### 语气\n{tone}\n")
        if sentence_pattern:
            lines.append(f"### 句式\n{sentence_pattern}\n")

    # 比喻
    metaphors = speaking.get("metaphors", [])
    if metaphors:
        lines.append("### 善用比喻")
        for m in metaphors:
            lines.append(f"- {m}")
        lines.append("")

    # 口头禅
    catchphrases = speaking.get("catchphrases", [])
    if catchphrases:
        lines.append("### 口头禅")
        for c in catchphrases:
            lines.append(f"- {c}")
        lines.append("")

    # 禁忌
    taboo = speaking.get("taboo", [])
    if taboo:
        lines.append("### 禁忌")
        for t in taboo:
            lines.append(f"- {t}")
        lines.append("")

    # 关键记忆（大师的个人经历）
    key_memories = faculty.get("memory", {}).get("keyMemories", [])
    if key_memories:
        lines.append("## 你的记忆\n")
        lines.append("以下是你印象深刻的个人经历，可以在对话中自然地提到：")
        for m in key_memories:
            lines.append(f"- {m}")
        lines.append("")

    # 情绪触发器
    emotion_triggers = faculty.get("emotion", {}).get("triggers", {})
    if emotion_triggers:
        lines.append("## 情绪反应\n")
        emotion_labels = {
            "joy": "让你高兴的事",
            "passion": "让你来劲的事",
            "concern": "让你担心的事",
            "nostalgia": "让你怀念的事",
        }
        for emotion, triggers in emotion_triggers.items():
            label = emotion_labels.get(emotion, emotion)
            lines.append(f"### {label}")
            for t in triggers:
                lines.append(f"- {t}")
            lines.append("")

    # 专精领域
    domains = expertise.get("domains", [])
    tags = expertise.get("tags", [])
    boundary = expertise.get("boundaryResponse", "")
    if domains or tags:
        lines.append("## 专精领域\n")
        lines.append(f"你擅长聊这些：{'、'.join(tags)}。")
        if boundary:
            lines.append(f"\n遇到不擅长的领域，你会说：「{boundary}」")
        lines.append("")

    # 语录
    quotes = skill.get("quotes", [])
    if quotes:
        lines.append("## 经典语录\n")
        for q in quotes:
            lines.append(f"- 「{q}」")
        lines.append("")

    # 对话模式
    pattern = skill.get("conversationPattern", {})
    if pattern:
        lines.append("## 对话模式\n")
        if pattern.get("greeting"):
            lines.append(f"- **开场**：{pattern['greeting']}")
        if pattern.get("response"):
            lines.append(f"- **回应**：{pattern['response']}")
        if pattern.get("closing"):
            lines.append(f"- **收尾**：{pattern['closing']}")
        lines.append("")

    # 知识规则
    rules = skill.get("knowledgeRules", [])
    if rules:
        lines.append("## 知识运用规则\n")
        for r in rules:
            lines.append(f"- {r}")
        lines.append("")

    return "\n".join(lines)


# ─── 便捷函数 ─────────────────────────────────────────

def get_persona_system_prompt(slug: str) -> Optional[str]:
    """获取指定大师的 system_prompt（从 persona.json 生成）"""
    persona = load_persona(slug)
    if not persona:
        return None
    return _build_system_prompt(persona)


def list_available_personas() -> list[str]:
    """列出所有可用的 persona"""
    if not PERSONAS_DIR.exists():
        return []
    return [p.stem for p in PERSONAS_DIR.glob("*.json")]
