"""硅基流动API封装 - Embedding服务"""
import aiohttp
import asyncio
from typing import List, Optional
import numpy as np

class SiliconFlowEmbeddings:
    """硅基流动Embedding客户端"""
    
    def __init__(
        self,
        api_key: str,
        model: str = "BAAI/bge-m3",
        base_url: str = "https://api.siliconflow.cn/v1"
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.embedding_dim = 1024  # bge-m3的维度
    
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """
        批量获取文本的embedding
        
        Args:
            texts: 文本列表
            
        Returns:
            embedding列表
        """
        if not texts:
            return []
        
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
                f"{self.base_url}/embeddings",
                headers=headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"API调用失败: {response.status}, {error_text}")
                
                data = await response.json()
                
                # 按index排序，确保顺序一致
                embeddings = sorted(
                    data["data"],
                    key=lambda x: x["index"]
                )
                
                return [item["embedding"] for item in embeddings]
    
    async def embed_single(self, text: str) -> List[float]:
        """单条文本embedding"""
        results = await self.embed([text])
        return results[0] if results else []
    
    async def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = True
    ) -> List[List[float]]:
        """
        大批量embedding，自动分批处理
        
        Args:
            texts: 文本列表
            batch_size: 每批大小
            show_progress: 是否显示进度
            
        Returns:
            所有embedding
        """
        all_embeddings = []
        total = len(texts)
        
        for i in range(0, total, batch_size):
            batch = texts[i:i + batch_size]
            embeddings = await self.embed(batch)
            all_embeddings.extend(embeddings)
            
            if show_progress:
                print(f"进度: {min(i + batch_size, total)}/{total}")
            
            # 避免速率限制，小延迟
            await asyncio.sleep(0.1)
        
        return all_embeddings


# 简单的同步包装（用于脚本）
def get_embeddings_sync(
    texts: List[str],
    api_key: str,
    batch_size: int = 32
) -> List[List[float]]:
    """同步方式获取embeddings（用于脚本）"""
    embedder = SiliconFlowEmbeddings(api_key=api_key)
    return asyncio.run(embedder.embed_batch(texts, batch_size=batch_size))