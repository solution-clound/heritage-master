"""SQLite 数据库初始化与连接管理

提供用户系统、对话记录、修行数据的持久化存储。
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from ..config import settings

_DB_PATH = settings.sqlite_path

SCHEMA_SQL = """
-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    nickname TEXT NOT NULL UNIQUE COLLATE UTF8,
    password_hash TEXT NOT NULL DEFAULT '',
    avatar_url TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 用户画像（大师对学徒的判断）
CREATE TABLE IF NOT EXISTS user_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id),
    master_id TEXT NOT NULL,
    relationship_stage TEXT DEFAULT '试探期',
    interest_tags TEXT DEFAULT '[]',
    aesthetic_pref TEXT DEFAULT '',
    personality_notes TEXT DEFAULT '',
    question_count INTEGER DEFAULT 0,
    first_met_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_talk_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, master_id)
);
CREATE INDEX IF NOT EXISTS idx_user_profiles_user ON user_profiles(user_id);

-- 对话会话
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    master_id TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    topic_summary TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id, master_id);

-- 对话消息
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);

-- 修行记录
CREATE TABLE IF NOT EXISTS cultivation_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id),
    master_id TEXT NOT NULL,
    practice_type TEXT NOT NULL,
    content TEXT NOT NULL,
    master_comment TEXT DEFAULT '',
    score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cultivation_user ON cultivation_records(user_id, master_id);

-- 阶段进度
CREATE TABLE IF NOT EXISTS stage_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id),
    master_id TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT '入门期',
    stage_entered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_practice_days INTEGER DEFAULT 0,
    total_questions INTEGER DEFAULT 0,
    UNIQUE(user_id, master_id)
);

-- 论坛帖子
CREATE TABLE IF NOT EXISTS forum_posts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'experience',
    images TEXT DEFAULT '[]',
    route_data TEXT DEFAULT '{}',
    like_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_forum_posts_user ON forum_posts(user_id);
CREATE INDEX IF NOT EXISTS idx_forum_posts_category ON forum_posts(category);
CREATE INDEX IF NOT EXISTS idx_forum_posts_created ON forum_posts(created_at DESC);

-- 论坛评论
CREATE TABLE IF NOT EXISTS forum_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT NOT NULL REFERENCES forum_posts(id),
    user_id TEXT NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    parent_id INTEGER REFERENCES forum_comments(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_forum_comments_post ON forum_comments(post_id);

-- 论坛点赞
CREATE TABLE IF NOT EXISTS forum_likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT NOT NULL REFERENCES forum_posts(id),
    user_id TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(post_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_forum_likes_post ON forum_likes(post_id);

-- 已保存路线
CREATE TABLE IF NOT EXISTS saved_routes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    days INTEGER DEFAULT 1,
    interests TEXT DEFAULT '[]',
    itinerary TEXT DEFAULT '',
    route_data TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_saved_routes_user ON saved_routes(user_id);
"""


def init_db(db_path: Optional[str] = None) -> None:
    """初始化数据库，创建所有表（如不存在）"""
    path = db_path or _DB_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.create_collation("UTF8", _utf8_collate)
    try:
        # 检查 users 表的 nickname 列是否已使用 UTF8 排序规则
        users_schema = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
        if users_schema and "COLLATE UTF8" not in users_schema[0]:
            # 需要迁移：重建 users 表以修复中文 UNIQUE 约束
            _migrate_users_table(conn)
        conn.executescript(SCHEMA_SQL)
        # 迁移：forum_posts 添加 route_data 列（已有表不会自动加列）
        try:
            conn.execute("ALTER TABLE forum_posts ADD COLUMN route_data TEXT DEFAULT '{}'")
        except sqlite3.OperationalError:
            pass  # 列已存在
        conn.commit()
    finally:
        conn.close()


def _migrate_users_table(conn) -> None:
    """重建 users 表，使用 UTF8 排序规则修复中文 UNIQUE 约束"""
    # 备份数据
    rows = conn.execute("SELECT * FROM users").fetchall()
    # 删除旧表（级联删除相关外键数据）
    conn.execute("DROP TABLE IF EXISTS users")
    # 重建表（新的 SCHEMA_SQL 会在 init_db 中执行）
    conn.executescript(SCHEMA_SQL)
    # 恢复数据
    for row in rows:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, nickname, password_hash, avatar_url, created_at, last_active_at) VALUES (?, ?, ?, ?, ?, ?)",
            tuple(row),
        )


def _utf8_collate(a, b):
    """UTF-8 排序规则，修复 Windows GBK 编码导致中文比较失败的问题"""
    if isinstance(a, str):
        a = a.encode("utf-8")
    if isinstance(b, str):
        b = b.encode("utf-8")
    return (a > b) - (a < b)


@contextmanager
def get_conn(db_path: Optional[str] = None):
    """获取数据库连接的上下文管理器"""
    path = db_path or _DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    # 注册 UTF-8 排序规则，修复 Windows GBK 编码问题
    conn.create_collation("UTF8", _utf8_collate)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reset_db(db_path: Optional[str] = None) -> None:
    """删除并重建数据库（仅用于测试）"""
    path = db_path or _DB_PATH
    p = Path(path)
    if p.exists():
        p.unlink()
    # 同时删除 WAL 和 SHM 文件
    for suffix in ("-wal", "-shm"):
        f = p.with_suffix(p.suffix + suffix)
        if f.exists():
            f.unlink()
    init_db(path)
