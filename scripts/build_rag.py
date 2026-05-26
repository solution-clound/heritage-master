#!/usr/bin/env python3
"""
构建 RAG 知识库 - 将知识文档向量化存入 ChromaDB

用法:
    python scripts/build_rag.py              # 构建全部
    python scripts/build_rag.py --file xxx.md  # 构建指定文件
    python scripts/build_rag.py --reset       # 重置知识库后重建
"""

import argparse
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


def build_single_file(collection, file_path: Path, embed_batch) -> int:
    """
    向量化单个文件并存入 ChromaDB。

    Args:
        collection: ChromaDB collection
        file_path: 文件路径
        embed_batch: 批量向量化函数

    Returns:
        处理的段落数
    """
    content = file_path.read_text(encoding="utf-8")
    paragraphs = split_paragraphs(content)

    if not paragraphs:
        print(f"  [跳过] {file_path.name}: 无有效段落")
        return 0

    # 生成 ID 和元数据
    ids = [f"{file_path.stem}_{i}" for i in range(len(paragraphs))]
    metadatas = [
        {
            "source": file_path.name,
            "source_stem": file_path.stem,
            "paragraph_index": i,
        }
        for i in range(len(paragraphs))
    ]

    # 向量化
    embeddings = embed_batch(paragraphs)

    # 存入 ChromaDB（upsert 避免重复）
    collection.upsert(
        ids=ids,
        documents=paragraphs,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    print(f"  [完成] {file_path.name}: {len(paragraphs)} 个段落")
    return len(paragraphs)


def main():
    """主函数"""
    import chromadb

    from heritage_master.config import settings
    from heritage_master.data.local_embedding import embed_batch

    parser = argparse.ArgumentParser(description="构建 RAG 知识库")
    parser.add_argument("--file", type=str, help="指定单个文件路径")
    parser.add_argument("--reset", action="store_true", help="重置知识库后重建")
    parser.add_argument("--knowledge-dir", type=str, help="知识目录路径")
    args = parser.parse_args()

    # 知识目录
    if args.knowledge_dir:
        knowledge_dir = Path(args.knowledge_dir)
    else:
        knowledge_dir = Path(__file__).parent.parent / "src" / "heritage_master" / "rag" / "knowledge"

    if not knowledge_dir.exists():
        print(f"[错误] 知识目录不存在: {knowledge_dir}")
        sys.exit(1)

    # 初始化 ChromaDB
    print(f"[信息] 初始化 ChromaDB: {settings.chroma_path}")
    client = chromadb.PersistentClient(path=settings.chroma_path)

    # 重置模式：删除旧集合
    if args.reset:
        try:
            client.delete_collection("heritage_knowledge")
            print("[信息] 已删除旧的知识库集合")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name="heritage_knowledge",
        metadata={"hnsw:space": "cosine"},
    )

    # 加载 embedding 模型
    print(f"[信息] 加载向量化模型: {settings.embedding_model}")
    print(f"[信息] 运算设备: {settings.embedding_device}")

    # 处理文件
    total_paragraphs = 0
    total_files = 0

    if args.file:
        # 处理单个文件
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"[错误] 文件不存在: {file_path}")
            sys.exit(1)
        total_paragraphs = build_single_file(collection, file_path, embed_batch)
        total_files = 1
    else:
        # 扫描知识目录
        md_files = sorted(knowledge_dir.glob("**/*.md"))
        if not md_files:
            print(f"[警告] 知识目录中没有找到 .md 文件: {knowledge_dir}")
            sys.exit(0)

        print(f"[信息] 找到 {len(md_files)} 个知识文件")
        for md_file in md_files:
            total_paragraphs += build_single_file(collection, md_file, embed_batch)
            total_files += 1

    print(f"\n[完成] 共处理 {total_files} 个文件，{total_paragraphs} 个段落")
    print(f"[信息] ChromaDB 存储路径: {settings.chroma_path}")
    print(f"[信息] 当前集合文档数: {collection.count()}")


if __name__ == "__main__":
    main()
