#!/usr/bin/env python3
"""
ILMA Release Manager
Governance pipeline for safely promoting configuration and logic updates.
"""
import sys
import json
import time
from pathlib import Path

CHANGELOG_FILE = Path("/root/.hermes/profiles/ilma/release_changelog.jsonl")

def propose_release(component: str, description: str, risk: str, test_plan: str):
    if not CHANGELOG_FILE.exists():
        CHANGELOG_FILE.touch()
    
    release_id = f"REL-{int(time.time())}"
    
    if risk in ["high", "critical"] and "rollback" not in test_plan.lower():
        print("[!] REJECTED: High risk releases must include a rollback step in the test plan.")
        return

    entry = {
        "release_id": release_id,
        "component": component,
        "description": description,
        "risk": risk,
        "test_plan": test_plan,
        "status": "pending_regression",
        "timestamp": time.time()
    }

    with open(CHANGELOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
        
    print(f"Release {release_id} proposed successfully.")
    print("Run `python3 tests/golden_capability_regression/run_golden_regression_v2.py` to validate.")

if __name__ == "__main__":
    if len(sys.argv) > 4:
        propose_release(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print("Usage: ilma_release_manager.py <component> <desc> <risk> <test_plan>")
