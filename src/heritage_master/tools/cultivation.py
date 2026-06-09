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
    "caizhengren": {
        "入门期": [
            "今天听一段昆曲《牡丹亭·游园》，感受水磨腔的韵味。",
            "了解一下昆曲的基本知识：生旦净末丑五大行当。",
            "看看昆曲演员的水袖动作，感受它的飘逸之美。",
            "听一段昆曲笛子伴奏，感受曲笛的音色。",
        ],
        "成长期": [
            "今天学唱一句昆曲《牡丹亭》的'原来姹紫嫣红开遍'，注意咬字。",
            "了解昆曲的曲牌体：一支曲子有固定的旋律框架。",
            "看一段昆曲《长生殿》的表演，注意演员的眼神和手势。",
            "学习昆曲的基本身段：云手、山膀、圆场。",
        ],
        "精进期": [
            "今天学唱一段《玉簪记·琴挑》，感受小生的儒雅气质。",
            "分析昆曲'一桌二椅'的舞台美学，体会以简驭繁的智慧。",
            "研究昆曲的'依字行腔'——字的声调如何决定旋律走向。",
            "写一段学习笔记，记录你对'昆曲是百戏之祖'的理解。",
        ],
        "传承期": [
            "给朋友唱一段昆曲，用你的方式讲解它的美。",
            "整理你学过的昆曲曲牌，做成自己的学习档案。",
            "思考：昆曲如何在年轻人中传承？写下你的想法。",
        ],
    },
    "wangxiuying": {
        "入门期": [
            "今天观察一幅广绣作品，注意丝线的光泽和色彩过渡。",
            "了解一下广绣的基本工具：绣针、绣架、丝线、绷布。",
            "看看广绣的针法：直针、续针、撕针、钉针。",
            "欣赏一幅广绣的荔枝图，感受它'远看是画，近看是绣'的效果。",
        ],
        "成长期": [
            "今天练习广绣的基本针法——直针和续针，绣一片叶子。",
            "了解广绣丝线的劈线技巧——一根丝线可以劈成多股。",
            "观察广绣的'留水路'技法——绣面留白的艺术。",
            "学习广绣的配色：如何用丝线的光泽表现物体的质感。",
        ],
        "精进期": [
            "今天尝试绣一朵广绣特色的牡丹花，注意花瓣的层次感。",
            "研究广绣的'金银线绣'技法，感受它的华丽效果。",
            "分析一幅广绣动物作品，注意如何用针法表现毛发的质感。",
            "写一段学习笔记，记录你对'以针代笔，以线代色'的理解。",
        ],
        "传承期": [
            "给朋友展示一幅广绣作品，用你的方式讲解它的门道。",
            "整理你学过的广绣技法，做成自己的学习档案。",
            "思考：广绣如何与现代设计结合？写下你的想法。",
        ],
    },
    "gaofenglian": {
        "入门期": [
            "今天剪一个简单的窗花，感受剪刀在纸上游走的感觉。",
            "了解一下剪纸的基本工具：剪刀、红纸、铅笔、蜡盘。",
            "看看传统剪纸的纹样：花鸟鱼虫、十二生肖。",
            "欣赏一幅陕北剪纸，感受它的粗犷和纯朴。",
        ],
        "成长期": [
            "今天练习剪纸的基本纹样——锯齿纹和月牙纹。",
            "了解剪纸的'阳剪'和'阴剪'两种基本技法。",
            "试着剪一幅对称的蝴蝶图案，注意折叠的方法。",
            "学习剪纸的'连而不断'——图案要连在一起才不会散。",
        ],
        "精进期": [
            "今天尝试剪一幅复杂的窗花，注意线条的流畅和细节的精致。",
            "研究剪纸的'意象造型'——不求形似，但求神似。",
            "分析一幅陕北民俗剪纸，了解它背后的文化寓意。",
            "写一段学习笔记，记录你对'剪纸是纸上的舞蹈'的理解。",
        ],
        "传承期": [
            "给朋友剪一幅生肖剪纸，用你的方式讲解它的寓意。",
            "整理你学过的剪纸纹样，做成自己的学习档案。",
            "思考：剪纸如何走进现代生活？写下你的想法。",
        ],
    },
}


# ─── 核心函数 ───────────────────────────────────────────

async def assign_daily_practice(user_id: str, master_id: str, llm_func=None) -> Dict[str, Any]:
    """分配今日功课（支持 LLM 动态生成）

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

    # 尝试 LLM 动态生成
    content = None
    if llm_func:
        content = await _generate_practice_with_llm(master_id, stage, llm_func)

    # 降级：从模板中选择
    if not content:
        templates = DAILY_PRACTICE_TEMPLATES.get(master_id, {}).get(stage, [])
        if not templates:
            content = "今天随心练习，记录你的感受和发现。"
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


async def submit_practice(user_id: str, master_id: str, content: str, llm_func=None) -> Dict[str, Any]:
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
    master_comment = await _generate_comment_async(master_id, content, llm_func)
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
    """生成大师点评（同步版本）"""
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
        "caizhengren": [
            "嗯，不错。昆曲讲究的是'慢'字，你慢慢来。",
            "有进步。不过唱腔还要再打磨，水磨腔就是这样磨出来的。",
            "行，我看到了你的用心。继续听，继续感受。",
            "还可以。不过身段要再优雅一些，昆曲讲的是'雅'。",
        ],
        "wangxiuying": [
            "嗯，针脚还算整齐。不过还要再细心，丝线不能打结。",
            "有进步。绣花要沉得住气，急不得。",
            "不错，颜色搭配可以。继续练，手要稳。",
            "行，我看到了你的耐心。绣花就是修心。",
        ],
        "gaofenglian": [
            "好着哩！剪纸就是要大胆，不要怕剪坏。",
            "嗯，有样子了。不过线条还要再流畅，一剪子下去要干脆。",
            "不错嘛！继续剪，剪多了就有感觉了。",
            "行咧！我看你有灵气。多剪，剪出自己的花样来。",
        ],
    }
    import random
    master_comments = comments.get(master_id, ["继续努力。"])
    return random.choice(master_comments)


async def _generate_comment_async(master_id: str, content: str, llm_func=None) -> str:
    """生成大师点评（异步版本，支持 LLM）"""
    if llm_func:
        try:
            from .master_prompt import get_master_prompt
            prompt = get_master_prompt(master_id)
            question = (
                f"一个学徒提交了他的练习感悟：\n\n{content}\n\n"
                f"请用你的风格给出点评，既指出亮点，也提出改进建议。2-3句话即可。"
            )
            result = await llm_func(question, prompt)
            if result and len(result.strip()) >= 5:
                return result.strip()
        except Exception:
            pass

    # 降级为模板点评
    return _generate_comment(master_id, content)


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


# ─── 每日功课问候 ─────────────────────────────────────────


async def get_daily_greeting(user_id: str, master_id: str) -> Dict[str, Any]:
    """获取每日问候（含今日功课 + 昨日收获提醒）

    每天首次访问：分配今日功课，生成围绕功课的问候
    同一天再次访问：返回已有的功课和问候

    Returns:
        {
            "greeting": str,          # 大师问候语（含今日功课介绍）
            "today_practice": str,    # 今日功课内容
            "practice_date": str,     # 功课日期
            "ask_harvest": bool,      # 是否需要问昨天的收获
            "yesterday_practice": str # 昨天的功课（如果有）
        }
    """
    from .master_prompt import get_master
    master = get_master(master_id)
    master_name = master["name"] if master else "师父"

    stage = _get_stage(user_id, master_id)
    today = datetime.utcnow().date().isoformat()
    yesterday = (datetime.utcnow().date() - timedelta(days=1)).isoformat()

    # 分配或获取今日功课
    practice = await assign_daily_practice(user_id, master_id)
    today_content = practice.get("content", "今天随心练习。")

    # 检查昨天是否有功课
    yesterday_practice = ""
    ask_harvest = False
    with get_conn() as conn:
        y_row = conn.execute(
            """SELECT content FROM cultivation_records
               WHERE user_id=? AND master_id=? AND practice_type='daily_practice'
               AND DATE(created_at)=?""",
            (user_id, master_id, yesterday),
        ).fetchone()
        if y_row:
            yesterday_practice = y_row["content"]
            # 检查昨天是否已提交收获
            harvest_row = conn.execute(
                """SELECT id FROM cultivation_records
                   WHERE user_id=? AND master_id=? AND practice_type='harvest'
                   AND DATE(created_at)=?""",
                (user_id, master_id, yesterday),
            ).fetchone()
            if not harvest_row:
                ask_harvest = True

    # 检查今天是否已有问候记录（避免重复）
    with get_conn() as conn:
        existing_greeting = conn.execute(
            """SELECT content FROM cultivation_records
               WHERE user_id=? AND master_id=? AND practice_type='daily_greeting'
               AND DATE(created_at)=?""",
            (user_id, master_id, today),
        ).fetchone()
        if existing_greeting:
            return {
                "greeting": existing_greeting["content"],
                "today_practice": today_content,
                "practice_date": today,
                "ask_harvest": ask_harvest,
                "yesterday_practice": yesterday_practice,
            }

    # 生成问候语
    greeting = _build_daily_greeting(master_id, master_name, stage, today_content, ask_harvest, yesterday_practice)

    # 保存问候记录
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO cultivation_records (user_id, master_id, practice_type, content, created_at)
               VALUES (?, ?, 'daily_greeting', ?, ?)""",
            (user_id, master_id, greeting, datetime.utcnow().isoformat()),
        )

    return {
        "greeting": greeting,
        "today_practice": today_content,
        "practice_date": today,
        "ask_harvest": ask_harvest,
        "yesterday_practice": yesterday_practice,
    }


def _build_daily_greeting(master_id: str, master_name: str, stage: str,
                          practice: str, ask_harvest: bool, yesterday: str) -> str:
    """构建每日问候语"""
    import random

    # 基于大师风格的问候模板
    greetings_map = {
        "chagongfu": {
            "prefix": [
                "来了？坐。炉子上水刚开。",
                "哟，来了。先喝一杯再说。",
                "坐。今天泡的这泡不错，你闻闻。",
            ],
            "practice_intro": f"今天的功课是——{practice}",
            "harvest_ask": f"对了，昨天的功课「{yesterday}」你做得怎么样？有什么感受？",
        },
        "wushishizi": {
            "prefix": [
                "来了？坐！鼓声刚停。",
                "哟，来了！正好歇歇。",
                "坐！我刚教完学生。",
            ],
            "practice_intro": f"今天的功课给你安排好了——{practice}",
            "harvest_ask": f"对了，昨天的功课「{yesterday}」你练了没有？说来听听！",
        },
        "caizhengren": {
            "prefix": [
                "来了？坐。我刚吊完嗓子。",
                "你来了。坐，今天排了一出新戏。",
                "坐吧。今天嗓子状态不错。",
            ],
            "practice_intro": f"今日功课——{practice}",
            "harvest_ask": f"昨日的功课「{yesterday}」，你可有感悟？",
        },
        "wangxiuying": {
            "prefix": [
                "来了？坐。我刚绣完一片叶子。",
                "你来了。来，看看我这幅新作品。",
                "坐吧。今天光线好，正适合绣花。",
            ],
            "practice_intro": f"今天的功课——{practice}",
            "harvest_ask": f"对了，昨天的功课「{yesterday}」你做了吗？绣得怎么样？",
        },
        "gaofenglian": {
            "prefix": [
                "来了？快坐！我刚剪了个新花样。",
                "来咧来咧！坐，炕上暖和。",
                "你来了！坐，我给你看个好东西。",
            ],
            "practice_intro": f"今日给你安排个功课——{practice}",
            "harvest_ask": f"对了，昨日的功课「{yesterday}」你剪了没有？剪得咋样？",
        },
    }

    g = greetings_map.get(master_id, greetings_map["chagongfu"])
    prefix = random.choice(g["prefix"])
    parts = [prefix, g["practice_intro"]]
    if ask_harvest and yesterday:
        parts.append(g["harvest_ask"])

    return "\n\n".join(parts)


def record_daily_harvest(user_id: str, master_id: str, content: str) -> Dict[str, Any]:
    """记录每日收获

    用户分享今日学习收获，记录到数据库。

    Returns:
        {"harvest_id": int, "recorded": bool}
    """
    today = datetime.utcnow().date().isoformat()

    # 检查今天是否已有收获记录
    with get_conn() as conn:
        existing = conn.execute(
            """SELECT id FROM cultivation_records
               WHERE user_id=? AND master_id=? AND practice_type='harvest'
               AND DATE(created_at)=?""",
            (user_id, master_id, today),
        ).fetchone()
        if existing:
            return {"harvest_id": existing["id"], "recorded": False, "message": "今天已经记录过收获了"}

    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        cursor = conn.execute(
            """INSERT INTO cultivation_records (user_id, master_id, practice_type, content, created_at)
               VALUES (?, ?, 'harvest', ?, ?)""",
            (user_id, master_id, content, now),
        )
        return {"harvest_id": cursor.lastrowid, "recorded": True}


def get_harvest_history(user_id: str, master_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """获取收获历史"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, content, master_comment, score, created_at
               FROM cultivation_records
               WHERE user_id=? AND master_id=? AND practice_type='harvest'
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, master_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


async def _generate_practice_with_llm(master_id: str, stage: str, llm_func) -> Optional[str]:
    """使用 LLM 动态生成功课内容

    Returns:
        功课内容字符串，失败返回 None
    """
    if not llm_func:
        return None

    try:
        from .master_prompt import get_master_prompt
        prompt = get_master_prompt(master_id)
        question = (
            f"请为一位处于「{stage}」阶段的学徒安排今天的功课。\n"
            f"要求：1. 一句话，不超过50字；2. 要具体可执行；3. 符合{stage}阶段的难度。\n"
            f"只输出功课内容，不要其他解释。"
        )
        result = await llm_func(question, prompt)
        if result and len(result.strip()) >= 10:
            return result.strip()
        return None
    except Exception:
        return None
