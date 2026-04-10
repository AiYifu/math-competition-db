"""构建向量索引脚本"""
import asyncio
import json
import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.retrieval_service.src.embeddings import SiliconFlowEmbeddings
from services.retrieval_service.src.vector_store import VectorStore
from services.retrieval_service.src.searcher import HybridSearcher

# 硅基流动API Key
API_KEY = "sk-mtxecjqwsqzpcagnafsqggltrokycncdktosawdxdezidgkr"

async def build_index_from_unified():
    """从统一格式的题目构建索引"""
    
    # 读取统一格式的题目
    unified_file = Path("../../data/processed/unified_problems.json")
    
    if not unified_file.exists():
        print(f"错误: 未找到 {unified_file}")
        print("请先运行: python scripts/data_pipeline.py")
        return
    
    print(f"加载题目数据: {unified_file}")
    with open(unified_file, 'r', encoding='utf-8') as f:
        problems = json.load(f)
    
    print(f"共加载 {len(problems)} 道题目")
    
    # 初始化检索器并构建索引
    searcher = HybridSearcher(
        api_key=API_KEY,
        index_dir=Path("../../data/indices/faiss")
    )
    
    await searcher.build_index(
        problems=problems,
        batch_size=32
    )
    
    print("索引构建完成!")

async def build_index_from_raw():
    """直接从原始数据构建索引"""
    
    # 读取书籍题目
    books_dir = Path("../../problem_database/books")
    problems = []
    
    print("扫描书籍题目...")
    for json_file in books_dir.rglob("*.json"):
        if json_file.name == "all_books.json":
            continue
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                problems.append({
                    "uid": data.get('uid', str(json_file.stem)),
                    "stem": data.get('stem_md', ''),
                    "source": "books",
                    "metadata": {
                        "book_title": data.get('book_title', ''),
                        "chapter": data.get('chapter', ''),
                        "section": data.get('section', '')
                    }
                })
        except Exception as e:
            print(f"加载失败 {json_file}: {e}")
    
    print(f"共 {len(problems)} 道题目")
    
    if len(problems) == 0:
        print("没有找到题目数据!")
        return
    
    # 构建索引
    searcher = HybridSearcher(
        api_key=API_KEY,
        index_dir=Path("../../data/indices/faiss")
    )
    
    await searcher.build_index(
        problems=problems,
        batch_size=32
    )
    
    print("索引构建完成!")

if __name__ == "__main__":
    import sys
    
    # 检查是否有统一格式的数据
    unified_file = Path("../../data/processed/unified_problems.json")
    
    if unified_file.exists():
        print("使用统一格式的数据构建索引...")
        asyncio.run(build_index_from_unified())
    else:
        print("从原始数据构建索引...")
        asyncio.run(build_index_from_raw())