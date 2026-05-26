"""数据迁移脚本

将现有 SQLite/JSON 数据迁移到 PostgreSQL/Neo4j/Milvus/Elasticsearch。

使用方式：
    python scripts/migrate_data.py
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root / "src"))

from heritage_master.config import settings

# 源文件路径
SQLITE_PATH = _root / "heritage_data.db"
GRAPH_JSON = _root / "src" / "heritage_master" / "data" / "graph.json"
KNOWLEDGE_JSON = _root / "src" / "heritage_master" / "data" / "knowledge.json"


async def migrate_sqlite_to_pg():
    """SQLite → PostgreSQL：迁移6张表数据"""
    if not SQLITE_PATH.exists():
        print("[SKIP] heritage_data.db 不存在，跳过 SQLite→PG 迁移")
        return

    try:
        import asyncpg
    except ImportError:
        print("[SKIP] asyncpg 未安装")
        return

    # 读取 SQLite 数据
    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row

    tables = ["users", "user_profiles", "chat_sessions", "chat_messages",
              "cultivation_records", "stage_progress"]

    print(f"[PG] 连接 PostgreSQL ...")
    try:
        pg = await asyncpg.connect(
            host=settings.pg_host,
            port=settings.pg_port,
            database=settings.pg_database,
            user=settings.pg_user,
            password=settings.pg_password,
        )
    except Exception as e:
        print(f"[PG] 连接失败: {e}")
        conn.close()
        return

    for table in tables:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            print(f"[PG] {table}: 0行，跳过")
            continue

        columns = rows[0].keys()
        # SQLite 用 ? 占位符，PG 用 $1,$2,...
        placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
        col_names = ", ".join(columns)
        insert_sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

        count = 0
        for row in rows:
            values = tuple(row[col] for col in columns)
            try:
                await pg.execute(insert_sql, *values)
                count += 1
            except Exception as e:
                print(f"[PG] {table} 插入失败: {e}")

        print(f"[PG] {table}: 迁移 {count}/{len(rows)} 行")

    await pg.close()
    conn.close()
    print("[PG] SQLite→PG 迁移完成")


def migrate_graph_to_neo4j():
    """graph.json → Neo4j：导入379节点+556边"""
    if not GRAPH_JSON.exists():
        print("[SKIP] graph.json 不存在，跳过 Neo4j 导入")
        return

    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("[SKIP] neo4j 驱动未安装")
        return

    graph = json.loads(GRAPH_JSON.read_text(encoding="utf-8"))
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])

    print(f"[Neo4j] 图谱数据: {len(nodes)} 节点, {len(edges)} 边")

    try:
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        driver.verify_connectivity()
    except Exception as e:
        print(f"[Neo4j] 连接失败: {e}")
        return

    with driver.session() as session:
        # 批量导入节点
        node_list = []
        for node_id, attrs in nodes.items():
            ntype = attrs.get("type", "Unknown")
            node_list.append({
                "node_id": node_id,
                "type": ntype,
                "name": attrs.get("name", ""),
                "title": attrs.get("title", ""),
                "specialty": attrs.get("specialty", ""),
                "description": attrs.get("description", ""),
                "category": attrs.get("category", ""),
                "level": attrs.get("level", ""),
            })

        # 按类型分批导入
        from collections import defaultdict
        by_type = defaultdict(list)
        for n in node_list:
            by_type[n["type"]].append(n)

        for ntype, nodes_of_type in by_type.items():
            query = f"""
                UNWIND $nodes AS n
                MERGE (p:{ntype} {{node_id: n.node_id}})
                SET p.name = n.name,
                    p.title = n.title,
                    p.specialty = n.specialty,
                    p.description = n.description,
                    p.category = n.category,
                    p.level = n.level
            """
            session.run(query, nodes=nodes_of_type)
            print(f"[Neo4j] 导入 {ntype}: {len(nodes_of_type)} 个节点")

        # 批量导入边
        from collections import Counter
        edge_type_counts = Counter()
        for edge in edges:
            edge_type_counts[edge.get("type", "RELATED_TO")] += 1

        for edge_type in edge_type_counts:
            batch = [e for e in edges if e.get("type") == edge_type]
            query = f"""
                UNWIND $edges AS e
                MATCH (a {{node_id: e.from}})
                MATCH (b {{node_id: e.to}})
                MERGE (a)-[r:{edge_type}]->(b)
            """
            session.run(query, edges=batch)
            print(f"[Neo4j] 导入 {edge_type}: {len(batch)} 条边")

    driver.close()
    print("[Neo4j] graph.json→Neo4j 迁移完成")


def migrate_knowledge_to_es():
    """knowledge.json + 内置数据 → Elasticsearch"""
    try:
        from elasticsearch import Elasticsearch, helpers
    except ImportError:
        print("[SKIP] elasticsearch 未安装")
        return

    try:
        es = Elasticsearch(settings.es_host)
        if not es.ping():
            print("[ES] 连接失败")
            return
    except Exception as e:
        print(f"[ES] 连接失败: {e}")
        return

    docs = []

    # 从 knowledge.json 提取
    if KNOWLEDGE_JSON.exists():
        knowledge = json.loads(KNOWLEDGE_JSON.read_text(encoding="utf-8"))
        for name, data in knowledge.items():
            docs.append({
                "_index": settings.es_index,
                "_id": f"knowledge:{name}",
                "_source": {
                    "title": name,
                    "content": json.dumps(data, ensure_ascii=False)[:8000],
                    "category": data.get("category", ""),
                    "region": ", ".join(data.get("region", [])) if isinstance(data.get("region"), list) else data.get("region", ""),
                    "level": data.get("level", ""),
                    "source": "knowledge.json",
                    "doc_type": "heritage_project",
                },
            })
        print(f"[ES] knowledge.json: {len(docs)} 条文档")

    # 从 crawler 内置数据提取
    try:
        from heritage_master.data.crawler import _get_builtin_data
        builtin = _get_builtin_data()
        for item in builtin:
            name = item.get("name", "")
            docs.append({
                "_index": settings.es_index,
                "_id": f"builtin:{name}",
                "_source": {
                    "title": name,
                    "content": item.get("description", "")[:8000],
                    "category": item.get("category", ""),
                    "region": item.get("region", ""),
                    "level": item.get("level", ""),
                    "source": "builtin",
                    "doc_type": "heritage_project",
                },
            })
        print(f"[ES] 内置数据: {len(builtin)} 条文档")
    except Exception:
        pass

    if docs:
        success, errors = helpers.bulk(es, docs, raise_on_error=False)
        print(f"[ES] 索引完成: {success} 成功, {len(errors)} 失败")
    else:
        print("[ES] 无数据可索引")


async def main():
    print("=" * 50)
    print("非遗大师助手 - 数据迁移")
    print("=" * 50)

    await migrate_sqlite_to_pg()
    migrate_graph_to_neo4j()
    migrate_knowledge_to_es()

    # Milvus 需要 Embedding 模型，单独处理
    print()
    print("[Milvus] 跳过（需要 Embedding API 配置后单独运行）")
    print("         运行: python scripts/index_to_milvus.py")

    print()
    print("=" * 50)
    print("迁移完成！")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
