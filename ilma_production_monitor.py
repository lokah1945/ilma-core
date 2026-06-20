#!/usr/bin/env python3
"""
ILMA Production Monitor & Dashboard
"""
import json
import time
from pathlib import Path

QGATE_LOG = Path("/root/.hermes/profiles/ilma/logs/quality_gate.jsonl")
APPROVAL_LOG = Path("/root/.hermes/profiles/ilma/approval_queue.jsonl")
TELEMETRY_LOG = Path("/root/.hermes/profiles/ilma/logs/agent.log") # simplified proxy

def generate_summary():
    health = {"status": "HEALTHY", "warnings": []}
    
    # 1. Approvals
    pending, approved, rejected, expired = 0, 0, 0, 0
    if APPROVAL_LOG.exists():
        with open(APPROVAL_LOG, "r") as f:
            for line in f:
                if not line.strip(): continue
                try:
                    d = json.loads(line)
                    st = d.get("status")
                    if st == "pending": pending += 1
                    elif st == "approved": approved += 1
                    elif st == "rejected": rejected += 1
                    elif st == "expired": expired += 1
                except: pass
    
    if pending > 10: health["status"] = "WARNING"; health["warnings"].append("High pending approvals.")

    # 2. Quality Gates
    passes, fails = 0, 0
    if QGATE_LOG.exists():
        with open(QGATE_LOG, "r") as f:
            lines = f.readlines()
            for line in lines[-100:]: # last 100
                try:
                    d = json.loads(line)
                    if d.get("overall_verdict") == "PASS": passes += 1
                    else: fails += 1
                except: pass
    
    fail_rate = fails / max(1, passes + fails)
    if fail_rate > 0.2: health["status"] = "WARNING"; health["warnings"].append(f"High QGate fail rate: {fail_rate:.2%}")

    print("=========================================")
    print("      ILMA PRODUCTION DASHBOARD          ")
    print("=========================================")
    print(f"Health Status    : {health['status']}")
    if health['warnings']:
        for w in health['warnings']: print(f"  - {w}")
    print("\n[ APPROVAL QUEUE ]")
    print(f"  Pending : {pending}")
    print(f"  Approved: {approved}")
    print(f"  Rejected: {rejected}")
    print(f"  Expired : {expired}")
    print("\n[ QUALITY GATES (Last 100) ]")
    print(f"  Pass    : {passes}")
    print(f"  Fail    : {fails}")
    print("=========================================")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "summary":
        generate_summary()
    else:
        print("Usage: ilma_production_monitor.py summary")
