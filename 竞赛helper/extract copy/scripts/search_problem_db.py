#!/usr/bin/env python3
"""Search extracted problem DB (SQLite/FTS5)."""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search problems.db with FTS5.")
    parser.add_argument("query", help='FTS query, e.g. "柯西 不等式" or "problem_id:例1.2"')
    parser.add_argument("--db", type=Path, default=Path("output/kimi_problem_db/problems.db"), help="Path to SQLite DB.")
    parser.add_argument("--limit", type=int, default=10, help="Max rows to print.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row

    sql = """
    SELECT
      p.uid,
      p.problem_id,
      p.problem_type,
      p.chapter,
      p.section,
      p.source_pages_json,
      p.stem_md,
      p.solution_md,
      bm25(problems_fts) AS score
    FROM problems_fts
    JOIN problems AS p ON p.uid = problems_fts.uid
    WHERE problems_fts MATCH ?
    ORDER BY score
    LIMIT ?
    """

    rows = conn.execute(sql, (args.query, args.limit)).fetchall()
    fallback_mode = False

    if not rows:
        terms = [term for term in re.split(r"\s+", args.query.strip()) if term]
        if terms:
            term_clauses = []
            params = []
            for term in terms:
                like = f"%{term}%"
                term_clauses.append(
                    "("
                    "COALESCE(problem_id,'') LIKE ? OR "
                    "COALESCE(chapter,'') LIKE ? OR "
                    "COALESCE(section,'') LIKE ? OR "
                    "COALESCE(title,'') LIKE ? OR "
                    "COALESCE(stem_md,'') LIKE ? OR "
                    "COALESCE(solution_md,'') LIKE ? OR "
                    "COALESCE(answer_md,'') LIKE ? OR "
                    "COALESCE(hints_md,'') LIKE ?"
                    ")"
                )
                params.extend([like] * 8)
            like_sql = (
                "SELECT uid, problem_id, problem_type, chapter, section, source_pages_json, stem_md, solution_md, 0.0 AS score "
                "FROM problems WHERE "
                + " AND ".join(term_clauses)
                + " LIMIT ?"
            )
            params.append(args.limit)
            rows = conn.execute(like_sql, tuple(params)).fetchall()
            fallback_mode = bool(rows)

    conn.close()

    if not rows:
        print("No matches.")
        return 0

    if fallback_mode:
        print("[fallback] FTS 未命中，已使用 LIKE 子串检索。")

    for row in rows:
        stem_preview = (row["stem_md"] or "").replace("\n", " ").strip()[:160]
        print("=" * 80)
        print(f"uid: {row['uid']}")
        print(f"problem_id: {row['problem_id']}")
        print(f"type: {row['problem_type']}")
        print(f"chapter/section: {row['chapter']} / {row['section']}")
        print(f"source_pages: {row['source_pages_json']}")
        print(f"score: {row['score']:.4f}")
        print(f"stem: {stem_preview}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
