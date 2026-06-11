import json
import logging
import time
import uuid
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from contextvars import ContextVar
from typing import Any

# Trace ID context variable
trace_id_var: ContextVar[str] = ContextVar('trace_id', default='')
user_id_var: ContextVar[str] = ContextVar('user_id', default='')
session_id_var: ContextVar[str] = ContextVar('session_id', default='')

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            'ts': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'event': getattr(record, 'event', 'log'),
        }
        # Add context vars
        tid = trace_id_var.get('')
        if tid:
            log_data['trace_id'] = tid
        uid = user_id_var.get('')
        if uid:
            log_data['user_id'] = uid
        sid = session_id_var.get('')
        if sid:
            log_data['session_id'] = sid
        # Add extra fields
        for k, v in getattr(record, 'extra_fields', {}).items():
            log_data[k] = v
        if record.exc_info and record.exc_info[0]:
            log_data['exception'] = self.formatException(record.exc_info)
        return json.dumps(log_data, ensure_ascii=False)

def setup_logger(log_dir: str = None, level: str = 'INFO'):
    logger = logging.getLogger('heritage')
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers = []
    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(JSONFormatter())
    logger.addHandler(console)
    # File handler (if log_dir specified)
    if log_dir:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        file_handler = TimedRotatingFileHandler(
            Path(log_dir) / 'heritage.log',
            when='midnight', backupCount=30
        )
        file_handler.setFormatter(JSONFormatter())
        logger.addHandler(file_handler)
    return logger

_logger = None

def get_logger():
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger

def agent_log(event: str, **kwargs):
    """Log an agent event with structured fields."""
    logger = get_logger()
    record = logger.makeRecord(
        'heritage', logging.INFO, '', 0, event, (), None
    )
    record.event = event
    record.extra_fields = kwargs
    logger.handle(record)

def generate_trace_id() -> str:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    short_uuid = uuid.uuid4().hex[:8]
    return f'tr_{ts}_{short_uuid}'

def set_context(trace_id: str = '', user_id: str = '', session_id: str = ''):
    if trace_id:
        trace_id_var.set(trace_id)
    if user_id:
        user_id_var.set(user_id)
    if session_id:
        session_id_var.set(session_id)

def clear_context():
    trace_id_var.set('')
    user_id_var.set('')
    session_id_var.set('')

# Timing helper
class Timer:
    def __init__(self):
        self.start = time.monotonic()
    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self.start) * 1000)
