#!/usr/bin/env python3
"""
ILMA Memory Execution Script
证据ID: P2E-MEMORY-001
"""
import argparse, json, sys, os, datetime

EVIDENCE_ID = "P2E-MEMORY-001"
VERSION = "1.0.0"
MEMORY_DIR = "/root/.hermes/profiles/ilma/logs/learning_events"

def write_learning_event(event_id, event_data):
    path = os.path.join(MEMORY_DIR, f"{event_id}.json")
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(path, "w") as f:
        json.dump(event_data, f, indent=2)
    return path

def read_learning_event(event_id):
    path = os.path.join(MEMORY_DIR, f"{event_id}.json")
    if not os.path.exists(path):
        return None, f"Event {event_id} not found"
    with open(path) as f:
        return json.load(f), None

def validate_learning_event(data):
    required = ["event_id", "timestamp", "phase", "summary"]
    missing = [k for k in required if k not in data]
    return len(missing) == 0, missing

def main():
    p = argparse.ArgumentParser(description="ILMA Memory Execution Script")
    p.add_argument("--write", help="Write learning event JSON")
    p.add_argument("--read", help="Read learning event ID")
    p.add_argument("--validate", help="Validate learning event JSON file")
    p.add_argument("--json", action="store_true")
    p.add_argument("--evidence-id", default=EVIDENCE_ID)
    args = p.parse_args()

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    results = []

    if args.write:
        data = json.loads(args.write)
        path = write_learning_event(data.get("event_id", "unnamed"), data)
        valid, missing = validate_learning_event(data)
        results.append({"operation": "write", "path": path, "valid": valid, "missing": missing})
        results.append({"operation": "read-back", "data": data, "valid": valid})

    if args.read:
        data, err = read_learning_event(args.read)
        if err:
            results.append({"operation": "read", "error": err})
        else:
            valid, missing = validate_learning_event(data)
            results.append({"operation": "read", "data": data, "valid": valid, "missing": missing})

    if args.validate:
        with open(args.validate) as f:
            data = json.load(f)
        valid, missing = validate_learning_event(data)
        results.append({"operation": "validate", "file": args.validate, "valid": valid, "missing": missing})

    if not results:
        results.append({"status": "no_operation", "help": "Use --write, --read, or --validate"})

    output = {
        "evidence_id": args.evidence_id,
        "version": VERSION,
        "timestamp": timestamp,
        "results": results,
        "status": "EXECUTED"
    }

    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"=== ILMA Memory ===")
        for r in results:
            print(f"  {r.get('operation','?')}: valid={r.get('valid','?')}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
