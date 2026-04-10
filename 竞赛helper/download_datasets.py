import json
import os
import hashlib
import re
from pathlib import Path
import pyarrow.parquet as pq
from datasets import load_dataset

OUTPUT_DIR = Path(__file__).parent / "datasets"
OUTPUT_DIR.mkdir(exist_ok=True)

def generate_uid(source, *args):
    content = "_".join(str(a) for a in args if a is not None)
    return hashlib.md5(content.encode()).hexdigest()[:12]

def clean_latex(text):
    if not text:
        return ""
    return text.strip()

def extract_contest_info(path, tags):
    contest = "Unknown"
    year = None
    
    if tags is not None and len(tags) > 0:
        for tag in tags:
            tag_str = str(tag)
            if "AIME" in tag_str:
                contest = "AIME"
            elif "IMO" in tag_str:
                contest = "IMO"
            elif "USAMO" in tag_str:
                contest = "USAMO"
            elif "IMO Shortlist" in tag_str:
                contest = "IMO Shortlist"
            elif "Putnam" in tag_str:
                contest = "Putnam"
            elif "BMO" in tag_str:
                contest = "BMO"
            elif "APMO" in tag_str:
                contest = "APMO"
            
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', tag_str)
            if year_match:
                year = int(year_match.group(1))
    
    if path:
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', path)
        if year_match and year is None:
            year = int(year_match.group(1))
    
    return contest, year

def process_aops_hf():
    print("Processing AI-MO/aops dataset...")
    
    parquet_path = OUTPUT_DIR / "aops_hf" / "data" / "train-00000-of-00001.parquet"
    
    if not parquet_path.exists():
        print(f"Parquet file not found: {parquet_path}")
        return []
    
    table = pq.read_table(parquet_path)
    df = table.to_pandas()
    
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
    
    print(f"Total rows: {len(df)}")
    
    problems = []
    for idx, row in df.iterrows():
        metadata = row.get('metadata', {})
        if not isinstance(metadata, dict):
            metadata = {}
        path = metadata.get('path', '')
        tags = row.get('tags', [])
        contest, year = extract_contest_info(path, tags)
        
        problem = {
            "uid": generate_uid("aops_hf", idx),
            "source": "aops_hf",
            "contest": contest,
            "year": year,
            "problem_num": idx,
            "stem_md": clean_latex(str(row.get('problem', ''))),
            "solution_md": clean_latex(str(row.get('solution', ''))),
            "answer_md": "",
            "hints_md": "",
            "source_url": f"aops://path/{path}" if path else "",
            "tags": to_list(tags),
            "confidence": "high" if row.get('solution') else "low",
            "is_incomplete": not row.get('solution'),
            "metadata": {
                "candidates": to_list(row.get('candidates', [])),
                "answer_score": to_native(metadata.get('answer_score')),
                "boxed": to_native(metadata.get('boxed')),
                "end_of_proof": to_native(metadata.get('end_of_proof')),
                "n_reply": to_native(metadata.get('n_reply')),
                "original_path": path
            }
        }
        problems.append(problem)
    
    return problems

def download_olympiadbench():
    print("Downloading OlympiadBench from HuggingFace...")
    
    local_dir = OUTPUT_DIR / "olympiadbench_data"
    
    try:
        dataset = load_dataset("Hothan/OlympiadBench", "OE_MM_maths_en_COMP", trust_remote_code=True)
        return dataset, local_dir
    except Exception as e:
        print(f"Error downloading: {e}")
        return None, None

def process_olympiadbench():
    print("Processing OlympiadBench dataset...")
    
    all_problems = []
    configs = [
        "OE_MM_maths_en_COMP",
        "OE_TO_maths_en_COMP", 
        "TP_TO_maths_en_COMP",
        "OE_MM_maths_zh_COMP",
        "OE_TO_maths_zh_COMP",
        "TP_TO_maths_zh_COMP",
        "OE_MM_physics_en_COMP",
        "OE_TO_physics_en_COMP",
        "OE_MM_maths_en_CEE",
        "OE_TO_maths_en_CEE",
        "OE_MM_maths_zh_CEE",
        "OE_TO_maths_zh_CEE",
        "OE_MM_physics_zh_CEE",
        "OE_TO_physics_zh_CEE",
    ]
    
    for config in configs:
        try:
            print(f"Loading config: {config}")
            ds = load_dataset("Hothan/OlympiadBench", config, trust_remote_code=True)
            
            for split in ds.keys():
                print(f"  Processing split: {split}")
                for idx, item in enumerate(ds[split]):
                    contest_type = "CEE" if "CEE" in config else "COMP"
                    subject = "physics" if "physics" in config else "maths"
                    lang = "zh" if "_zh_" in config else "en"
                    
                    problem = {
                        "uid": generate_uid("olympiadbench", config, split, idx),
                        "source": "olympiadbench",
                        "contest": f"{subject}_{contest_type}",
                        "year": None,
                        "problem_num": item.get('id', idx),
                        "stem_md": clean_latex(item.get('question', '')),
                        "solution_md": clean_latex(item.get('solution', [''])[0] if isinstance(item.get('solution'), list) else item.get('solution', '')),
                        "answer_md": clean_latex(item.get('final_answer', [''])[0] if isinstance(item.get('final_answer'), list) else item.get('final_answer', '')),
                        "hints_md": "",
                        "source_url": "",
                        "tags": [item.get('subfield', ''), f"language:{lang}", f"type:{contest_type}"],
                        "confidence": "high",
                        "is_incomplete": not item.get('question'),
                        "metadata": {
                            "config": config,
                            "split": split,
                            "subfield": item.get('subfield'),
                            "context": item.get('context'),
                            "is_multiple_answer": item.get('is_multiple_answer'),
                            "unit": item.get('unit'),
                            "answer_type": item.get('answer_type')
                        }
                    }
                    all_problems.append(problem)
        except Exception as e:
            print(f"Error loading config {config}: {e}")
            continue
    
    return all_problems

def save_problems(problems, filename):
    output_path = OUTPUT_DIR / filename
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(problems, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(problems)} problems to {output_path}")
    
    problems_dir = OUTPUT_DIR / f"{filename.replace('.json', '_problems')}"
    problems_dir.mkdir(exist_ok=True)
    
    batch_size = 1000
    for i in range(0, len(problems), batch_size):
        batch = problems[i:i+batch_size]
        batch_file = problems_dir / f"batch_{i//batch_size:04d}.json"
        with open(batch_file, 'w', encoding='utf-8') as f:
            json.dump(batch, f, ensure_ascii=False, indent=2)
    
    print(f"Saved batch files to {problems_dir}")

def main():
    print("="*50)
    print("Processing datasets")
    print("="*50)
    
    aops_problems = process_aops_hf()
    if aops_problems:
        save_problems(aops_problems, "aops_hf.json")
    
    print("\n" + "="*50)
    
    ob_problems = process_olympiadbench()
    if ob_problems:
        save_problems(ob_problems, "olympiadbench.json")
    
    print("\n" + "="*50)
    print("Summary:")
    print(f"  AoPS: {len(aops_problems)} problems")
    print(f"  OlympiadBench: {len(ob_problems)} problems")
    print(f"  Total: {len(aops_problems) + len(ob_problems)} problems")
    print("Done!")

if __name__ == "__main__":
    main()
