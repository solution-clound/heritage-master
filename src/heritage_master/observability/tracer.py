"""Request trace collector — stores recent traces in memory."""
import threading
from collections import deque
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class TraceStep:
    timestamp: str
    event: str
    data: Dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0

@dataclass
class Trace:
    trace_id: str
    user_id: str
    session_id: str
    started_at: str
    steps: List[TraceStep] = field(default_factory=list)
    status: str = 'running'  # running / completed / failed
    total_ms: int = 0
    reply_len: int = 0

class TraceCollector:
    def __init__(self, max_traces: int = 1000):
        self._traces: deque = deque(maxlen=max_traces)
        self._active: Dict[str, Trace] = {}
        self._lock = threading.Lock()

    def start_trace(self, trace_id: str, user_id: str = '', session_id: str = '') -> Trace:
        trace = Trace(
            trace_id=trace_id,
            user_id=user_id,
            session_id=session_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._active[trace_id] = trace
        return trace

    def add_step(self, trace_id: str, event: str, data: Dict = None, duration_ms: int = 0):
        with self._lock:
            trace = self._active.get(trace_id)
            if trace:
                step = TraceStep(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    event=event,
                    data=data or {},
                    duration_ms=duration_ms,
                )
                trace.steps.append(step)

    def end_trace(self, trace_id: str, status: str = 'completed', reply_len: int = 0, total_ms: int = 0):
        with self._lock:
            trace = self._active.pop(trace_id, None)
            if trace:
                trace.status = status
                trace.reply_len = reply_len
                trace.total_ms = total_ms
                self._traces.append(trace)

    def get_recent(self, limit: int = 20) -> List[Trace]:
        with self._lock:
            return list(self._traces)[-limit:]

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        with self._lock:
            # Check active
            if trace_id in self._active:
                return self._active[trace_id]
            # Check completed
            for t in self._traces:
                if t.trace_id == trace_id:
                    return t
        return None

# Global singleton
collector = TraceCollector()
