"""
硅基流动API嵌入服务封装
使用BAAI/bge-m3模型
"""
import os
import aiohttp
import numpy as np
from typing import List, Union
from functools import lru_cache


class SiliconFlowEmbeddings:
    """硅基流动API嵌入服务"""
    
    def __init__(
        self,
        api_key: str = None,
        base_url: str = "https://api.siliconflow.cn/v1",
        model: str = "BAAI/bge-m3",
        batch_size: int = 8
    ):
        self.api_key = api_key or os.getenv("SILICONFLOW_API_KEY")
        self.base_url = base_url
        self.model = model
        self.batch_size = batch_size
        self.embedding_url = f"{self.base_url}/embeddings"
    
    async def _get_embedding(self, texts: List[str]) -> List[List[float]]:
        """调用API获取嵌入向量"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.embedding_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"API请求失败: {response.status}, {error_text}")
                
                result = await response.json()
                embeddings = [item["embedding"] for item in result["data"]]
                return embeddings
    
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        嵌入文档列表
        
        Args:
            texts: 文档文本列表
            
        Returns:
            嵌入向量列表
        """
        if not texts:
            return []
        
        all_embeddings = []
        
        # 分批处理
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            embeddings = await self._get_embedding(batch)
            all_embeddings.extend(embeddings)
        
        return all_embeddings
    
    async def embed_query(self, text: str) -> List[float]:
        """
        嵌入查询文本
        
        Args:
            text: 查询文本
            
        Returns:
            嵌入向量
        """
        embeddings = await self._get_embedding([text])
        return embeddings[0]
    
    async def embed_documents_with_metadata(
        self,
        texts: List[str],
        metadatas: List[dict] = None
    ) -> List[dict]:
        """
        嵌入文档并返回带元数据的结果
        
        Args:
            texts: 文档文本列表
            metadatas: 元数据列表
            
        Returns:
            包含id、embedding、metadata和text的字典列表
        """
        embeddings = await self.embed_documents(texts)
        
        results = []
        for i, (text, embedding) in enumerate(zip(texts, embeddings)):
            result = {
                "id": f"doc_{i}",
                "embedding": embedding,
                "text": text,
                "metadata": metadatas[i] if metadatas and i < len(metadatas) else {}
            }
            results.append(result)
        
        return results


@lru_cache()
def get_embeddings_service() -> SiliconFlowEmbeddings:
    """获取嵌入服务单例"""
    return SiliconFlowEmbeddings()
