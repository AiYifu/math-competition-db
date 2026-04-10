from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Literal
from datetime import datetime

class Problem(BaseModel):
    """
    统一题目模型 - 兼容所有来源（Books/AoPS/Datasets）
    """
    # 核心标识
    uid: str = Field(..., description="全局唯一ID")
    source: Literal["books", "aops", "aops_hf", "olympiadbench"]
    source_id: str
    
    # 题目内容
    stem: str = Field(..., description="题干（LaTeX格式）")
    stem_text: Optional[str] = None
    solution: Optional[str] = None
    answer: Optional[str] = None
    
    # 元数据
    metadata: Dict = Field(default_factory=dict)
    
    # 去重相关
    fingerprint_exact: Optional[str] = None
    fingerprint_structural: Optional[str] = None
    is_duplicate: bool = False
    canonical_id: Optional[str] = None
    
    # 索引相关
    indexed_at: Optional[datetime] = None
    
    class Config:
        extra = "allow"

class SearchRequest(BaseModel):
    query_image: Optional[bytes] = None
    query_text: Optional[str] = None
    top_k: int = 5
    use_rerank: bool = True

class SearchResult(BaseModel):
    problem: Problem
    scores: Dict[str, float]
    matched_fields: List[str]

class SearchResponse(BaseModel):
    results: List[SearchResult]
    exact_match: bool
    query_time_ms: float