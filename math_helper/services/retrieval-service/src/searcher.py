"""检索编排器 - 整合多层检索"""
from typing import List, Dict, Tuple, Optional
import time
import numpy as np
from pathlib import Path
import json

from embeddings import SiliconFlowEmbeddings
from vector_store import VectorStore
from bm25_index import BM25Index

class HybridSearcher:
    """混合检索器：向量检索 + BM25稀疏检索 + 融合排序"""
    
    def __init__(
        self,
        api_key: str,
        index_dir: Path = Path("./data/indices/faiss"),
        bm25_dir: Path = Path("./data/indices/bm25"),
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3
    ):
        self.api_key = api_key
        self.index_dir = index_dir
        self.bm25_dir = bm25_dir
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        
        self.embedder = SiliconFlowEmbeddings(api_key=api_key)
        self.vector_store = VectorStore()
        self.bm25_index = BM25Index()
        
        # 加载已有索引
        if (index_dir / "index.faiss").exists():
            self.vector_store.load(index_dir)
            print(f"加载向量索引: {self.vector_store.get_stats()}")
        
        if self.bm25_index.load(bm25_dir):
            print(f"加载BM25索引: {self.bm25_index.N} 文档")
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        exact_match_threshold: float = 0.99,
        use_hybrid: bool = True
    ) -> List[Dict]:
        """
        执行混合检索
        
        Args:
            query: 查询文本（LaTeX格式）
            top_k: 返回结果数量
            exact_match_threshold: 精确匹配阈值
            use_hybrid: 是否使用混合检索（向量+BM25）
            
        Returns:
            检索结果列表
        """
        start_time = time.time()
        
        # Step 1: 向量检索
        query_emb = await self.embedder.embed_single(query)
        recall_k = max(top_k * 8, 40)  # 召回更多用于融合
        vector_ids, vector_scores = self.vector_store.search(query_emb, k=recall_k)
        
        # 检查精确匹配
        exact_match = False
        if vector_scores and vector_scores[0] >= exact_match_threshold:
            exact_match = True
        
        # Step 2: BM25检索（如果使用混合检索）
        if use_hybrid and self.bm25_index.N > 0:
            bm25_results = self.bm25_index.search(query, top_k=recall_k)
        else:
            bm25_results = []
        
        # Step 3: 融合排序（RRF - Reciprocal Rank Fusion）
        if use_hybrid and bm25_results:
            fused_results = self._reciprocal_rank_fusion(
                list(zip(vector_ids, vector_scores)),
                bm25_results,
                top_k=top_k
            )
        else:
            # 仅使用向量结果
            fused_results = [
                {"uid": uid, "score": score, "match_type": "semantic"}
                for uid, score in zip(vector_ids[:top_k], vector_scores[:top_k])
            ]
        
        query_time = (time.time() - start_time) * 1000
        
        return {
            "results": fused_results,
            "exact_match": exact_match,
            "query_time_ms": query_time,
            "vector_results": len(vector_ids),
            "bm25_results": len(bm25_results)
        }
    
    def _reciprocal_rank_fusion(
        self,
        vector_results: List[Tuple[str, float]],
        bm25_results: List[Tuple[str, float]],
        top_k: int = 5,
        k: int = 60  # RRF常数
    ) -> List[Dict]:
        """
        使用RRF（倒数排名融合）合并向量检索和BM25结果
        
        RRF公式: score = sum(1 / (k + rank))
        """
        scores = {}
        
        # 处理向量检索结果
        for rank, (uid, score) in enumerate(vector_results, 1):
            if uid not in scores:
                scores[uid] = {"rrf_score": 0, "vector_score": score, "bm25_score": 0}
            scores[uid]["rrf_score"] += 1.0 / (k + rank)
            scores[uid]["vector_rank"] = rank
        
        # 处理BM25结果
        for rank, (uid, score) in enumerate(bm25_results, 1):
            if uid not in scores:
                scores[uid] = {"rrf_score": 0, "vector_score": 0, "bm25_score": score}
            scores[uid]["rrf_score"] += 1.0 / (k + rank)
            scores[uid]["bm25_rank"] = rank
        
        # 按RRF分数排序
        sorted_results = sorted(scores.items(), key=lambda x: x[1]["rrf_score"], reverse=True)
        
        # 组装返回结果
        results = []
        for uid, score_info in sorted_results[:top_k]:
            # 确定匹配类型
            if score_info.get("vector_rank", 999) <= 3 and score_info.get("bm25_rank", 999) <= 3:
                match_type = "hybrid_strong"
            elif score_info.get("vector_rank", 999) <= 5 or score_info.get("bm25_rank", 999) <= 5:
                match_type = "hybrid_medium"
            elif score_info["vector_score"] > 0:
                match_type = "semantic"
            else:
                match_type = "keyword"
            
            results.append({
                "uid": uid,
                "score": score_info["rrf_score"],
                "vector_score": score_info["vector_score"],
                "bm25_score": score_info["bm25_score"],
                "match_type": match_type
            })
        
        return results
    
    async def build_index(
        self,
        problems: List[Dict],
        batch_size: int = 32
    ):
        """
        从题目列表构建索引（向量+BM25）
        
        Args:
            problems: 题目列表，每个包含uid和stem字段
            batch_size: 批处理大小
        """
        print(f"开始构建索引，共 {len(problems)} 道题目...")
        
        # 构建BM25索引（先构建，不需要API调用）
        print("构建BM25索引...")
        self.bm25_index = BM25Index()
        self.bm25_index.add_documents(problems)
        self.bm25_index.save(self.bm25_dir)
        print(f"BM25索引完成: {self.bm25_index.N} 文档")
        
        # 构建向量索引
        print("构建向量索引...")
        texts = [p["stem"] for p in problems]
        ids = [p["uid"] for p in problems]
        metadata = [
            {
                "uid": p["uid"],
                "source": p.get("source", ""),
                "metadata": p.get("metadata", {})
            }
            for p in problems
        ]
        
        # 批量生成embedding
        print("生成embeddings...")
        embeddings = await self.embedder.embed_batch(
            texts,
            batch_size=batch_size,
            show_progress=True
        )
        
        # 添加到向量存储
        print("添加到FAISS索引...")
        self.vector_store.add(embeddings, ids, metadata)
        
        # 保存索引
        print(f"保存索引...")
        self.vector_store.save(self.index_dir)
        
        print(f"索引构建完成!")
        print(f"  向量索引: {self.vector_store.get_stats()}")
        print(f"  BM25索引: {self.bm25_index.N} 文档")
    
    def get_document(self, uid: str) -> Optional[Dict]:
        """根据ID获取文档元数据"""
        return self.vector_store.metadata.get(uid)
    
    def get_stats(self) -> Dict:
        """获取索引统计信息"""
        return {
            "vector": self.vector_store.get_stats(),
            "bm25": {"documents": self.bm25_index.N}
        }
