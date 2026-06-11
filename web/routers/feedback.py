"""用户反馈 + 健康检查 + 管理链路追踪 API"""
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from heritage_master.data.db import get_conn

router = APIRouter()
_app_start_time = time.monotonic()


# ─── 反馈 ────────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    trace_id: str = ''
    user_id: str
    session_id: str = ''
    message_idx: int = 0
    rating: str  # 'good' / 'bad' / 'need_more'
    reason: str = ''


@router.post('/api/feedback')
def api_submit_feedback(req: FeedbackRequest):
    """提交用户反馈"""
    if req.rating not in ('good', 'bad', 'need_more'):
        return JSONResponse({'error': 'rating must be good/bad/need_more'}, 400)
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            '''INSERT INTO feedback (trace_id, user_id, session_id, message_idx, rating, reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (req.trace_id, req.user_id, req.session_id, req.message_idx, req.rating, req.reason, now)
        )
    return {'ok': True}


@router.get('/api/feedback/stats')
def api_feedback_stats(days: int = Query(7, ge=1, le=90)):
    """反馈统计"""
    with get_conn() as conn:
        rows = conn.execute(
            '''SELECT rating, COUNT(*) as cnt FROM feedback
               WHERE created_at >= datetime('now', ?) GROUP BY rating''',
            (f'-{days} days',)
        ).fetchall()
        stats = {r['rating']: r['cnt'] for r in rows}
        total = sum(stats.values())
        good = stats.get('good', 0)
        return {
            'total': total,
            'good': good,
            'bad': stats.get('bad', 0),
            'need_more': stats.get('need_more', 0),
            'satisfaction_rate': round(good / total * 100, 1) if total > 0 else 0,
            'days': days,
        }


# ─── 健康检查 ─────────────────────────────────────────────────

@router.get('/api/health')
def api_health():
    """健康检查"""
    checks = {}
    healthy = True

    # Database
    try:
        with get_conn() as conn:
            conn.execute('SELECT 1')
        checks['database'] = {'status': 'ok'}
    except Exception as e:
        checks['database'] = {'status': 'error', 'error': str(e)}
        healthy = False

    # LLM config
    try:
        from heritage_master.config import settings
        if settings.llm_api_key:
            checks['llm'] = {
                'status': 'ok',
                'provider': settings.llm_provider,
                'model': settings.llm_model,
            }
        else:
            checks['llm'] = {'status': 'not_configured'}
    except Exception as e:
        checks['llm'] = {'status': 'error', 'error': str(e)}

    # Heritage data
    try:
        from heritage_master.data.crawler import _get_builtin_data
        data = _get_builtin_data()
        checks['heritage_data'] = {'status': 'ok', 'builtin_count': len(data)}
    except Exception:
        checks['heritage_data'] = {'status': 'error'}

    # Graph
    try:
        from heritage_master.data.knowledge_graph import get_graph_stats
        stats = get_graph_stats()
        checks['knowledge_graph'] = {'status': 'ok', 'nodes': stats.get('total_nodes', 0)}
    except Exception:
        checks['knowledge_graph'] = {'status': 'error'}

    uptime = int(time.monotonic() - _app_start_time)
    return {
        'status': 'healthy' if healthy else 'degraded',
        'uptime_seconds': uptime,
        'checks': checks,
    }


# ─── 管理员：请求链路追踪 ─────────────────────────────────────

@router.get('/api/admin/traces')
def api_traces(limit: int = Query(20, ge=1, le=100)):
    """查看最近的请求链路"""
    from heritage_master.observability.tracer import collector

    traces = collector.get_recent(limit)
    result = []
    for t in traces:
        result.append({
            'trace_id': t.trace_id,
            'user_id': t.user_id,
            'status': t.status,
            'total_ms': t.total_ms,
            'reply_len': t.reply_len,
            'step_count': len(t.steps),
            'started_at': t.started_at,
            'steps': [
                {'event': s.event, 'ms': s.duration_ms, 'data': s.data}
                for s in t.steps
            ],
        })
    return {'traces': result, 'total': len(result)}
