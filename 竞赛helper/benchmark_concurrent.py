#!/usr/bin/env python3
"""并发测试版：并发调用 Kimi API 处理 20 页图片，测速对比。"""

import os
import sys
import json
import time
import base64
import concurrent.futures
from pathlib import Path

import requests

SCRIPT_ROOT = Path(__file__).resolve().parent / "extract copy"
PROMPT_FILE = SCRIPT_ROOT / "prompts" / "kimi_problem_extract_prompt.txt"

# 试试硅基流动 (SiliconFlow)
BASE_URL = "https://api.siliconflow.cn/v1"
MODEL = "Qwen/Qwen2.5-VL-72B-Instruct"  # 硅基流动的多模态模型

def to_data_url(image_path):
    suffix = image_path.suffix.lower()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"

def call_kimi(session, api_key, content_parts, timeout=300):
    url = BASE_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "你是严谨的教材结构化提取助手。你只输出一个 JSON 对象，且必须合法可解析。"},
            {"role": "user", "content": content_parts},
        ],
    }
    response = session.post(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:500]}")
    data = response.json()
    message_content = data["choices"][0]["message"]["content"]
    if isinstance(message_content, list):
        text_parts = [p.get("text", "") for p in message_content if isinstance(p, dict) and p.get("type") == "text"]
        return "\n".join(text_parts).strip()
    return str(message_content).strip()

def make_content_parts(image_paths, prompt_text):
    parts = [{"type": "text", "text": prompt_text}]
    for img_path in image_paths:
        parts.append({"type": "image_url", "image_url": {"url": to_data_url(img_path)}})
    return parts

def process_chunk(chunk_id, image_paths, prompt_text, session, api_key):
    t0 = time.time()
    print(f"\n[{chunk_id}] 开始处理 {len(image_paths)} 页...")
    
    content_parts = make_content_parts(image_paths, prompt_text)
    upload_mb = sum(p.stat().st_size for p in image_paths) / 1024 / 1024
    print(f"  上传数据: {upload_mb:.1f}MB")
    
    result_text = call_kimi(session, api_key, content_parts)
    elapsed = time.time() - t0
    
    # Quick validation
    try:
        data = json.loads(result_text)
        problems = data.get("problems", [])
        print(f"  [{chunk_id}] 完成! 用时: {elapsed:.1f}s, 提取题目: {len(problems)} 个")
        return {"chunk_id": chunk_id, "problems": len(problems), "elapsed": elapsed, "status": "ok"}
    except Exception as e:
        preview = result_text[:200] if result_text else "<empty>"
        print(f"  [{chunk_id}] JSON解析失败: {e}")
        print(f"  预览: {preview}")
        return {"chunk_id": chunk_id, "problems": 0, "elapsed": elapsed, "status": "failed"}

def main():
    image_dir = Path(__file__).parent / "test_20_pages"
    if not image_dir.exists() or not list(image_dir.glob("*.jpg")):
        print(f"错误：请先运行 convert_20_test.py 把图片放到 {image_dir}")
        return 1

    # Get API key
    api_key = os.environ.get("ALI_API_KEY") or os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("KIMI_API_KEY")
    if not api_key:
        print("错误：未设置 API key。请设置环境变数 ALI_API_KEY 或 DASHSCOPE_API_KEY")
        return 1

    # Sort images
    images = sorted(image_dir.glob("*.jpg"))
    total_images = len(images)
    print(f"图片数量: {total_images}")
    print(f"总大小: {sum(p.stat().st_size for p in images)/1024/1024:.1f}MB")

    # Load prompt
    prompt_template = PROMPT_FILE.read_text(encoding="utf-8")

    # Split into 3 chunks (7+7+6 or 8+8+4)
    chunk_size = 7  # 20 pages / 3 chunks ≈ 6.7
    chunks = []
    for i in range(0, total_images, chunk_size):
        chunk_imgs = images[i:i+chunk_size]
        page_nums = [int(p.stem.split('-')[1]) for p in chunk_imgs]
        chunk_id = f"chunk-{i//chunk_size+1:02d}"
        
        # Replace placeholders directly (avoid .format() which conflicts with JSON braces)
        prompt = prompt_template.replace("{{BOOK_TITLE}}", "不等式的秘密 第1卷 第2版")
        prompt = prompt.replace("{{CHUNK_ID}}", chunk_id)
        prompt = prompt.replace("{{PAGE_LIST}}", ", ".join(str(p) for p in page_nums))
        prompt = prompt.replace("{{PAGE_RANGE}}", f"{page_nums[0]}-{page_nums[-1]}")
        
        chunks.append((chunk_id, chunk_imgs, prompt))
        print(f"{chunk_id}: 页 {page_nums[0]}-{page_nums[-1]} ({len(chunk_imgs)}页, {sum(p.stat().st_size for p in chunk_imgs)/1024:.0f}KB)")

    print(f"\n共 {len(chunks)} 个 chunks")
    print("\n" + "="*60)
    print("测试 1：串行处理（原方案）")
    print("="*60)

    t0 = time.time()
    session = requests.Session()
    results_serial = []
    for chunk_id, chunk_imgs, prompt in chunks:
        r = process_chunk(chunk_id, chunk_imgs, prompt, session, api_key)
        results_serial.append(r)
    serial_time = time.time() - t0

    print(f"\n[串行] 总耗时: {serial_time:.1f}s")

    print(f"\n{'='*60}")
    print("测试 2：并发处理（3线程同时发请求）")
    print("="*60)

    t0 = time.time()
    results_concurrent = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {}
        for chunk_id, chunk_imgs, prompt in chunks:
            sess = requests.Session()
            future = executor.submit(process_chunk, chunk_id, chunk_imgs, prompt, sess, api_key)
            futures[future] = chunk_id
        
        for future in concurrent.futures.as_completed(futures):
            r = future.result()
            results_concurrent.append(r)

    concurrent_time = time.time() - t0
    print(f"\n[并发] 总耗时: {concurrent_time:.1f}s")

    print(f"\n{'='*60}")
    print("对比结果")
    print(f"{'='*60}")
    print(f"串行耗时: {serial_time:.1f}s")
    print(f"并发耗时: {concurrent_time:.1f}s")
    print(f"加速比: {serial_time/concurrent_time:.1f}x")
    
    if serial_time / concurrent_time < 2.0:
        print("\n⚠️ 并发加速不明显，可能的原因：")
        print("  - API 速率限制（同账号并发请求被限流）")
        print("  - 网络带宽不足")
        print("  - 服务器端处理能力有限")
    
    print("\n如果测试成功，可以把并发集成到 extract_kimi_problem_db.py 中加速全部221页。")

if __name__ == "__main__":
    raise SystemExit(main())
