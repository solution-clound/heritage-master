"""
LangGraph Agent 模块 — 非遗大师助手

基于 LangGraph StateGraph 实现的 Agent 编排引擎，
替代原有的手写 for 循环 function calling。

核心组件：
- state.py  — 状态定义 (AgentState)
- tools.py  — 工具定义 (@tool 装饰器)
- nodes.py  — 图节点 (agent / tools / memory)
- graph.py  — StateGraph 构建与编译
"""

from heritage_master.agent.graph import build_heritage_agent, run_heritage_agent

__all__ = ["build_heritage_agent", "run_heritage_agent"]
