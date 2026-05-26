#!/usr/bin/env python3
"""初始化 RAG 知识库 - 扫描知识文档并存入 ChromaDB"""

import sys
from pathlib import Path

# 添加 src 到 path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def split_paragraphs(text: str, min_length: int = 20) -> list[str]:
    """
    按段落拆分文本，过滤过短的段落。

    Args:
        text: 输入文本
        min_length: 最小段落长度

    Returns:
        段落列表
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return [p for p in paragraphs if len(p) >= min_length]


def main():
    """主函数：扫描知识目录，向量化并存入 ChromaDB"""
    import chromadb

    from heritage_master.config import settings

    # 知识目录
    knowledge_dir = Path(__file__).parent.parent / "src" / "heritage_master" / "rag" / "knowledge"
    if not knowledge_dir.exists():
        print(f"[错误] 知识目录不存在: {knowledge_dir}")
        sys.exit(1)

    # 扫描 md 文件
    md_files = sorted(knowledge_dir.glob("**/*.md"))
    if not md_files:
        print(f"[警告] 知识目录中没有找到 .md 文件: {knowledge_dir}")
        sys.exit(0)

    print(f"[信息] 找到 {len(md_files)} 个知识文件")

    # 初始化 ChromaDB
    print(f"[信息] 初始化 ChromaDB: {settings.chroma_path}")
    client = chromadb.PersistentClient(path=settings.chroma_path)
    collection = client.get_or_create_collection(
        name="heritage_knowledge",
        metadata={"hnsw:space": "cosine"},
    )

    # 加载 embedding 模型
    print(f"[信息] 加载向量化模型: {settings.embedding_model}")
    from heritage_master.data.local_embedding import embed_batch

    # 处理每个文件
    total_paragraphs = 0
    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        paragraphs = split_paragraphs(content)

        if not paragraphs:
            print(f"  [跳过] {md_file.name}: 无有效段落")
            continue

        # 生成 ID 和元数据
        ids = [f"{md_file.stem}_{i}" for i in range(len(paragraphs))]
        metadatas = [
            {
                "source": md_file.name,
                "source_stem": md_file.stem,
                "paragraph_index": i,
            }
            for i in range(len(paragraphs))
        ]

        # 向量化
        embeddings = embed_batch(paragraphs)

        # 存入 ChromaDB
        collection.upsert(
            ids=ids,
            documents=paragraphs,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        total_paragraphs += len(paragraphs)
        print(f"  [完成] {md_file.name}: {len(paragraphs)} 个段落")

    print(f"\n[完成] 共处理 {len(md_files)} 个文件，{total_paragraphs} 个段落")
    print(f"[信息] ChromaDB 存储路径: {settings.chroma_path}")


if __name__ == "__main__":
    main()
