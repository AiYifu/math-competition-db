# -*- coding: utf-8 -*-
"""
Batch process all 4 math competition PDFs using Pix2Text
Output: Markdown files with LaTeX formulas
"""

import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from pix2text import Pix2Text
import fitz
import os
import time

# Config
BOOKS = [
    (r"C:\竞赛helper\小蓝本高中卷4 均值不等式与柯西不等式.pdf", "蓝本卷4"),
    (r"C:\竞赛helper\小蓝本高中卷9 不等式的解题与技巧.pdf", "蓝本卷9"),
    (r"C:\竞赛helper\不等式的秘密第1卷第2版 [（越）范建熊 著] 2014年版.pdf", "秘密卷1"),
    (
        r"C:\竞赛helper\不等式的秘密  第2卷 [（越南）范建熊著；隋振林译][哈尔滨工业大学出版社][2014.01][215页].pdf",
        "秘密卷2",
    ),
]
OUTPUT_BASE = r"C:\竞赛helper\OCR结果_Pix2Text"
MAX_PAGES = 20  # Limit to 20 pages per book for testing

# Load once
print("=" * 60)
print("Loading Pix2Text OCR model (no table recognition)")
print("=" * 60)
p2t = Pix2Text(enable_table=False, device="cpu")
print("Model loaded!\n")

os.makedirs(OUTPUT_BASE, exist_ok=True)

for pdf_path, short_name in BOOKS:
    if not os.path.exists(pdf_path):
        print(f"[SKIP] File not found: {pdf_path}")
        continue

    filename = os.path.basename(pdf_path)
    out_dir = os.path.join(OUTPUT_BASE, short_name)
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n{'=' * 60}")
    print(f"Processing: {short_name}")
    print(f"File: {filename}")
    print(f"{'=' * 60}")

    doc = fitz.open(pdf_path)
    total = len(doc)

    for page_num in range(total):
        t0 = time.time()
        page = doc[page_num]

        # Render to image at 2x
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        img_path = os.path.join(out_dir, f"page_{page_num + 1:04d}.png")
        pix.save(img_path)

        # OCR with formula recognition
        result = p2t.recognize(img_path, return_text=True)

        # Save per-page markdown
        md_path = os.path.join(out_dir, f"page_{page_num + 1:04d}.md")
        header = f"# 第 {page_num + 1} 页\n\n"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(header + result)

        dt = time.time() - t0
        print(f"  Page {page_num + 1:4d}/{total} | {dt:6.1f}s")

        if MAX_PAGES and page_num + 1 >= MAX_PAGES:
            print(f"  >> Reached MAX_PAGES limit ({MAX_PAGES})")
            break

    doc.close()
    print(f"\n  >> Saved to: {out_dir}")

print(f"\n{'=' * 60}")
print("ALL DONE!")
print(f"Output: {OUTPUT_BASE}")
print(f"{'=' * 60}")
