#!/usr/bin/env python3
"""单次API调用测试 - 只处理一小块"""

import os
import sys
import json
import time
import base64
from pathlib import Path
import requests

# 硅基流动
BASE_URL = "https://api.siliconflow.cn/v1"
MODEL = "Qwen/Qwen2.5-VL-72B-Instruct"
API_KEY = "sk-mtxecjqwsqzpcagnafsqggltrokycncdktosawdxdezidgkr"

SCRIPT_ROOT = Path(__file__).resolve().parent / "extract copy"
PROMPT_FILE = SCRIPT_ROOT / "prompts" / "kimi_problem_extract_prompt.txt"

def to_data_url(image_path):
    suffix = image_path.suffix.lower()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"

def main():
    image_dir = Path(__file__).parent / "test_20_pages"
    images = sorted(image_dir.glob("*.jpg"))[:3]  # 只取3页
    
    if not images:
        print("No images found")
        return 1
    
    print(f"测试 {len(images)} 页图片")
    print(f"总大小: {sum(p.stat().st_size for p in images)/1024:.0f}KB")
    
    # Build prompt
    prompt_template = PROMPT_FILE.read_text(encoding="utf-8")
    page_nums = [int(p.stem.split('-')[1]) for p in images]
    prompt = prompt_template.replace("{{BOOK_TITLE}}", "不等式的秘密 第1卷 第2版")
    prompt = prompt.replace("{{CHUNK_ID}}", "test-chunk")
    prompt = prompt.replace("{{PAGE_LIST}}", ", ".join(str(p) for p in page_nums))
    prompt = prompt.replace("{{PAGE_RANGE}}", f"{page_nums[0]}-{page_nums[-1]}")
    
    # Build content
    content_parts = [{"type": "text", "text": prompt}]
    for img in images:
        content_parts.append({"type": "image_url", "image_url": {"url": to_data_url(img)}})
    
    payload = {
        "model": MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "你是严谨的教材结构化提取助手。你只输出一个 JSON 对象，且必须合法可解析。"},
            {"role": "user", "content": content_parts},
        ],
    }
    
    print(f"\n发送请求到 {BASE_URL}...")
    print(f"模型: {MODEL}")
    
    t0 = time.time()
    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=600,  # 10分钟超时
        )
        elapsed = time.time() - t0
        print(f"\n响应时间: {elapsed:.1f}s")
        print(f"状态码: {response.status_code}")
        
        if response.status_code >= 400:
            print(f"错误: {response.text[:500]}")
            return 1
        
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        
        # Try to parse JSON
        try:
            parsed = json.loads(content)
            problems = parsed.get("problems", [])
            print(f"提取题目: {len(problems)} 个")
            if problems:
                print(f"\n第一题预览:")
                p = problems[0]
                print(f"  ID: {p.get('problem_id')}")
                print(f"  题干: {p.get('stem_md', '')[:100]}...")
        except json.JSONDecodeError:
            print(f"JSON解析失败，响应前200字符:")
            print(content[:200])
        
        # Save response
        (Path(__file__).parent / "test_response.json").write_text(content, encoding="utf-8")
        print(f"\n完整响应已保存到 test_response.json")
        
    except requests.Timeout:
        print(f"\n请求超时 (>{time.time()-t0:.0f}s)")
        return 1
    except Exception as e:
        print(f"\n错误: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
