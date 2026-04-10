import os
from pathlib import Path
import pypdfium2 as pdfium
from PIL import Image
import time

# Find all PDFs and print them sorted by size
pdfs = sorted(
    [p for p in Path('.').glob('*.pdf')],
    key=lambda x: x.stat().st_size
)
print("PDFs found:")
for i, p in enumerate(pdfs):
    mb = p.stat().st_size / (1024*1024)
    print(f"  [{i}] {p.name} ({mb:.0f}MB)")

# Use the one that's ~31MB (book 1)
# Index should match one of the larger files
# [0] sample_5_pages.pdf (small)
# [1] something ~21-23MB  (blue book)  
# [2] something ~23MB     (blue book)
# [3] something ~31MB     (book 1)
# [4] something ~33MB     (book 2)

for p in pdfs:
    mb = p.stat().st_size / (1024*1024)
    if 30 <= mb <= 32:
        pdf_path = p
        print(f"\nUsing: {p.name} ({mb:.0f}MB)")
        break
else:
    print("\nERROR: could not find 30-32MB PDF. Using largest instead.")
    pdf_path = pdfs[-1]
    print(f"Using: {pdf_path.name} ({pdf_path.stat().st_size/(1024*1024):.0f}MB)")

output_dir = Path("test_20_pages")
output_dir.mkdir(exist_ok=True)

start = time.time()
pdf = pdfium.PdfDocument(str(pdf_path))
total = len(pdf)
print(f"Total pages: {total}")

# Convert pages 40-59 (20 pages)
page_nums = list(range(40, 60))
print(f"Converting pages: {page_nums}")

count = 0
size_total = 0
for pnum in page_nums:
    idx = pnum - 1
    if idx >= total:
        print(f"  Skipped page {pnum} (exceeds total {total})")
        continue
    page = pdf[idx]
    img = page.render(scale=200/72).to_pil()
    out_path = output_dir / f"page-{pnum:03d}.jpg"
    img.save(str(out_path), "JPEG", quality=90)
    count += 1
    size_total += out_path.stat().st_size
    if count % 5 == 0:
        print(f"  Converted {count} pages...")

pdf.close()
elapsed = time.time() - start

print(f"\nConverted {count} images in {elapsed:.1f}s")
print(f"Total size: {size_total/1024/1024:.1f}MB")
print(f"Average per page: {elapsed/count:.2f}s, {size_total/count/1024:.0f}KB")
print(f"Output: {output_dir}")
