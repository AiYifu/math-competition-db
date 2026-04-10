#!/usr/bin/env python3
"""
并发版题目提取脚本 - 支持断点续传
用法: python extract_concurrent.py --book secret2 [--workers 3] [--limit-chunks 5]
"""

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import time
import concurrent.futures
from pathlib import Path
from typing import Any, Dict, List, Sequence, Set, Tuple

import requests

BASE_URL = "https://api.moonshot.cn/v1"
MODEL = "kimi-k2.5"
API_KEY = "sk-xdtXiFdLBh7BJZmO4AdIrvEiXvW8sfEt2SYkqb2rY784ClwR"

BOOKS = {
    "secret2": {
        "title": "不等式的秘密 第2卷",
        "dir": "data/secret2",
        "pages": 233,
    },
    "tip4": {
        "title": "小蓝本高中卷4 均值不等式与柯西不等式",
        "dir": "data/tip4",
        "pages": 228,
    },
    "tip9": {
        "title": "小蓝本高中卷9 不等式的解题与技巧",
        "dir": "data/tip9",
        "pages": 231,
    },
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
- 所有键名必须与下面一致，不要新增无关键。

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


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", required=True, choices=list(BOOKS.keys()), help="Book to process")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent workers (default: 1 to avoid rate limits)")
    parser.add_argument("--chunk-size", type=int, default=8, help="Pages per chunk")
    parser.add_argument("--limit-chunks", type=int, default=0, help="Limit chunks (0=all)")
    parser.add_argument("--pages", default="", help='Page range, e.g. "1-20,50-60"')
    parser.add_argument("--timeout", type=int, default=300, help="Request timeout")
    parser.add_argument("--resume", action="store_true", help="Resume from cache")
    parser.add_argument("--sleep", type=float, default=30.0, help="Sleep seconds between requests (default: 30)")
    parser.add_argument("--chunk-nums", default="", help='Only process specific chunks, e.g. "5,7,10,11,13"')
    return parser.parse_args()


def list_images(data_dir: Path) -> List[Tuple[int, Path]]:
    images = []
    for ext in ["*.jpg", "*.jpeg", "*.png"]:
        for p in data_dir.glob(ext):
            m = re.search(r"(\d+)", p.stem)
            if m:
                images.append((int(m.group(1)), p))
    return sorted(images, key=lambda x: x[0])


def parse_page_range(spec: str) -> Set[int]:
    if not spec.strip():
        return set()
    pages = set()
    for part in spec.split(","):
        p = part.strip()
        if "-" in p:
            s, e = p.split("-", 1)
            pages.update(range(int(s), int(e) + 1))
        else:
            pages.add(int(p))
    return pages


def to_data_url(img_path: Path) -> str:
    suffix = img_path.suffix.lower()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    data = base64.b64encode(img_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def extract_json(text: str) -> Dict:
    text = text.strip()
    # Remove markdown code fence if present
    if text.startswith("```"):
        lines = text.split("\n")
        if len(lines) > 1:
            # Remove first and last line if they're code fences
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
    
    # Try direct parse
    try:
        return json.loads(text)
    except:
        pass
    
    # Find JSON object (more robust)
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in response")
    
    # Track depth to find matching brace
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
    
    json_str = text[start:end+1]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # Try to fix common issues
        # Sometimes the model puts extra text inside the JSON
        raise ValueError(f"JSON parse error: {e}")


def call_api(session: requests.Session, content_parts: List, timeout: int) -> str:
    resp = session.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "temperature": 1,
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


def process_chunk(
    chunk_id: str,
    images: List[Tuple[int, Path]],
    book_title: str,
    output_dir: Path,
    timeout: int,
    resume: bool,
    max_retries: int = 5,
) -> Dict:
    cache_file = output_dir / "chunks" / f"{chunk_id}.json"
    raw_file = output_dir / "raw" / f"{chunk_id}.txt"
    
    # Resume check
    if resume and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            return {"chunk_id": chunk_id, "status": "cached", "problems": len(cached), "elapsed": 0}
        except:
            pass
    
    page_nums = [p[0] for p in images]
    prompt = PROMPT_TEMPLATE.replace("{{CHUNK_ID}}", chunk_id)
    prompt = prompt.replace("{{BOOK_TITLE}}", book_title)
    prompt = prompt.replace("{{PAGE_LIST}}", ", ".join(str(p) for p in page_nums))
    prompt = prompt.replace("{{PAGE_RANGE}}", f"{page_nums[0]}-{page_nums[-1]}")
    
    content_parts = [{"type": "text", "text": prompt}]
    for _, img_path in images:
        content_parts.append({"type": "image_url", "image_url": {"url": to_data_url(img_path)}})
    
    t0 = time.time()
    print(f"[{chunk_id}] Processing {len(images)} pages (p{page_nums[0]}-p{page_nums[-1]})...")
    
    session = requests.Session()
    text = ""
    
    # Retry loop with exponential backoff
    for attempt in range(max_retries):
        try:
            text = call_api(session, content_parts, timeout)
            parsed = extract_json(text)
            problems = parsed.get("problems", [])
            elapsed = time.time() - t0
            
            # Save
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            raw_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(problems, ensure_ascii=False, indent=2), encoding="utf-8")
            raw_file.write_text(text, encoding="utf-8")
            
            print(f"[{chunk_id}] Done in {elapsed:.0f}s, {len(problems)} problems")
            return {"chunk_id": chunk_id, "status": "ok", "problems": len(problems), "elapsed": elapsed}
        
        except Exception as e:
            err_str = str(e)
            # Rate limit: wait and retry
            if "429" in err_str or "rate limit" in err_str.lower():
                wait = min(60, 10 * (2 ** attempt))  # 10, 20, 40, 60s
                print(f"[{chunk_id}] Rate limited, waiting {wait}s (attempt {attempt+1}/{max_retries})...")
                time.sleep(wait)
                continue
            
            # Other errors: save and report
            elapsed = time.time() - t0
            raw_file.parent.mkdir(parents=True, exist_ok=True)
            if text:
                raw_file.write_text(text, encoding="utf-8")
                preview = text[:200].replace("\n", " ")
                print(f"[{chunk_id}] FAILED in {elapsed:.0f}s: {e}")
            else:
                raw_file.write_text(f"ERROR: {e}", encoding="utf-8")
                print(f"[{chunk_id}] FAILED in {elapsed:.0f}s: {e}")
            
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                return {"chunk_id": chunk_id, "status": "failed", "error": str(e), "problems": 0, "elapsed": elapsed}
    
    return {"chunk_id": chunk_id, "status": "failed", "error": "Max retries exceeded", "problems": 0, "elapsed": time.time() - t0}


def normalize_problem(raw: Dict, chunk_id: str, book_title: str, default_pages: List[int]) -> Dict:
    pages = raw.get("source_pages", default_pages)
    if isinstance(pages, int):
        pages = [pages]
    pages = sorted(set(int(p) for p in pages if isinstance(p, (int, str))))
    if not pages:
        pages = default_pages
    
    stem = (raw.get("stem_md") or "").strip()
    solution = (raw.get("solution_md") or "").strip()
    
    fingerprint = hashlib.sha1(f"{stem}|{solution}".encode()).hexdigest()[:10]
    problem_id = raw.get("problem_id") or ""
    page_scope = f"p{min(pages):03d}_{max(pages):03d}"
    slug = re.sub(r"[^\w\u4e00-\u9fff-]", "_", problem_id)[:30] or "problem"
    uid = f"{page_scope}_{slug}_{fingerprint}"
    
    return {
        "uid": uid,
        "book_title": book_title,
        "chapter": raw.get("chapter"),
        "section": raw.get("section"),
        "problem_id": problem_id or None,
        "problem_type": raw.get("problem_type") or "unknown",
        "title": raw.get("title"),
        "source_pages": pages,
        "stem_md": stem,
        "solution_md": solution,
        "answer_md": (raw.get("answer_md") or "").strip(),
        "hints_md": (raw.get("hints_md") or "").strip(),
        "original_text_md": (raw.get("original_text_md") or "").strip(),
        "tags": raw.get("tags") or [],
        "confidence": raw.get("confidence") or "medium",
        "is_incomplete": bool(raw.get("is_incomplete")),
        "chunk_id": chunk_id,
    }


def main():
    args = parse_args()
    book = BOOKS[args.book]
    
    script_dir = Path(__file__).parent
    data_dir = script_dir / book["dir"]
    output_dir = script_dir / "output" / args.book
    
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "chunks").mkdir(exist_ok=True)
    (output_dir / "raw").mkdir(exist_ok=True)
    (output_dir / "problems").mkdir(exist_ok=True)
    
    images = list_images(data_dir)
    if not images:
        print(f"No images in {data_dir}")
        return 1
    
    # Filter pages
    if args.pages:
        selected = parse_page_range(args.pages)
        images = [(p, path) for p, path in images if p in selected]
    
    # Make chunks
    chunks = []
    for i in range(0, len(images), args.chunk_size):
        chunk_images = images[i:i+args.chunk_size]
        chunk_id = f"chunk-{i//args.chunk_size+1:04d}"
        chunks.append((chunk_id, chunk_images))
    
    # Filter by specific chunk numbers if provided
    if args.chunk_nums:
        selected_nums = [int(x.strip()) for x in args.chunk_nums.split(",")]
        chunks = [(cid, cimgs) for cid, cimgs in chunks if int(cid.replace("chunk-", "")) in selected_nums]
    
    if args.limit_chunks:
        chunks = chunks[:args.limit_chunks]
    
    print(f"Book: {book['title']}")
    print(f"Pages: {len(images)}, Chunks: {len(chunks)}, Workers: {args.workers}")
    print(f"Sleep between requests: {args.sleep}s")
    print(f"Output: {output_dir}")
    print()
    
    t0 = time.time()
    results = []
    
    # Process chunks (serial to avoid rate limits, or parallel if workers > 1)
    if args.workers == 1:
        # Serial processing with sleep
        for i, (chunk_id, chunk_images) in enumerate(chunks):
            result = process_chunk(
                chunk_id,
                chunk_images,
                book["title"],
                output_dir,
                args.timeout,
                args.resume,
            )
            results.append(result)
            
            # Sleep after successful request to avoid rate limits
            if result["status"] == "ok" and i < len(chunks) - 1:
                print(f"  Waiting {args.sleep}s before next request...")
                time.sleep(args.sleep)
    else:
        # Parallel processing (use with caution - may hit rate limits)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {}
            for chunk_id, chunk_images in chunks:
                future = executor.submit(
                    process_chunk,
                    chunk_id,
                    chunk_images,
                    book["title"],
                    output_dir,
                    args.timeout,
                    args.resume,
                )
                futures[future] = chunk_id
            
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                results.append(result)
    
    # Collect all problems
    all_problems = []
    seen = set()
    for chunk_id, _ in chunks:
        cache_file = output_dir / "chunks" / f"{chunk_id}.json"
        if cache_file.exists():
            raw_problems = json.loads(cache_file.read_text(encoding="utf-8"))
            default_pages = [1]
            for raw in raw_problems:
                prob = normalize_problem(raw, chunk_id, book["title"], default_pages)
                if prob["uid"] not in seen:
                    seen.add(prob["uid"])
                    all_problems.append(prob)
    
    # Sort and save
    all_problems.sort(key=lambda p: (min(p["source_pages"]), p["uid"]))
    
    # Save individual files
    for prob in all_problems:
        out_file = output_dir / "problems" / f"{prob['uid']}.json"
        out_file.write_text(json.dumps(prob, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # Save JSONL
    jsonl = output_dir / "problems.jsonl"
    with open(jsonl, "w", encoding="utf-8") as f:
        for prob in all_problems:
            f.write(json.dumps(prob, ensure_ascii=False) + "\n")
    
    # Summary
    elapsed = time.time() - t0
    ok_chunks = sum(1 for r in results if r["status"] in ("ok", "cached"))
    total_problems = len(all_problems)
    
    summary = {
        "book": book["title"],
        "total_pages": len(images),
        "total_chunks": len(chunks),
        "ok_chunks": ok_chunks,
        "failed_chunks": len(chunks) - ok_chunks,
        "total_problems": total_problems,
        "elapsed_seconds": round(elapsed, 1),
        "chunks": results,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    
    print(f"\n{'='*60}")
    print(f"Done! {total_problems} problems in {elapsed:.0f}s")
    print(f"Output: {output_dir}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
