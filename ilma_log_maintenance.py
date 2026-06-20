#!/usr/bin/env python3
"""
ILMA Log Maintenance
Safely rotates JSONL logs (Quality Gate, Approval Queue, Shadow Eval) to prevent disk bloat.
"""
import os
import time
import gzip
import shutil
from pathlib import Path

LOGS_DIR = Path("/root/.hermes/profiles/ilma/logs")
APPROVAL_LOG = Path("/root/.hermes/profiles/ilma/approval_queue.jsonl")
SHADOW_LOG = Path("/root/.hermes/profiles/ilma/shadow_eval_log.jsonl")

MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

def rotate_file(filepath: Path):
    if not filepath.exists():
        return
    
    if filepath.stat().st_size > MAX_SIZE_BYTES:
        ts = int(time.time())
        archive_name = filepath.with_name(f"{filepath.name}.{ts}.gz")
        
        print(f"Rotating {filepath} -> {archive_name}")
        with open(filepath, 'rb') as f_in:
            with gzip.open(archive_name, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
                
        # Clear the original file safely
        open(filepath, 'w').close()

def main():
    print("Running log maintenance...")
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    logs_to_check = [
        APPROVAL_LOG,
        SHADOW_LOG,
        LOGS_DIR / "quality_gate.jsonl",
        LOGS_DIR / "agent.log"
    ]
    
    for log in logs_to_check:
        rotate_file(log)
        
    print("Log maintenance complete.")

if __name__ == "__main__":
    main()
