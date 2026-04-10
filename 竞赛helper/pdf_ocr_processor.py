# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import fitz
import os
import easyocr
import time

# Initialize EasyOCR (Chinese and English)
print("Loading OCR model, please wait...")
reader = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)

def extract_text_from_page(doc, page_num):
    """Try to extract embedded text from PDF page"""
    page = doc[page_num]
    text = page.get_text()
    return text.strip()

def ocr_page(doc, page_num, reader, dpi=200):
    """Render PDF page to image and perform OCR"""
    page = doc[page_num]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    
    # Convert to bytes and process with EasyOCR
    img_bytes = pix.tobytes("png")
    
    # OCR from bytes
    import numpy as np
    import cv2
    
    # Convert PNG bytes to image
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # Perform OCR
    result = reader.readtext(img, paragraph=True)
    
    # Extract text
    texts = []
    for line in result:
        if line and len(line) >= 2:
            text_content = line[1]
            confidence = line[2]
            y_pos = line[0][0][1] if len(line[0]) > 0 else 0
            texts.append((y_pos, text_content, confidence))
    
    # Sort by y position
    texts.sort(key=lambda x: x[0])
    
    return [t[1] for t in texts]

def process_pdf(pdf_path, output_dir, max_pages=None):
    """Process a single PDF file"""
    filename = os.path.basename(pdf_path)
    book_name = os.path.splitext(filename)[0]
    # Clean up the filename for display
    book_name_clean = book_name[:50] + "..." if len(book_name) > 50 else book_name
    
    # Create output header
    output_content = []
    output_content.append(f"{'='*60}")
    output_content.append(f"《{book_name_clean}》")
    output_content.append(f"来源: {filename}")
    output_content.append(f"{'='*60}\n")
    
    print(f"\n{'='*50}")
    print(f"Processing: {book_name_clean}")
    print(f"{'='*50}")
    
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    
    if max_pages and max_pages < total_pages:
        total_pages = max_pages
    
    for page_num in range(total_pages):
        page_start = time.time()
        
        # First try to extract embedded text
        embedded_text = extract_text_from_page(doc, page_num)
        
        page_header = f"\n{'─'*50}\n[Page {page_num + 1}/{len(doc)}]"
        
        if embedded_text and len(embedded_text.strip()) > 100:
            # If embedded text is substantial, use it
            page_text = embedded_text
            method = "Extracted Text"
        else:
            # Otherwise use OCR
            try:
                ocr_results = ocr_page(doc, page_num, reader)
                page_text = '\n'.join(ocr_results)
                method = "OCR"
            except Exception as e:
                page_text = f"[OCR Error on page {page_num + 1}: {str(e)}]"
                method = "Error"
        
        output_content.append(f"{page_header} ({method})\n{'─'*50}")
        output_content.append(page_text)
        
        elapsed = time.time() - page_start
        print(f"  Page {page_num + 1}/{len(doc)} done ({method}) - Time: {elapsed:.1f}s")
    
    doc.close()
    
    # Save results
    os.makedirs(output_dir, exist_ok=True)
    # Create a safe filename
    safe_name = book_name[:40].strip()
    output_file = os.path.join(output_dir, f"{safe_name}.txt")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_content))
    
    print(f"\nResult saved to: {output_file}")
    return output_file

def main():
    # PDF files (fixed path)
    pdf_files = [
        r"C:\竞赛helper\小蓝本高中卷9 不等式的解题与技巧.pdf",
        r"C:\竞赛helper\小蓝本高中卷4 均值不等式与柯西不等式.pdf",
        r"C:\竞赛helper\不等式的秘密第1卷第2版 [（越）范建熊 著] 2014年版.pdf",
        r"C:\竞赛helper\不等式的秘密  第2卷 [（越南）范建熊著；隋振林译][哈尔滨工业大学出版社][2014.01][215页].pdf"
    ]
    
    # Output directory
    output_dir = r"C:\竞赛helper\OCR结果"
    
    processed_files = []
    
    for pdf_file in pdf_files:
        if os.path.exists(pdf_file):
            result = process_pdf(pdf_file, output_dir)
            processed_files.append(result)
        else:
            print(f"File not found: {pdf_file}")
    
    print(f"\n{'='*50}")
    print("All processing completed!")
    print(f"Output directory: {output_dir}")
    print(f"Files processed: {len(processed_files)}")

if __name__ == "__main__":
    main()
