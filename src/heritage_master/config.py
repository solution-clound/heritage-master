"""配置管理 - 从环境变量读取配置"""

from pathlib import Path as _Path
from pydantic_settings import BaseSettings
from pydantic import Field

_PROJECT_ROOT = str(_Path(__file__).resolve().parent.parent.parent)


class Settings(BaseSettings):
    """非遗大师助手配置"""

    # 高德地图 API
    amap_key: str = Field(default="", description="高德 Web Service API Key")
    amap_js_key: str = Field(default="", description="高德 Web JS API Key（前端地图用，为空时回退到 amap_key）")
    amap_security_code: str = Field(default="", description="高德 JS API 安全密钥")

    # GitHub 论坛
    github_token: str = Field(default="", description="GitHub Personal Access Token")
    forum_repo: str = Field(default="", description="论坛仓库，格式: owner/repo")

    # RAG 知识库
    rag_enabled: bool = Field(default=True, description="是否启用 RAG 知识库")
    chroma_path: str = Field(default=_PROJECT_ROOT + "/heritage_chroma_db", description="ChromaDB 存储路径")
    embedding_model: str = Field(
        default="paraphrase-multilingual-MiniLM-L12-v2",
        description="向量化模型名称"
    )
    embedding_device: str = Field(default="cpu", description="向量化运算设备 (cpu/cuda)")

    # 爬虫配置
    crawler_cache_ttl: int = Field(default=2592000, description="爬虫缓存过期时间（秒）")
    crawler_cache_dir: str = Field(default=_PROJECT_ROOT + "/heritage_cache", description="爬虫缓存目录")

    # 请求配置
    request_timeout: int = Field(default=30, description="HTTP 请求超时（秒）")

    # SQLite 用户数据库（兼容层，实际使用 PostgreSQL）
    sqlite_path: str = Field(default=_PROJECT_ROOT + "/heritage_data.db", description="SQLite 数据库路径（兼容）")

    # PostgreSQL
    pg_host: str = Field(default="localhost", description="PostgreSQL 主机")
    pg_port: int = Field(default=5432, description="PostgreSQL 端口")
    pg_database: str = Field(default="heritage_db", description="PostgreSQL 数据库名")
    pg_user: str = Field(default="postgres", description="PostgreSQL 用户名")
    pg_password: str = Field(default="", description="PostgreSQL 密码")

    # Neo4j
    neo4j_uri: str = Field(default="bolt://localhost:7687", description="Neo4j 连接 URI")
    neo4j_user: str = Field(default="neo4j", description="Neo4j 用户名")
    neo4j_password: str = Field(default="", description="Neo4j 密码")

    # Milvus
    milvus_host: str = Field(default="localhost", description="Milvus 主机")
    milvus_port: int = Field(default=19530, description="Milvus 端口")
    milvus_collection: str = Field(default="heritage_vectors", description="Milvus Collection 名称")

    # Elasticsearch
    es_host: str = Field(default="http://localhost:9200", description="Elasticsearch 地址")
    es_index: str = Field(default="heritage_literature", description="Elasticsearch 索引名")

    # Redis 缓存
    redis_enabled: bool = Field(default=False, description="是否启用 Redis 缓存")
    redis_host: str = Field(default="localhost", description="Redis 主机")
    redis_port: int = Field(default=6379, description="Redis 端口")
    redis_db: int = Field(default=0, description="Redis DB 编号")
    redis_password: str = Field(default="", description="Redis 密码")

    # 长期记忆
    memory_dir: str = Field(default=_PROJECT_ROOT + "/src/heritage_master/memory", description="记忆文件存储目录")
    memory_consolidation_threshold: int = Field(default=50, description="记忆条数达到此阈值触发整理")
    memory_cache_ttl: int = Field(default=600, description="记忆缓存过期时间（秒）")

    # LLM 大模型（支持多模型切换）
    llm_provider: str = Field(default="deepseek", description="LLM Provider (deepseek/openai/claude/qwen)")
    llm_api_key: str = Field(default="", description="LLM API Key")
    llm_base_url: str = Field(default="https://api.deepseek.com/v1", description="LLM API 地址")
    llm_model: str = Field(default="deepseek-chat", description="LLM 模型名称")
    user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        description="爬虫 User-Agent"
    )

    model_config = {"env_prefix": "HERITAGE_", "env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
