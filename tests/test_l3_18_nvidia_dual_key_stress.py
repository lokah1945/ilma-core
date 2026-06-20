#!/usr/bin/env python3
"""
ILMA Phase 4F-R — Task L3-18: NVIDIA dual-key round-robin stress
Objective: Stress test NVIDIA dual-key round-robin selection under load.
"""
import sys
import json
sys.path.insert(0, '/root/.hermes/profiles/ilma')
from ilma_credentials_v2 import get_credential

def test_nvidia_dual_key_round_robin():
    """Call get_credential('nvidia') many times and verify alternating keys."""
    # We'll simulate by checking that we see both keys in a reasonable sample.
    # Since the actual keys are long, we'll hash the key or take a slice.
    seen_keys = set()
    results = []
    for i in range(50):
        key = get_credential('nvidia')
        if key is None:
            results.append(None)
            continue
        # Use a slice that is likely unique but not the full secret: first 12 and last 8
        ident = key[:12] + '...' + key[-8:]
        results.append(ident)
        seen_keys.add(ident)
    # Expect exactly two distinct keys (assuming both keys are valid and healthy)
    assert len(seen_keys) == 2, f"Expected 2 distinct keys, got {seen_keys}"
    # Additionally, check that the sequence alternates (or at least not all same)
    # We'll do a simple check: no more than 2 same in a row (allowing for health changes)
    max_same = 1
    current_run = 1
    for i in range(1, len(results)):
        if results[i] == results[i-1] and results[i] is not None:
            current_run += 1
            if current_run > max_same:
                max_same = current_run
        else:
            current_run = 1
    # Allow up to 3 same in a row in case of health issues, but we expect alternation
    assert max_same <= 3, f"Saw {max_same} same keys in a row, indicating possible failure to alternate"
    return {
        "total_calls": 50,
        "unique_keys": len(seen_keys),
        "key_samples": list(seen_keys)[:2],
        "max_consecutive_same": max_same,
        "status": "passed"
    }

if __name__ == "__main__":
    try:
        result = test_nvidia_dual_key_round_robin()
        print(json.dumps(result, indent=2))
        sys.exit(0)
    except AssertionError as e:
        print(json.dumps({"status": "failed", "error": str(e)}, indent=2))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}, indent=2))
        sys.exit(1)