"""检索编排器 - 整合多层检索"""
from typing import List, Dict, Tuple, Optional
import time
import numpy as np
from pathlib import Path
import json

from .embeddings import SiliconFlowEmbeddings
from .vector_store import VectorStore

class HybridSearcher:
    """混合检索器：向量检索 + 精确匹配 + 重排序"""
    
    def __init__(
        self,
        api_key: str,
        index_dir: Path = Path("./data/indices/faiss")
    ):
        self.api_key = api_key
        self.index_dir = index_dir
        
        self.embedder = SiliconFlowEmbeddings(api_key=api_key)
        self.vector_store = VectorStore()
        
        # 加载已有索引
        if (index_dir / "index.faiss").exists():
            self.vector_store.load(index_dir)
            print(f"加载索引: {self.vector_store.get_stats()}")
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        exact_match_threshold: float = 0.99
    ) -> List[Dict]:
        """
        执行混合检索
        
        Args:
            query: 查询文本（LaTeX格式）
            top_k: 返回结果数量
            exact_match_threshold: 精确匹配阈值
            
        Returns:
            检索结果列表
        """
        start_time = time.time()
        
        # Step 1: 获取查询embedding
        query_emb = await self.embedder.embed_single(query)
        
        # Step 2: 向量检索（召回更多，用于重排序）
        recall_k = max(top_k * 4, 20)
        vector_ids, vector_scores = self.vector_store.search(query_emb, k=recall_k)
        
        results = []
        exact_match = False
        
        # 检查精确匹配
        if vector_scores and vector_scores[0] >= exact_match_threshold:
            exact_match = True
            results = [
                {
                    "uid": uid,
                    "score": score,
                    "match_type": "exact"
                }
                for uid, score in zip(vector_ids[:top_k], vector_scores[:top_k])
            ]
        else:
            # 组装结果
            results = [
                {
                    "uid": uid,
                    "score": score,
                    "match_type": "semantic"
                }
                for uid, score in zip(vector_ids[:top_k], vector_scores[:top_k])
            ]
        
        query_time = (time.time() - start_time) * 1000
        
        return {
            "results": results,
            "exact_match": exact_match,
            "query_time_ms": query_time
        }
    
    async def build_index(
        self,
        problems: List[Dict],
        batch_size: int = 32
    ):
        """
        从题目列表构建索引
        
        Args:
            problems: 题目列表，每个包含uid和stem字段
            batch_size: 批处理大小
        """
        print(f"开始构建索引，共 {len(problems)} 道题目...")
        
        # 提取文本
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
        print(f"保存索引到 {self.index_dir}...")
        self.vector_store.save(self.index_dir)
        
        print(f"索引构建完成: {self.vector_store.get_stats()}")
    
    def get_document(self, uid: str) -> Optional[Dict]:
        """根据ID获取文档元数据"""
        return self.vector_store.metadata.get(uid)
    
    def get_stats(self) -> Dict:
        """获取索引统计信息"""
        return self.vector_store.get_stats()