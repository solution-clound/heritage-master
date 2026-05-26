"""实时数据模块测试

注意：所有测试验证的是"不返回假数据"，而非"一定返回数据"。
因为实时数据依赖网络请求，测试环境可能无法访问外部 API。
"""

import pytest
from heritage_master.data.realtime import (
    get_heritage_news,
    get_news_for_context,
    get_data_status,
)


def test_get_data_status():
    """测试数据状态查询"""
    status = get_data_status()
    assert isinstance(status, dict)
    assert "ihchina_news" in status
    assert status["ihchina_news"]["source"] == "ihchina.cn"
    assert status["ihchina_news"]["type"] == "real_time"


@pytest.mark.asyncio
async def test_get_heritage_news_returns_list():
    """测试获取新闻返回列表（可能为空）"""
    news = await get_heritage_news(limit=5)
    assert isinstance(news, list)
    # 不断言 len >= 1，因为网络请求可能失败


@pytest.mark.asyncio
async def test_get_heritage_news_limit():
    """测试新闻数量限制"""
    news = await get_heritage_news(limit=3)
    assert len(news) <= 3


@pytest.mark.asyncio
async def test_get_heritage_news_fields():
    """测试返回的新闻字段完整性"""
    news = await get_heritage_news(limit=5)
    for n in news:
        assert "title" in n, "新闻缺少 title 字段"
        assert "source" in n, "新闻缺少 source 字段"
        assert n["title"], "新闻 title 为空"
        # 验证来源是真实的
        assert n["source"] in ("中国非遗网",), f"未知数据来源: {n['source']}"


def test_get_news_for_context_returns_list():
    """测试上下文新闻返回列表"""
    news = get_news_for_context("你好")
    assert isinstance(news, list)


def test_get_news_for_context_no_cache():
    """测试无缓存时返回空列表（不返回假数据）"""
    # 在测试环境中，缓存通常为空
    # 应该返回空列表，而不是假数据
    news = get_news_for_context("非遗")
    assert isinstance(news, list)
    # 如果没有缓存，应该返回空
    # 如果有缓存（之前有网络请求），应该返回真实数据


def test_get_news_for_context_limit():
    """测试新闻数量限制"""
    news = get_news_for_context("非遗", limit=3)
    assert len(news) <= 3


def test_no_fake_data_in_module():
    """测试模块中没有硬编码的假新闻数据"""
    import heritage_master.data.realtime as rt
    # 确保没有 _FALLBACK_NEWS 这种假数据
    assert not hasattr(rt, '_FALLBACK_NEWS'), "模块中不应有硬编码的兜底假数据"
