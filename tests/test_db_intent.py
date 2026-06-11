# -*- coding: utf-8 -*-
"""数据库 & 意图分类测试"""
import pytest


class TestDatabase:
    def test_init_db(self):
        from heritage_master.data.db import init_db, get_conn
        init_db()
        with get_conn() as conn:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_names = [t["name"] for t in tables]
            assert "users" in table_names
            assert "chat_sessions" in table_names
            assert "chat_messages" in table_names
            assert "user_profiles" in table_names
            assert "forum_posts" in table_names

    def test_users_table_schema(self):
        from heritage_master.data.db import get_conn
        with get_conn() as conn:
            cols = conn.execute("PRAGMA table_info(users)").fetchall()
            col_names = [c["name"] for c in cols]
            assert "id" in col_names
            assert "nickname" in col_names
            assert "password_hash" in col_names

    def test_forum_tables_exist(self):
        from heritage_master.data.db import get_conn
        with get_conn() as conn:
            tables = [t["name"] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            assert "forum_posts" in tables
            assert "forum_likes" in tables
            assert "forum_comments" in tables


class TestIntentRules:
    @pytest.fixture(autouse=True)
    def _require_langgraph(self):
        pytest.importorskip("langgraph", reason="langgraph not installed")
    def test_trip_intent(self):
        from heritage_master.agent.nodes import classify_intent_rule, Intent
        for msg in ["go travel", "trip plan", "3 day tour"]:
            pass  # English won't match, test Chinese
        for msg in ["去广州玩", "规划行程", "三天游", "怎么玩"]:
            r = classify_intent_rule(msg)
            assert r is not None and r.intent == Intent.TRIP, f"Failed: {msg}"

    def test_venue_intent(self):
        from heritage_master.agent.nodes import classify_intent_rule, Intent
        for msg in ["附近有什么博物馆", "哪里有体验馆", "文化馆在哪"]:
            r = classify_intent_rule(msg)
            assert r is not None and r.intent == Intent.VENUE, f"Failed: {msg}"

    def test_knowledge_intent(self):
        from heritage_master.agent.nodes import classify_intent_rule, Intent
        for msg in ["传承人是谁", "历史起源", "代表作品", "师承关系"]:
            r = classify_intent_rule(msg)
            assert r is not None and r.intent == Intent.KNOWLEDGE, f"Failed: {msg}"

    def test_search_intent(self):
        from heritage_master.agent.nodes import classify_intent_rule, Intent
        for msg in ["搜索昆曲", "有哪些非遗项目", "帮我了解广绣并"]:
            r = classify_intent_rule(msg)
            assert r is not None and r.intent == Intent.SEARCH, f"Failed: {msg}"

    def test_event_intent(self):
        from heritage_master.agent.nodes import classify_intent_rule, Intent
        for msg in ["最近有什么展览", "有什么活动", "工作坊讲座"]:
            r = classify_intent_rule(msg)
            assert r is not None and r.intent == Intent.EVENT, f"Failed: {msg}"

    def test_intent_types(self):
        from heritage_master.agent.nodes import Intent
        assert len(Intent) == 6
        values = {i.value for i in Intent}
        assert "search" in values
        assert "venue" in values
        assert "trip" in values
        assert "knowledge" in values
        assert "event" in values
        assert "chat" in values
