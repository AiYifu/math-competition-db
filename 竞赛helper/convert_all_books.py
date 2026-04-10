#!/usr/bin/env python3
"""PDF to JPEG converter - batch convert 3 books."""

from pathlib import Path
import pypdfium2 as pdfium
from PIL import Image
import time

BOOKS = [
    ("不等式的秘密  第2卷 [（越南）范建熊著；隋振林译][哈尔滨工业大学出版社][2014.01][215页].pdf", "secret2"),
    ("小蓝本高中卷4 均值不等式与柯西不等式.pdf", "tip4"),
    ("小蓝本高中卷9 不等式的解题与技巧.pdf", "tip9"),
]

DPI = 200
QUALITY = 90

def main():
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)
    
    pdf_files = sorted(Path(".").glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files")
    
    total_pages = 0
    total_size = 0
    
    for pdf_name, folder_name in BOOKS:
        # Find the PDF (handle encoding issues)
        pdf_path = None
        for p in pdf_files:
            if folder_name == "secret2" and "第2卷" in p.name and "范建熊" in p.name:
                pdf_path = p
                break
            elif folder_name == "tip4" and "卷4" in p.name:
                pdf_path = p
                break
            elif folder_name == "tip9" and "卷9" in p.name:
                pdf_path = p
                break
        
        if not pdf_path:
            print(f"[skip] {folder_name}: PDF not found")
            continue
        
        out_dir = data_dir / folder_name
        out_dir.mkdir(exist_ok=True)
        
        print(f"\n{'='*60}")
        print(f"Converting: {pdf_path.name}")
        print(f"Output: {out_dir}")
        
        t0 = time.time()
        pdf = pdfium.PdfDocument(str(pdf_path))
        n_pages = len(pdf)
        print(f"Pages: {n_pages}")
        
        count = 0
        for i in range(n_pages):
            page = pdf[i]
            img = page.render(scale=DPI / 72).to_pil()
            if img.mode != "RGB":
                img = img.convert("RGB")
            
            out_path = out_dir / f"page-{i+1:03d}.jpg"
            img.save(str(out_path), "JPEG", quality=QUALITY)
            count += 1
            
            if (i + 1) % 50 == 0:
                print(f"  Progress: {i+1}/{n_pages}")
        
        pdf.close()
        elapsed = time.time() - t0
        
        dir_size = sum(p.stat().st_size for p in out_dir.glob("*.jpg")) / 1024 / 1024
        print(f"Done: {count} pages in {elapsed:.1f}s, {dir_size:.1f}MB")
        total_pages += count
        total_size += dir_size
    
    print(f"\n{'='*60}")
    print(f"All done! Total: {total_pages} pages, {total_size:.1f}MB")
    print(f"Output directory: {data_dir}")

if __name__ == "__main__":
    main()
