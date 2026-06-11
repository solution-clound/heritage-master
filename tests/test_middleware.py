# -*- coding: utf-8 -*-
"""认证中间件 & 限流中间件测试"""
import pytest
import os
from unittest.mock import patch


class TestAuthMiddleware:
    def test_dev_mode_allows_all(self):
        with patch.dict(os.environ, {"HERITAGE_API_KEYS": "", "HERITAGE_JWT_SECRET": ""}):
            from heritage_master.middleware.auth import authenticate_request, reload_api_keys
            reload_api_keys()
            # Mock request
            class MockRequest:
                headers = {}
            result = authenticate_request(MockRequest())
            assert result.authenticated is True
            assert result.method == "none"

    def test_api_key_auth(self):
        with patch.dict(os.environ, {"HERITAGE_API_KEYS": '{"test-key": "user1"}'}):
            from heritage_master.middleware.auth import authenticate_request, reload_api_keys
            reload_api_keys()
            class MockRequest:
                headers = {"X-API-Key": "test-key"}
            result = authenticate_request(MockRequest())
            assert result.authenticated is True
            assert result.user_id == "user1"
            assert result.method == "api_key"

    def test_invalid_api_key(self):
        with patch.dict(os.environ, {"HERITAGE_API_KEYS": '{"test-key": "user1"}'}):
            from heritage_master.middleware.auth import authenticate_request, reload_api_keys
            reload_api_keys()
            class MockRequest:
                headers = {"X-API-Key": "wrong-key"}
            result = authenticate_request(MockRequest())
            assert result.authenticated is False

    def test_no_auth_when_required(self):
        with patch.dict(os.environ, {"HERITAGE_API_KEYS": '{"test-key": "user1"}'}):
            from heritage_master.middleware.auth import authenticate_request, reload_api_keys
            reload_api_keys()
            class MockRequest:
                headers = {}
            result = authenticate_request(MockRequest())
            assert result.authenticated is False


class TestPublicPaths:
    def test_health_is_public(self):
        from heritage_master.middleware.auth import _PUBLIC_PREFIXES
        assert "/health" in _PUBLIC_PREFIXES

    def test_login_is_public(self):
        from heritage_master.middleware.auth import _PUBLIC_PREFIXES
        assert "/api/user/login" in _PUBLIC_PREFIXES

    def test_register_is_public(self):
        from heritage_master.middleware.auth import _PUBLIC_PREFIXES
        assert "/api/user/register" in _PUBLIC_PREFIXES

    def test_search_is_public(self):
        from heritage_master.middleware.auth import _PUBLIC_PREFIXES
        assert "/api/search" in _PUBLIC_PREFIXES

    def test_slash_not_in_public(self):
        from heritage_master.middleware.auth import _PUBLIC_PREFIXES
        assert "/" not in _PUBLIC_PREFIXES


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_in_memory_allows(self):
        from heritage_master.middleware.rate_limit import InMemoryRateLimiter
        limiter = InMemoryRateLimiter()
        assert await limiter.is_allowed("test", 5, 60) is True

    @pytest.mark.asyncio
    async def test_in_memory_blocks(self):
        from heritage_master.middleware.rate_limit import InMemoryRateLimiter
        limiter = InMemoryRateLimiter()
        for _ in range(5):
            await limiter.is_allowed("test", 5, 60)
        assert await limiter.is_allowed("test", 5, 60) is False

    @pytest.mark.asyncio
    async def test_in_memory_separate_keys(self):
        from heritage_master.middleware.rate_limit import InMemoryRateLimiter
        limiter = InMemoryRateLimiter()
        for _ in range(5):
            await limiter.is_allowed("key1", 5, 60)
        assert await limiter.is_allowed("key2", 5, 60) is True

    def test_match_rate_limit(self):
        from heritage_master.middleware.rate_limit import _match_rate_limit
        assert _match_rate_limit("/api/agent") is not None
        assert _match_rate_limit("/api/agent/chat") is not None
        assert _match_rate_limit("/api/nonexistent") is None

    def test_get_client_ip_forwarded(self):
        from heritage_master.middleware.rate_limit import get_client_ip
        class Req:
            headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
            client = type("C", (), {"host": "9.9.9.9"})()
        assert get_client_ip(Req()) == "1.2.3.4"

    def test_get_client_ip_direct(self):
        from heritage_master.middleware.rate_limit import get_client_ip
        class Req:
            headers = {}
            client = type("C", (), {"host": "9.9.9.9"})()
        assert get_client_ip(Req()) == "9.9.9.9"


class TestRateLimitRules:
    def test_agent_limited(self):
        from heritage_master.middleware.rate_limit import RATE_LIMITS
        assert "/api/agent" in RATE_LIMITS
        max_req, window = RATE_LIMITS["/api/agent"]
        assert max_req == 10
        assert window == 60

    def test_search_limited(self):
        from heritage_master.middleware.rate_limit import RATE_LIMITS
        assert "/api/search" in RATE_LIMITS
