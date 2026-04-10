#!/usr/bin/env python3
"""Batch extract math problems from JPEG pages with Kimi and build a searchable DB.

Lightweight design:
1) Send 8-10 pages per request (default chunk size: 9).
2) Final artifacts are one JSON file per problem.
3) Preserve original text as much as possible (stem/solution/answer/hints/original_text).
4) Keep raw model outputs for future post-processing.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

import requests


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "kimi-k2.5"
DEFAULT_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "kimi_problem_extract_prompt.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract one-JSON-per-problem dataset from page images.")
    parser.add_argument("--input-dir", type=Path, default=Path("data/secret"), help="Directory containing page images.")
    parser.add_argument("--output-dir", type=Path, default=Path("output/kimi_problem_db"), help="Output root directory.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model name.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="OpenAI-compatible endpoint base URL.")
    parser.add_argument("--api-key-env", default="ALI_API_KEY", help="Environment variable name for API key.")
    parser.add_argument("--book-title", default="不等式的秘密 第1卷 第2版", help="Book title metadata.")
    parser.add_argument("--chunk-size", type=int, default=9, help="Pages per request. Recommended: 8-10.")
    parser.add_argument("--pages", default="", help='Only process selected pages, e.g. "1-20,33,40-45".')
    parser.add_argument("--limit-chunks", type=int, default=0, help="Only process first N chunks.")
    parser.add_argument("--max-retries", type=int, default=4, help="Retries per chunk on API failure.")
    parser.add_argument("--timeout", type=int, default=300, help="HTTP timeout seconds per request.")
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="Sleep between chunk requests.")
    parser.add_argument("--prompt-file", type=Path, default=DEFAULT_PROMPT_PATH, help="Prompt template file.")
    parser.add_argument("--resume", action="store_true", help="Reuse previously extracted chunk cache files.")
    parser.add_argument("--omit-raw-problem", action="store_true", help="Do not store raw model problem object in per-problem JSON.")
    return parser.parse_args()


def extract_page_number(path: Path) -> int:
    match = re.search(r"(\d+)", path.stem)
    if not match:
        raise ValueError(f"Cannot parse page number from file name: {path.name}")
    return int(match.group(1))


def list_images(input_dir: Path) -> List[Tuple[int, Path]]:
    files = [*input_dir.glob("*.jpg"), *input_dir.glob("*.jpeg"), *input_dir.glob("*.png")]
    pages: List[Tuple[int, Path]] = []
    for file_path in files:
        pages.append((extract_page_number(file_path), file_path))
    pages.sort(key=lambda x: x[0])
    if not pages:
        raise RuntimeError(f"No image files found in {input_dir}")
    return pages


def parse_pages_selector(selector: str) -> Set[int]:
    if not selector.strip():
        return set()
    selected: Set[int] = set()
    for part in selector.split(","):
        piece = part.strip()
        if not piece:
            continue
        if "-" in piece:
            left, right = piece.split("-", 1)
            start = int(left.strip())
            end = int(right.strip())
            if end < start:
                start, end = end, start
            selected.update(range(start, end + 1))
        else:
            selected.add(int(piece))
    return selected


def make_chunks(items: Sequence[Tuple[int, Path]], chunk_size: int) -> List[List[Tuple[int, Path]]]:
    return [list(items[idx : idx + chunk_size]) for idx in range(0, len(items), chunk_size)]


def to_data_url(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def render_prompt(template: str, replacements: Dict[str, str]) -> str:
    text = template
    for key, value in replacements.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text


def _extract_first_json(text: str) -> Dict[str, Any]:
    content = text.strip()
    if not content:
        raise ValueError("Empty model output.")

    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))

    start = content.find("{")
    if start == -1:
        raise ValueError("No JSON object found in model output.")

    depth = 0
    in_str = False
    escape = False
    end = -1
    for index in range(start, len(content)):
        char = content[index]
        if in_str:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_str = False
            continue
        if char == '"':
            in_str = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index
                break
    if end == -1:
        raise ValueError("Unbalanced JSON braces in model output.")
    return json.loads(content[start : end + 1])


def _norm_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _norm_tags(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(tag).strip() for tag in value if str(tag).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _norm_pages(value: Any, fallback_pages: Sequence[int]) -> List[int]:
    pages: List[int] = []
    if isinstance(value, list):
        for item in value:
            try:
                pages.append(int(item))
            except (TypeError, ValueError):
                continue
    elif isinstance(value, (int, str)):
        try:
            pages.append(int(value))
        except ValueError:
            pass
    if not pages:
        pages = [fallback_pages[0]]
    pages = sorted(set(pages))
    return pages


def _norm_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        val = value.strip().lower()
        if val in {"1", "true", "yes", "y", "是"}:
            return True
        if val in {"0", "false", "no", "n", "否"}:
            return False
    return False


def _slug(text: str, max_len: int = 40) -> str:
    clean = re.sub(r"\s+", "_", text)
    clean = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "", clean)
    clean = clean.strip("_")
    if not clean:
        clean = "item"
    return clean[:max_len]


def _build_original_text(stem_md: str, solution_md: str, answer_md: str, hints_md: str, original_text_md: str) -> str:
    if original_text_md:
        return original_text_md
    parts = [part for part in [stem_md, solution_md, answer_md, hints_md] if part]
    return "\n\n".join(parts)


def normalize_problem_record(
    problem: Dict[str, Any],
    fallback_pages: Sequence[int],
    chunk_id: str,
    book_title: str,
    chunk_page_map: Dict[int, str],
    raw_response_rel: str,
    raw_api_rel: str,
    omit_raw_problem: bool,
) -> Dict[str, Any]:
    source_pages = _norm_pages(problem.get("source_pages"), fallback_pages)
    source_images = [chunk_page_map[p] for p in source_pages if p in chunk_page_map]

    problem_id = _norm_text(problem.get("problem_id"))
    problem_type = _norm_text(problem.get("problem_type")) or "unknown"
    chapter = _norm_text(problem.get("chapter")) or None
    section = _norm_text(problem.get("section")) or None
    title = _norm_text(problem.get("title"))
    stem_md = _norm_text(problem.get("stem_md"))
    solution_md = _norm_text(problem.get("solution_md"))
    answer_md = _norm_text(problem.get("answer_md"))
    hints_md = _norm_text(problem.get("hints_md"))
    original_text_md = _norm_text(problem.get("original_text_md"))
    original_text_md = _build_original_text(stem_md, solution_md, answer_md, hints_md, original_text_md)
    confidence = (_norm_text(problem.get("confidence")) or "medium").lower()
    is_incomplete = _norm_bool(problem.get("is_incomplete", False))
    tags = _norm_tags(problem.get("tags"))

    fingerprint_src = f"{problem_id}|{stem_md[:500]}|{solution_md[:500]}|{answer_md[:200]}|{original_text_md[:500]}"
    digest = hashlib.sha1(fingerprint_src.lower().encode("utf-8")).hexdigest()
    id_source = problem_id or title or stem_md[:32] or "problem"
    page_scope = f"p{min(source_pages):03d}_{max(source_pages):03d}"
    uid = f"{page_scope}_{_slug(id_source)}_{digest[:10]}"

    record: Dict[str, Any] = {
        "uid": uid,
        "book_title": book_title,
        "chapter": chapter,
        "section": section,
        "problem_id": problem_id or None,
        "problem_type": problem_type,
        "title": title or None,
        "source_pages": source_pages,
        "source_images": source_images,
        "stem_md": stem_md,
        "solution_md": solution_md,
        "answer_md": answer_md,
        "hints_md": hints_md,
        "original_text_md": original_text_md,
        "tags": tags,
        "confidence": confidence,
        "is_incomplete": is_incomplete,
        "chunk_id": chunk_id,
        "raw_response_file": raw_response_rel,
        "raw_api_file": raw_api_rel,
        "fingerprint": digest,
    }
    if not omit_raw_problem:
        record["raw_problem"] = problem
    return record


def call_kimi_chunk(
    session: requests.Session,
    *,
    api_key: str,
    base_url: str,
    model: str,
    prompt_text: str,
    chunk_pages: Sequence[Tuple[int, Path]],
    timeout: int,
) -> Tuple[str, Dict[str, Any]]:
    url = base_url.rstrip("/") + "/chat/completions"
    content_parts: List[Dict[str, Any]] = [{"type": "text", "text": prompt_text}]
    for _, image_path in chunk_pages:
        content_parts.append({"type": "image_url", "image_url": {"url": to_data_url(image_path)}})

    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": "你是严谨的教材结构化提取助手。你只输出一个 JSON 对象，且必须合法可解析。",
            },
            {"role": "user", "content": content_parts},
        ],
    }

    response = session.post(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:1000]}")
    data = response.json()
    try:
        message_content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected API response shape: {json.dumps(data, ensure_ascii=False)[:1200]}") from exc

    if isinstance(message_content, list):
        text_parts: List[str] = []
        for part in message_content:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(str(part.get("text", "")))
        content_text = "\n".join(text_parts).strip()
    else:
        content_text = str(message_content).strip()

    if not content_text:
        raise RuntimeError("Model returned empty content.")
    return content_text, data


def ensure_dirs(root: Path) -> Dict[str, Path]:
    dirs = {
        "root": root,
        "raw": root / "raw",
        "chunks": root / "chunks",
        "problems": root / "problems",
    }
    for directory in dirs.values():
        directory.mkdir(parents=True, exist_ok=True)
    return dirs


def sort_records(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(records, key=lambda item: (min(item["source_pages"]), max(item["source_pages"]), item["uid"]))


def write_problem_files(records: Sequence[Dict[str, Any]], problems_dir: Path) -> None:
    for old_file in problems_dir.glob("*.json"):
        old_file.unlink()
    for record in records:
        out_path = problems_dir / f"{record['uid']}.json"
        out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(records: Sequence[Dict[str, Any]], jsonl_path: Path) -> None:
    with jsonl_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_sqlite(records: Sequence[Dict[str, Any]], db_path: Path) -> bool:
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")

    conn.execute(
        """
        CREATE TABLE problems (
            uid TEXT PRIMARY KEY,
            book_title TEXT,
            chapter TEXT,
            section TEXT,
            problem_id TEXT,
            problem_type TEXT,
            title TEXT,
            source_pages_json TEXT NOT NULL,
            source_images_json TEXT,
            stem_md TEXT,
            solution_md TEXT,
            answer_md TEXT,
            hints_md TEXT,
            original_text_md TEXT,
            tags_json TEXT,
            confidence TEXT,
            is_incomplete INTEGER NOT NULL,
            chunk_id TEXT,
            raw_response_file TEXT,
            raw_api_file TEXT,
            fingerprint TEXT
        )
        """
    )
    conn.execute("CREATE INDEX idx_problems_chapter ON problems(chapter)")
    conn.execute("CREATE INDEX idx_problems_section ON problems(section)")
    conn.execute("CREATE INDEX idx_problems_problem_id ON problems(problem_id)")

    fts_enabled = True
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE problems_fts USING fts5(
                uid UNINDEXED,
                book_title,
                chapter,
                section,
                problem_id,
                problem_type,
                title,
                stem_md,
                solution_md,
                answer_md,
                hints_md,
                original_text_md,
                tags,
                tokenize = 'unicode61'
            )
            """
        )
    except sqlite3.OperationalError:
        fts_enabled = False

    for item in records:
        source_pages_json = json.dumps(item["source_pages"], ensure_ascii=False)
        source_images_json = json.dumps(item["source_images"], ensure_ascii=False)
        tags_json = json.dumps(item["tags"], ensure_ascii=False)
        conn.execute(
            """
            INSERT INTO problems (
                uid, book_title, chapter, section, problem_id, problem_type, title,
                source_pages_json, source_images_json, stem_md, solution_md, answer_md, hints_md,
                original_text_md, tags_json, confidence, is_incomplete, chunk_id,
                raw_response_file, raw_api_file, fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["uid"],
                item["book_title"],
                item["chapter"],
                item["section"],
                item["problem_id"],
                item["problem_type"],
                item["title"],
                source_pages_json,
                source_images_json,
                item["stem_md"],
                item["solution_md"],
                item["answer_md"],
                item["hints_md"],
                item["original_text_md"],
                tags_json,
                item["confidence"],
                1 if item["is_incomplete"] else 0,
                item["chunk_id"],
                item["raw_response_file"],
                item["raw_api_file"],
                item["fingerprint"],
            ),
        )
        if fts_enabled:
            conn.execute(
                """
                INSERT INTO problems_fts (
                    uid, book_title, chapter, section, problem_id, problem_type,
                    title, stem_md, solution_md, answer_md, hints_md, original_text_md, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["uid"],
                    item["book_title"] or "",
                    item["chapter"] or "",
                    item["section"] or "",
                    item["problem_id"] or "",
                    item["problem_type"] or "",
                    item["title"] or "",
                    item["stem_md"] or "",
                    item["solution_md"] or "",
                    item["answer_md"] or "",
                    item["hints_md"] or "",
                    item["original_text_md"] or "",
                    " ".join(item["tags"]),
                ),
            )

    conn.commit()
    conn.close()
    return fts_enabled


def load_prompt_template(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def main() -> int:
    args = parse_args()

    if not (8 <= args.chunk_size <= 10):
        print(f"[warn] chunk-size={args.chunk_size} is outside your preferred 8-10 range.", file=sys.stderr)

    api_key = os.environ.get(args.api_key_env) or os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("KIMI_API_KEY")
    if not api_key:
        raise RuntimeError(
            f"API key not found. Set env var {args.api_key_env} "
            "(or DASHSCOPE_API_KEY / KIMI_API_KEY)."
        )

    pages = list_images(args.input_dir)
    selected_pages = parse_pages_selector(args.pages)
    if selected_pages:
        pages = [(p, path) for p, path in pages if p in selected_pages]
        if not pages:
            raise RuntimeError("No images matched --pages filter.")

    chunks = make_chunks(pages, args.chunk_size)
    if args.limit_chunks > 0:
        chunks = chunks[: args.limit_chunks]
    if not chunks:
        raise RuntimeError("No chunks to process.")

    dirs = ensure_dirs(args.output_dir)
    prompt_template = load_prompt_template(args.prompt_file)
    session = requests.Session()

    all_records: List[Dict[str, Any]] = []
    seen_fingerprints: Set[str] = set()
    chunk_reports: List[Dict[str, Any]] = []

    page_manifest = [
        {
            "page": page,
            "image": str(path.relative_to(args.input_dir)),
            "image_path": str(path),
        }
        for page, path in pages
    ]
    (dirs["root"] / "page_manifest.json").write_text(json.dumps(page_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    start_time = time.time()

    for chunk_index, chunk in enumerate(chunks, start=1):
        chunk_id = f"chunk-{chunk_index:04d}"
        chunk_cache_path = dirs["chunks"] / f"{chunk_id}.problems.json"
        raw_response_path = dirs["raw"] / f"{chunk_id}.response.txt"
        raw_api_json_path = dirs["raw"] / f"{chunk_id}.api.json"
        chunk_pages = [page for page, _ in chunk]
        page_list_text = ", ".join(str(p) for p in chunk_pages)
        page_range_text = f"{chunk_pages[0]}-{chunk_pages[-1]}"
        chunk_page_map = {page: str(path.relative_to(args.input_dir)) for page, path in chunk}

        if args.resume and chunk_cache_path.exists():
            cached = json.loads(chunk_cache_path.read_text(encoding="utf-8"))
            restored = 0
            for record in cached:
                if record.get("fingerprint") in seen_fingerprints:
                    continue
                seen_fingerprints.add(record["fingerprint"])
                all_records.append(record)
                restored += 1
            print(f"[resume] {chunk_id}: restored {restored} problems from cache.")
            chunk_reports.append(
                {
                    "chunk_id": chunk_id,
                    "pages": chunk_pages,
                    "status": "cached",
                    "problem_count": restored,
                }
            )
            continue

        prompt_text = render_prompt(
            prompt_template,
            {
                "BOOK_TITLE": args.book_title,
                "CHUNK_ID": chunk_id,
                "PAGE_LIST": page_list_text,
                "PAGE_RANGE": page_range_text,
            },
        )

        error_msg = ""
        parsed_obj: Dict[str, Any] = {}
        api_response_json: Dict[str, Any] = {}
        model_text = ""
        for attempt in range(1, args.max_retries + 1):
            try:
                model_text, api_response_json = call_kimi_chunk(
                    session,
                    api_key=api_key,
                    base_url=args.base_url,
                    model=args.model,
                    prompt_text=prompt_text,
                    chunk_pages=chunk,
                    timeout=args.timeout,
                )
                parsed_obj = _extract_first_json(model_text)
                break
            except Exception as exc:  # pylint: disable=broad-except
                error_msg = str(exc)
                wait_seconds = min(10.0, attempt * 1.5)
                print(f"[retry] {chunk_id} attempt {attempt}/{args.max_retries}: {error_msg}")
                if attempt < args.max_retries:
                    time.sleep(wait_seconds)

        raw_response_path.write_text(model_text or error_msg, encoding="utf-8")
        raw_api_json_path.write_text(json.dumps(api_response_json, ensure_ascii=False, indent=2), encoding="utf-8")

        if not parsed_obj:
            print(f"[error] {chunk_id} failed after retries: {error_msg}", file=sys.stderr)
            chunk_reports.append(
                {
                    "chunk_id": chunk_id,
                    "pages": chunk_pages,
                    "status": "failed",
                    "error": error_msg,
                    "problem_count": 0,
                }
            )
            continue

        raw_problems = parsed_obj.get("problems")
        if not isinstance(raw_problems, list):
            raise RuntimeError(f"{chunk_id}: JSON has no valid 'problems' array.")

        raw_response_rel = str(raw_response_path.relative_to(args.output_dir))
        raw_api_rel = str(raw_api_json_path.relative_to(args.output_dir))

        chunk_records: List[Dict[str, Any]] = []
        duplicates = 0
        for raw_problem in raw_problems:
            if not isinstance(raw_problem, dict):
                continue
            record = normalize_problem_record(
                raw_problem,
                chunk_pages,
                chunk_id,
                args.book_title,
                chunk_page_map,
                raw_response_rel,
                raw_api_rel,
                args.omit_raw_problem,
            )
            if record["fingerprint"] in seen_fingerprints:
                duplicates += 1
                continue
            seen_fingerprints.add(record["fingerprint"])
            chunk_records.append(record)
            all_records.append(record)

        chunk_cache_path.write_text(json.dumps(chunk_records, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"[ok] {chunk_id} pages={page_range_text} "
            f"problems={len(chunk_records)} duplicates={duplicates}"
        )
        chunk_reports.append(
            {
                "chunk_id": chunk_id,
                "pages": chunk_pages,
                "status": "ok",
                "problem_count": len(chunk_records),
                "duplicate_skipped": duplicates,
            }
        )

        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    sorted_records = sort_records(all_records)
    write_problem_files(sorted_records, dirs["problems"])
    write_jsonl(sorted_records, dirs["root"] / "problems.jsonl")
    fts_enabled = build_sqlite(sorted_records, dirs["root"] / "problems.db")

    summary = {
        "book_title": args.book_title,
        "input_dir": str(args.input_dir),
        "output_dir": str(args.output_dir),
        "model": args.model,
        "base_url": args.base_url,
        "chunk_size": args.chunk_size,
        "total_chunks": len(chunks),
        "completed_chunks": sum(1 for report in chunk_reports if report["status"] in {"ok", "cached"}),
        "failed_chunks": sum(1 for report in chunk_reports if report["status"] == "failed"),
        "total_problems": len(sorted_records),
        "fts_enabled": fts_enabled,
        "duration_seconds": round(time.time() - start_time, 2),
        "chunks": chunk_reports,
    }
    (dirs["root"] / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"[done] total_problems={len(sorted_records)} "
        f"fts={'on' if fts_enabled else 'off'} output={args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
