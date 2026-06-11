"""LangGraph Agent 模块测试"""

import pytest


def test_imports():
    """测试模块能正常导入"""
    from heritage_master.agent.state import AgentState
    from heritage_master.agent.tools import HERITAGE_TOOLS, search_heritage, find_venues
    from heritage_master.agent.nodes import agent_node, tool_node, memory_node
    from heritage_master.agent.graph import build_graph, build_heritage_agent

    # 验证工具数量
    assert len(HERITAGE_TOOLS) == 6

    # 验证工具名称
    tool_names = {t.name for t in HERITAGE_TOOLS}
    expected = {"search_heritage", "find_venues", "plan_trip",
                "query_knowledge_graph", "get_inheritance_chain", "find_events"}
    assert tool_names == expected


def test_state_definition():
    """测试状态类型定义"""
    from heritage_master.agent.state import AgentState
    import typing

    hints = typing.get_type_hints(AgentState)
    assert "messages" in hints
    assert "user_id" in hints
    assert "session_id" in hints
    assert "panels" in hints
    assert "tool_results_cache" in hints
    assert "system_prompt" in hints
    assert "final_reply" in hints


def test_graph_build():
    """测试图构建"""
    from heritage_master.agent.graph import build_graph
    from langgraph.graph import StateGraph

    graph = build_graph()
    assert isinstance(graph, StateGraph)

    # 验证节点
    nodes = list(graph.nodes)
    assert "agent" in nodes
    assert "tools" in nodes
    assert "memory" in nodes


def test_graph_compile():
    """测试图编译"""
    from heritage_master.agent.graph import build_heritage_agent

    agent = build_heritage_agent()
    assert agent is not None

    # 验证图结构
    graph_dict = agent.get_graph().to_json()
    assert "nodes" in graph_dict
    assert "edges" in graph_dict


def test_tool_schemas():
    """测试工具 schema 生成"""
    from heritage_master.agent.tools import HERITAGE_TOOLS

    for tool in HERITAGE_TOOLS:
        schema = tool.args_schema.model_json_schema()
        assert "properties" in schema
        assert "title" in schema


def test_route_after_agent():
    """测试条件路由逻辑"""
    from heritage_master.agent.graph import route_after_agent
    from langchain_core.messages import AIMessage, HumanMessage

    # 无 tool_calls → memory
    state = {
        "messages": [AIMessage(content="你好")],
    }
    assert route_after_agent(state) == "memory"

    # 有 tool_calls → tools
    state = {
        "messages": [
            AIMessage(content="", tool_calls=[{
                "name": "search_heritage",
                "args": {"query": "昆曲"},
                "id": "test_123",
            }]),
        ],
    }
    assert route_after_agent(state) == "tools"


@pytest.mark.asyncio
async def test_search_heritage_tool():
    """测试 search_heritage 工具（需要网络）"""
    from heritage_master.agent.tools import search_heritage

    result = await search_heritage.ainvoke({"query": "昆曲", "region": "", "category": ""})
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_query_knowledge_graph_tool():
    """测试 query_knowledge_graph 工具"""
    from heritage_master.agent.tools import query_knowledge_graph

    result = await query_knowledge_graph.ainvoke({"query": "醒狮", "node_type": ""})
    assert isinstance(result, str)
