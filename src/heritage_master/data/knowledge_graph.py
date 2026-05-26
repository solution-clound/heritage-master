"""文化知识图谱

基于 JSON 的轻量图谱引擎，支持节点查询、邻居查找、路径搜索、师承溯源。
"""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Set
from collections import deque

_GRAPH_FILE = Path(__file__).parent / "graph.json"
_graph_cache = None


def load_graph() -> Dict[str, Any]:
    """加载图谱数据（带缓存）"""
    global _graph_cache
    if _graph_cache is not None:
        return _graph_cache
    try:
        _graph_cache = json.loads(_GRAPH_FILE.read_text(encoding="utf-8"))
    except Exception:
        _graph_cache = {"nodes": {}, "edges": []}
    return _graph_cache


def reload_graph() -> Dict[str, Any]:
    """强制重新加载图谱"""
    global _graph_cache
    _graph_cache = None
    return load_graph()


def get_node(node_id: str) -> Optional[Dict[str, Any]]:
    """获取节点信息"""
    graph = load_graph()
    return graph["nodes"].get(node_id)


def get_neighbors(node_id: str, edge_type: str = None) -> List[Dict[str, Any]]:
    """获取邻居节点

    Args:
        node_id: 节点ID
        edge_type: 可选，只返回特定类型的边连接的节点

    Returns:
        邻居节点列表，每个包含 node_id, edge_type, 以及节点属性
    """
    graph = load_graph()
    neighbors = []

    for edge in graph["edges"]:
        target_id = None
        if edge["from"] == node_id:
            target_id = edge["to"]
        elif edge["to"] == node_id:
            target_id = edge["from"]

        if target_id and (edge_type is None or edge["type"] == edge_type):
            node = graph["nodes"].get(target_id)
            if node:
                neighbors.append({
                    "node_id": target_id,
                    "edge_type": edge["type"],
                    **node,
                })

    return neighbors


def find_path(from_id: str, to_id: str, max_depth: int = 4) -> List[List[str]]:
    """BFS查找两个节点之间的路径

    Returns:
        路径列表，每条路径是节点ID列表。返回所有最短路径。
    """
    graph = load_graph()
    if from_id not in graph["nodes"] or to_id not in graph["nodes"]:
        return []

    # 构建邻接表
    adj = {}
    for edge in graph["edges"]:
        adj.setdefault(edge["from"], []).append(edge["to"])
        adj.setdefault(edge["to"], []).append(edge["from"])

    # BFS
    queue = deque([(from_id, [from_id])])
    visited = {from_id}
    found_paths = []
    found_depth = None

    while queue:
        current, path = queue.popleft()

        if found_depth and len(path) > found_depth:
            break

        if current == to_id:
            found_paths.append(path)
            found_depth = len(path)
            continue

        if len(path) >= max_depth:
            continue

        for neighbor in adj.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    return found_paths


def search_nodes(query: str, node_type: str = None, limit: int = 20) -> List[Dict[str, Any]]:
    """按名称/描述搜索节点

    Args:
        query: 搜索关键词
        node_type: 可选，限定节点类型
        limit: 返回数量

    Returns:
        匹配的节点列表
    """
    graph = load_graph()
    results = []
    query_lower = query.lower()

    for node_id, node in graph["nodes"].items():
        if node_type and node.get("type") != node_type:
            continue

        # 搜索名称和描述
        name = node.get("name", "").lower()
        desc = node.get("description", "").lower()

        if query_lower in name or query_lower in desc:
            results.append({"node_id": node_id, **node})

        if len(results) >= limit:
            break

    return results


def get_inheritance_chain(person_id: str) -> List[Dict[str, Any]]:
    """获取师承链（向上追溯）

    Returns:
        从当前人物向上追溯的师承链
    """
    graph = load_graph()
    chain = []
    current = person_id
    visited = set()

    while current and current not in visited:
        visited.add(current)
        node = graph["nodes"].get(current)
        if not node:
            break

        chain.append({"node_id": current, **node})

        # 找 INHERITS_FROM 边
        master_id = None
        for edge in graph["edges"]:
            if edge["from"] == current and edge["type"] == "INHERITS_FROM":
                master_id = edge["to"]
                break

        current = master_id

    return chain


def get_related_projects(node_id: str) -> List[str]:
    """获取与某节点相关的非遗项目"""
    graph = load_graph()
    projects = set()

    # 直接关联
    for edge in graph["edges"]:
        if edge["type"] in ("HAS_INHERITOR", "HAS_TECHNIQUE", "FROM_REGION", "PART_OF"):
            if edge["to"] == node_id:
                projects.add(edge["from"])
            elif edge["from"] == node_id:
                projects.add(edge["to"])

    # 通过邻居间接关联
    for edge in graph["edges"]:
        if edge["from"] == node_id or edge["to"] == node_id:
            other = edge["to"] if edge["from"] == node_id else edge["from"]
            # 检查other是否是project
            other_node = graph["nodes"].get(other)
            if other_node and other_node.get("type") == "project":
                projects.add(other)

    return list(projects)


def get_graph_stats() -> Dict[str, Any]:
    """获取图谱统计信息"""
    graph = load_graph()
    nodes = graph["nodes"]
    edges = graph["edges"]

    # 节点类型统计
    node_types = {}
    for node in nodes.values():
        t = node.get("type", "unknown")
        node_types[t] = node_types.get(t, 0) + 1

    # 边类型统计
    edge_types = {}
    for edge in edges:
        t = edge.get("type", "unknown")
        edge_types[t] = edge_types.get(t, 0) + 1

    return {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "node_types": node_types,
        "edge_types": edge_types,
    }


def get_nodes_by_type(node_type: str, limit: int = 100) -> List[Dict[str, Any]]:
    """获取指定类型的所有节点"""
    graph = load_graph()
    results = []
    for node_id, node in graph["nodes"].items():
        if node.get("type") == node_type:
            results.append({"node_id": node_id, **node})
            if len(results) >= limit:
                break
    return results


def explore_node(node_id: str, depth: int = 2) -> Dict[str, Any]:
    """从某节点出发探索图谱

    Returns:
        包含中心节点和多层邻居的图结构
    """
    graph = load_graph()
    center = graph["nodes"].get(node_id)
    if not center:
        return {"error": "节点不存在"}

    result = {
        "center": {"node_id": node_id, **center},
        "neighbors": [],
    }

    visited = {node_id}
    current_level = [node_id]

    for d in range(depth):
        next_level = []
        for nid in current_level:
            for edge in graph["edges"]:
                target = None
                if edge["from"] == nid:
                    target = edge["to"]
                elif edge["to"] == nid:
                    target = edge["from"]

                if target and target not in visited:
                    visited.add(target)
                    node = graph["nodes"].get(target)
                    if node:
                        result["neighbors"].append({
                            "node_id": target,
                            "from": nid,
                            "edge_type": edge["type"],
                            "depth": d + 1,
                            **node,
                        })
                        next_level.append(target)
        current_level = next_level

    return result
