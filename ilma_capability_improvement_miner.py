#!/usr/bin/env python3
"""
ILMA Capability Improvement Miner
Scrapes telemetry/quality gates to generate a product backlog for the AI.
"""

import json
import time
from pathlib import Path
from collections import defaultdict

QGATE_LOG = Path("/root/.hermes/profiles/ilma/logs/quality_gate.jsonl")
BACKLOG_FILE = Path("/root/.hermes/profiles/ilma/capability_improvement_backlog.jsonl")

def mine_improvements():
    if not QGATE_LOG.exists(): return
    
    fails = defaultdict(list)
    with open(QGATE_LOG, "r") as f:
        for line in f:
            if not line.strip(): continue
            try:
                data = json.loads(line)
                if data.get("overall_verdict") != "PASS":
                    dom = data.get("ctype", "UNKNOWN")
                    fails[dom].append(data)
            except: pass

    new_items = 0
    for dom, records in fails.items():
        if len(records) > 3: # Arbitrary threshold to trigger backlog item
            # Create backlog item
            entry = {
                "id": f"IMP-{int(time.time())}-{dom}",
                "domain": dom,
                "failure_pattern": "Repeated Quality Gate Failures",
                "evidence_count": len(records),
                "recommended_patch": f"Review methodology constraints or update prompt templates for {dom}.",
                "priority": "high",
                "status": "open"
            }
            with open(BACKLOG_FILE, "a") as bf:
                bf.write(json.dumps(entry) + "\n")
            new_items += 1
            # clear the buffer concept in a real app, here we just append
            
    print(f"Mined {new_items} new improvement opportunities into backlog.")

if __name__ == "__main__":
    mine_improvements()
