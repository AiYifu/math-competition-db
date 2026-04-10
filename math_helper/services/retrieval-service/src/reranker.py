"""
Cross Encoder重排序模块
使用硅基流动API调用BAAI/bge-reranker模型
"""
import os
import aiohttp
from typing import List, Dict, Tuple, Optional, Union
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class RerankResult:
    """重排序结果"""
    index: int              # 原始候选列表中的索引
    text: str               # 候选文本
    score: float            # 重排序分数 (0-1)
    metadata: Optional[Dict] = None  # 原始元数据


class CrossEncoderReranker:
    """
    基于硅基流动API的Cross Encoder重排序器
    使用BAAI/bge-reranker-v2-m3模型
    """
    
    def __init__(
        self,
        api_key: str = None,
        base_url: str = "https://api.siliconflow.cn/v1",
        model: str = "BAAI/bge-reranker-v2-m3",
        batch_size: int = 32
    ):
        """
        初始化重排序器
        
        Args:
            api_key: 硅基流动API密钥
            base_url: API基础URL
            model: 重排序模型名称
            batch_size: 批量处理大小
        """
        self.api_key = api_key or os.getenv("SILICONFLOW_API_KEY")
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.batch_size = batch_size
        self.rerank_url = f"{self.base_url}/rerank"
    
    async def _call_rerank_api(
        self,
        query: str,
        documents: List[str],
        top_n: Optional[int] = None
    ) -> List[Dict]:
        """
        调用硅基流动rerank API
        
        Args:
            query: 查询文本
            documents: 候选文档列表
            top_n: 返回前n个结果，默认返回全部
            
        Returns:
            API返回的结果列表
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "return_documents": False  # 我们只需要索引和分数
        }
        
        if top_n is not None:
            payload["top_n"] = top_n
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.rerank_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(
                        f"Rerank API请求失败: {response.status}, {error_text}"
                    )
                
                result = await response.json()
                return result.get("results", [])
    
    async def rerank(
        self,
        query: str,
        candidates: List[str],
        top_k: Optional[int] = None
    ) -> List[RerankResult]:
        """
        对候选列表进行重排序
        
        Args:
            query: 查询文本
            candidates: 候选文本列表
            top_k: 返回前k个结果，默认返回全部
            
        Returns:
            按分数降序排列的重排序结果列表
        """
        if not candidates:
            return []
        
        # 处理空查询
        if not query or not query.strip():
            return [
                RerankResult(index=i, text=text, score=0.0)
                for i, text in enumerate(candidates)
            ]
        
        # 批量处理（如果候选数量超过batch_size）
        all_results = []
        
        for batch_start in range(0, len(candidates), self.batch_size):
            batch_end = min(batch_start + self.batch_size, len(candidates))
            batch = candidates[batch_start:batch_end]
            
            # 调用API
            api_results = await self._call_rerank_api(
                query=query,
                documents=batch,
                top_n=None  # 返回全部结果
            )
            
            # 调整索引（考虑批量偏移）
            for item in api_results:
                original_index = batch_start + item["index"]
                all_results.append({
                    "index": original_index,
                    "text": candidates[original_index],
                    "score": item["relevance_score"]
                })
        
        # 按分数降序排序
        all_results.sort(key=lambda x: x["score"], reverse=True)
        
        # 转换为RerankResult对象
        results = [
            RerankResult(
                index=r["index"],
                text=r["text"],
                score=r["score"]
            )
            for r in all_results
        ]
        
        # 限制返回数量
        if top_k is not None and top_k > 0:
            results = results[:top_k]
        
        return results
    
    async def rerank_with_metadata(
        self,
        query: str,
        candidates: List[str],
        metadatas: Optional[List[Dict]] = None,
        top_k: Optional[int] = None
    ) -> List[RerankResult]:
        """
        对候选列表进行重排序（带元数据）
        
        Args:
            query: 查询文本
            candidates: 候选文本列表
            metadatas: 候选文本的元数据列表
            top_k: 返回前k个结果
            
        Returns:
            按分数降序排列的重排序结果列表
        """
        results = await self.rerank(query, candidates, top_k)
        
        # 添加元数据
        if metadatas:
            for result in results:
                if result.index < len(metadatas):
                    result.metadata = metadatas[result.index]
        
        return results
    
    async def batch_rerank(
        self,
        queries: List[str],
        candidates_list: List[List[str]],
        top_k: Optional[int] = None
    ) -> List[List[RerankResult]]:
        """
        批量重排序（多个查询）
        
        Args:
            queries: 查询文本列表
            candidates_list: 每个查询对应的候选列表
            top_k: 每个查询返回前k个结果
            
        Returns:
            每个查询的重排序结果列表
        """
        if len(queries) != len(candidates_list):
            raise ValueError("queries和candidates_list长度必须相同")
        
        results = []
        for query, candidates in zip(queries, candidates_list):
            result = await self.rerank(query, candidates, top_k)
            results.append(result)
        
        return results
    
    def compute_scores(
        self,
        query: str,
        candidates: List[str]
    ) -> List[float]:
        """
        计算重排序分数（同步版本，用于简单场景）
        
        Args:
            query: 查询文本
            candidates: 候选文本列表
            
        Returns:
            分数列表（与candidates顺序一致）
        """
        import asyncio
        
        async def _async_compute():
            results = await self.rerank(query, candidates)
            # 创建索引到分数的映射
            score_map = {r.index: r.score for r in results}
            # 按原始顺序返回分数
            return [score_map.get(i, 0.0) for i in range(len(candidates))]
        
        return asyncio.run(_async_compute())


@lru_cache()
def get_reranker() -> CrossEncoderReranker:
    """获取重排序器单例"""
    return CrossEncoderReranker()


# 便捷函数
async def rerank_documents(
    query: str,
    documents: List[str],
    top_k: Optional[int] = None,
    **kwargs
) -> List[RerankResult]:
    """
    便捷函数：重排序文档
    
    Args:
        query: 查询文本
        documents: 文档列表
        top_k: 返回前k个结果
        **kwargs: 传递给CrossEncoderReranker的参数
        
    Returns:
        重排序结果列表
    """
    reranker = CrossEncoderReranker(**kwargs)
    return await reranker.rerank(query, documents, top_k)
