from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime
import hashlib
import json


@dataclass
class Problem:
    """
    统一数学竞赛题目模型
    
    支持从多种数据源(AoPS, Books, HuggingFace)转换而来
    """
    # 必需字段
    uid: str  # 唯一标识符
    content: str  # 题目内容 (LaTeX/Markdown格式)
    
    # 来源信息
    source: str  # 数据来源: aops, books, aops_hf, olympiadbench
    source_url: Optional[str] = None  # 原始链接
    
    # 竞赛信息
    contest: Optional[str] = None  # 竞赛名称: IMO, CMO, etc.
    year: Optional[int] = None  # 年份
    problem_num: Optional[int] = None  # 题目编号
    
    # 内容字段
    solution: Optional[str] = None  # 解答
    answer: Optional[str] = None  # 答案
    hints: Optional[str] = None  # 提示
    
    # 分类标签
    tags: List[str] = field(default_factory=list)  # 标签列表
    difficulty: Optional[str] = None  # 难度等级
    
    # 书籍特有字段
    book_title: Optional[str] = None  # 书名
    chapter: Optional[str] = None  # 章节
    section: Optional[str] = None  # 小节
    
    # 元数据
    confidence: str = "high"  # 数据质量: high, medium, low
    is_incomplete: bool = False  # 是否不完整
    language: str = "zh"  # 语言: zh, en
    
    # 扩展字段
    metadata: Dict[str, Any] = field(default_factory=dict)  # 其他元数据
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self, ensure_ascii: bool = False) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Problem":
        """从字典创建"""
        # 过滤掉类中不存在的字段
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)
    
    @classmethod
    def from_aops(cls, data: Dict[str, Any]) -> "Problem":
        """从AoPS格式转换"""
        # 生成唯一ID
        uid = f"aops_{data.get('contest', 'unknown')}_{data.get('year', 0)}_{data.get('problem_num', 0)}"
        
        return cls(
            uid=uid,
            content=data.get('statement', ''),
            source='aops',
            source_url=data.get('source_url'),
            contest=data.get('contest'),
            year=data.get('year'),
            problem_num=data.get('problem_num'),
            solution=data.get('solution'),
            language='en' if data.get('contest') in ['IMO', 'USAMO', 'Putnam'] else 'zh',
            tags=[data.get('contest', 'Unknown')] if data.get('contest') else [],
            confidence='high',
            is_incomplete=False
        )
    
    @classmethod
    def from_books(cls, data: Dict[str, Any]) -> "Problem":
        """从Books格式转换"""
        uid = data.get('uid') or cls._generate_uid(data)
        
        # 提取标签
        tags = data.get('tags', [])
        if data.get('book_title'):
            tags.append(data.get('book_title'))
        
        return cls(
            uid=uid,
            content=data.get('stem_md', ''),
            source='books',
            book_title=data.get('book_title'),
            chapter=data.get('chapter'),
            section=data.get('section'),
            solution=data.get('solution_md'),
            answer=data.get('answer_md'),
            hints=data.get('hints_md'),
            tags=list(set(tags)),
            language='zh',
            confidence=data.get('confidence', 'high'),
            is_incomplete=data.get('is_incomplete', False),
            metadata={
                'problem_id': data.get('problem_id'),
                'problem_type': data.get('problem_type'),
                'source_pages': data.get('source_pages'),
                'chunk_id': data.get('chunk_id')
            }
        )
    
    @classmethod
    def from_aops_hf(cls, data: Dict[str, Any]) -> "Problem":
        """从AoPS HuggingFace格式转换"""
        return cls(
            uid=data.get('uid', cls._generate_uid(data)),
            content=data.get('stem_md', ''),
            source='aops_hf',
            source_url=data.get('source_url'),
            contest=data.get('contest'),
            year=data.get('year'),
            problem_num=data.get('problem_num'),
            solution=data.get('solution_md'),
            answer=data.get('answer_md'),
            hints=data.get('hints_md'),
            tags=data.get('tags', []),
            language='en',
            confidence=data.get('confidence', 'high'),
            is_incomplete=data.get('is_incomplete', False),
            metadata=data.get('metadata', {})
        )
    
    @classmethod
    def from_olympiadbench(cls, data: Dict[str, Any]) -> "Problem":
        """从OlympiadBench格式转换"""
        uid = data.get('uid') or cls._generate_uid(data)
        
        return cls(
            uid=uid,
            content=data.get('question', ''),
            source='olympiadbench',
            contest=data.get('source', ''),
            solution=data.get('solution'),
            answer=data.get('answer'),
            tags=data.get('keywords', []),
            difficulty=data.get('difficulty'),
            language='en' if data.get('language') == 'en' else 'zh',
            confidence='high',
            metadata={
                'domain': data.get('domain'),
                'subdomain': data.get('subdomain'),
                'unit': data.get('unit')
            }
        )
    
    @staticmethod
    def _generate_uid(data: Dict[str, Any]) -> str:
        """生成唯一ID"""
        content = json.dumps(data, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def get_full_text(self) -> str:
        """获取完整文本（用于向量索引）"""
        parts = [self.content]
        if self.solution:
            parts.append(f"\nSolution:\n{self.solution}")
        if self.hints:
            parts.append(f"\nHints:\n{self.hints}")
        return "\n".join(parts)
    
    def get_search_text(self) -> str:
        """获取用于搜索的文本"""
        parts = [self.content]
        if self.tags:
            parts.append(f"Tags: {', '.join(self.tags)}")
        return "\n".join(parts)