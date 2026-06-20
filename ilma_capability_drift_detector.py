#!/usr/bin/env python3
"""
ILMA Capability Drift Detector
Analyzes recent logs to detect degradation in capability domains.
"""
import json
import os
from pathlib import Path
from collections import defaultdict

QGATE_LOG = Path("/root/.hermes/profiles/ilma/logs/quality_gate.jsonl")

def detect_drift():
    if not QGATE_LOG.exists():
        print("No QualityGate logs to analyze.")
        return

    domain_fails = defaultdict(int)
    domain_totals = defaultdict(int)

    with open(QGATE_LOG, "r") as f:
        for line in f:
            if not line.strip(): continue
            try:
                d = json.loads(line)
                # Proxying domain from task content if not explicitly logged yet
                ctype = d.get("ctype", "unknown")
                domain_totals[ctype] += 1
                if d.get("overall_verdict") != "PASS":
                    domain_fails[ctype] += 1
            except: pass

    print("--- DRIFT ANALYSIS ---")
    drift_detected = False
    for dom, total in domain_totals.items():
        fail_rate = domain_fails[dom] / total
        print(f"Domain: {dom:10} | Fail Rate: {fail_rate:.1%}")
        if fail_rate > 0.3:
            print(f"  [!] DRIFT WARNING: {dom} exceeds 30% failure rate!")
            drift_detected = True

    if not drift_detected:
        print("Capabilities are stable.")

if __name__ == "__main__":
    detect_drift()
