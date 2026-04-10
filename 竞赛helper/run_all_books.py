#!/usr/bin/env python3
"""Run all 3 book extractions concurrently."""

import subprocess
import sys
from pathlib import Path

BOOKS = ["secret2", "tip4", "tip9"]
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

processes = []
for book in BOOKS:
    log_file = LOGS_DIR / f"{book}.log"
    err_file = LOGS_DIR / f"{book}_err.log"
    
    cmd = [
        sys.executable,
        "extract_concurrent.py",
        "--book", book,
        "--workers", "3",
        "--chunk-size", "8",
        "--resume",
    ]
    
    print(f"Starting {book}...")
    with open(log_file, "w") as log, open(err_file, "w") as err:
        p = subprocess.Popen(cmd, stdout=log, stderr=err)
        processes.append((book, p))
    
print(f"\nStarted {len(processes)} books!")
print(f"Logs: {LOGS_DIR}")
print("\nMonitor progress with:")
print(f"  python -c \"print(open('logs/secret2.log').read()[-500:])\"")
print(f"  python -c \"print(open('logs/tip4.log').read()[-500:])\"")
print(f"  python -c \"print(open('logs/tip9.log').read()[-500:])\"")
