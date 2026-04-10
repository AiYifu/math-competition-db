"""
检索服务FastAPI入口
"""
import os
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .embeddings import SiliconFlowEmbeddings, get_embeddings_service
from .vector_store import FAISSVectorStore, get_vector_store, set_vector_store
from .searcher import Searcher, SearchResult, get_searcher


# ==================== Pydantic模型 ====================

class IndexRequest(BaseModel):
    """索引请求"""
    texts: List[str] = Field(..., description="文档文本列表", min_items=1)
    metadatas: Optional[List[Dict[str, Any]]] = Field(None, description="元数据列表")
    ids: Optional[List[str]] = Field(None, description="文档ID列表")


class IndexResponse(BaseModel):
    """索引响应"""
    doc_ids: List[str] = Field(..., description="文档ID列表")
    message: str = Field(..., description="状态消息")


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(..., description="查询文本", min_length=1)
    top_k: int = Field(5, description="返回结果数量", ge=1, le=50)
    filter_dict: Optional[Dict[str, Any]] = Field(None, description="过滤条件")
    min_score: Optional[float] = Field(None, description="最小相似度分数", ge=0, le=1)


class SearchResultItem(BaseModel):
    """搜索结果项"""
    doc_id: str = Field(..., description="文档ID")
    score: float = Field(..., description="相似度分数")
    text: str = Field(..., description="文档文本")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class SearchResponse(BaseModel):
    """搜索响应"""
    results: List[SearchResultItem] = Field(..., description="搜索结果列表")
    total: int = Field(..., description="结果总数")
    query: str = Field(..., description="查询文本")


class DocumentResponse(BaseModel):
    """文档响应"""
    doc_id: str = Field(..., description="文档ID")
    text: str = Field(..., description="文档文本")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class StatsResponse(BaseModel):
    """统计响应"""
    total_documents: int = Field(..., description="总文档数")
    indexed_vectors: int = Field(..., description="索引向量数")
    dimension: int = Field(..., description="向量维度")
    index_type: str = Field(..., description="索引类型")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    version: str = Field("0.1.0", description="版本号")


# ==================== 生命周期管理 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    storage_path = os.getenv("VECTOR_STORE_PATH", "./data/vector_store")
    
    # 创建向量存储
    vector_store = FAISSVectorStore(
        dimension=1024,  # bge-m3维度
        storage_path=storage_path
    )
    
    # 尝试加载已有索引
    if os.path.exists(storage_path):
        try:
            loaded = await vector_store.load(storage_path)
            if loaded:
                print(f"已加载向量存储: {storage_path}")
            else:
                print(f"未找到现有向量存储，创建新的")
        except Exception as e:
            print(f"加载向量存储失败: {e}")
    
    set_vector_store(vector_store)
    
    yield
    
    # 关闭时保存
    try:
        await vector_store.save(storage_path)
        print(f"向量存储已保存: {storage_path}")
    except Exception as e:
        print(f"保存向量存储失败: {e}")


# ==================== FastAPI应用 ====================

app = FastAPI(
    title="检索服务",
    description="基于硅基流动API和FAISS的语义检索服务",
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


# ==================== API路由 ====================

@app.get("/", response_model=HealthResponse)
async def root():
    """根路径"""
    return HealthResponse(status="healthy")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return HealthResponse(status="healthy")


@app.post("/index", response_model=IndexResponse)
async def index_documents(
    request: IndexRequest,
    searcher: Searcher = Depends(get_searcher)
):
    """
    索引文档
    
    将文档添加到向量索引中
    """
    try:
        doc_ids = await searcher.index_documents(
            texts=request.texts,
            metadatas=request.metadatas,
            ids=request.ids
        )
        return IndexResponse(
            doc_ids=doc_ids,
            message=f"成功索引 {len(doc_ids)} 个文档"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    searcher: Searcher = Depends(get_searcher)
):
    """
    搜索文档
    
    基于语义相似度检索相关文档
    """
    try:
        results = await searcher.search(
            query=request.query,
            top_k=request.top_k,
            filter_dict=request.filter_dict,
            min_score=request.min_score
        )
        
        return SearchResponse(
            results=[
                SearchResultItem(
                    doc_id=r.doc_id,
                    score=r.score,
                    text=r.text,
                    metadata=r.metadata
                )
                for r in results
            ],
            total=len(results),
            query=request.query
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: str,
    searcher: Searcher = Depends(get_searcher)
):
    """
    获取文档
    
    根据文档ID获取文档内容
    """
    doc = await searcher.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"文档不存在: {doc_id}")
    
    return DocumentResponse(
        doc_id=doc["id"],
        text=doc["text"],
        metadata=doc.get("metadata", {})
    )


@app.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    searcher: Searcher = Depends(get_searcher)
):
    """
    删除文档
    
    从索引中删除文档（软删除）
    """
    success = await searcher.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"文档不存在: {doc_id}")
    
    return {"message": f"文档已删除: {doc_id}"}


@app.get("/stats", response_model=StatsResponse)
async def get_stats(
    searcher: Searcher = Depends(get_searcher)
):
    """
    获取统计信息
    
    获取索引的统计信息
    """
    stats = await searcher.get_stats()
    return StatsResponse(**stats)


# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(app, host=host, port=port)
