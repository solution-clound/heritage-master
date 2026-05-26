"""修行系统

管理学徒的修行路径：每日功课、练习提交、大师点评、阶段转换。

四阶段：入门期 → 成长期 → 精进期 → 传承期
"""

import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from ..data.db import get_conn

# ─── 阶段定义 ───────────────────────────────────────────

STAGES = ["入门期", "成长期", "精进期", "传承期"]

STAGE_REQUIREMENTS = {
    "入门期": {
        "description": "刚开始接触，需要培养兴趣和基本认知",
        "next": "成长期",
        "min_practice_days": 5,
        "min_questions": 20,
    },
    "成长期": {
        "description": "有了基础，开始深入了解和实践",
        "next": "精进期",
        "min_practice_days": 15,
        "min_questions": 50,
    },
    "精进期": {
        "description": "有了一定功底，需要精进和沉淀",
        "next": "传承期",
        "min_practice_days": 30,
        "min_questions": 100,
    },
    "传承期": {
        "description": "已经入门，可以传承和分享",
        "next": None,
        "min_practice_days": 0,
        "min_questions": 0,
    },
}

# ─── 每日功课模板 ───────────────────────────────────────

DAILY_PRACTICE_TEMPLATES = {
    "chagongfu": {
        "入门期": [
            "今天泡一杯茶，不急着喝，先闻闻香气，感受一下。",
            "了解一下潮州工夫茶的基本器具：孟臣壶、若琛杯、砂铫、红泥炉。",
            "看一段潮州工夫茶二十一式的视频，注意注水和出汤的手法。",
            "品尝一杯凤凰单丛，试着分辨它的香气类型。",
        ],
        "成长期": [
            "今天练习温杯和闻香，注意水温对香气的影响。",
            "了解凤凰单丛的主要香型：鸭屎香、蜜兰香、芝兰香。",
            "试着用盖碗泡一泡茶，注意注水的角度和速度。",
            "学习潮州工夫茶的'关公巡城'和'韩信点兵'手法。",
        ],
        "精进期": [
            "今天练习控水温，同一款茶用不同温度泡，对比口感。",
            "品鉴一泡老丛水仙，感受它的'山韵'和回甘。",
            "研究凤凰单丛的产地和海拔对茶味的影响。",
            "写一段学习笔记，记录你对'茶性俭'的理解。",
        ],
        "传承期": [
            "给朋友泡一壶工夫茶，用你的方式讲解它的门道。",
            "整理你学过的冲泡技法，做成自己的学习档案。",
            "思考：工夫茶在当代如何传承？写下你的想法。",
        ],
    },
    "wushishizi": {
        "入门期": [
            "今天看一段醒狮表演视频，注意狮子的表情和步法。",
            "了解一下醒狮的基本知识：狮头、狮被、鼓乐配合。",
            "看看不同颜色狮头的含义：红狮关公、黑狮张飞、黄狮刘备。",
            "听一段醒狮鼓乐，感受鼓点的节奏和气势。",
        ],
        "成长期": [
            "今天练习扎马步，感受下盘稳固的重要性。",
            "了解醒狮的基本步法：马步、弓步、虚步、麒麟步。",
            "看一段'采青'表演的视频，注意狮子探头、试探、叼走的动作。",
            "学习醒狮鼓乐的基本节奏：咚咚锵、咚咚锵。",
        ],
        "精进期": [
            "今天练习醒狮的基本套路，注意步法和鼓点的配合。",
            "分析一段高台醒狮表演，注意平衡和配合的技巧。",
            "研究南狮和北狮的区别，了解各自的特色。",
            "写一段学习笔记，记录你对'狮无精神不如犬'的理解。",
        ],
        "传承期": [
            "给朋友介绍醒狮，用自己的话说说它为什么是'精气神'。",
            "整理你学过的醒狮套路，做成自己的学习档案。",
            "思考：醒狮如何在校园和社区推广？写下你的想法。",
        ],
    },
}


# ─── 核心函数 ───────────────────────────────────────────

def assign_daily_practice(user_id: str, master_id: str) -> Dict[str, Any]:
    """分配今日功课

    Returns:
        {"practice_id": int, "content": str, "practice_type": "daily_practice"}
    """
    # 获取用户当前阶段
    stage = _get_stage(user_id, master_id)

    # 获取今日是否已有功课
    today = datetime.utcnow().date().isoformat()
    with get_conn() as conn:
        existing = conn.execute(
            """SELECT id, content FROM cultivation_records
               WHERE user_id=? AND master_id=? AND practice_type='daily_practice'
               AND DATE(created_at)=?""",
            (user_id, master_id, today),
        ).fetchone()
        if existing:
            return {
                "practice_id": existing["id"],
                "content": existing["content"],
                "practice_type": "daily_practice",
            }

    # 选择功课
    templates = DAILY_PRACTICE_TEMPLATES.get(master_id, {}).get(stage, [])
    if not templates:
        content = f"今天随心练习，记录你的感受和发现。"
    else:
        import random
        content = random.choice(templates)

    # 保存到数据库
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        cursor = conn.execute(
            """INSERT INTO cultivation_records (user_id, master_id, practice_type, content, created_at)
               VALUES (?, ?, 'daily_practice', ?, ?)""",
            (user_id, master_id, content, now),
        )
        practice_id = cursor.lastrowid
        # 更新练习天数
        _increment_practice_days(conn, user_id, master_id)

    return {
        "practice_id": practice_id,
        "content": content,
        "practice_type": "daily_practice",
    }


def submit_practice(user_id: str, master_id: str, content: str, llm_func=None) -> Dict[str, Any]:
    """提交练习记录，获取大师点评

    Args:
        user_id: 用户ID
        master_id: 大师ID
        content: 练习内容/感悟
        llm_func: 可选的 LLM 调用函数，用于生成大师点评

    Returns:
        {"practice_id": int, "master_comment": str, "score": int}
    """
    now = datetime.utcnow().isoformat()

    # 生成大师点评
    master_comment = _generate_comment(master_id, content, llm_func)
    score = _evaluate_score(content)

    with get_conn() as conn:
        cursor = conn.execute(
            """INSERT INTO cultivation_records
               (user_id, master_id, practice_type, content, master_comment, score, created_at)
               VALUES (?, ?, 'free_practice', ?, ?, ?, ?)""",
            (user_id, master_id, content, master_comment, score, now),
        )
        practice_id = cursor.lastrowid

        # 更新练习天数
        _increment_practice_days(conn, user_id, master_id)

    return {
        "practice_id": practice_id,
        "master_comment": master_comment,
        "score": score,
    }


def get_practice_history(user_id: str, master_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """获取练习历史"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, practice_type, content, master_comment, score, created_at
               FROM cultivation_records
               WHERE user_id=? AND master_id=?
               ORDER BY id DESC LIMIT ?""",
            (user_id, master_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def check_stage_transition(user_id: str, master_id: str) -> Dict[str, Any]:
    """检查是否满足阶段转换条件

    Returns:
        {"can_transition": bool, "current_stage": str, "next_stage": str|None, "progress": dict}
    """
    current_stage = _get_stage(user_id, master_id)
    requirements = STAGE_REQUIREMENTS.get(current_stage, {})

    if not requirements.get("next"):
        return {
            "can_transition": False,
            "current_stage": current_stage,
            "next_stage": None,
            "progress": {"message": "已达最高阶段"},
        }

    with get_conn() as conn:
        # 获取统计数据
        progress = conn.execute(
            """SELECT total_practice_days, total_questions
               FROM stage_progress
               WHERE user_id=? AND master_id=?""",
            (user_id, master_id),
        ).fetchone()

        practice_days = progress["total_practice_days"] if progress else 0
        questions = progress["total_questions"] if progress else 0

        # 获取平均评分
        avg_score_row = conn.execute(
            """SELECT AVG(score) as avg_score
               FROM cultivation_records
               WHERE user_id=? AND master_id=? AND score > 0""",
            (user_id, master_id),
        ).fetchone()
        avg_score = avg_score_row["avg_score"] or 0

    min_days = requirements.get("min_practice_days", 0)
    min_questions = requirements.get("min_questions", 0)

    can_transition = (
        practice_days >= min_days
        and questions >= min_questions
    )

    return {
        "can_transition": can_transition,
        "current_stage": current_stage,
        "next_stage": requirements["next"],
        "progress": {
            "practice_days": practice_days,
            "required_days": min_days,
            "questions": questions,
            "required_questions": min_questions,
            "avg_score": round(avg_score, 1),
            "stage_description": requirements["description"],
        },
    }


def do_stage_transition(user_id: str, master_id: str) -> Dict[str, Any]:
    """执行阶段转换

    Returns:
        {"success": bool, "old_stage": str, "new_stage": str}
    """
    check = check_stage_transition(user_id, master_id)
    if not check["can_transition"]:
        return {
            "success": False,
            "old_stage": check["current_stage"],
            "new_stage": check["current_stage"],
            "message": "尚不满足转换条件",
        }

    old_stage = check["current_stage"]
    new_stage = check["next_stage"]
    now = datetime.utcnow().isoformat()

    with get_conn() as conn:
        conn.execute(
            """UPDATE stage_progress SET stage=?, stage_entered_at=?
               WHERE user_id=? AND master_id=?""",
            (new_stage, now, user_id, master_id),
        )
        # 同步更新 user_profiles
        conn.execute(
            """UPDATE user_profiles SET relationship_stage=?
               WHERE user_id=? AND master_id=?""",
            (new_stage, user_id, master_id),
        )

    return {
        "success": True,
        "old_stage": old_stage,
        "new_stage": new_stage,
    }


def get_cultivation_map(user_id: str, master_id: str) -> Dict[str, Any]:
    """获取修行地图数据"""
    current_stage = _get_stage(user_id, master_id)

    with get_conn() as conn:
        progress = conn.execute(
            """SELECT total_practice_days, total_questions
               FROM stage_progress
               WHERE user_id=? AND master_id=?""",
            (user_id, master_id),
        ).fetchone()

    practice_days = progress["total_practice_days"] if progress else 0
    questions = progress["total_questions"] if progress else 0

    # 构建地图数据
    stages = []
    for stage_name in STAGES:
        req = STAGE_REQUIREMENTS[stage_name]
        is_current = stage_name == current_stage
        is_completed = STAGES.index(stage_name) < STAGES.index(current_stage)

        stage_data = {
            "name": stage_name,
            "description": req["description"],
            "is_current": is_current,
            "is_completed": is_completed,
            "requirements": {
                "min_practice_days": req.get("min_practice_days", 0),
                "min_questions": req.get("min_questions", 0),
            },
        }

        if is_current:
            stage_data["current_progress"] = {
                "practice_days": practice_days,
                "questions": questions,
            }

        stages.append(stage_data)

    return {
        "current_stage": current_stage,
        "total_practice_days": practice_days,
        "total_questions": questions,
        "stages": stages,
    }


def get_stage_info(user_id: str, master_id: str) -> Dict[str, Any]:
    """获取当前阶段信息"""
    stage = _get_stage(user_id, master_id)
    check = check_stage_transition(user_id, master_id)

    return {
        "stage": stage,
        "description": STAGE_REQUIREMENTS.get(stage, {}).get("description", ""),
        "transition": check,
    }


def increment_question_count(user_id: str, master_id: str) -> None:
    """增加提问计数（在用户提问时调用）"""
    with get_conn() as conn:
        conn.execute(
            """UPDATE stage_progress SET total_questions = total_questions + 1
               WHERE user_id=? AND master_id=?""",
            (user_id, master_id),
        )


# ─── 内部辅助函数 ───────────────────────────────────────

def _get_stage(user_id: str, master_id: str) -> str:
    """获取用户当前阶段"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT stage FROM stage_progress WHERE user_id=? AND master_id=?",
            (user_id, master_id),
        ).fetchone()
        return row["stage"] if row else "入门期"


def _increment_practice_days(conn, user_id: str, master_id: str) -> None:
    """增加练习天数（每天只计一次）"""
    today = datetime.utcnow().date().isoformat()

    # 检查今天是否已有练习记录
    today_count = conn.execute(
        """SELECT COUNT(*) as cnt FROM cultivation_records
           WHERE user_id=? AND master_id=? AND DATE(created_at)=?""",
        (user_id, master_id, today),
    ).fetchone()["cnt"]

    if today_count <= 1:  # 第一次提交（刚插入的那条）
        conn.execute(
            """UPDATE stage_progress SET total_practice_days = total_practice_days + 1
               WHERE user_id=? AND master_id=?""",
            (user_id, master_id),
        )


def _generate_comment(master_id: str, content: str, llm_func=None) -> str:
    """生成大师点评"""
    # 如果有 LLM 函数，使用 LLM 生成点评
    if llm_func:
        try:
            from .master_prompt import get_master_prompt
            prompt = get_master_prompt(master_id)
            question = f"一个学徒提交了他的练习感悟：\n\n{content}\n\n请用你的风格给出点评，既指出亮点，也提出改进建议。2-3句话即可。"
            # 这里需要同步调用，实际使用时可能需要异步版本
            return llm_func(question, prompt)
        except Exception:
            pass

    # 降级为模板点评
    comments = {
        "chagongfu": [
            "嗯，有进步。再喝一杯，慢慢来。",
            "还不错。但你还得再用心感受，茶汤会告诉你答案。",
            "有想法。不过泡茶还得再练，水温差一点就差很多。",
            "行，我看到了你的努力。继续。",
        ],
        "wushishizi": [
            "不错，有感觉了。继续练，马步要扎稳。",
            "嗯，看得出你用心了。但动作还要再干脆利落。",
            "有进步。记住，醒狮讲的是精气神。",
            "行，我看到了。继续，别着急。",
        ],
    }
    import random
    master_comments = comments.get(master_id, ["继续努力。"])
    return random.choice(master_comments)


def _evaluate_score(content: str) -> int:
    """简单评估练习质量分数（0-100）"""
    # 基于内容长度和关键词的简单评估
    score = 60  # 基础分

    if len(content) > 100:
        score += 10
    if len(content) > 200:
        score += 10

    # 检查是否有思考深度的关键词
    depth_keywords = ["感受", "理解", "思考", "发现", "体会", "领悟", "启发"]
    for kw in depth_keywords:
        if kw in content:
            score += 5
            break

    # 检查是否有具体描述
    detail_keywords = ["今天", "练习", "学习", "尝试", "观察", "分析"]
    for kw in detail_keywords:
        if kw in content:
            score += 5
            break

    return min(score, 100)
