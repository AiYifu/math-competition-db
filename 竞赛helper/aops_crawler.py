#!/usr/bin/env python3
"""
AoPS Wiki Contest Problems Crawler
通过MediaWiki API爬取AoPS Wiki上的竞赛题目

支持的竞赛：
- AMC 8/10/12
- AIME
- USAJMO/USAMO
- IMO
- 其他竞赛
"""

import requests
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import html

WIKI_API = "https://artofproblemsolving.com/wiki/api.php"
OUTPUT_DIR = Path("aops_problems")

@dataclass
class Problem:
    contest: str
    year: int
    round: str  # I, II, etc.
    problem_num: int
    statement: str
    solution: str
    answer: str
    source_url: str
    
    def to_dict(self):
        return {
            "contest": self.contest,
            "year": self.year,
            "round": self.round,
            "problem_num": self.problem_num,
            "statement": self.statement,
            "solution": self.solution,
            "answer": self.answer,
            "source_url": self.source_url,
        }


def wiki_query(params: dict, retries=3) -> Optional[dict]:
    """查询MediaWiki API"""
    params['format'] = 'json'
    params['formatversion'] = 2
    
    for attempt in range(retries):
        try:
            resp = requests.get(WIKI_API, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"API query failed: {e}")
                return None


def get_page_content(title: str, follow_redirects: bool = True) -> Optional[str]:
    """获取Wiki页面原始内容，支持跟踪重定向"""
    result = wiki_query({
        'action': 'query',
        'prop': 'revisions',
        'rvprop': 'content',
        'titles': title,
        'redirects': 'true' if follow_redirects else 'false',
    })
    
    if result and 'query' in result and 'pages' in result['query']:
        pages = result['query']['pages']
        if pages and len(pages) > 0:
            page = pages[0]
            
            # Check for redirect in content
            if 'revisions' in page and len(page['revisions']) > 0:
                content = page['revisions'][0]['content']
                
                # Handle #redirect
                redirect_match = re.match(r'#redirect\s*\[\[([^\]]+)\]\]', content, re.IGNORECASE)
                if redirect_match and follow_redirects:
                    redirect_title = redirect_match.group(1)
                    print(f"    Redirect: {title} -> {redirect_title}")
                    return get_page_content(redirect_title, follow_redirects=False)
                
                return content
    
    return None


def get_category_members(category: str, limit: int = 500) -> List[str]:
    """获取分类下的所有页面"""
    members = []
    params = {
        'action': 'query',
        'list': 'categorymembers',
        'cmtitle': f'Category:{category}',
        'cmlimit': limit,
    }
    
    while True:
        result = wiki_query(params)
        if not result or 'query' not in result:
            break
            
        items = result['query'].get('categorymembers', [])
        for item in items:
            members.append(item['title'])
        
        if 'continue' in result:
            params['cmcontinue'] = result['continue']['cmcontinue']
        else:
            break
    
    return members


def parse_latex(text: str) -> str:
    """处理LaTeX公式，转换为标准格式"""
    # AoPS uses <math>...</math> tags
    text = re.sub(r'<math>(.*?)</math>', r'$\1$', text, flags=re.DOTALL)
    # Clean up extra whitespace
    text = re.sub(r'\$\s+', r'$', text)
    text = re.sub(r'\s+\$', r'$', text)
    return text


def parse_problem_page(title: str, content: str) -> Optional[Problem]:
    """解析题目页面"""
    # Expected title format: "2024 AMC 12A Problems/Problem 1"
    # or "2024 AIME I Problems/Problem 1"
    
    match = re.match(r'(\d{4})\s+(AMC\s*\d+[AB]?|AIME\s*[I]+|USAMO|USAJMO|IMO)\s+Problems(?:/\s*(?:Problem|P)\s*(\d+))?', title, re.IGNORECASE)
    
    if not match:
        return None
    
    year = int(match.group(1))
    contest = match.group(2).upper()
    problem_num = int(match.group(3)) if match.group(3) else 0
    
    # Determine round
    round_name = ""
    if "AIME I" in contest or "AIMEI" in contest:
        round_name = "I"
    elif "AIME II" in contest or "AIMEII" in contest:
        round_name = "II"
    elif "A" in contest[-1]:
        round_name = "A"
    elif "B" in contest[-1]:
        round_name = "B"
    
    # Extract problem statement
    # Typically after ==Problem== header
    statement = ""
    solution = ""
    answer = ""
    
    # Try to extract sections
    sections = re.split(r'==+\s*(.*?)\s*==+', content)
    
    current_section = ""
    for i, section in enumerate(sections):
        if i % 2 == 0:  # Content
            if current_section.lower() == 'problem':
                statement = section.strip()
            elif current_section.lower() in ('solution', 'solutions'):
                solution = section.strip()
            elif current_section.lower() == 'answer':
                answer = section.strip()
        else:  # Header
            current_section = section
    
    # Clean up
    statement = parse_latex(statement)
    solution = parse_latex(solution)
    
    # Remove wiki markup
    statement = re.sub(r'\[\[([^\]|]+\|)?([^\]]+)\]\]', r'\2', statement)
    solution = re.sub(r'\[\[([^\]|]+\|)?([^\]]+)\]\]', r'\2', solution)
    
    return Problem(
        contest=contest,
        year=year,
        round=round_name,
        problem_num=problem_num,
        statement=statement,
        solution=solution,
        answer=answer,
        source_url=f"https://artofproblemsolving.com/wiki/index.php/{title.replace(' ', '_')}",
    )


def crawl_contest(contest_name: str, start_year: int, end_year: int) -> List[Problem]:
    """爬取某个竞赛的所有题目"""
    problems = []
    
    for year in range(start_year, end_year + 1):
        print(f"  Processing {year} {contest_name}...")
        
        # Try different round patterns
        rounds = ['A', 'B'] if 'AMC' in contest_name else ['I', 'II']
        
        for round_name in rounds:
            # Build page title
            if 'AMC' in contest_name:
                # AMC 10A, AMC 10B, AMC 12A, AMC 12B
                for amc_level in ['10', '12']:
                    title = f"{year} AMC {amc_level}{round_name} Problems"
                    content = get_page_content(title)
                    if content:
                        # Get individual problems
                        for pnum in range(1, 26):
                            ptitle = f"{title}/Problem {pnum}"
                            pcontent = get_page_content(ptitle)
                            if pcontent:
                                prob = parse_problem_page(ptitle, pcontent)
                                if prob:
                                    problems.append(prob)
                                    print(f"    Found: {ptitle}")
                        time.sleep(0.5)  # Rate limiting
            
            elif 'AIME' in contest_name:
                title = f"{year} AIME {round_name} Problems"
                content = get_page_content(title)
                if content:
                    for pnum in range(1, 16):
                        ptitle = f"{title}/Problem {pnum}"
                        pcontent = get_page_content(ptitle)
                        if pcontent:
                            prob = parse_problem_page(ptitle, pcontent)
                            if prob:
                                problems.append(prob)
                                print(f"    Found: {ptitle}")
                        time.sleep(0.3)
            
            time.sleep(0.5)
    
    return problems


def crawl_amc_problems():
    """爬取AMC所有题目"""
    all_problems = []
    
    # AMC 8 (1985-2024)
    print("Crawling AMC 8...")
    problems = crawl_contest("AMC 8", 1985, 2024)
    all_problems.extend(problems)
    
    # AMC 10/12 (2000-2024)
    print("Crawling AMC 10/12...")
    problems = crawl_contest("AMC", 2000, 2024)
    all_problems.extend(problems)
    
    # AIME (1983-2024)
    print("Crawling AIME...")
    problems = crawl_contest("AIME", 1983, 2024)
    all_problems.extend(problems)
    
    return all_problems


def save_problems(problems: List[Problem], filename: str):
    """保存题目到JSON文件"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    filepath = OUTPUT_DIR / filename
    
    data = {
        "total": len(problems),
        "problems": [p.to_dict() for p in problems],
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Saved {len(problems)} problems to {filepath}")


def quick_test():
    """快速测试：获取一道AMC题目"""
    print("Testing: fetching 2024 AMC 12A Problem 1...")
    
    content = get_page_content("2024 AMC 12A Problems/Problem 1")
    if content:
        print("Content preview:")
        print(content[:500])
        print("\n" + "="*50 + "\n")
        
        prob = parse_problem_page("2024 AMC 12A Problems/Problem 1", content)
        if prob:
            print(f"Contest: {prob.contest}")
            print(f"Year: {prob.year}")
            print(f"Statement: {prob.statement[:200]}...")
    else:
        print("Failed to fetch content")


def main():
    import sys
    
    print("AoPS Wiki Contest Problems Crawler")
    print("="*50)
    
    # Parse command line args
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python aops_crawler.py test              - Test single problem")
        print("  python aops_crawler.py amc8               - Crawl AMC 8 (2020-2024)")
        print("  python aops_crawler.py amc10              - Crawl AMC 10 (2020-2024)")
        print("  python aops_crawler.py amc12              - Crawl AMC 12 (2020-2024)")
        print("  python aops_crawler.py aime               - Crawl AIME (2020-2024)")
        print("  python aops_crawler.py YEAR CONTEST       - Crawl specific year/contest")
        print("    Example: python aops_crawler.py 2023 'AMC 12A'")
        return
    
    command = sys.argv[1].lower()
    
    if command == 'test':
        print("\nTesting single problem fetch...")
        quick_test()
    
    elif command == 'amc8':
        print("\nCrawling AMC 8 (2020-2024)...")
        problems = crawl_contest("AMC 8", 2020, 2024)
        save_problems(problems, "amc8_2020_2024.json")
    
    elif command == 'amc10':
        print("\nCrawling AMC 10 (2020-2024)...")
        # AMC 10 has problems 1-25
        all_problems = []
        for year in range(2020, 2025):
            for round_name in ['A', 'B']:
                print(f"  Processing {year} AMC 10{round_name}...")
                for pnum in range(1, 26):
                    title = f"{year} AMC 10{round_name} Problems/Problem {pnum}"
                    content = get_page_content(title)
                    if content and not content.startswith('#redirect'):
                        prob = parse_problem_page(title, content)
                        if prob:
                            all_problems.append(prob)
                            print(f"    Found: Problem {pnum}")
                    time.sleep(0.3)
        save_problems(all_problems, "amc10_2020_2024.json")
    
    elif command == 'amc12':
        print("\nCrawling AMC 12 (2020-2024)...")
        all_problems = []
        for year in range(2020, 2025):
            for round_name in ['A', 'B']:
                print(f"  Processing {year} AMC 12{round_name}...")
                for pnum in range(1, 26):
                    title = f"{year} AMC 12{round_name} Problems/Problem {pnum}"
                    content = get_page_content(title)
                    if content and not content.startswith('#redirect'):
                        prob = parse_problem_page(title, content)
                        if prob:
                            all_problems.append(prob)
                            print(f"    Found: Problem {pnum}")
                    time.sleep(0.3)
        save_problems(all_problems, "amc12_2020_2024.json")
    
    elif command == 'aime':
        print("\nCrawling AIME (2020-2024)...")
        all_problems = []
        for year in range(2020, 2025):
            for round_name in ['I', 'II']:
                print(f"  Processing {year} AIME {round_name}...")
                for pnum in range(1, 16):
                    title = f"{year} AIME {round_name} Problems/Problem {pnum}"
                    content = get_page_content(title)
                    if content:
                        prob = parse_problem_page(title, content)
                        if prob:
                            all_problems.append(prob)
                            print(f"    Found: Problem {pnum}")
                    time.sleep(0.3)
        save_problems(all_problems, "aime_2020_2024.json")
    
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
