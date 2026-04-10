import json
import hashlib
import os
from pathlib import Path
import pyarrow.parquet as pq

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "problem_database" / "datasets" / "aops_hf_problems"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def generate_uid(idx, contest=""):
    content = f"aops_hf_{contest}_{idx}"
    return hashlib.md5(content.encode()).hexdigest()[:12]

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
    
    if not parquet_path.exists():
        parquet_path = BASE_DIR / "problem_database" / "datasets" / "aops_hf.parquet"
    
    if parquet_path.exists():
        print(f"Reading from parquet: {parquet_path}")
        table = pq.read_table(parquet_path)
        df = table.to_pandas()
        total = len(df)
        print(f"Total problems: {total}")
        
        for idx, row in df.iterrows():
            problem = convert_problem(dict(row), idx)
            
            filename = f"p{idx:05d}_{problem['contest']}_{problem['uid'].split('_')[-1]}.json"
            filepath = OUTPUT_DIR / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(problem, f, ensure_ascii=False, indent=2)
            
            if (idx + 1) % 10000 == 0:
                print(f"Processed {idx + 1}/{total} problems...")
        
        print(f"Done! Saved {total} problems to {OUTPUT_DIR}")
    else:
        json_path = BASE_DIR / "竞赛helper" / "datasets" / "aops_hf.json"
        if json_path.exists():
            print(f"Reading from JSON: {json_path}")
            with open(json_path, 'r', encoding='utf-8') as f:
                problems = json.load(f)
            
            total = len(problems)
            print(f"Total problems: {total}")
            
            for idx, problem in enumerate(problems):
                converted = convert_problem(problem, idx)
                
                filename = f"p{idx:05d}_{converted['contest']}_{converted['uid'].split('_')[-1]}.json"
                filepath = OUTPUT_DIR / filename
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(converted, f, ensure_ascii=False, indent=2)
                
                if (idx + 1) % 10000 == 0:
                    print(f"Processed {idx + 1}/{total} problems...")
            
            print(f"Done! Saved {total} problems to {OUTPUT_DIR}")
        else:
            print("No aops_hf data found!")

if __name__ == "__main__":
    main()
