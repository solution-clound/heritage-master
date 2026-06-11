"""Token 预算管理器

控制每次 Agent 请求的总 token 消耗，防止意外高成本请求。
当预算耗尽时，跳过非必要 LLM 调用（如记忆提取的 LLM 通道）。

用法：在 AgentState 中设置 token_budget 字段，
      每次 LLM 调用后调用 deduct() 扣减。
"""
from __future__ import annotations
import logging

logger = logging.getLogger("heritage.token_budget")

# 默认预算（每次用户请求）
DEFAULT_BUDGET = 6000  # tokens

# 各节点预估消耗
NODE_COSTS = {
    "classify_and_plan": 800,   # 意图+规划（合并后）
    "agent": 1500,              # 主 LLM 决策
    "memory_extract": 500,      # 记忆提取（可跳过）
}


def check_budget(budget: int, node_name: str) -> bool:
    """检查是否有足够预算执行该节点的 LLM 调用。
    
    Returns:
        True=允许执行, False=预算不足，应跳过
    """
    if budget < 0:
        return True  # -1 表示无限制
    cost = NODE_COSTS.get(node_name, 500)
    if budget < cost:
        logger.info("[token_budget] 预算不足: remaining=%d, %s needs ~%d", budget, node_name, cost)
        return False
    return True


def deduct(budget: int, node_name: str, actual_tokens: int = 0) -> int:
    """扣减 token 预算，返回剩余值。
    
    Args:
        budget: 当前剩余预算
        node_name: 节点名称（用于预估）
        actual_tokens: 实际消耗（如果已知，否则用预估值）
    
    Returns:
        扣减后的预算值
    """
    if budget < 0:
        return -1
    cost = actual_tokens if actual_tokens > 0 else NODE_COSTS.get(node_name, 500)
    remaining = max(0, budget - cost)
    logger.debug("[token_budget] %s consumed ~%d, remaining=%d", node_name, cost, remaining)
    return remaining
