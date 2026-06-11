"""图谱存储抽象层

GraphStore 抽象基类 + 工厂函数，支持自动选择 JSON / Neo4j 后端。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class GraphStore(ABC):
    """图谱存储抽象基类 — 定义所有图谱后端必须实现的接口"""

    @abstractmethod
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取节点信息"""
        ...

    @abstractmethod
    def get_neighbors(self, node_id: str, edge_type: str = None) -> List[Dict[str, Any]]:
        """获取邻居节点

        Args:
            node_id: 节点ID
            edge_type: 可选，只返回特定类型的边连接的节点

        Returns:
            邻居节点列表，每个包含 node_id, edge_type, 以及节点属性
        """
        ...

    @abstractmethod
    def find_path(self, from_id: str, to_id: str, max_depth: int = 4) -> List[List[str]]:
        """BFS查找两个节点之间的路径

        Returns:
            路径列表，每条路径是节点ID列表。返回所有最短路径。
        """
        ...

    @abstractmethod
    def search_nodes(self, query: str, node_type: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """按名称/描述搜索节点

        Args:
            query: 搜索关键词
            node_type: 可选，限定节点类型
            limit: 返回数量

        Returns:
            匹配的节点列表
        """
        ...

    @abstractmethod
    def get_inheritance_chain(self, person_id: str) -> List[Dict[str, Any]]:
        """获取师承链（向上追溯）

        Returns:
            从当前人物向上追溯的师承链
        """
        ...

    @abstractmethod
    def explore_node(self, node_id: str, depth: int = 2) -> Dict[str, Any]:
        """从某节点出发探索图谱

        Returns:
            包含中心节点和多层邻居的图结构
        """
        ...

    @abstractmethod
    def get_graph_stats(self) -> Dict[str, Any]:
        """获取图谱统计信息"""
        ...

    @abstractmethod
    def get_nodes_by_type(self, node_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取指定类型的所有节点"""
        ...


def create_graph_store() -> GraphStore:
    """工厂函数 — 根据配置自动选择后端

    优先尝试 Neo4j，如果未配置或连接失败则降级到 JSON。
    """
    from heritage_master.config import settings

    # 如果配置了 Neo4j 密码，尝试连接
    if settings.neo4j_password:
        try:
            from heritage_master.data.neo4j_store import Neo4jStore
            store = Neo4jStore()
            # 用 get_graph_stats 验证连接是否畅通
            store.get_graph_stats()
            return store
        except Exception:
            pass

    # 降级到 JSON 后端
    from heritage_master.data.json_graph_store import JsonGraphStore
    return JsonGraphStore()


# 全局单例
_instance: Optional[GraphStore] = None


def get_graph_store() -> GraphStore:
    """获取全局 GraphStore 单例"""
    global _instance
    if _instance is None:
        _instance = create_graph_store()
    return _instance
