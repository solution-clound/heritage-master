# -*- coding: utf-8 -*-
"""用户管理系统测试 — 注册、登录、画像、会话"""
import pytest
from heritage_master.tools.user_manager import (
    create_user, login_user, get_user, _hash_password, _verify_password,
    start_session, end_session, get_session, add_message, get_recent_messages,
    get_user_profile, update_user_profile, auto_update_profile,
    _ensure_profile,
)
from heritage_master.data.db import init_db


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


class TestPasswordHashing:
    def test_hash_and_verify(self):
        h, salt = _hash_password("test1234")
        assert _verify_password("test1234", h) is True

    def test_wrong_password(self):
        h, salt = _hash_password("test1234")
        assert _verify_password("wrong", h) is False

    def test_different_salts(self):
        h1, s1 = _hash_password("test1234")
        h2, s2 = _hash_password("test1234")
        assert s1 != s2  # Different salts

    def test_empty_password(self):
        h, salt = _hash_password("")
        assert _verify_password("", h) is True

    def test_unicode_password(self):
        h, salt = _hash_password("密码123")
        assert _verify_password("密码123", h) is True

    def test_long_password(self):
        long_pw = "a" * 200
        h, salt = _hash_password(long_pw)
        assert _verify_password(long_pw, h) is True


class TestUserCRUD:
    def test_create_user(self):
        result = create_user("test_user_" + str(id(self)), "pass1234")
        assert "id" in result
        assert "nickname" in result
        assert "error" not in result

    def test_create_duplicate_user(self):
        name = "dup_user_" + str(id(self))
        create_user(name, "pass1234")
        result = create_user(name, "pass5678")
        assert "error" in result

    def test_login_success(self):
        name = "login_user_" + str(id(self))
        create_user(name, "mypass123")
        result = login_user(name, "mypass123")
        assert result is not None
        assert result["nickname"] == name

    def test_login_wrong_password(self):
        name = "wrong_pw_" + str(id(self))
        create_user(name, "correct")
        result = login_user(name, "incorrect")
        assert result is None

    def test_login_nonexistent_user(self):
        result = login_user("nonexistent_user_xyz", "pass")
        assert result is None

    def test_get_user(self):
        name = "get_user_" + str(id(self))
        created = create_user(name, "pass1234")
        user = get_user(created["id"])
        assert user is not None
        assert user["nickname"] == name

    def test_get_nonexistent_user(self):
        user = get_user("nonexistent-uuid-12345")
        assert user is None


class TestSessionManagement:
    def test_start_session(self):
        name = "sess_user_" + str(id(self))
        user = create_user(name, "pass1234")
        sid = start_session(user["id"], "explorer")
        assert sid
        session = get_session(sid)
        assert session is not None

    def test_end_session(self):
        name = "end_user_" + str(id(self))
        user = create_user(name, "pass1234")
        sid = start_session(user["id"], "explorer")
        end_session(sid)
        session = get_session(sid)
        assert session["ended_at"] is not None

    def test_add_message(self):
        name = "msg_user_" + str(id(self))
        user = create_user(name, "pass1234")
        sid = start_session(user["id"], "explorer")
        msg_id = add_message(sid, "user", "hello")
        assert msg_id > 0
        msgs = get_recent_messages(sid, limit=10)
        assert len(msgs) >= 1
        assert msgs[0]["content"] == "hello"


class TestUserProfile:
    def test_profile_created_on_session(self):
        name = "prof_user_" + str(id(self))
        user = create_user(name, "pass1234")
        start_session(user["id"], "explorer")
        profile = get_user_profile(user["id"], "explorer")
        assert profile is not None

    def test_update_profile(self):
        name = "upd_user_" + str(id(self))
        user = create_user(name, "pass1234")
        start_session(user["id"], "explorer")
        update_user_profile(user["id"], "explorer", interest_tags=["昆曲", "京剧"])
        profile = get_user_profile(user["id"], "explorer")
        assert "昆曲" in profile["interest_tags"]

    def test_auto_update_profile(self):
        name = "auto_user_" + str(id(self))
        user = create_user(name, "pass1234")
        start_session(user["id"], "explorer")
        auto_update_profile(user["id"], "explorer", {"new_interests": ["刺绣"]})
        profile = get_user_profile(user["id"], "explorer")
        assert "刺绣" in profile["interest_tags"]
