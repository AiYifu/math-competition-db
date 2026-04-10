"""测试检索功能 - 使用小批量数据快速验证"""
import asyncio
import json
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "services" / "retrieval-service" / "src"))
sys.path.insert(0, str(project_root))

from embeddings import SiliconFlowEmbeddings
from vector_store import VectorStore
from searcher import HybridSearcher

API_KEY = "sk-mtxecjqwsqzpcagnafsqggltrokycncdktosawdxdezidgkr"

async def test_with_small_batch():
    """使用100道题目测试"""
    
    # 读取统一格式的题目
    unified_file = Path("../data/processed/unified_problems.json")
    
    print(f"加载题目数据...")
    with open(unified_file, 'r', encoding='utf-8') as f:
        all_problems = json.load(f)
    
    # 只取前100道进行测试
    test_problems = all_problems[:100]
    print(f"使用 {len(test_problems)} 道题目进行测试（总共 {len(all_problems)} 道）")
    
    # 初始化检索器
    searcher = HybridSearcher(
        api_key=API_KEY,
        index_dir=Path("../data/indices/faiss")
    )
    
    # 构建索引
    print("\n开始构建索引...")
    await searcher.build_index(
        problems=test_problems,
        batch_size=32
    )
    
    print("\n索引构建完成!")
    print(f"索引统计: {searcher.get_stats()}")
    
    # 测试查询
    test_queries = [
        "证明：对于任何非负实数 $a,b$，有 $a^2+b^2 \\geqslant 2ab$",
        "柯西不等式",
        "设 $a, b, c > 0$，证明不等式",
    ]
    
    print("\n" + "="*60)
    print("测试检索功能")
    print("="*60)
    
    for query in test_queries:
        print(f"\n查询: {query[:50]}...")
        result = await searcher.search(query, top_k=3)
        
        print(f"  是否精确匹配: {result['exact_match']}")
        print(f"  查询耗时: {result['query_time_ms']:.2f}ms")
        print(f"  返回结果数: {len(result['results'])}")
        
        for i, item in enumerate(result['results'], 1):
            print(f"  Top {i}: {item['uid']} (相似度: {item['score']:.4f})")
    
    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_with_small_batch())
