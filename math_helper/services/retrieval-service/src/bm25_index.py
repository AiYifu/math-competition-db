"""BM25稀疏检索实现"""
import json
import pickle
from pathlib import Path
from typing import List, Dict, Tuple
import re

class BM25Index:
    """基于rank-bm25的稀疏检索索引"""
    
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.documents = []
        self.doc_ids = []
        self.tokenized_docs = []
        self.idf = {}
        self.avgdl = 0
        self.doc_freqs = {}
        self.N = 0
        
    def _tokenize(self, text: str) -> List[str]:
        """
        对数学题目进行分词 - 改进版
        更好地提取数学表达式和关键词
        """
        import re
        
        tokens = []
        text_lower = text.lower()
        
        # 1. 提取LaTeX公式中的内容
        # 匹配 \( ... \) 或 $...$ 或 $$...$$
        latex_patterns = [
            r'\\\((.*?)\\\)',  # \(...\)
            r'\$\$(.*?)\$\$',   # $$...$$
            r'\$(.*?)\$',        # $...$
        ]
        
        latex_content = []
        for pattern in latex_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            latex_content.extend(matches)
        
        # 2. 从LaTeX中提取数学符号和变量
        for latex in latex_content:
            # 提取变量名（单字母，常见数学变量）
            vars_found = re.findall(r'(?<![a-zA-Z])([a-zA-Z])(?![a-zA-Z])', latex)
            tokens.extend(vars_found)
            
            # 提取数学函数和运算符
            math_funcs = ['sqrt', 'frac', 'sum', 'prod', 'int', 'leq', 'geq', 'geqslant', 'leqslant', 'cdot']
            for func in math_funcs:
                if func in latex:
                    tokens.append(func)
            
            # 提取数字
            numbers = re.findall(r'\d+', latex)
            tokens.extend(numbers)
            
            # 提取特殊符号组合
            if 'geq' in latex or 'geqslant' in latex:
                tokens.append('>=')
            if 'leq' in latex or 'leqslant' in latex:
                tokens.append('<=')
            if 'frac' in latex:
                tokens.append('fraction')
            if 'sqrt' in latex:
                tokens.append('sqrt')
        
        # 3. 提取中文关键词（更全面的列表）
        keywords = [
            # 基本数学概念
            '不等式', '证明', '求证', '正数', '实数', '非负', '整数', '自然数',
            '算术', '几何', '平均', '均值', '平方', '立方', '乘积', '和', '差',
            # 不等式类型
            '柯西', '柯西不等式', '均值不等式', '排序不等式', '琴生', '赫尔德',
            '调整法', '归纳法', '数学归纳法', '反证法', '构造法',
            # 约束条件
            '约束', '条件', '给定', '满足', '且', '或',
            # 变量描述
            '正实数', '非负实数', '任意', '一切', '所有',
            # 操作
            '求', '证明', '求证', '计算', '求值',
        ]
        
        for kw in keywords:
            if kw in text:
                tokens.append(kw)
        
        # 4. 提取数字（包括题目编号）
        numbers = re.findall(r'\d+', text)
        tokens.extend([f"num_{n}" for n in numbers])
        
        # 5. 提取变量模式（如 a+b, ab, a^2 等）
        var_patterns = [
            r'([a-z])\s*\+\s*([a-z])',  # a + b
            r'([a-z])([a-z])',            # ab
            r'([a-z])\^2',               # a^2
            r'([a-z])\^3',               # a^3
        ]
        for pattern in var_patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                if isinstance(match, tuple):
                    tokens.append(''.join(match))
                else:
                    tokens.append(match)
        
        return tokens
    
    def add_documents(self, documents: List[Dict]):
        """
        添加文档到索引
        
        Args:
            documents: 文档列表，每个包含uid和stem字段
        """
        for doc in documents:
            self.doc_ids.append(doc['uid'])
            self.documents.append(doc['stem'])
            tokens = self._tokenize(doc['stem'])
            self.tokenized_docs.append(tokens)
        
        self.N = len(self.documents)
        self._calculate_idf()
        
    def _calculate_idf(self):
        """计算IDF值"""
        # 统计每个词项的文档频率
        for tokens in self.tokenized_docs:
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1
        
        # 计算IDF
        import math
        for token, freq in self.doc_freqs.items():
            self.idf[token] = math.log((self.N - freq + 0.5) / (freq + 0.5) + 1)
        
        # 计算平均文档长度
        total_len = sum(len(tokens) for tokens in self.tokenized_docs)
        self.avgdl = total_len / self.N if self.N > 0 else 0
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        搜索文档
        
        Returns:
            (doc_id, score)列表，按分数降序排列
        """
        query_tokens = self._tokenize(query)
        
        scores = []
        for idx, doc_tokens in enumerate(self.tokenized_docs):
            score = self._score_document(query_tokens, doc_tokens)
            scores.append((self.doc_ids[idx], score))
        
        # 按分数降序排序
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return scores[:top_k]
    
    def _score_document(self, query_tokens: List[str], doc_tokens: List[str]) -> float:
        """计算BM25分数"""
        import math
        
        score = 0.0
        doc_len = len(doc_tokens)
        
        # 统计文档中每个词项的频率
        token_freq = {}
        for token in doc_tokens:
            token_freq[token] = token_freq.get(token, 0) + 1
        
        for token in query_tokens:
            if token in self.idf:
                freq = token_freq.get(token, 0)
                idf = self.idf[token]
                
                # BM25公式
                numerator = freq * (self.k1 + 1)
                denominator = freq + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                score += idf * numerator / denominator
        
        return score
    
    def save(self, directory: Path):
        """保存索引"""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        
        data = {
            'k1': self.k1,
            'b': self.b,
            'documents': self.documents,
            'doc_ids': self.doc_ids,
            'tokenized_docs': self.tokenized_docs,
            'idf': self.idf,
            'avgdl': self.avgdl,
            'doc_freqs': self.doc_freqs,
            'N': self.N
        }
        
        with open(directory / 'bm25_index.pkl', 'wb') as f:
            pickle.dump(data, f)
    
    def load(self, directory: Path):
        """加载索引"""
        directory = Path(directory)
        index_file = directory / 'bm25_index.pkl'
        
        if index_file.exists():
            with open(index_file, 'rb') as f:
                data = pickle.load(f)
            
            self.k1 = data['k1']
            self.b = data['b']
            self.documents = data['documents']
            self.doc_ids = data['doc_ids']
            self.tokenized_docs = data['tokenized_docs']
            self.idf = data['idf']
            self.avgdl = data['avgdl']
            self.doc_freqs = data['doc_freqs']
            self.N = data['N']
            return True
        return False
