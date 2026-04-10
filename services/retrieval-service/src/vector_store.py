"""
FAISS向量存储封装
"""
import os
import pickle
import numpy as np
import faiss
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor


class FAISSVectorStore:
    """FAISS向量存储"""
    
    def __init__(
        self,
        dimension: int = 1024,  # bge-m3的维度
        index_type: str = "IndexFlatIP",  # 内积相似度，适用于归一化向量
        storage_path: Optional[str] = None
    ):
        self.dimension = dimension
        self.index_type = index_type
        self.storage_path = storage_path
        
        # 创建FAISS索引
        self.index = self._create_index()
        
        # 存储文档数据
        self.documents: Dict[str, Dict] = {}
        self.id_to_index: Dict[str, int] = {}
        self.index_to_id: Dict[int, str] = {}
        self.next_index = 0
        
        # 线程池用于同步操作
        self._executor = ThreadPoolExecutor(max_workers=4)
    
    def _create_index(self) -> faiss.Index:
        """创建FAISS索引"""
        if self.index_type == "IndexFlatIP":
            # 内积（余弦相似度，向量需归一化）
            return faiss.IndexFlatIP(self.dimension)
        elif self.index_type == "IndexFlatL2":
            # L2距离
            return faiss.IndexFlatL2(self.dimension)
        else:
            raise ValueError(f"不支持的索引类型: {self.index_type}")
    
    async def add_documents(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[str]:
        """
        添加文档到向量存储
        
        Args:
            documents: 文档列表，每个文档包含id、embedding、text、metadata
            
        Returns:
            文档ID列表
        """
        if not documents:
            return []
        
        # 提取嵌入向量
        embeddings = []
        doc_ids = []
        
        for doc in documents:
            doc_id = doc.get("id", f"doc_{self.next_index}")
            embedding = doc["embedding"]
            
            embeddings.append(embedding)
            doc_ids.append(doc_id)
            
            # 存储文档数据
            self.documents[doc_id] = {
                "id": doc_id,
                "text": doc.get("text", ""),
                "metadata": doc.get("metadata", {})
            }
            
            # 更新ID映射
            self.id_to_index[doc_id] = self.next_index
            self.index_to_id[self.next_index] = doc_id
            self.next_index += 1
        
        # 转换为numpy数组并归一化（用于内积相似度）
        embeddings_np = np.array(embeddings, dtype=np.float32)
        faiss.normalize_L2(embeddings_np)
        
        # 在线程池中执行FAISS操作（FAISS不是线程安全的）
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self._executor,
            self.index.add,
            embeddings_np
        )
        
        return doc_ids
    
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_dict: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索相似文档
        
        Args:
            query_embedding: 查询向量
            top_k: 返回结果数量
            filter_dict: 过滤条件
            
        Returns:
            相似文档列表，包含score、document
        """
        if self.index.ntotal == 0:
            return []
        
        # 归一化查询向量
        query_np = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query_np)
        
        # 执行搜索
        loop = asyncio.get_event_loop()
        distances, indices = await loop.run_in_executor(
            self._executor,
            lambda: self.index.search(query_np, top_k)
        )
        
        results = []
        for score, idx in zip(distances[0], indices[0]):
            if idx == -1:  # FAISS返回-1表示没有更多结果
                continue
                
            doc_id = self.index_to_id.get(int(idx))
            if not doc_id:
                continue
                
            doc = self.documents.get(doc_id)
            if not doc:
                continue
            
            # 应用过滤条件
            if filter_dict:
                metadata = doc.get("metadata", {})
                if not all(metadata.get(k) == v for k, v in filter_dict.items()):
                    continue
            
            results.append({
                "score": float(score),
                "document": doc
            })
        
        return results
    
    async def delete_document(self, doc_id: str) -> bool:
        """
        删除文档（注：FAISS不支持直接删除，需要重建索引）
        
        Args:
            doc_id: 文档ID
            
        Returns:
            是否成功
        """
        if doc_id not in self.documents:
            return False
        
        # 标记为已删除（软删除）
        self.documents[doc_id]["_deleted"] = True
        return True
    
    async def get_document(self, doc_id: str) -> Optional[Dict]:
        """
        获取文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            文档数据或None
        """
        return self.documents.get(doc_id)
    
    async def get_all_documents(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        获取所有文档
        
        Args:
            limit: 数量限制
            offset: 偏移量
            
        Returns:
            文档列表
        """
        docs = list(self.documents.values())
        return docs[offset:offset + limit]
    
    async def save(self, path: Optional[str] = None) -> str:
        """
        保存索引到磁盘
        
        Args:
            path: 保存路径
            
        Returns:
            保存路径
        """
        save_path = path or self.storage_path
        if not save_path:
            raise ValueError("未指定存储路径")
        
        save_path = Path(save_path)
        save_path.mkdir(parents=True, exist_ok=True)
        
        # 保存FAISS索引
        index_file = save_path / "faiss.index"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self._executor,
            faiss.write_index,
            self.index,
            str(index_file)
        )
        
        # 保存文档数据
        data_file = save_path / "documents.pkl"
        data = {
            "documents": self.documents,
            "id_to_index": self.id_to_index,
            "index_to_id": self.index_to_id,
            "next_index": self.next_index,
            "dimension": self.dimension,
            "index_type": self.index_type
        }
        await loop.run_in_executor(
            self._executor,
            lambda: pickle.dump(data, open(data_file, "wb"))
        )
        
        return str(save_path)
    
    async def load(self, path: str) -> bool:
        """
        从磁盘加载索引
        
        Args:
            path: 加载路径
            
        Returns:
            是否成功
        """
        load_path = Path(path)
        index_file = load_path / "faiss.index"
        data_file = load_path / "documents.pkl"
        
        if not index_file.exists() or not data_file.exists():
            return False
        
        loop = asyncio.get_event_loop()
        
        # 加载FAISS索引
        self.index = await loop.run_in_executor(
            self._executor,
            faiss.read_index,
            str(index_file)
        )
        
        # 加载文档数据
        data = await loop.run_in_executor(
            self._executor,
            lambda: pickle.load(open(data_file, "rb"))
        )
        
        self.documents = data["documents"]
        self.id_to_index = data["id_to_index"]
        self.index_to_id = data["index_to_id"]
        self.next_index = data["next_index"]
        self.dimension = data["dimension"]
        self.index_type = data["index_type"]
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        return {
            "total_documents": len(self.documents),
            "indexed_vectors": self.index.ntotal,
            "dimension": self.dimension,
            "index_type": self.index_type
        }


# 全局向量存储实例
_vector_store: Optional[FAISSVectorStore] = None


async def get_vector_store() -> FAISSVectorStore:
    """获取向量存储实例"""
    global _vector_store
    if _vector_store is None:
        _vector_store = FAISSVectorStore()
    return _vector_store


def set_vector_store(store: FAISSVectorStore):
    """设置向量存储实例"""
    global _vector_store
    _vector_store = store
