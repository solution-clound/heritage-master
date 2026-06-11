"""JSON 文件图谱存储

将 knowledge_graph.py 中的模块级函数封装为 GraphStore 子类。
保持原有逻辑不变，仅加了一层面向对象的包装。
"""

import json
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

from heritage_master.data.graph_store import GraphStore

_GRAPH_FILE = Path(__file__).parent / "graph.json"


class JsonGraphStore(GraphStore):
    """基于 JSON 文件的轻量图谱存储"""

    def __init__(self):
        self._graph_cache: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # 内部：加载 / 重载
    # ------------------------------------------------------------------

    def _load_graph(self) -> Dict[str, Any]:
        """加载图谱数据（带缓存）"""
        if self._graph_cache is not None:
            return self._graph_cache
        try:
            self._graph_cache = json.loads(_GRAPH_FILE.read_text(encoding="utf-8"))
        except Exception:
            self._graph_cache = {"nodes": {}, "edges": []}
        return self._graph_cache

    def reload_graph(self) -> Dict[str, Any]:
        """强制重新加载图谱"""
        self._graph_cache = None
        return self._load_graph()

    # ------------------------------------------------------------------
    # GraphStore 接口实现
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取节点信息"""
        graph = self._load_graph()
        return graph["nodes"].get(node_id)

    def get_neighbors(self, node_id: str, edge_type: str = None) -> List[Dict[str, Any]]:
        """获取邻居节点"""
        graph = self._load_graph()
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

    def find_path(self, from_id: str, to_id: str, max_depth: int = 4) -> List[List[str]]:
        """BFS查找两个节点之间的路径

        Returns:
            路径列表，每条路径是节点ID列表。返回所有最短路径。
        """
        graph = self._load_graph()
        if from_id not in graph["nodes"] or to_id not in graph["nodes"]:
            return []

        # 构建邻接表
        adj: Dict[str, List[str]] = {}
        for edge in graph["edges"]:
            adj.setdefault(edge["from"], []).append(edge["to"])
            adj.setdefault(edge["to"], []).append(edge["from"])

        # BFS
        queue = deque([(from_id, [from_id])])
        visited = {from_id}
        found_paths: List[List[str]] = []
        found_depth: Optional[int] = None

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

    def search_nodes(self, query: str, node_type: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """按名称/描述搜索节点"""
        graph = self._load_graph()
        results: List[Dict[str, Any]] = []
        query_lower = query.lower()

        for node_id, node in graph["nodes"].items():
            if node_type and node.get("type") != node_type:
                continue

            name = node.get("name", "").lower()
            desc = node.get("description", "").lower()

            if query_lower in name or query_lower in desc:
                results.append({"node_id": node_id, **node})

            if len(results) >= limit:
                break

        return results

    def get_inheritance_chain(self, person_id: str) -> List[Dict[str, Any]]:
        """获取师承链（向上追溯）"""
        graph = self._load_graph()
        chain: List[Dict[str, Any]] = []
        current = person_id
        visited: set = set()

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

    def explore_node(self, node_id: str, depth: int = 2) -> Dict[str, Any]:
        """从某节点出发探索图谱

        Returns:
            包含中心节点和多层邻居的图结构
        """
        graph = self._load_graph()
        center = graph["nodes"].get(node_id)
        if not center:
            return {"error": "节点不存在"}

        result: Dict[str, Any] = {
            "center": {"node_id": node_id, **center},
            "neighbors": [],
        }

        visited = {node_id}
        current_level = [node_id]

        for d in range(depth):
            next_level: List[str] = []
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

    def get_graph_stats(self) -> Dict[str, Any]:
        """获取图谱统计信息"""
        graph = self._load_graph()
        nodes = graph["nodes"]
        edges = graph["edges"]

        node_types: Dict[str, int] = {}
        for node in nodes.values():
            t = node.get("type", "unknown")
            node_types[t] = node_types.get(t, 0) + 1

        edge_types: Dict[str, int] = {}
        for edge in edges:
            t = edge.get("type", "unknown")
            edge_types[t] = edge_types.get(t, 0) + 1

        return {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "node_types": node_types,
            "edge_types": edge_types,
        }

    def get_nodes_by_type(self, node_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取指定类型的所有节点"""
        graph = self._load_graph()
        results: List[Dict[str, Any]] = []
        for node_id, node in graph["nodes"].items():
            if node.get("type") == node_type:
                results.append({"node_id": node_id, **node})
                if len(results) >= limit:
                    break
        return results
