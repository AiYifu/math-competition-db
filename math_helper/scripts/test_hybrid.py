"""测试BM25混合检索改进效果"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "retrieval-service" / "src"))

from searcher import HybridSearcher

API_KEY = "sk-mtxecjqwsqzpcagnafsqggltrokycncdktosawdxdezidgkr"

test_cases = [
    {
        "uid": "p002_008_1_1_dbdaf07a50",
        "original": "AM-GM不等式基本证明",
        "rewrites": [
            "证明两个非负数的算术平均数大于等于几何平均数",
            "对于正实数a和b，证明(a+b)/2 >= sqrt(ab)",
            "均值不等式的基本形式证明",
        ]
    },
    {
        "uid": "p017_017_10_5cca9e3e21", 
        "original": "三元不等式证明",
        "rewrites": [
            "三个正数满足平方和条件，证明一个分式不等式",
            "abc都是正数，给定约束条件，证明三个分数相加至少为3",
            "涉及a²+b²+c²和(a+b+c)²约束的不等式证明",
        ]
    },
    {
        "uid": "p017_017_17_42a45caf5f",
        "original": "三正数乘积不等式",
        "rewrites": [
            "三个正数之和为1，证明(1+a)(1+b)(1+c) >= 8(1-a)(1-b)(1-c)",
            "a+b+c=1的条件下，证明一个乘积不等式",
            "给定三个正数的和为定值，证明关于1加减变量的不等式",
        ]
    }
]

async def test_improved_recall():
    """测试改进后的召回率"""
    
    # 检查是否需要重新构建索引
    bm25_index_path = Path("../data/indices/bm25/bm25_index.pkl")
    
    searcher = HybridSearcher(
        api_key=API_KEY,
        index_dir=Path("../data/indices/faiss"),
        bm25_dir=Path("../data/indices/bm25")
    )
    
    # 如果没有BM25索引，需要构建
    if not bm25_index_path.exists():
        print("需要构建BM25索引...")
        import json
        unified_file = Path("../data/processed/unified_problems.json")
        with open(unified_file, 'r', encoding='utf-8') as f:
            problems = json.load(f)
        
        # 使用100道题目测试
        test_problems = problems[:100]
        await searcher.build_index(test_problems, batch_size=32)
    
    # 将输出写入文件
    output_file = Path("test_hybrid_result.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("="*70 + "\n")
        f.write("BM25混合检索测试\n")
        f.write("="*70 + "\n")
        
        total_tests = 0
        top1_recalls = 0
        top3_recalls = 0
        
        for i, case in enumerate(test_cases, 1):
            f.write(f"\n{'='*70}\n")
            f.write(f"测试题目 {i}: {case['uid']}\n")
            f.write(f"{'='*70}\n")
            
            for j, rewrite in enumerate(case['rewrites'], 1):
                f.write(f"\n  改写版本 {j}: {rewrite}\n")
                total_tests += 1
                
                # 使用混合检索
                result = await searcher.search(rewrite, top_k=5, use_hybrid=True)
                
                found_in_top1 = False
                found_in_top3 = False
                
                for rank, item in enumerate(result['results'], 1):
                    if item['uid'] == case['uid']:
                        if rank == 1:
                            found_in_top1 = True
                            top1_recalls += 1
                        if rank <= 3:
                            found_in_top3 = True
                        match_type = item.get('match_type', 'unknown')
                        f.write(f"    [OK] 在Top{rank}召回原题 (RRF分数: {item['score']:.4f}, 类型: {match_type})\n")
                        f.write(f"         向量分数: {item.get('vector_score', 0):.4f}, BM25分数: {item.get('bm25_score', 0):.4f}\n")
                        break
                
                if not found_in_top1 and not found_in_top3:
                    f.write(f"    [FAIL] 未在Top3召回\n")
                    if result['results']:
                        f.write(f"    Top1是: {result['results'][0]['uid']} (RRF: {result['results'][0]['score']:.4f})\n")
        
        # 统计结果
        f.write(f"\n{'='*70}\n")
        f.write("召回统计\n")
        f.write(f"{'='*70}\n")
        f.write(f"总测试次数: {total_tests}\n")
        f.write(f"Top1召回率: {top1_recalls}/{total_tests} = {top1_recalls/total_tests*100:.1f}%\n")
        f.write(f"Top3召回率: {top3_recalls}/{total_tests} = {top3_recalls/total_tests*100:.1f}%\n")
        f.write(f"\n对比之前的测试:\n")
        f.write(f"  原Top1召回率: 11.1%\n")
        f.write(f"  原Top3召回率: 22.2%\n")
    
    print(f"测试结果已保存到: {output_file.absolute()}")

if __name__ == "__main__":
    asyncio.run(test_improved_recall())
