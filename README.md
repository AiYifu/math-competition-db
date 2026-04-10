# Math Competition Helper

基于RAG的数学竞赛题目检索与提示生成系统。

## 架构

- **OCR Service**: 图片转LaTeX
- **Retrieval Service**: 题目检索（向量+关键词+重排序）
- **Dedup Service**: 题目去重
- **Hint Service**: 分步提示生成

## 快速开始

```bash
# 1. 安装依赖
make install

# 2. 构建索引
make build

# 3. 启动服务
make run

# 或本地启动
make run-local
```

## 服务端口

- OCR Service: http://localhost:8001
- Retrieval Service: http://localhost:8002

## API文档

启动服务后访问：
- http://localhost:8001/docs (OCR)
- http://localhost:8002/docs (Retrieval)

## 项目结构

```
math_helper/
├── services/           # 微服务
├── shared/            # 共享组件
├── data/              # 数据与索引
├── scripts/           # 运维脚本
└── notebooks/         # 实验分析
```