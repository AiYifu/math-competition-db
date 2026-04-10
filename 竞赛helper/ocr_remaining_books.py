# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import fitz
import os
import easyocr
import time
import numpy as np
import cv2

print("Loading OCR model, please wait...")
reader = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)
print("OCR model loaded successfully!")

def ocr_page_with_eastocr(doc, page_num, reader, dpi=200):
    """Render PDF page to image and perform OCR with EasyOCR"""
    page = doc[page_num]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    
    # Convert to OpenCV format
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
    if pix.n == 4:  # RGBA
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
    elif pix.n == 2:  # Grayscale + alpha
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    elif pix.n == 1:  # Grayscale
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    
    # Perform OCR
    result = reader.readtext(img, paragraph=True)
    
    # Extract text and sort by position
    texts = []
    for line in result:
        if line and len(line) >= 2:
            text_content = line[1]
            confidence = line[2]
            y_pos = line[0][0][1] if len(line[0]) > 0 else 0
            if confidence > 0.5:  # Only keep high-confidence results
                texts.append((y_pos, text_content, confidence))
    
    # Sort by y position
    texts.sort(key=lambda x: x[0])
    
    return [t[1] for t in texts]

def process_pdf_with_ocr(pdf_path, output_dir, max_pages=None, dpi=200):
    """Process a single PDF file with OCR"""
    filename = os.path.basename(pdf_path)
    book_name = os.path.splitext(filename)[0]
    book_name_clean = book_name[:50] + "..." if len(book_name) > 50 else book_name
    
    output_content = []
    output_content.append(f"{'='*60}")
    output_content.append(f"《{book_name_clean}》")
    output_content.append(f"来源: {filename}")
    output_content.append(f"处理方式: OCR图像识别 (DPI={dpi})")
    output_content.append(f"{'='*60}\n")
    
    print(f"\n{'='*50}")
    print(f"Processing with OCR: {book_name_clean}")
    print(f"{'='*50}")
    
    doc = fitz.open(pdf_path)
    total_pages_doc = len(doc)
    total_pages = total_pages_doc if not max_pages else min(max_pages, total_pages_doc)
    
    for page_num in range(total_pages):
        page_start = time.time()
        
        page_header = f"\n{'─'*50}\n[Page {page_num + 1}/{total_pages_doc}]"
        
        try:
            ocr_results = ocr_page_with_eastocr(doc, page_num, reader, dpi)
            page_text = '\n'.join(ocr_results)
            
            if not page_text.strip():
                page_text = "[OCR detected no text on this page]"
        except Exception as e:
            page_text = f"[OCR Error: {str(e)}]"
        
        output_content.append(f"{page_header}\n{'─'*50}")
        output_content.append(page_text)
        
        elapsed = time.time() - page_start
        print(f"  Page {page_num + 1}/{total_pages_doc} done - Time: {elapsed:.1f}s")
    
    doc.close()
    
    # Save results
    os.makedirs(output_dir, exist_ok=True)
    safe_name = book_name[:40].strip()
    output_file = os.path.join(output_dir, f"{safe_name}_OCR.txt")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_content))
    
    print(f"\nResult saved to: {output_file}")
    return output_file

def main():
    pdf_files = [
        r"C:\竞赛helper\不等式的秘密第1卷第2版 [（越）范建熊 著] 2014年版.pdf",
        r"C:\竞赛helper\不等式的秘密  第2卷 [（越南）范建熊著；隋振林译][哈尔滨工业大学出版社][2014.01][215页].pdf"
    ]
    
    output_dir = r"C:\竞赛helper\OCR结果"
    
    for pdf_file in pdf_files:
        if os.path.exists(pdf_file):
            result = process_pdf_with_ocr(pdf_file, output_dir, dpi=200)
        else:
            print(f"File not found: {pdf_file}")
    
    print(f"\n{'='*50}")
    print("OCR processing completed!")

if __name__ == "__main__":
    main()
