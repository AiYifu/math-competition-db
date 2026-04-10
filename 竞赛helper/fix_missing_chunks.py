#!/usr/bin/env python3
"""补全缺失的chunks - 使用更长的等待时间避免速率限制"""

import os
import sys
import json
import time
import base64
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests

BASE_URL = "https://api.siliconflow.cn/v1"
MODEL = "Qwen/Qwen2.5-VL-72B-Instruct"
API_KEY = "sk-mtxecjqwsqzpcagnafsqggltrokycncdktosawdxdezidgkr"

BOOKS = {
    "secret2": {"title": "不等式的秘密 第2卷", "dir": "data/secret2", "total_chunks": 30},
    "tip4": {"title": "小蓝本高中卷4 均值不等式与柯西不等式", "dir": "data/tip4", "total_chunks": 29},
    "tip9": {"title": "小蓝本高中卷9 不等式的解题与技巧", "dir": "data/tip9", "total_chunks": 29},
}

PROMPT_TEMPLATE = """你是一个"数学教材题目结构化提取助手"。

输入说明：
- 本次请求包含同一本书的连续多页图片，通常为 8-10 页。
- 当前批次标识：{{CHUNK_ID}}
- 书名：{{BOOK_TITLE}}
- 本批次页码列表（按图片顺序）：{{PAGE_LIST}}
- 本批次页码范围：{{PAGE_RANGE}}

任务目标：
1) 抽取本批次图片中出现的每一道题目及其解答，不要遗漏。
2) 每道题都要包含：题号、章节、题干、解答、答案（若存在）、来源页码。
2.1) 尽量保留原文措辞，不要改写；如果有标点/换行，尽量按原文结构保留。
3) 若题目跨页，请在 source_pages 中列出全部页码，并将 is_incomplete 设为 false。
4) 若本批次只出现题干或只出现解答，先按已见内容输出，并将 is_incomplete 设为 true。
5) 数学公式必须用 Markdown + LaTeX 表示：
   - 行内公式：$...$
   - 独立公式：$$...$$
6) 不要翻译原文，不要总结，不要改写原意。
7) 看不清的字符使用 [[无法辨认]] 标记，不要编造。

输出要求（非常重要）：
- 只输出一个 JSON 对象。
- 禁止输出 markdown 代码块、解释文本或额外前后缀。
- JSON 必须可直接被 json.loads 解析。

JSON 模板：
{
  "chunk_id": "{{CHUNK_ID}}",
  "book_title": "{{BOOK_TITLE}}",
  "page_range": "{{PAGE_RANGE}}",
  "problems": [
    {
      "problem_id": "例如：例1.2 / 习题3 / 12",
      "problem_type": "example|exercise|theorem|definition|proof|unknown",
      "chapter": "章节名，没有则 null",
      "section": "小节名，没有则 null",
      "title": "题目标题，没有则 null",
      "source_pages": [12, 13],
      "stem_md": "题干全文（Markdown）",
      "solution_md": "解答全文（Markdown）",
      "answer_md": "答案（若无则空字符串）",
      "hints_md": "提示/注释（若无则空字符串）",
      "original_text_md": "把该题在图片中可见的原文内容尽量完整拼接（Markdown）",
      "tags": ["可选标签1", "可选标签2"],
      "confidence": "high|medium|low",
      "is_incomplete": false
    }
  ],
  "notes_md": "本批次非题目正文内容，可为空字符串"
}"""


def find_missing_chunks(output_dir: Path, total: int) -> List[int]:
    """找出缺失的chunk编号"""
    existing = set()
    for f in output_dir.joinpath("chunks").glob("chunk-*.json"):
        m = re.search(r"chunk-(\d+)\.json", f.name)
        if m:
            existing.add(int(m.group(1)))
    return sorted(set(range(1, total + 1)) - existing)


def list_images(data_dir: Path) -> List[Tuple[int, Path]]:
    images = []
    for ext in ["*.jpg", "*.jpeg", "*.png"]:
        for p in data_dir.glob(ext):
            m = re.search(r"(\d+)", p.stem)
            if m:
                images.append((int(m.group(1)), p))
    return sorted(images, key=lambda x: x[0])


def to_data_url(img_path: Path) -> str:
    suffix = img_path.suffix.lower()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    data = base64.b64encode(img_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def extract_json(text: str) -> Dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found")
    
    depth = 0
    in_str = False
    escape = False
    end = -1
    
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    
    if end == -1:
        raise ValueError("Could not find end of JSON object")
    
    return json.loads(text[start:end+1])


def call_api(session, content_parts: List, timeout: int = 300) -> str:
    resp = session.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "temperature": 0,
            "max_tokens": 16000,
            "messages": [
                {"role": "system", "content": "你是严谨的教材结构化提取助手。你只输出一个 JSON 对象，且必须合法可解析。"},
                {"role": "user", "content": content_parts},
            ],
        },
        timeout=timeout,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    if isinstance(content, list):
        parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
        return "\n".join(parts)
    return str(content)


def process_chunk(chunk_num: int, images: List[Tuple[int, Path]], book_title: str, output_dir: Path, chunk_size: int = 8):
    chunk_id = f"chunk-{chunk_num:04d}"
    cache_file = output_dir / "chunks" / f"{chunk_id}.json"
    raw_file = output_dir / "raw" / f"{chunk_id}.txt"
    
    page_nums = [p[0] for p in images]
    prompt = PROMPT_TEMPLATE.replace("{{CHUNK_ID}}", chunk_id)
    prompt = prompt.replace("{{BOOK_TITLE}}", book_title)
    prompt = prompt.replace("{{PAGE_LIST}}", ", ".join(str(p) for p in page_nums))
    prompt = prompt.replace("{{PAGE_RANGE}}", f"{page_nums[0]}-{page_nums[-1]}")
    
    content_parts = [{"type": "text", "text": prompt}]
    for _, img_path in images:
        content_parts.append({"type": "image_url", "image_url": {"url": to_data_url(img_path)}})
    
    session = requests.Session()
    
    # Retry with exponential backoff
    for attempt in range(10):
        try:
            print(f"  [{chunk_id}] Attempt {attempt+1}: pages {page_nums[0]}-{page_nums[-1]}...") 
            text = call_api(session, content_parts)
            parsed = extract_json(text)
            problems = parsed.get("problems", [])
            
            # Save
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            raw_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(problems, ensure_ascii=False, indent=2), encoding="utf-8")
            raw_file.write_text(text, encoding="utf-8")
            
            print(f"  [{chunk_id}] OK: {len(problems)} problems")
            return True
        
        except Exception as e:
            err = str(e)
            if "429" in err or "rate limit" in err.lower():
                wait = min(120, 30 * (2 ** attempt))
                print(f"  [{chunk_id}] Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  [{chunk_id}] Error: {e}")
                time.sleep(10)
    
    print(f"  [{chunk_id}] FAILED after 10 attempts")
    return False


def main():
    script_dir = Path(__file__).parent
    
    for book_key, book_info in BOOKS.items():
        output_dir = script_dir / "output" / book_key
        data_dir = script_dir / book_info["dir"]
        
        missing = find_missing_chunks(output_dir, book_info["total_chunks"])
        
        if not missing:
            print(f"{book_key}: No missing chunks")
            continue
        
        print(f"\n{'='*60}")
        print(f"{book_key}: {len(missing)} missing chunks: {missing}")
        print(f"{'='*60}")
        
        images = list_images(data_dir)
        
        for chunk_num in missing:
            # Get images for this chunk
            start_idx = (chunk_num - 1) * 8
            chunk_images = images[start_idx:start_idx + 8]
            
            if not chunk_images:
                print(f"  [{chunk_num}] No images found")
                continue
            
            success = process_chunk(chunk_num, chunk_images, book_info["title"], output_dir)
            
            # Wait between successful requests
            if success:
                print(f"  Waiting 90s before next chunk...")
                time.sleep(90)
        
        print(f"\n{book_key}: Done!")
    
    print("\n" + "="*60)
    print("All missing chunks processed!")


if __name__ == "__main__":
    main()
