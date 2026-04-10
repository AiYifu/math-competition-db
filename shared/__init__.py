"""共享组件

包含所有服务共享的数据模型、工具和配置。
"""

from .models import Problem, SearchRequest, SearchResponse, SearchResult

__all__ = ["Problem", "SearchRequest", "SearchResponse", "SearchResult"]