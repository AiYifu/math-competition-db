#!/usr/bin/env python3
"""Find and process missing chunks."""

import json
from pathlib import Path

BOOKS = {
    "secret2": {"total_chunks": 30, "pages": 233},
    "tip4": {"total_chunks": 29, "pages": 228},
    "tip9": {"total_chunks": 29, "pages": 231},
}

CHUNK_SIZE = 8

def find_missing_chunks(book):
    output_dir = Path("output") / book / "chunks"
    existing = set()
    for f in output_dir.glob("chunk-*.json"):
        try:
            num = int(f.stem.split("-")[1])
            existing.add(num)
        except:
            pass
    
    all_chunks = set(range(1, BOOKS[book]["total_chunks"] + 1))
    missing = sorted(all_chunks - existing)
    
    # Map to page numbers
    pages_missing = []
    for chunk_num in missing:
        start_page = (chunk_num - 1) * CHUNK_SIZE + 1
        end_page = min(chunk_num * CHUNK_SIZE, BOOKS[book]["pages"])
        pages_missing.append((chunk_num, start_page, end_page))
    
    return missing, pages_missing

def main():
    print("Missing chunks analysis:\n")
    print("=" * 70)
    
    all_missing = {}
    
    for book in BOOKS:
        missing, pages = find_missing_chunks(book)
        all_missing[book] = missing
        
        print(f"\n{book}:")
        print(f"  Total chunks: {BOOKS[book]['total_chunks']}")
        print(f"  Missing chunks: {len(missing)}")
        
        if missing:
            print(f"  Missing: {missing}")
            print(f"  Pages affected:")
            for chunk_num, start, end in pages:
                print(f"    chunk-{chunk_num:04d}: pages {start}-{end}")
    
    # Save for processing
    with open("missing_chunks.json", "w") as f:
        json.dump(all_missing, f, indent=2)
    
    print(f"\n{'=' * 70}")
    
    total_missing = sum(len(v) for v in all_missing.values())
    print(f"Total missing chunks: {total_missing}")
    
    # Generate commands
    print("\nTo process missing chunks, run:")
    for book, chunks in all_missing.items():
        if chunks:
            pages_list = []
            for c in chunks:
                start = (c - 1) * CHUNK_SIZE + 1
                end = min(c * CHUNK_SIZE, BOOKS[book]["pages"])
                pages_list.append(f"{start}-{end}")
            pages_arg = ",".join(pages_list)
            print(f"  python extract_concurrent.py --book {book} --pages \"{pages_arg}\" --resume --sleep 30")

if __name__ == "__main__":
    main()
