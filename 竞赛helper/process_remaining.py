# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import fitz
import os
import time

def extract_text_from_page(doc, page_num):
    """Try to extract embedded text from PDF page"""
    page = doc[page_num]
    text = page.get_text()
    return text.strip()

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
    total_pages_doc = len(doc)
    total_pages = total_pages_doc
    
    if max_pages and max_pages < total_pages:
        total_pages = max_pages
    
    for page_num in range(total_pages):
        page_start = time.time()
        
        # Extract embedded text
        embedded_text = extract_text_from_page(doc, page_num)
        
        page_header = f"\n{'─'*50}\n[Page {page_num + 1}/{total_pages_doc}]"
        
        output_content.append(f"{page_header}\n{'─'*50}")
        output_content.append(embedded_text if embedded_text else "[No text on this page]")
        
        elapsed = time.time() - page_start
        if (page_num + 1) % 10 == 0 or page_num == 0:
            print(f"  Page {page_num + 1}/{total_pages_doc} done - Time: {elapsed:.2f}s")
    
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
    # Remaining PDF files to process
    pdf_files = [
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
    print("Remaining books processing completed!")
    print(f"Output directory: {output_dir}")
    print(f"Files processed: {len(processed_files)}")

if __name__ == "__main__":
    main()
