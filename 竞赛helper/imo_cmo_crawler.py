#!/usr/bin/env python3
"""
IMO 和 CMO 历史题目爬虫
从 AoPS Wiki 爬取所有 IMO (1959-2024) 和 CMO 题目
"""

import requests
import json
import re
import time
from pathlib import Path
from dataclasses import dataclass, asdict

WIKI_API = "https://artofproblemsolving.com/wiki/api.php"
OUTPUT_DIR = Path("aops_contests")
OUTPUT_DIR.mkdir(exist_ok=True)

RATE_LIMIT_DELAY = 0.3  # 秒，避免请求太快

@dataclass
class Problem:
    contest: str
    year: int
    problem_num: int
    statement: str
    solution: str
    source_url: str


def wiki_query(params: dict) -> dict:
    """查询 MediaWiki API"""
    params['format'] = 'json'
    params['formatversion'] = 2
    
    resp = requests.get(WIKI_API, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_page_content(title: str) -> str:
    """获取页面内容，处理重定向"""
    result = wiki_query({
        'action': 'query',
        'prop': 'revisions',
        'rvprop': 'content',
        'titles': title,
        'redirects': 'true',
    })
    
    pages = result['query']['pages']
    if pages and 'revisions' in pages[0]:
        content = pages[0]['revisions'][0]['content']
        # 处理重定向
        redirect_match = re.match(r'#redirect\s*\[\[([^\]]+)\]\]', content, re.IGNORECASE)
        if redirect_match:
            time.sleep(RATE_LIMIT_DELAY)
            return get_page_content(redirect_match.group(1))
        return content
    return ""


def clean_latex(text: str) -> str:
    """转换 LaTeX 格式"""
    # <math>...</math> → $...$
    text = re.sub(r'<math>(.*?)</math>', r'$\1$', text, flags=re.DOTALL)
    # 清理多余空格
    text = re.sub(r'\$\s+', r'$', text)
    text = re.sub(r'\s+\$', r'$', text)
    return text


def extract_sections(content: str) -> dict:
    """提取 Problem, Solution, Answer 章节"""
    sections = {}
    
    # 切分章节
    parts = re.split(r'^==+\s*([^=]+?)\s*==+', content, flags=re.MULTILINE)
    
    current_section = ""
    for i, part in enumerate(parts):
        if i % 2 == 0:
            # 内容
            section_name = current_section.lower().strip()
            if 'problem' in section_name:
                sections['statement'] = part.strip()
            elif 'solution' in section_name or 'solutions' in section_name:
                sections['solution'] = part.strip()
            elif 'answer' in section_name:
                sections['answer'] = part.strip()
        else:
            # 标题
            current_section = part
    
    return sections


def crawl_imo():
    """爬取所有 IMO 题目 (1959-2024, 2020年停办)"""
    all_problems = []
    years = list(range(1959, 2025))
    years.remove(2020)  # 2020年停办
    
    print("开始爬取 IMO 题目...")
    print(f"年份范围: {years[0]}-{years[-1]}, 共 {len(years)} 年")
    print(f"预计题目数: {len(years) * 6}")
    print()
    
    for year in years:
        print(f"\n[{year} IMO]")
        
        for prob_num in range(1, 7):
            title = f"{year} IMO Problems/Problem {prob_num}"
            url = f"https://artofproblemsolving.com/wiki/index.php/{title.replace(' ', '_')}"
            
            try:
                content = get_page_content(title)
                
                if content:
                    sections = extract_sections(content)
                    
                    statement = clean_latex(sections.get('statement', ''))
                    solution = clean_latex(sections.get('solution', ''))
                    
                    prob = Problem(
                        contest='IMO',
                        year=year,
                        problem_num=prob_num,
                        statement=statement[:2000] if statement else '',
                        solution=solution[:5000] if solution else '',
                        source_url=url
                    )
                    all_problems.append(prob)
                    print(f"  Problem {prob_num}: OK ({len(statement)} chars)")
                else:
                    print(f"  Problem {prob_num}: NOT FOUND")
                
            except Exception as e:
                print(f"  Problem {prob_num}: ERROR - {e}")
            
            time.sleep(RATE_LIMIT_DELAY)
    
    return all_problems


def crawl_cmo():
    """爬取中国数学奥林匹克 (CMO) 题目"""
    all_problems = []
    
    # CMO 年份范围 (大约1986-2024)
    # CMO 冬令营每年举办，通常有6道题
    print("开始爬取 CMO 题目...")
    
    # 先获取CMO总页面确定年份列表
    try:
        cmo_list_page = get_page_content("China_Mathematical_Olympiad")
        # 从页面提取年份链接
        year_links = re.findall(r'\[\[(\d{4})\s*(?:China|CMO|Chinese)', cmo_list_page)
        years = sorted(set(int(y) for y in year_links))
        if not years:
            years = list(range(1986, 2025))
    except:
        years = list(range(1986, 2025))
    
    print(f"年份范围: {years[0]}-{years[-1]}, 共 {len(years)} 年")
    print()
    
    for year in years:
        print(f"\n[{year} CMO]")
        
        for prob_num in range(1, 7):
            # 尝试不同的命名格式
            titles = [
                f"{year} CMO Problems/Problem {prob_num}",
                f"{year} China Mathematical Olympiad Problems/Problem {prob_num}",
                f"{year} Chinese Mathematical Olympiad Problems/Problem {prob_num}",
            ]
            
            for title in titles:
                try:
                    content = get_page_content(title)
                    if content and '#redirect' not in content.lower():
                        url = f"https://artofproblemsolving.com/wiki/index.php/{title.replace(' ', '_')}"
                        sections = extract_sections(content)
                        
                        statement = clean_latex(sections.get('statement', ''))
                        solution = clean_latex(sections.get('solution', ''))
                        
                        prob = Problem(
                            contest='CMO',
                            year=year,
                            problem_num=prob_num,
                            statement=statement[:2000] if statement else '',
                            solution=solution[:5000] if solution else '',
                            source_url=url
                        )
                        all_problems.append(prob)
                        print(f"  Problem {prob_num}: OK")
                        break
                except:
                    continue
                
                time.sleep(RATE_LIMIT_DELAY)
    
    return all_problems


def save_problems(problems: list, filename: str):
    """保存题目"""
    filepath = OUTPUT_DIR / filename
    
    # 转换为 dict
    data = {
        "total": len(problems),
        "contests": list(set(p.contest for p in problems)),
        "years": sorted(list(set(p.year for p in problems))),
        "problems": [asdict(p) for p in problems]
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n保存到: {filepath}")
    print(f"题目数: {len(problems)}")


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  python imo_cmo_crawler.py imo     # 爬取IMO")
        print("  python imo_cmo_crawler.py cmo     # 爬取CMO")
        print("  python imo_cmo_crawler.py all     # 全部爬取")
        return
    
    cmd = sys.argv[1].lower()
    
    if cmd == 'imo':
        problems = crawl_imo()
        save_problems(problems, "imo_all.json")
    
    elif cmd == 'cmo':
        problems = crawl_cmo()
        save_problems(problems, "cmo_all.json")
    
    elif cmd == 'all':
        print("=" * 50)
        print("爬取 IMO")
        print("=" * 50)
        imo_problems = crawl_imo()
        save_problems(imo_problems, "imo_all.json")
        
        print("\n" + "=" * 50)
        print("爬取 CMO")
        print("=" * 50)
        cmo_problems = crawl_cmo()
        save_problems(cmo_problems, "cmo_all.json")
        
        print("\n" + "=" * 50)
        print("全部完成!")
        print(f"IMO: {len(imo_problems)} 题")
        print(f"CMO: {len(cmo_problems)} 题")
        print(f"总计: {len(imo_problems) + len(cmo_problems)} 题")
    
    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    main()
