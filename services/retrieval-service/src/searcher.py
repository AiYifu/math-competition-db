"""
检索Orchestrator
整合嵌入服务和向量存储，提供统一的检索接口
"""
from typing import List, Dict, Optional, Any, AsyncIterator
import asyncio

from .embeddings import SiliconFlowEmbeddings, get_embeddings_service
from .vector_store import FAISSVectorStore, get_vector_store


class SearchResult:
    """搜索结果"""
    
    def __init__(
        self,
        score: float,
        text: str,
        metadata: Dict[str, Any],
        doc_id: str
    ):
        self.score = score
        self.text = text
        self.metadata = metadata
        self.doc_id = doc_id
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "text": self.text,
            "metadata": self.metadata,
            "doc_id": self.doc_id
        }


class Searcher:
    """检索Orchestrator"""
    
    def __init__(
        self,
        embeddings_service: Optional[SiliconFlowEmbeddings] = None,
        vector_store: Optional[FAISSVectorStore] = None
    ):
        self.embeddings = embeddings_service or get_embeddings_service()
        self.vector_store = vector_store
    
    async def _get_vector_store(self) -> FAISSVectorStore:
        """获取向量存储"""
        if self.vector_store is None:
            self.vector_store = await get_vector_store()
        return self.vector_store
    
    async def index_documents(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        索引文档
        
        Args:
            texts: 文档文本列表
            metadatas: 元数据列表
            ids: 文档ID列表
            
        Returns:
            文档ID列表
        """
        if not texts:
            return []
        
        # 生成嵌入
        embeddings_with_metadata = await self.embeddings.embed_documents_with_metadata(
            texts, metadatas
        )
        
        # 使用自定义ID
        if ids:
            for doc, doc_id in zip(embeddings_with_metadata, ids):
                doc["id"] = doc_id
        
        # 添加到向量存储
        store = await self._get_vector_store()
        doc_ids = await store.add_documents(embeddings_with_metadata)
        
        return doc_ids
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        filter_dict: Optional[Dict] = None,
        min_score: Optional[float] = None
    ) -> List[SearchResult]:
        """
        检索文档
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter_dict: 过滤条件
            min_score: 最小相似度分数
            
        Returns:
            搜索结果列表
        """
        # 生成查询嵌入
        query_embedding = await self.embeddings.embed_query(query)
        
        # 搜索向量存储
        store = await self._get_vector_store()
        results = await store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_dict=filter_dict
        )
        
        # 转换为SearchResult
        search_results = []
        for result in results:
            score = result["score"]
            
            # 过滤低分结果
            if min_score is not None and score < min_score:
                continue
            
            doc = result["document"]
            search_results.append(SearchResult(
                score=score,
                text=doc["text"],
                metadata=doc.get("metadata", {}),
                doc_id=doc["id"]
            ))
        
        return search_results
    
    async def batch_search(
        self,
        queries: List[str],
        top_k: int = 5,
        filter_dict: Optional[Dict] = None
    ) -> List[List[SearchResult]]:
        """
        批量检索
        
        Args:
            queries: 查询文本列表
            top_k: 返回结果数量
            filter_dict: 过滤条件
            
        Returns:
            搜索结果列表的列表
        """
        tasks = [
            self.search(query, top_k, filter_dict)
            for query in queries
        ]
        return await asyncio.gather(*tasks)
    
    async def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        keyword_weight: float = 0.3,
        semantic_weight: float = 0.7
    ) -> List[SearchResult]:
        """
        混合检索（语义+关键词）
        注：基础框架，后续可扩展实现
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            keyword_weight: 关键词检索权重
            semantic_weight: 语义检索权重
            
        Returns:
            搜索结果列表
        """
        # 目前仅实现语义检索
        # TODO: 后续添加关键词检索和重排序
        return await self.search(query, top_k)
    
    async def get_document(self, doc_id: str) -> Optional[Dict]:
        """
        获取文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            文档数据
        """
        store = await self._get_vector_store()
        return await store.get_document(doc_id)
    
    async def delete_document(self, doc_id: str) -> bool:
        """
        删除文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            是否成功
        """
        store = await self._get_vector_store()
        return await store.delete_document(doc_id)
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取检索统计信息"""
        store = await self._get_vector_store()
        return store.get_stats()


# 全局Searcher实例
_searcher: Optional[Searcher] = None


async def get_searcher() -> Searcher:
    """获取Searcher实例"""
    global _searcher
    if _searcher is None:
        _searcher = Searcher()
    return _searcher
