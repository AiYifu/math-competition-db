"""FAISS向量存储封装"""
import faiss
import numpy as np
import pickle
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import json

class VectorStore:
    """基于FAISS的向量存储"""
    
    def __init__(self, dim: int = 1024):
        self.dim = dim
        self.index = None
        self.metadata = {}  # id -> metadata
        self.id_to_idx = {}  # uid -> faiss index
        self.idx_to_id = {}  # faiss index -> uid
        self._next_idx = 0
    
    def create_index(self):
        """创建新的FAISS索引（内积 = 余弦相似度，前提是向量已归一化）"""
        self.index = faiss.IndexFlatIP(self.dim)
    
    def add(
        self,
        embeddings: List[List[float]],
        ids: List[str],
        metadata: List[Dict] = None
    ):
        """
        添加向量到索引
        
        Args:
            embeddings: 向量列表
            ids: 对应的ID列表
            metadata: 对应的元数据列表
        """
        if self.index is None:
            self.create_index()
        
        # 转换为numpy数组并归一化
        vectors = np.array(embeddings, dtype=np.float32)
        faiss.normalize_L2(vectors)  # L2归一化，使内积=余弦相似度
        
        # 添加到FAISS
        self.index.add(vectors)
        
        # 保存元数据映射
        for i, uid in enumerate(ids):
            idx = self._next_idx + i
            self.id_to_idx[uid] = idx
            self.idx_to_id[idx] = uid
            if metadata:
                self.metadata[uid] = metadata[i]
        
        self._next_idx += len(ids)
    
    def search(
        self,
        query_embedding: List[float],
        k: int = 10
    ) -> Tuple[List[str], List[float]]:
        """
        搜索最相似的向量
        
        Returns:
            (id列表, 相似度分数列表)
        """
        if self.index is None or self.index.ntotal == 0:
            return [], []
        
        # 归一化查询向量
        query = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query)
        
        # 搜索
        scores, indices = self.index.search(query, k)
        
        # 转换为ID
        results = []
        result_scores = []
        for idx, score in zip(indices[0], scores[0]):
            if idx != -1 and idx in self.idx_to_id:
                results.append(self.idx_to_id[idx])
                result_scores.append(float(score))
        
        return results, result_scores
    
    def batch_search(
        self,
        query_embeddings: List[List[float]],
        k: int = 10
    ) -> List[Tuple[List[str], List[float]]]:
        """批量搜索"""
        if self.index is None or self.index.ntotal == 0:
            return [([], []) for _ in query_embeddings]
        
        queries = np.array(query_embeddings, dtype=np.float32)
        faiss.normalize_L2(queries)
        
        scores, indices = self.index.search(queries, k)
        
        results = []
        for query_indices, query_scores in zip(indices, scores):
            ids = []
            sim_scores = []
            for idx, score in zip(query_indices, query_scores):
                if idx != -1 and idx in self.idx_to_id:
                    ids.append(self.idx_to_id[idx])
                    sim_scores.append(float(score))
            results.append((ids, sim_scores))
        
        return results
    
    def save(self, directory: Path):
        """保存索引和元数据"""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        
        # 保存FAISS索引
        if self.index is not None:
            faiss.write_index(self.index, str(directory / "index.faiss"))
        
        # 保存元数据
        with open(directory / "metadata.pkl", "wb") as f:
            pickle.dump({
                "metadata": self.metadata,
                "id_to_idx": self.id_to_idx,
                "idx_to_id": self.idx_to_id,
                "next_idx": self._next_idx,
                "dim": self.dim
            }, f)
    
    def load(self, directory: Path):
        """加载索引和元数据"""
        directory = Path(directory)
        
        # 加载FAISS索引
        index_path = directory / "index.faiss"
        if index_path.exists():
            self.index = faiss.read_index(str(index_path))
        
        # 加载元数据
        metadata_path = directory / "metadata.pkl"
        if metadata_path.exists():
            with open(metadata_path, "rb") as f:
                data = pickle.load(f)
                self.metadata = data["metadata"]
                self.id_to_idx = data["id_to_idx"]
                self.idx_to_id = data["idx_to_id"]
                self._next_idx = data["next_idx"]
                self.dim = data.get("dim", self.dim)
    
    def get_stats(self) -> Dict:
        """获取索引统计信息"""
        return {
            "total_vectors": self.index.ntotal if self.index else 0,
            "dimension": self.dim,
            "unique_ids": len(self.id_to_idx)
        }