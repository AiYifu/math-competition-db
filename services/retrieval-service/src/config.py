"""
检索服务配置
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    
    # 服务配置
    APP_NAME: str = "检索服务"
    APP_VERSION: str = "0.1.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # 硅基流动API配置
    SILICONFLOW_API_KEY: str = "sk-mtxecjqwsqzpcagnafsqggltrokycncdktosawdxdezidgkr"
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_BATCH_SIZE: int = 8
    
    # 向量存储配置
    VECTOR_STORE_PATH: str = "./data/vector_store"
    VECTOR_DIMENSION: int = 1024  # bge-m3维度
    INDEX_TYPE: str = "IndexFlatIP"
    
    # 检索配置
    DEFAULT_TOP_K: int = 5
    MAX_TOP_K: int = 50
    DEFAULT_MIN_SCORE: float = 0.0
    
    class Config:
        env_file = ".env"


# 全局配置实例
settings = Settings()
