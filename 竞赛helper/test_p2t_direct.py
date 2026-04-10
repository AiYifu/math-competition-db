# -*- coding: utf-8 -*-
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from pix2text import Pix2Text
import fitz
import os

PDF_FILE = r"C:\竞赛helper\sample_5_pages.pdf"
OUTPUT_DIR = r"C:\竞赛helper\out_pix2text"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Loading Pix2Text (no table)...")
p2t = Pix2Text(enable_table=False, device="cpu")
print("Loaded successfully!")

print(f"\nProcessing: {PDF_FILE}")
doc = fitz.open(PDF_FILE)

all_pages = []
for page_num in range(len(doc)):
    page = doc[page_num]
    mat = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=mat)

    img_path = os.path.join(OUTPUT_DIR, f"page_{page_num + 1}.png")
    pix.save(img_path)

    print(f"\n--- Page {page_num + 1}/{len(doc)} ---")
    print(f"Image: {img_path} ({pix.w}x{pix.h})")

    result = p2t.recognize(img_path, return_text=False)

    # Result is a dict or list, let's inspect
    print(f"Result type: {type(result)}")
    if isinstance(result, dict):
        print(f"Result keys: {result.keys()}")
    elif isinstance(result, list):
        print(f"Result length: {len(result)}")
        if len(result) > 0:
            print(f"First item type: {type(result[0])}")
            if isinstance(result[0], dict):
                print(f"First item keys: {result[0].keys()}")

    # Also get text-only version
    result_text = p2t.recognize(img_path, return_text=True)
    print(f"Text result type: {type(result_text)}")
    if isinstance(result_text, str):
        print(f"Text length: {len(result_text)}")
        print("Preview:")
        print(result_text[:500])

    all_pages.append(result_text)

doc.close()
print("\n" + "=" * 60)
print("Summary of all pages:")
for i, page_text in enumerate(all_pages):
    print(f"\nPage {i + 1}:")
    print(page_text[:300] if isinstance(page_text, str) else str(page_text)[:300])
