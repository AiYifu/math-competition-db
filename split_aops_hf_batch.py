import json
import hashlib
import os
from pathlib import Path
import pyarrow.parquet as pq

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "problem_database" / "datasets" / "aops_hf_split"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FILES_PER_DIR = 1000

def to_list(val):
    if val is None:
        return []
    if hasattr(val, 'tolist'):
        return val.tolist()
    if isinstance(val, (list, tuple)):
        return list(val)
    return [val]

def to_native(val):
    if val is None:
        return None
    if hasattr(val, 'item'):
        return val.item()
    return val

def generate_uid(idx, contest=""):
    content = f"aops_hf_{contest}_{idx}"
    return hashlib.md5(content.encode()).hexdigest()[:12]

def convert_problem(problem, idx):
    tags = problem.get('tags', [])
    contest = "Unknown"
    year = None
    
    if tags is not None and len(tags) > 0:
        for tag in tags:
            tag_str = str(tag)
            for c in ['AIME', 'IMO', 'USAMO', 'Putnam', 'BMO', 'APMO', 'IMO Shortlist']:
                if c in tag_str:
                    contest = c
                    break
            import re
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', tag_str)
            if year_match:
                year = int(year_match.group(1))
                break
    
    metadata = problem.get('metadata', {})
    if not isinstance(metadata, dict):
        metadata = {}
    
    uid = generate_uid(idx, contest)
    
    return {
        "uid": f"aops_hf_{idx:05d}_{uid}",
        "source": "aops_hf",
        "contest": contest,
        "year": year,
        "problem_num": idx,
        "stem_md": str(problem.get('problem', '')),
        "solution_md": str(problem.get('solution', '')),
        "answer_md": "",
        "hints_md": "",
        "source_url": f"aops://metadata/{metadata.get('path', '')}",
        "tags": to_list(tags),
        "confidence": "high" if problem.get('solution') else "low",
        "is_incomplete": not problem.get('solution'),
        "metadata": {
            "candidates": to_list(problem.get('candidates', [])),
            "answer_score": to_native(metadata.get('answer_score')),
            "boxed": to_native(metadata.get('boxed')),
            "end_of_proof": to_native(metadata.get('end_of_proof')),
            "n_reply": to_native(metadata.get('n_reply')),
            "original_path": metadata.get('path', '')
        }
    }

def main():
    print("Reading aops_hf dataset...")
    
    parquet_path = BASE_DIR / "竞赛helper" / "datasets" / "aops_hf" / "data" / "train-00000-of-00001.parquet"
    
    print(f"Reading from parquet: {parquet_path}")
    table = pq.read_table(parquet_path)
    df = table.to_pandas()
    total = len(df)
    print(f"Total problems: {total}")
    
    batch = []
    batch_idx = 0
    file_idx = 0
    
    for idx, row in df.iterrows():
        problem = convert_problem(dict(row), idx)
        batch.append(problem)
        
        if len(batch) >= FILES_PER_DIR:
            dir_name = f"batch_{batch_idx:04d}"
            dir_path = OUTPUT_DIR / dir_name
            dir_path.mkdir(exist_ok=True)
            
            batch_file = dir_path / "problems.json"
            with open(batch_file, 'w', encoding='utf-8') as f:
                json.dump(batch, f, ensure_ascii=False, indent=2)
            
            file_idx += len(batch)
            print(f"Saved batch {batch_idx:04d}: {len(batch)} problems (total: {file_idx})")
            
            batch = []
            batch_idx += 1
    
    if batch:
        dir_name = f"batch_{batch_idx:04d}"
        dir_path = OUTPUT_DIR / dir_name
        dir_path.mkdir(exist_ok=True)
        
        batch_file = dir_path / "problems.json"
        with open(batch_file, 'w', encoding='utf-8') as f:
            json.dump(batch, f, ensure_ascii=False, indent=2)
        
        file_idx += len(batch)
        print(f"Saved batch {batch_idx:04d}: {len(batch)} problems (total: {file_idx})")
    
    summary = {
        "total": total,
        "batches": batch_idx + 1,
        "files_per_batch": FILES_PER_DIR,
        "source": "https://huggingface.co/datasets/AI-MO/aops"
    }
    
    with open(OUTPUT_DIR / "summary.json", 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\nDone! Saved {total} problems in {batch_idx + 1} batches to {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
