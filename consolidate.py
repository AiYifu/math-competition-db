import json
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "problem_database"

def consolidate_books():
    books_dir = OUTPUT_DIR / "books"
    
    sources = [
        ("volume1", BASE_DIR / "竞赛helper" / "problems"),
        ("volume2", BASE_DIR / "竞赛helper" / "output" / "secret2" / "problems"),
        ("tip4", BASE_DIR / "竞赛helper" / "output" / "tip4" / "problems"),
        ("tip9", BASE_DIR / "竞赛helper" / "output" / "tip9" / "problems"),
    ]
    
    for name, src_dir in sources:
        if src_dir.exists():
            dst_dir = books_dir / name
            dst_dir.mkdir(exist_ok=True)
            count = 0
            for f in src_dir.glob("*.json"):
                shutil.copy2(f, dst_dir / f.name)
                count += 1
            print(f"Books/{name}: {count} problems")
    
    all_problems = []
    for subdir in books_dir.iterdir():
        if subdir.is_dir():
            for f in subdir.glob("*.json"):
                with open(f, 'r', encoding='utf-8') as fp:
                    all_problems.append(json.load(fp))
    
    with open(books_dir / "all_books.json", 'w', encoding='utf-8') as f:
        json.dump(all_problems, f, ensure_ascii=False, indent=2)
    print(f"Books total: {len(all_problems)} problems")

def consolidate_aops():
    aops_dir = OUTPUT_DIR / "aops"
    
    src_files = [
        ("imo", BASE_DIR / "竞赛helper" / "aops_contests" / "imo_all.json"),
        ("cmo", BASE_DIR / "竞赛helper" / "aops_contests" / "cmo_all.json"),
    ]
    
    for name, src_file in src_files:
        if src_file.exists():
            dst_file = aops_dir / f"{name}.json"
            shutil.copy2(src_file, dst_file)
            
            with open(src_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                count = len(data.get('problems', []))
            print(f"AoPS/{name}: {count} problems")
    
    all_problems = []
    for f in aops_dir.glob("*.json"):
        if f.name != "all_aops.json":
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                problems = data.get('problems', [])
                for p in problems:
                    p['source_file'] = f.stem
                all_problems.extend(problems)
    
    with open(aops_dir / "all_aops.json", 'w', encoding='utf-8') as f:
        json.dump({"total": len(all_problems), "problems": all_problems}, f, ensure_ascii=False, indent=2)
    print(f"AoPS total: {len(all_problems)} problems")

def consolidate_datasets():
    datasets_dir = OUTPUT_DIR / "datasets"
    
    src_files = [
        ("aops_hf", BASE_DIR / "竞赛helper" / "datasets" / "aops_hf.json"),
        ("olympiadbench", BASE_DIR / "竞赛helper" / "datasets" / "olympiadbench.json"),
    ]
    
    for name, src_file in src_files:
        if src_file.exists():
            dst_file = datasets_dir / f"{name}.json"
            shutil.copy2(src_file, dst_file)
            
            with open(src_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                count = len(data) if isinstance(data, list) else 0
            print(f"Datasets/{name}: {count} problems")
    
    total = 0
    for f in datasets_dir.glob("*.json"):
        if f.name != "all_datasets.json":
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                total += len(data) if isinstance(data, list) else 0
    
    with open(datasets_dir / "README.md", 'w', encoding='utf-8') as f:
        f.write("# Large Datasets\n\n")
        f.write("- `aops_hf.json` - 80,661 problems from AI-MO/aops\n")
        f.write("- `olympiadbench.json` - 7,430 problems from OlympiadBench\n")
    print(f"Datasets total: ~{total} problems")

def create_index():
    index = {
        "description": "Math Competition Problem Database",
        "structure": {
            "books/": "Problems extracted from PDF books",
            "aops/": "Problems crawled from AoPS Wiki",
            "datasets/": "Large datasets from HuggingFace"
        },
        "counts": {}
    }
    
    books_count = len(list((OUTPUT_DIR / "books").glob("**/*.json"))) - 1
    aops_file = OUTPUT_DIR / "aops" / "all_aops.json"
    datasets_dir = OUTPUT_DIR / "datasets"
    
    if aops_file.exists():
        with open(aops_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            index["counts"]["aops"] = data.get("total", 0)
    
    index["counts"]["books"] = books_count
    
    with open(OUTPUT_DIR / "index.json", 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    
    readme = """# Math Competition Problem Database

A collection of math competition problems from various sources.

## Structure

```
problem_database/
├── books/          # Problems extracted from PDF books
│   ├── volume1/    # 不等式的秘密 第1卷 (309 problems)
│   ├── volume2/    # 不等式的秘密 第2卷 (113 problems)
│   ├── tip4/       # 小蓝本 卷4 (134 problems)
│   ├── tip9/       # 小蓝本 卷9 (102 problems)
│   └── all_books.json
├── aops/           # Problems from AoPS Wiki
│   ├── imo.json    # IMO problems (384)
│   ├── cmo.json    # CMO problems (8)
│   └── all_aops.json
├── datasets/       # Large datasets
│   ├── aops_hf.json         # 80,661 problems (344MB)
│   └── olympiadbench.json   # 7,430 problems (16MB)
└── index.json
```

## Total: ~89,000+ problems

## Sources

- **Books**: 不等式的秘密, 小蓝本
- **AoPS Wiki**: https://artofproblemsolving.com/wiki/
- **AI-MO/aops**: https://huggingface.co/datasets/AI-MO/aops
- **OlympiadBench**: https://huggingface.co/datasets/Hothan/OlympiadBench
"""
    
    with open(OUTPUT_DIR / "README.md", 'w', encoding='utf-8') as f:
        f.write(readme)

def main():
    print("=" * 50)
    print("Consolidating all problems...")
    print("=" * 50)
    
    consolidate_books()
    print()
    consolidate_aops()
    print()
    consolidate_datasets()
    print()
    create_index()
    
    print("=" * 50)
    print("Done! Problems consolidated in problem_database/")

if __name__ == "__main__":
    main()
