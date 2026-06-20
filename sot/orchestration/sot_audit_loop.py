#!/usr/bin/env python3
"""
sot_audit_loop.py — Run sot_audit N times to detect flakiness/regressions
========================================================================

Each iteration runs the full audit. If any iteration finds bugs that
weren't in the previous iteration, OR a previously-clean audit becomes
dirty, log it. Run for N iterations and report stability.

Usage:
    python3 sot_audit_loop.py --iterations 1000
    python3 sot_audit_loop.py --iterations 10 --break-on-bug
"""
import os, sys, json, argparse, time, subprocess
from datetime import datetime, timezone

SOT_DIR = "/root/.hermes/profiles/ilma/sot"


def run_audit_once(verbose: bool = False, skip_validators: bool = False,
                   skip_disk: bool = False) -> dict:
    """Run sot_audit.py once and return parsed result."""
    cmd = ["python3", "orchestration/sot_audit.py", "--json"]
    if skip_disk:
        cmd.append("--no-materialize-check")
    r = subprocess.run(
        cmd, cwd=SOT_DIR, capture_output=True, text=True, timeout=300,
    )
    if not r.stdout.strip():
        return {"error": r.stderr[-500:], "exit_code": r.returncode}
    try:
        out = r.stdout
        if "{" in out:
            start = out.rfind("\n{\n")
            if start == -1:
                start = out.find("{")
            json_text = out[start:]
            data = json.loads(json_text)
            return data
    except Exception as e:
        return {"error": f"parse: {e}", "raw": r.stdout[-500:], "exit_code": r.returncode}
    return {"error": "no JSON found", "raw": r.stdout[-500:]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--break-on-bug", action="store_true",
                        help="Stop on first bug detection")
    parser.add_argument("--full-disk-check-every", type=int, default=10,
                        help="Run disk cache check every N iterations (1=every iter)")
    parser.add_argument("--full-validator-check-every", type=int, default=100,
                        help="Run validator subprocess every N iterations")
    parser.add_argument("--skip-validators", action="store_true",
                        help="Skip validator subprocess entirely")
    args = parser.parse_args()

    print(f"=== SOT Audit Loop — {args.iterations} iterations ===")
    print(f"  started: {datetime.now(timezone.utc).isoformat()}")
    print(f"  break_on_bug: {args.break_on_bug}")
    print(f"  full_disk_check_every: {args.full_disk_check_every}")
    print(f"  full_validator_check_every: {args.full_validator_check_every}")
    print(f"  skip_validators: {args.skip_validators}")
    print()

    bug_counts = []
    bug_signatures = {}
    first_failure_iter = None
    last_clean_iter = 0
    flakiness = []

    last_state = None
    t0 = time.time()
    for i in range(1, args.iterations + 1):
        # Build command — skip disk check on non-checkpoint iterations
        cmd = ["python3", "orchestration/sot_audit.py", "--json"]
        if i % args.full_disk_check_every != 0:
            cmd.append("--no-materialize-check")
        if args.skip_validators or i % args.full_validator_check_every != 0:
            cmd.append("--skip-validators")
        r = subprocess.run(
            cmd, cwd=SOT_DIR, capture_output=True, text=True, timeout=300,
        )
        result = {}
        if r.stdout.strip():
            try:
                out = r.stdout
                start = out.rfind("\n{\n")
                if start == -1:
                    start = out.find("{")
                result = json.loads(out[start:])
            except Exception:
                result = {"bugs": [{"severity": "PARSE_ERROR", "code": "PARSE", "count": 1, "message": r.stdout[-200:]}], "exit_code": r.returncode}
        else:
            result = {"bugs": [{"severity": "PARSE_ERROR", "code": "EMPTY", "count": 1, "message": r.stderr[-200:]}], "exit_code": r.returncode}

        bug_count = len(result.get("bugs", []))
        bug_counts.append(bug_count)

        sig = tuple(sorted((b["severity"], b["code"], b["count"])
                           for b in result.get("bugs", [])))
        bug_signatures[sig] = bug_signatures.get(sig, 0) + 1

        if bug_count > 0:
            if first_failure_iter is None:
                first_failure_iter = i
            if args.break_on_bug:
                print(f"  Iter {i}: ❌ {bug_count} bug(s) found — breaking")
                print(json.dumps(result, indent=2, default=str)[:2000])
                break
        else:
            last_clean_iter = i

        if sig != last_state:
            flakiness.append((i, sig))
            last_state = sig

        if i % 50 == 0 or i == 1:
            elapsed = time.time() - t0
            print(f"  Iter {i:4d}: bugs={bug_count} | unique_sigs={len(bug_signatures)} | elapsed={elapsed:.1f}s ({elapsed/i:.2f}s/iter)")
        sys.stdout.flush()

    elapsed = time.time() - t0
    print()
    print("=" * 60)
    print("AUDIT LOOP SUMMARY")
    print("=" * 60)
    print(f"  Total iterations: {i}")
    print(f"  Total time: {elapsed:.1f}s ({elapsed/i:.2f}s/iter)")
    print(f"  First failure iter: {first_failure_iter}")
    print(f"  Last clean iter: {last_clean_iter}")
    print(f"  Unique bug signatures seen: {len(bug_signatures)}")
    print(f"  State changes (flakiness): {len(flakiness)}")

    if bug_signatures:
        print("\n  Bug signature distribution:")
        for sig, cnt in sorted(bug_signatures.items(), key=lambda x: -x[1])[:20]:
            print(f"    [{cnt}x] {len(sig)} bugs: {[b for b in sig[:3]]}{'...' if len(sig) > 3 else ''}")

    if all(c == 0 for c in bug_counts):
        print("\n✅ ALL ITERATIONS CLEAN — SOT is stable.")
        return 0
    elif len(bug_signatures) == 1:
        sig, cnt = list(bug_signatures.items())[0]
        print(f"\n⚠️  CONSISTENT BUGS — same {len(sig)} bug(s) in {cnt} iterations: {sig}")
        return 1
    else:
        print(f"\n❌ FLAKY — {len(bug_signatures)} different bug states seen")
        return 2


if __name__ == "__main__":
    sys.exit(main())
