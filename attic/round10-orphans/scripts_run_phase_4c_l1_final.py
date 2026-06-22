#!/usr/bin/env python3
"""ILMA Phase 4C — Live L1 coding task with fixed adapter"""
import sys, os, json, time, subprocess
from pathlib import Path

ILMA = "/root/.hermes/profiles/ilma"
sys.path.insert(0, ILMA)
os.chdir(ILMA)

SANDBOX = Path("/root/.hermes/profiles/ilma/sandbox/phase_4c_l1_repo")
os.chdir(SANDBOX)

TASK = (
    "Create safe_json.py in the current directory with these two functions:\n\n"
    "1. safe_load_json(path, default=None) - load JSON file, return default on error\n"
    "2. safe_write_json(path, data, indent=2) - atomic write via temp file + rename, return True on success\n\n"
    "Then create test_safe_json.py with pytest tests:\n"
    "- test_load_valid_json\n"
    "- test_load_missing_returns_default\n"
    "- test_load_invalid_returns_default\n"
    "- test_write_read_roundtrip\n"
    "- test_write_creates_parent_dirs\n"
    "- test_atomic_write\n\n"
    "Write Python code only. Do not run tests yourself."
)

print("[EXEC] L1 task via fixed CodingWorkerAdapter (Phase 4C)")
print(f"[SANDBOX] {SANDBOX}")
start = time.time()

from ilma_coding_worker_adapter import CodingWorkerAdapter, CodingTaskSpec

adapter = CodingWorkerAdapter(repo_root=str(SANDBOX))
spec = CodingTaskSpec(
    task_id="P4C-L1-001",
    description=TASK,
    files_to_edit=["safe_json.py", "test_safe_json.py"],
    tier="L1_light",
    run_tests=True,
    repo=str(SANDBOX),
)

result = adapter.execute(spec)
elapsed = time.time() - start
print(f"\n[RESULT] elapsed={elapsed:.1f}s")
print(f"[RESULT] model={result.model_used} provider={result.provider_used}")
print(f"[RESULT] free_policy={result.free_policy_passed} paid_bypass={result.paid_provider_bypass}")
print(f"[RESULT] routed_via_subagent={result.routed_via_subagent_router}")
print(f"[RESULT] content_size={len(result.content)} chars")
print(f"[RESULT] files_written={result.files_changed}")
print(f"[RESULT] tests: run={result.tests_run} passed={result.tests_passed} failed={result.tests_failed}")
print(f"[RESULT] production_ready={result.production_ready}")
print(f"[RESULT] confidence={result.confidence_score}")
if result.error_type:
    print(f"[RESULT] ERROR: {result.error_type} — {result.error_message}")

# Verify files exist
print("\n[VERIFY FILES]")
for f in ["safe_json.py", "test_safe_json.py"]:
    p = Path(f)
    if p.exists():
        print(f"  {f}: {p.stat().st_size} bytes | first 60: {p.read_text()[:60]!r}")
    else:
        print(f"  {f}: NOT FOUND")

# Run pytest directly to confirm
print("\n[PYTEST DIRECT]")
pr = subprocess.run(
    ["python3", "-m", "pytest", "test_safe_json.py", "-v", "--tb=short"],
    capture_output=True, text=True, timeout=60, cwd=SANDBOX
)
print(f"RC={pr.returncode}")
print(pr.stdout[-800:] if pr.stdout else pr.stderr[-800:])

# Capture git diff
diff = subprocess.run(["git", "diff"], capture_output=True, text=True, timeout=10).stdout

# Write artifacts
ts = subprocess.run(["date","+%Y-%m-%dT%H:%M:%S"], capture_output=True, text=True).stdout.strip()

artifacts = {
    "phase": "4C", "task": "L1 live coding", "timestamp": ts,
    "elapsed_seconds": round(elapsed, 1),
    "model_used": result.model_used,
    "provider_used": result.provider_used,
    "routed_via_subagent_router": result.routed_via_subagent_router,
    "free_policy_passed": result.free_policy_passed,
    "paid_provider_bypass": result.paid_provider_bypass,
    "used_fallback": result.used_fallback,
    "content_size_chars": len(result.content),
    "files_written": result.files_changed,
    "tests_run": result.tests_run,
    "tests_passed": result.tests_passed,
    "tests_failed": result.tests_failed,
    "pytest_rc": pr.returncode,
    "production_ready": result.production_ready,
    "error_type": result.error_type or "",
    "error_message": result.error_message or "",
}

for fname, data in [
    ("ILMA_PHASE_4C_L1_MODEL_TRACE.json", artifacts),
    ("ILMA_PHASE_4C_L1_TEST_RESULTS.json", {
        "phase": "4C", "task": "L1 live",
        "tests_run": result.tests_run, "tests_passed": result.tests_passed,
        "tests_failed": result.tests_failed, "pytest_rc": pr.returncode,
        "production_ready": result.production_ready,
        "files_written": result.files_changed,
    }),
]:
    with open(Path(ILMA) / fname, "w") as f:
        json.dump(data, f, indent=2)

with open(Path(ILMA) / "ILMA_PHASE_4C_L1_DIFF.patch", "w") as f:
    f.write(diff)

# Rollback
rollback_file = Path(ILMA) / "ILMA_PHASE_4C_L1_ROLLBACK.patch"
with open(rollback_file, "w") as f:
    f.write("(no previous version — initial file creation)\n")

print(f"""
=== Phase 4C L1 Live Summary ===
Model:       {result.model_used}
Provider:    {result.provider_used}
Free:        {result.free_policy_passed}
Content:     {len(result.content)} chars
Files:       {result.files_changed}
Tests:       {result.tests_run} run | {result.tests_passed} pass | {result.tests_failed} fail
Pytest RC:   {pr.returncode}
Ready:       {'YES ✅' if result.tests_failed == 0 and pr.returncode == 0 else 'NO ❌'}
Time:        {elapsed:.1f}s
""")