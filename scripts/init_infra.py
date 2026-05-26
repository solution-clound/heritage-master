"""基础设施初始化脚本

初始化 PostgreSQL、Neo4j、Elasticsearch、Milvus 的表结构和索引。

使用方式：
    python scripts/init_infra.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# 将 src 加入 path
_root = Path(__file__).parent.parent
sys.path.insert(0, str(_root / "src"))

from heritage_master.config import settings


async def init_postgreSQL():
    """初始化 PostgreSQL：创建表结构 + pgvector 扩展"""
    try:
        import asyncpg
    except ImportError:
        print("[SKIP] asyncpg 未安装，跳过 PostgreSQL 初始化")
        return

    print(f"[PG] 连接 {settings.pg_host}:{settings.pg_port}/{settings.pg_database} ...")
    try:
        conn = await asyncpg.connect(
            host=settings.pg_host,
            port=settings.pg_port,
            database=settings.pg_database,
            user=settings.pg_user,
            password=settings.pg_password,
        )
    except Exception as e:
        print(f"[PG] 连接失败: {e}")
        return

    try:
        # 启用 pgvector 扩展
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("[PG] pgvector 扩展已启用")

        # 创建表（语法适配 PostgreSQL）
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                nickname TEXT NOT NULL,
                avatar_url TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                master_id TEXT NOT NULL,
                relationship_stage TEXT DEFAULT '试探期',
                interest_tags TEXT DEFAULT '[]',
                aesthetic_pref TEXT DEFAULT '',
                personality_notes TEXT DEFAULT '',
                question_count INTEGER DEFAULT 0,
                first_met_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_talk_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, master_id)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                master_id TEXT NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                topic_summary TEXT DEFAULT ''
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES chat_sessions(id),
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS cultivation_records (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                master_id TEXT NOT NULL,
                practice_type TEXT NOT NULL,
                content TEXT NOT NULL,
                master_comment TEXT DEFAULT '',
                score INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS stage_progress (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                master_id TEXT NOT NULL,
                stage TEXT NOT NULL DEFAULT '入门期',
                stage_entered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_practice_days INTEGER DEFAULT 0,
                total_questions INTEGER DEFAULT 0,
                UNIQUE(user_id, master_id)
            )
        """)

        print("[PG] 6张表创建完成")
    finally:
        await conn.close()


def init_neo4j():
    """初始化 Neo4j：创建约束和索引"""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("[SKIP] neo4j 驱动未安装，跳过 Neo4j 初始化")
        return

    print(f"[Neo4j] 连接 {settings.neo4j_uri} ...")
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
        # 为每种节点类型创建唯一性约束
        node_types = ["Person", "Project", "School", "Region", "Technique", "Work"]
        for ntype in node_types:
            try:
                session.run(
                    f"CREATE CONSTRAINT IF NOT EXISTS "
                    f"FOR (n:{ntype}) REQUIRE n.node_id IS UNIQUE"
                )
                print(f"[Neo4j] 约束创建: {ntype}.node_id UNIQUE")
            except Exception as e:
                print(f"[Neo4j] 约略 {ntype}: {e}")

        # 全文索引
        try:
            session.run("""
                CREATE FULLTEXT INDEX heritage_fulltext IF NOT EXISTS
                FOR (n:Person|Project|School|Region|Technique|Work)
                ON EACH [n.name, n.description]
            """)
            print("[Neo4j] 全文索引创建完成")
        except Exception as e:
            print(f"[Neo4j] 全文索引: {e}")

    driver.close()
    print("[Neo4j] 初始化完成")


def init_elasticsearch():
    """初始化 Elasticsearch：创建索引和 mapping"""
    try:
        from elasticsearch import Elasticsearch
    except ImportError:
        print("[SKIP] elasticsearch 未安装，跳过 ES 初始化")
        return

    print(f"[ES] 连接 {settings.es_host} ...")
    try:
        es = Elasticsearch(settings.es_host)
        if not es.ping():
            print("[ES] 连接失败")
            return
    except Exception as e:
        print(f"[ES] 连接失败: {e}")
        return

    # 创建索引（使用 ik 分词器，如未安装则回退到 standard）
    mapping = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    "heritage_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "cjk_width"],
                    }
                }
            },
        },
        "mappings": {
            "properties": {
                "title": {"type": "text", "analyzer": "heritage_analyzer"},
                "content": {"type": "text", "analyzer": "heritage_analyzer"},
                "category": {"type": "keyword"},
                "region": {"type": "keyword"},
                "level": {"type": "keyword"},
                "source": {"type": "keyword"},
                "doc_type": {"type": "keyword"},
                "created_at": {"type": "date"},
            }
        },
    }

    if es.indices.exists(index=settings.es_index):
        print(f"[ES] 索引 {settings.es_index} 已存在，跳过创建")
    else:
        es.indices.create(index=settings.es_index, body=mapping)
        print(f"[ES] 索引 {settings.es_index} 创建完成")


def init_milvus():
    """初始化 Milvus：创建 Collection"""
    try:
        from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
    except ImportError:
        print("[SKIP] pymilvus 未安装，跳过 Milvus 初始化")
        return

    print(f"[Milvus] 连接 {settings.milvus_host}:{settings.milvus_port} ...")
    try:
        connections.connect(
            alias="default",
            host=settings.milvus_host,
            port=settings.milvus_port,
        )
    except Exception as e:
        print(f"[Milvus] 连接失败: {e}")
        return

    collection_name = settings.milvus_collection

    if utility.has_collection(collection_name):
        print(f"[Milvus] Collection {collection_name} 已存在，跳过创建")
        connections.disconnect("default")
        return

    # 定义 Schema
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192),
        FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
    ]

    schema = CollectionSchema(fields=fields, description="非遗知识向量库")
    collection = Collection(name=collection_name, schema=schema)

    # 创建 IVF_FLAT 索引
    index_params = {
        "metric_type": "COSINE",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128},
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    print(f"[Milvus] Collection {collection_name} 创建完成（dim=1536, COSINE）")

    connections.disconnect("default")


async def main():
    print("=" * 50)
    print("非遗大师助手 - 基础设施初始化")
    print("=" * 50)

    await init_postgreSQL()
    init_neo4j()
    init_elasticsearch()
    init_milvus()

    print()
    print("=" * 50)
    print("初始化完成！")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
