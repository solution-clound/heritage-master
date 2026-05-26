from __future__ import annotations

"""Neo4j 图谱存储层 - 替代 JSON 文件的知识图谱引擎"""

from typing import Any, Dict, List, Optional

from heritage_master.config import settings

_driver = None


def get_driver():
    """获取或创建 Neo4j Driver"""
    global _driver
    if _driver is None:
        try:
            from neo4j import GraphDatabase
            _driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
        except ImportError:
            raise RuntimeError("neo4j 未安装，请运行: pip install neo4j")
    return _driver


def close_driver():
    """关闭 Driver"""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


class Neo4jStore:
    """Neo4j 知识图谱存储"""

    def __init__(self):
        self._driver = get_driver()

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取节点信息"""
        with self._driver.session() as session:
            result = session.run(
                "MATCH (n {node_id: $node_id}) RETURN n",
                node_id=node_id,
            )
            record = result.single()
            if record:
                node = record["n"]
                return dict(node)
            return None

    def get_neighbors(
        self,
        node_id: str,
        edge_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """获取邻居节点"""
        with self._driver.session() as session:
            if edge_type:
                query = """
                    MATCH (n {node_id: $node_id})-[r]->(m)
                    WHERE type(r) = $edge_type
                    RETURN m, type(r) AS edge_type
                    LIMIT $limit
                """
                result = session.run(
                    query, node_id=node_id, edge_type=edge_type, limit=limit
                )
            else:
                query = """
                    MATCH (n {node_id: $node_id})-[r]->(m)
                    RETURN m, type(r) AS edge_type
                    LIMIT $limit
                """
                result = session.run(query, node_id=node_id, limit=limit)

            neighbors = []
            for record in result:
                node = dict(record["m"])
                node["edge_type"] = record["edge_type"]
                node["from"] = node_id
                neighbors.append(node)
            return neighbors

    def find_path(
        self, from_id: str, to_id: str, max_depth: int = 4
    ) -> List[Dict[str, Any]]:
        """查找两个节点间的最短路径"""
        with self._driver.session() as session:
            query = """
                MATCH path = shortestPath(
                    (a {node_id: $from_id})-[*..%d]-(b {node_id: $to_id})
                )
                RETURN [n IN nodes(path) | n.node_id] AS node_ids,
                       [r IN relationships(path) | type(r)] AS edge_types
            """ % max_depth

            result = session.run(query, from_id=from_id, to_id=to_id)
            record = result.single()
            if record:
                return [
                    {"node_ids": record["node_ids"], "edge_types": record["edge_types"]}
                ]
            return []

    def search_nodes(
        self,
        query: str,
        node_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """按名称搜索节点"""
        with self._driver.session() as session:
            if node_type:
                cypher = """
                    MATCH (n:%s)
                    WHERE n.name CONTAINS $query
                    RETURN n LIMIT $limit
                """ % node_type.capitalize()
            else:
                cypher = """
                    MATCH (n)
                    WHERE n.name CONTAINS $query
                    RETURN n LIMIT $limit
                """

            result = session.run(cypher, query=query, limit=limit)
            nodes = []
            for record in result:
                node = dict(record["n"])
                nodes.append(node)
            return nodes

    def get_inheritance_chain(self, person_id: str) -> List[Dict[str, Any]]:
        """获取师承链（向上追溯）"""
        with self._driver.session() as session:
            query = """
                MATCH path = (p {node_id: $person_id})-[:INHERITS_FROM*]->(master)
                RETURN [n IN nodes(path) | {name: n.name, title: n.title}] AS chain
                LIMIT 1
            """
            result = session.run(query, person_id=person_id)
            record = result.single()
            if record:
                return record["chain"]
            return []

    def explore_node(
        self, node_id: str, depth: int = 2
    ) -> Dict[str, Any]:
        """从某节点出发探索图谱"""
        center = self.get_node(node_id)
        if not center:
            return {"error": f"节点 {node_id} 不存在"}

        neighbors = []
        visited = {node_id}
        frontier = [node_id]

        for d in range(depth):
            next_frontier = []
            for nid in frontier:
                for neighbor in self.get_neighbors(nid, limit=20):
                    neighbor_id = neighbor.get("node_id", "")
                    if neighbor_id and neighbor_id not in visited:
                        visited.add(neighbor_id)
                        neighbor["depth"] = d + 1
                        neighbors.append(neighbor)
                        next_frontier.append(neighbor_id)
            frontier = next_frontier

        return {"center": center, "neighbors": neighbors}

    def get_graph_stats(self) -> Dict[str, Any]:
        """获取图谱统计信息"""
        with self._driver.session() as session:
            # 节点统计
            node_result = session.run(
                "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt"
            )
            node_types = {}
            total_nodes = 0
            for record in node_result:
                label = record["label"] or "Unknown"
                cnt = record["cnt"]
                node_types[label.lower()] = cnt
                total_nodes += cnt

            # 边统计
            edge_result = session.run("MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS cnt")
            edge_types = {}
            total_edges = 0
            for record in edge_result:
                etype = record["type"]
                cnt = record["cnt"]
                edge_types[etype] = cnt
                total_edges += cnt

            return {
                "total_nodes": total_nodes,
                "total_edges": total_edges,
                "node_types": node_types,
                "edge_types": edge_types,
            }

    def get_nodes_by_type(
        self, node_type: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """按类型获取节点列表"""
        with self._driver.session() as session:
            result = session.run(
                "MATCH (n:%s) RETURN n LIMIT $limit" % node_type.capitalize(),
                limit=limit,
            )
            return [dict(record["n"]) for record in result]

    def import_from_json(self, graph_json_path: str) -> Dict[str, int]:
        """从 graph.json 批量导入数据"""
        import json
        from collections import Counter, defaultdict

        graph = json.loads(Path(graph_json_path).read_text(encoding="utf-8"))
        nodes = graph.get("nodes", {})
        edges = graph.get("edges", [])

        # 按类型分批导入节点
        by_type = defaultdict(list)
        for node_id, attrs in nodes.items():
            ntype = attrs.get("type", "Unknown")
            by_type[ntype].append({
                "node_id": node_id,
                "name": attrs.get("name", ""),
                "title": attrs.get("title", ""),
                "specialty": attrs.get("specialty", ""),
                "description": attrs.get("description", ""),
                "category": attrs.get("category", ""),
                "level": attrs.get("level", ""),
            })

        node_count = 0
        with self._driver.session() as session:
            for ntype, nodes_of_type in by_type.items():
                query = f"""
                    UNWIND $nodes AS n
                    MERGE (p:{ntype} {{node_id: n.node_id}})
                    SET p.name = n.name, p.title = n.title,
                        p.specialty = n.specialty, p.description = n.description
                """
                session.run(query, nodes=nodes_of_type)
                node_count += len(nodes_of_type)

            # 按类型分批导入边
            edge_count = 0
            for edge in edges:
                edge_type = edge.get("type", "RELATED_TO")
                query = f"""
                    MATCH (a {{node_id: $from_id}})
                    MATCH (b {{node_id: $to_id}})
                    MERGE (a)-[:{edge_type}]->(b)
                """
                try:
                    session.run(query, from_id=edge["from"], to_id=edge["to"])
                    edge_count += 1
                except Exception:
                    pass

        return {"nodes_imported": node_count, "edges_imported": edge_count}


from pathlib import Path
