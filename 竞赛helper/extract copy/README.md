# Kimi 批量题库提取（每题一个 JSON）

这个目录下的流程已经按以下要求设计：

- 每次请求发送 **8-10 页**（默认 9 页）给 `kimi-k2.5`
- 最终产物是 **每道题一个 JSON 文件**
- 每题 JSON 保留 `stem_md / solution_md / answer_md / hints_md / original_text_md`，并默认附带 `raw_problem`
- 同步生成 `problems.jsonl` 和可检索的 `SQLite + FTS5` 数据库

## 目录结构

- `data/secret/`: 书页 JPEG 图片（已存在）
- `prompts/kimi_problem_extract_prompt.txt`: 提取提示词模板
- `scripts/extract_kimi_problem_db.py`: 主流程（提取 + 归档 + 建库）
- `scripts/search_problem_db.py`: 检索脚本
- `output/kimi_problem_db/`: 输出目录（运行后生成）

## 1) 设置 API Key

建议先在 shell 里设置环境变量（不要把 key 写进代码）：

```bash
export ALI_API_KEY='你的阿里 API Key'
```

## 2) 先跑小样本验证

```bash
python3 scripts/extract_kimi_problem_db.py \
  --input-dir data/secret \
  --output-dir output/kimi_problem_db \
  --model kimi-k2.5 \
  --chunk-size 9 \
  --limit-chunks 1 \
  --resume
```

## 3) 全量提取

```bash
python3 scripts/extract_kimi_problem_db.py \
  --input-dir data/secret \
  --output-dir output/kimi_problem_db \
  --model kimi-k2.5 \
  --chunk-size 9 \
  --resume
```

可选参数：

- `--pages "1-40,60-80"`: 只提取指定页
- `--max-retries 4`: 失败重试次数
- `--timeout 300`: 单次请求超时秒数
- `--sleep-seconds 1`: 请求间隔

## 4) 输出说明

运行后可看到：

- `output/kimi_problem_db/problems/*.json`: 每题一个文件
- `output/kimi_problem_db/problems.jsonl`: 全量题目 JSONL
- `output/kimi_problem_db/problems.db`: SQLite 题库
- `output/kimi_problem_db/summary.json`: 批处理汇总
- `output/kimi_problem_db/chunks/*.problems.json`: 每个 8-10 页批次的缓存
- `output/kimi_problem_db/raw/*.response.txt`: 模型原始返回
- `output/kimi_problem_db/page_manifest.json`: 页码与图片文件映射

## 5) 检索示例

```bash
python3 scripts/search_problem_db.py "柯西 不等式" --limit 5
```

如果需要更细粒度的检索，也可以直接在 `problems.db` 上执行 SQL。
