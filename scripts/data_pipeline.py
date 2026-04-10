import json
import os
from pathlib import Path
from typing import List, Dict
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.models.problem import Problem

def load_books_problems() -> List[Problem]:
    """加载书籍题目"""
    books_dir = Path("../problem_database/books")
    problems = []
    
    if not books_dir.exists():
        print(f"Warning: {books_dir} not found")
        return problems
    
    for json_file in books_dir.rglob("*.json"):
        if json_file.name == "all_books.json":
            continue
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 转换为统一格式
                problem = Problem(
                    uid=data.get('uid', str(json_file.stem)),
                    source="books",
                    source_id=data.get('problem_id', ''),
                    stem=data.get('stem_md', ''),
                    solution=data.get('solution_md', ''),
                    answer=data.get('answer_md', ''),
                    metadata={
                        'book_title': data.get('book_title', ''),
                        'chapter': data.get('chapter', ''),
                        'section': data.get('section', ''),
                        'tags': data.get('tags', [])
                    }
                )
                problems.append(problem)
        except Exception as e:
            print(f"Error loading {json_file}: {e}")
    
    return problems

def load_aops_problems() -> List[Problem]:
    """加载AoPS题目"""
    aops_file = Path("../problem_database/aops/all_aops.json")
    problems = []
    
    if not aops_file.exists():
        print(f"Warning: {aops_file} not found")
        return problems
    
    try:
        with open(aops_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for p in data.get('problems', []):
                problem = Problem(
                    uid=f"aops_{p.get('contest')}_{p.get('year')}_{p.get('problem_num')}",
                    source="aops",
                    source_id=str(p.get('problem_num', '')),
                    stem=p.get('statement', ''),
                    solution=p.get('solution', ''),
                    metadata={
                        'contest': p.get('contest', ''),
                        'year': p.get('year', ''),
                        'source_url': p.get('source_url', '')
                    }
                )
                problems.append(problem)
    except Exception as e:
        print(f"Error loading AoPS: {e}")
    
    return problems

def unify_all_problems():
    """统一所有题目格式"""
    print("Loading problems...")
    
    books_problems = load_books_problems()
    print(f"Books: {len(books_problems)} problems")
    
    aops_problems = load_aops_problems()
    print(f"AoPS: {len(aops_problems)} problems")
    
    all_problems = books_problems + aops_problems
    
    # 保存
    output_dir = Path("../data/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "unified_problems.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump([p.model_dump() for p in all_problems], f, ensure_ascii=False, indent=2)
    
    print(f"Saved {len(all_problems)} problems to {output_file}")
    return all_problems

if __name__ == "__main__":
    unify_all_problems()