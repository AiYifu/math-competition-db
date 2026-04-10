"""检索服务FastAPI主入口"""
import os
from pathlib import Path
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .searcher import HybridSearcher
from .embeddings import SiliconFlowEmbeddings

# 全局检索器实例
searcher: Optional[HybridSearcher] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global searcher
    
    # 启动时初始化
    api_key = os.getenv("SILICONFLOW_API_KEY")
    if not api_key:
        print("警告: 未设置 SILICONFLOW_API_KEY 环境变量")
        api_key = "sk-mtxecjqwsqzpcagnafsqggltrokycncdktosawdxdezidgkr"
    
    index_dir = Path(os.getenv("INDEX_DIR", "./data/indices/faiss"))
    searcher = HybridSearcher(api_key=api_key, index_dir=index_dir)
    
    print(f"检索服务启动完成: {searcher.get_stats()}")
    
    yield
    
    # 关闭时清理
    print("检索服务关闭")

app = FastAPI(
    title="数学竞赛题目检索服务",
    description="基于向量相似度的数学题目检索API",
    version="0.1.0",
    lifespan=lifespan
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据模型
class SearchRequest(BaseModel):
    query: str = Field(..., description="查询文本(LaTeX格式)", min_length=1)
    top_k: int = Field(5, ge=1, le=20, description="返回结果数量")
    use_rerank: bool = Field(True, description="是否使用重排序")

class SearchResultItem(BaseModel):
    uid: str
    score: float
    match_type: str
    metadata: Optional[dict] = None

class SearchResponse(BaseModel):
    results: List[SearchResultItem]
    exact_match: bool
    query_time_ms: float
    total_indexed: int

class IndexBuildRequest(BaseModel):
    problems: List[dict] = Field(..., description="题目列表")
    batch_size: int = Field(32, ge=1, le=64)

class StatsResponse(BaseModel):
    total_vectors: int
    dimension: int
    unique_ids: int

# API路由
@app.get("/")
async def root():
    return {
        "message": "数学竞赛题目检索服务",
        "docs": "/docs",
        "version": "0.1.0"
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "searcher_ready": searcher is not None and searcher.get_stats()["total_vectors"] > 0
    }

@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """获取索引统计信息"""
    if searcher is None:
        raise HTTPException(status_code=503, detail="检索器未初始化")
    
    stats = searcher.get_stats()
    return StatsResponse(**stats)

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    搜索相似题目
    
    基于向量相似度检索最相关的数学题目
    """
    if searcher is None:
        raise HTTPException(status_code=503, detail="检索器未初始化")
    
    result = await searcher.search(
        query=request.query,
        top_k=request.top_k
    )
    
    # 获取完整元数据
    results_with_meta = []
    for item in result["results"]:
        doc = searcher.get_document(item["uid"])
        results_with_meta.append(SearchResultItem(
            uid=item["uid"],
            score=item["score"],
            match_type=item["match_type"],
            metadata=doc.get("metadata", {}) if doc else None
        ))
    
    return SearchResponse(
        results=results_with_meta,
        exact_match=result["exact_match"],
        query_time_ms=result["query_time_ms"],
        total_indexed=searcher.get_stats()["total_vectors"]
    )

@app.get("/search")
async def search_get(
    q: str = Query(..., description="查询文本"),
    top_k: int = Query(5, ge=1, le=20)
):
    """GET方式搜索（方便浏览器测试）"""
    return await search(SearchRequest(query=q, top_k=top_k))

@app.post("/index")
async def build_index(request: IndexBuildRequest):
    """
    构建索引
    
    从题目列表构建向量索引
    """
    if searcher is None:
        raise HTTPException(status_code=503, detail="检索器未初始化")
    
    try:
        await searcher.build_index(
            problems=request.problems,
            batch_size=request.batch_size
        )
        
        return {
            "success": True,
            "message": f"索引构建完成，共 {len(request.problems)} 道题目",
            "stats": searcher.get_stats()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"索引构建失败: {str(e)}")

@app.get("/document/{uid}")
async def get_document(uid: str):
    """根据ID获取文档详情"""
    if searcher is None:
        raise HTTPException(status_code=503, detail="检索器未初始化")
    
    doc = searcher.get_document(uid)
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    return doc

@app.delete("/index")
async def clear_index():
    """清空索引（谨慎使用）"""
    if searcher is None:
        raise HTTPException(status_code=503, detail="检索器未初始化")
    
    # 重新创建空索引
    searcher.vector_store = searcher.vector_store.__class__(dim=1024)
    searcher.vector_store.create_index()
    searcher.vector_store.save(searcher.index_dir)
    
    return {
        "success": True,
        "message": "索引已清空",
        "stats": searcher.get_stats()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)