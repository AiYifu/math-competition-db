#!/usr/bin/env python3
"""Convert PDF pages to JPEG images for OCR/AI extraction."""

import argparse
from pathlib import Path
import pypdfium2 as pdfium
from PIL import Image


def main():
    parser = argparse.ArgumentParser(description="PDF to JPEG converter")
    parser.add_argument("pdf", type=Path, help="Input PDF file")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory (default: pdf_name_pages)")
    parser.add_argument("--dpi", type=float, default=200.0, help="DPI for rendering (default: 200)")
    parser.add_argument("--pages", default="", help='Page range, e.g. "1-20" or "1,3,5-10"')
    parser.add_argument("--prefix", default="page-", help="Filename prefix (default: page-)")
    parser.add_argument("--quality", type=int, default=90, help="JPEG quality 1-100 (default: 90)")
    parser.add_argument("--start", type=int, default=1, help="Start page")
    parser.add_argument("--end", type=int, default=0, help="End page (0 = all)")
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"Error: {args.pdf} not found")
        return 1

    # Setup output directory
    if args.output_dir is None:
        args.output_dir = Path(f"{args.pdf.stem}_pages")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Parse pages
    if args.pages:
        selected = set()
        for part in args.pages.split(","):
            part = part.strip()
            if "-" in part:
                s, e = part.split("-", 1)
                selected.update(range(int(s), int(e) + 1))
            else:
                selected.add(int(part))
        pages_to_process = sorted(selected)
    else:
        pages_to_process = list(range(args.start, args.end or 9999))

    # Convert
    print(f"PDF: {args.pdf.name}")
    print(f"Output: {args.output_dir}")
    print(f"DPI: {args.dpi}")

    pdf = pdfium.PdfDocument(str(args.pdf))
    total_pages = len(pdf)

    if not pages_to_process:
        pages_to_process = list(range(1, total_pages + 1))

    # Filter valid pages
    pages_to_process = [p for p in pages_to_process if 1 <= p <= total_pages]
    print(f"Pages to convert: {len(pages_to_process)} (total PDF pages: {total_pages})")

    count = 0
    for page_num in pages_to_process:
        idx = page_num - 1
        page = pdf[idx]
        img = page.render(scale=args.dpi / 72).to_pil()
        if img.mode != "RGB":
            img = img.convert("RGB")

        out_path = args.output_dir / f"{args.prefix}{page_num:03d}.jpg"
        img.save(str(out_path), "JPEG", quality=args.quality)
        count += 1

        if count % 10 == 0:
            print(f"  Converted: {count}/{len(pages_to_process)}")

    pdf.close()
    print(f"\nDone! {count} images saved to {args.output_dir}")
    print(f"  Total size: {sum(p.stat().st_size for p in args.output_dir.glob('*.jpg')) / 1024 / 1024:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
