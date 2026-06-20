#!/usr/bin/env python3
"""
ILMA Shadow Evaluator
Observes tasks, writes non-destructive insights based on real queries.
"""
import hashlib
import json
import time
from pathlib import Path

LOG_FILE = Path("/root/.hermes/profiles/ilma/shadow_eval_log.jsonl")

def observe_task(prompt: str, domain: str, skill: str, verdict: str, fallback_used: bool):
    """Log an event safely without retaining sensitive payload content if unnecessary."""
    h = hashlib.sha256(prompt.encode()).hexdigest()[:12]
    
    entry = {
        "ts": time.time(),
        "input_hash": h,
        "domain_classified": domain,
        "skill_used": skill,
        "qgate_verdict": verdict,
        "fallback_used": fallback_used,
        "shadow_insight": "Review required" if verdict == "FAIL" else "Stable"
    }
    
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

if __name__ == "__main__":
    observe_task("dummy prompt for testing shadow logger", "GENERAL", "none", "PASS", False)
    print("Shadow eval logged.")
