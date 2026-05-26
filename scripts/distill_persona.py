#!/usr/bin/env python3
"""
人设蒸馏脚本 - 从语录/采访文本提取人设特征，生成 OpenPersona 格式的 persona.json

使用方式：
    # 从文本文件蒸馏
    python scripts/distill_persona.py --input quotes.txt --name "叶汉钟" --craft "潮州工夫茶艺"

    # 从已有 master_prompt.py 提取
    python scripts/distill_persona.py --from-master chagongfu

    # 批量蒸馏（从 docs/real_masters_distillation.md）
    python scripts/distill_persona.py --from-doc

依赖：需要配置 HERITAGE_LLM_API_KEY（DeepSeek/OpenAI）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 添加项目路径
_project_root = Path(__file__).resolve().parent.parent
_src_dir = str(_project_root / "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

# ─── 模板 ─────────────────────────────────────────────

PERSONA_TEMPLATE = {
    "soul": {
        "identity": {
            "personaName": "",
            "slug": "",
            "bio": "",
            "avatar": "",
            "era": "",
            "location": "",
            "craft": "",
            "category": "",
            "level": ""
        },
        "character": {
            "personality": "",
            "values": [],
            "temperament": "",
            "quirks": []
        },
        "speakingStyle": {
            "tone": "",
            "vocabulary": [],
            "sentencePattern": "",
            "metaphors": [],
            "catchphrases": [],
            "taboo": []
        },
        "expertise": {
            "domains": [],
            "tags": [],
            "deepTopics": [],
            "boundaryResponse": ""
        }
    },
    "body": {
        "scene": {
            "name": "",
            "description": "",
            "objects": [],
            "mood": ""
        },
        "props": {
            "interactive": []
        }
    },
    "faculty": {
        "memory": {
            "type": "semantic",
            "keyMemories": []
        },
        "emotion": {
            "triggers": {}
        },
        "relationshipStages": {
            "试探期": {
                "openness": 0.3,
                "greetingStyle": "警惕",
                "detailLevel": "浅",
                "proactiveTeach": False,
                "sampleGreetings": []
            },
            "信任期": {
                "openness": 0.7,
                "greetingStyle": "热情",
                "detailLevel": "中",
                "proactiveTeach": True,
                "sampleGreetings": []
            },
            "修行期": {
                "openness": 1.0,
                "greetingStyle": "亲昵",
                "detailLevel": "深",
                "proactiveTeach": True,
                "specialTopics": ["传承心得", "行业观察", "人生感悟"],
                "sampleGreetings": []
            }
        }
    },
    "skill": {
        "conversationPattern": {
            "greeting": "",
            "response": "",
            "topicSwitch": "",
            "closing": ""
        },
        "knowledgeRules": [],
        "quotes": []
    },
    "evolution": {
        "version": "1.0.0",
        "createdAt": "",
        "source": "",
        "distillationMethod": "LLM-assisted distillation",
        "updateHistory": []
    }
}


# ─── LLM 蒸馏 ─────────────────────────────────────────

DISTILL_SYSTEM_PROMPT = """你是一个专业的人设蒸馏助手。你的任务是从原始文本素材中提取人物的人格特征，生成结构化的 JSON 数据。

你需要从语录、采访、描述文本中提取以下信息：

1. **身份信息**（identity）：姓名、简介、年代、地区、技艺、类别
2. **性格特征**（character）：性格、价值观、气质、习惯动作
3. **说话风格**（speakingStyle）：语气、常用词、句式特点、比喻方式、口头禅、禁忌
4. **专业领域**（expertise）：擅长领域、深度话题、能力边界
5. **场景设定**（body/scene）：典型场景、物件、氛围
6. **关键记忆**（faculty/memory）：重要经历、标志性事件
7. **语录**（skill/quotes）：原话、经典表达

输出要求：
- 输出纯 JSON，不要包含 markdown 代码块标记
- 所有文本使用中文
- 语录和口头禅尽量使用原文
- 不确定的字段留空字符串或空数组"""


async def distill_from_text(
    name: str,
    craft: str,
    text: str,
    llm_api_key: str = "",
    llm_base_url: str = "https://api.deepseek.com/v1",
    llm_model: str = "deepseek-chat",
) -> dict:
    """从文本素材蒸馏人设"""
    import httpx

    prompt = f"""请从以下关于「{name}」（{craft}）的文本素材中提取人设特征。

文本素材：
---
{text[:8000]}
---

请输出完整的 persona JSON 数据。参考以下结构：
- soul.identity: 基本信息（personaName, slug, bio, avatar, era, location, craft, category, level）
- soul.character: 性格特征（personality, values, temperament, quirks）
- soul.speakingStyle: 说话风格（tone, vocabulary, sentencePattern, metaphors, catchphrases, taboo）
- soul.expertise: 专业领域（domains, tags, deepTopics, boundaryResponse）
- body.scene: 场景设定（name, description, objects, mood）
- faculty.memory: 关键记忆（keyMemories）
- skill.quotes: 语录列表
- skill.conversationPattern: 对话模式（greeting, response, topicSwitch, closing）

输出纯 JSON："""

    if not llm_api_key:
        print("[distill] 未配置 LLM API Key，使用模板生成骨架")
        return _generate_skeleton(name, craft, text)

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{llm_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {llm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": llm_model,
                    "messages": [
                        {"role": "system", "content": DISTILL_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 4000,
                },
            )
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            # 清理可能的 markdown 代码块标记
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
            content = content.strip()

            persona = json.loads(content)

            # 补充元数据
            from datetime import datetime
            persona.setdefault("evolution", {})
            persona["evolution"]["version"] = "1.0.0"
            persona["evolution"]["createdAt"] = datetime.now().strftime("%Y-%m-%d")
            persona["evolution"]["source"] = "LLM蒸馏"
            persona["evolution"]["distillationMethod"] = "LLM-assisted distillation"

            return persona

    except Exception as e:
        print(f"[distill] LLM 蒸馏失败: {e}")
        return _generate_skeleton(name, craft, text)


def _generate_skeleton(name: str, craft: str, text: str) -> dict:
    """无 LLM 时生成骨架数据"""
    import copy
    from datetime import datetime

    persona = copy.deepcopy(PERSONA_TEMPLATE)
    persona["soul"]["identity"]["personaName"] = name
    persona["soul"]["identity"]["slug"] = name.lower().replace(" ", "")
    persona["soul"]["identity"]["craft"] = craft
    persona["evolution"]["createdAt"] = datetime.now().strftime("%Y-%m-%d")

    # 从文本中提取引号内的语录
    import re
    quotes = re.findall(r'[""「」]([^""「」]{5,80})[""「」]', text)
    persona["skill"]["quotes"] = quotes[:20]

    return persona


# ─── 从现有 master_prompt.py 提取 ──────────────────────

def extract_from_master(master_id: str) -> dict:
    """从现有 master_prompt.py 的 MASTERS 字段提取 persona"""
    from heritage_master.tools.master_prompt import MASTERS
    import copy
    from datetime import datetime

    if master_id not in MASTERS:
        print(f"[distill] 未找到大师: {master_id}")
        print(f"[distill] 可用大师: {', '.join(MASTERS.keys())}")
        return {}

    master = MASTERS[master_id]
    persona = copy.deepcopy(PERSONA_TEMPLATE)

    # 映射字段
    identity = persona["soul"]["identity"]
    identity["personaName"] = master.get("name", "")
    identity["slug"] = master.get("id", "")
    identity["bio"] = master.get("intro", "")
    identity["avatar"] = master.get("avatar", "")

    # 从 system_prompt 提取更多信息
    sys_prompt = master.get("system_prompt", "")

    # 提取 expertis
    persona["soul"]["expertise"]["domains"] = master.get("expertise", [])
    persona["soul"]["expertise"]["tags"] = master.get("expertise_tags", [])

    # 场景
    persona["body"]["scene"]["description"] = master.get("scene", "")

    # 关系阶段
    for stage_name, stage_data in master.get("stage_behavior", {}).items():
        if stage_name in persona["faculty"]["relationshipStages"]:
            stage = persona["faculty"]["relationshipStages"][stage_name]
            stage["openness"] = stage_data.get("openness", 0.5)
            stage["greetingStyle"] = stage_data.get("greeting_style", "")
            stage["detailLevel"] = stage_data.get("detail_level", "")
            stage["proactiveTeach"] = stage_data.get("proactive_teach", False)
            stage["sampleGreetings"] = stage_data.get("greetings", [])

    # 问候语
    persona["skill"]["conversationPattern"]["greeting"] = "不客套，直接招呼"

    # 元数据
    persona["evolution"]["createdAt"] = datetime.now().strftime("%Y-%m-%d")
    persona["evolution"]["source"] = "master_prompt.py 提取"
    persona["evolution"]["distillationMethod"] = "从现有代码提取 + OpenPersona规范化"

    return persona


# ─── 从文档批量提取 ─────────────────────────────────────

def extract_from_doc(doc_path: str) -> dict[str, dict]:
    """从蒸馏文档提取所有人设"""
    path = Path(doc_path)
    if not path.exists():
        print(f"[distill] 文件不存在: {doc_path}")
        return {}

    content = path.read_text(encoding="utf-8")

    # 分割不同大师的段落
    sections = content.split("---")
    masters = {}

    for section in sections:
        if "叶汉钟" in section:
            masters["chagongfu"] = {
                "name": "叶汉钟",
                "craft": "潮州工夫茶艺",
                "text": section.strip(),
            }
        elif "陈少峰" in section:
            masters["wushishizi"] = {
                "name": "陈少峰",
                "craft": "广东醒狮",
                "text": section.strip(),
            }

    return masters


# ─── 主函数 ─────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="非遗大师人设蒸馏工具")
    parser.add_argument("--name", help="大师姓名")
    parser.add_argument("--craft", help="技艺类别")
    parser.add_argument("--input", help="输入文本文件路径")
    parser.add_argument("--from-master", help="从现有 master_prompt.py 提取（master_id）")
    parser.add_argument("--from-doc", help="从蒸馏文档批量提取")
    parser.add_argument("--output", help="输出路径（默认 personas/{slug}.json）")
    parser.add_argument("--llm-key", default="", help="LLM API Key")
    parser.add_argument("--llm-url", default="https://api.deepseek.com/v1", help="LLM API URL")
    parser.add_argument("--llm-model", default="deepseek-chat", help="LLM 模型名")

    args = parser.parse_args()
    output_dir = _project_root / "personas"
    output_dir.mkdir(exist_ok=True)

    if args.from_master:
        # 从现有代码提取
        persona = extract_from_master(args.from_master)
        if persona:
            output_path = Path(args.output) if args.output else output_dir / f"{args.from_master}.json"
            output_path.write_text(
                json.dumps(persona, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[distill] 已提取 {args.from_master} -> {output_path}")

    elif args.from_doc:
        # 从文档批量提取
        masters = extract_from_doc(args.from_doc)
        for master_id, info in masters.items():
            persona = await distill_from_text(
                name=info["name"],
                craft=info["craft"],
                text=info["text"],
                llm_api_key=args.llm_key,
                llm_base_url=args.llm_url,
                llm_model=args.llm_model,
            )
            output_path = output_dir / f"{master_id}.json"
            output_path.write_text(
                json.dumps(persona, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"[distill] 已蒸馏 {info['name']} -> {output_path}")

    elif args.input:
        # 从文本文件蒸馏
        if not args.name or not args.craft:
            print("[distill] 从文本蒸馏需要 --name 和 --craft 参数")
            return

        text = Path(args.input).read_text(encoding="utf-8")
        persona = await distill_from_text(
            name=args.name,
            craft=args.craft,
            text=text,
            llm_api_key=args.llm_key,
            llm_base_url=args.llm_url,
            llm_model=args.llm_model,
        )

        slug = persona.get("soul", {}).get("identity", {}).get("slug", args.name)
        output_path = Path(args.output) if args.output else output_dir / f"{slug}.json"
        output_path.write_text(
            json.dumps(persona, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[distill] 已蒸馏 {args.name} -> {output_path}")

    else:
        parser.print_help()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
