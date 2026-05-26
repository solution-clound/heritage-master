"""从 knowledge.json 构建 graph.json

一次性脚本：解析扁平知识库，提取实体和关系，生成图谱数据。

运行方式：
    python scripts/build_graph.py
"""

import json
import sys
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).parent.parent
KNOWLEDGE_FILE = ROOT / "src" / "heritage_master" / "data" / "knowledge.json"
GRAPH_FILE = ROOT / "src" / "heritage_master" / "data" / "graph.json"


def normalize_id(prefix: str, name: str) -> str:
    """生成标准化的节点ID"""
    return f"{prefix}:{name.strip()}"


def build_graph():
    """从 knowledge.json 构建图谱"""
    knowledge = json.loads(KNOWLEDGE_FILE.read_text(encoding="utf-8"))

    nodes = {}  # node_id -> node_data
    edges = []  # list of edge dicts
    edge_set = set()  # 去重

    def add_node(node_id: str, **attrs):
        if node_id not in nodes:
            nodes[node_id] = attrs

    def add_edge(from_id: str, to_id: str, edge_type: str):
        key = (from_id, to_id, edge_type)
        if key not in edge_set:
            edge_set.add(key)
            edges.append({"from": from_id, "to": to_id, "type": edge_type})

    for project_name, data in knowledge.items():
        project_id = normalize_id("project", project_name)

        # 添加项目节点
        add_node(project_id,
                 type="project",
                 name=data.get("name", project_name),
                 category=data.get("category", ""),
                 level=data.get("level", ""),
                 batch=data.get("batch", ""),
                 description=data.get("description", "")[:200])

        # 添加地域节点和边
        regions = data.get("region", [])
        if isinstance(regions, str):
            regions = [regions]
        for region_name in regions:
            if not region_name:
                continue
            region_id = normalize_id("region", region_name)
            add_node(region_id, type="region", name=region_name)
            add_edge(project_id, region_id, "FROM_REGION")

        # 添加传承人节点和边
        inheritors = data.get("inheritors", [])
        for inheritor in inheritors:
            name = inheritor.get("name", "")
            if not name:
                continue
            person_id = normalize_id("person", name)
            add_node(person_id,
                     type="person",
                     name=name,
                     title=inheritor.get("title", ""),
                     specialty=inheritor.get("specialty", ""))
            add_edge(project_id, person_id, "HAS_INHERITOR")

        # 添加流派节点和边
        schools = data.get("schools", [])
        if isinstance(schools, dict):
            schools = [f"{k}: {', '.join(v[:2])}" for k, v in schools.items()]
        for school_name in schools:
            if not school_name:
                continue
            school_id = normalize_id("school", school_name)
            add_node(school_id, type="school", name=school_name)
            add_edge(school_id, project_id, "PART_OF")

        # 添加代表作节点和边
        masterpieces = data.get("masterpieces", [])
        for work_name in masterpieces:
            if not work_name:
                continue
            work_id = normalize_id("work", work_name)
            add_node(work_id, type="work", name=work_name)
            add_edge(work_id, project_id, "BELONGS_TO")

        # 添加相关项目边
        related = data.get("related", [])
        for rel_name in related:
            if not rel_name:
                continue
            rel_id = normalize_id("project", rel_name)
            # 相关项目节点可能还不存在，先添加
            add_node(rel_id, type="project", name=rel_name)
            add_edge(project_id, rel_id, "RELATED_TO")

        # 从起源信息提取关键人物
        origin = data.get("origin", {})
        if origin:
            founder = origin.get("founder", "")
            if founder:
                # 可能有多个，用顿号分隔
                for f in founder.split("、"):
                    f = f.strip().split("（")[0].strip()  # 去掉括号注释
                    if f and len(f) >= 2:
                        fid = normalize_id("person", f)
                        add_node(fid, type="person", name=f, title="创始人")
                        add_edge(project_id, fid, "FOUNDED_BY")

            reformer = origin.get("reformer", "")
            if reformer:
                for r in reformer.split("、"):
                    r = r.strip().split("（")[0].strip()
                    if r and len(r) >= 2:
                        rid = normalize_id("person", r)
                        add_node(rid, type="person", name=r, title="改革者")
                        add_edge(project_id, rid, "REFORMED_BY")

        # 添加技艺节点（从类别推导）
        category = data.get("category", "")
        if category:
            tech_id = normalize_id("technique", category)
            add_node(tech_id, type="technique", name=category)
            add_edge(project_id, tech_id, "HAS_TECHNIQUE")

    # 构建师承关系（从传承人的 specialty 字段推导）
    # 如果某人的 specialty 与某项目匹配，建立 PRACTICES 关系
    for node_id, node in list(nodes.items()):
        if node.get("type") == "person" and node.get("specialty"):
            specialty = node["specialty"]
            # 查找匹配的项目
            for pid, pdata in nodes.items():
                if pdata.get("type") == "project":
                    pname = pdata.get("name", "")
                    if specialty in pname or pname in specialty:
                        add_edge(node_id, pid, "PRACTICES")

    graph = {"nodes": nodes, "edges": edges}

    # 写入文件
    GRAPH_FILE.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

    # 输出统计
    stats = {}
    for node in nodes.values():
        t = node.get("type", "unknown")
        stats[t] = stats.get(t, 0) + 1

    edge_stats = {}
    for edge in edges:
        t = edge.get("type", "unknown")
        edge_stats[t] = edge_stats.get(t, 0) + 1

    print(f"图谱构建完成: {GRAPH_FILE}")
    print(f"节点总数: {len(nodes)}")
    for t, c in sorted(stats.items()):
        print(f"  {t}: {c}")
    print(f"边总数: {len(edges)}")
    for t, c in sorted(edge_stats.items()):
        print(f"  {t}: {c}")


if __name__ == "__main__":
    build_graph()
