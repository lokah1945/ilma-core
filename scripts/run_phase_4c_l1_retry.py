#!/usr/bin/env python3
"""ILMA Phase 4C — L1 Live Task (Retry with focused prompt)"""
import sys, os, json, time, traceback, subprocess
from pathlib import Path

ILMA_PROFILE = "/root/.hermes/profiles/ilma"
sys.path.insert(0, ILMA_PROFILE)
os.chdir(ILMA_PROFILE)

SANDBOX = Path("/root/.hermes/profiles/ilma/sandbox/phase_4c_l1_repo")
os.chdir(SANDBOX)

# Simpler prompt
TASK = (
    "Create safe_json.py in the current directory with these two functions:\n\n"
    "1. safe_load_json(path, default=None) - load JSON file, return default on error\n"
    "2. safe_write_json(path, data, indent=2) - atomic write via temp file + rename, return True on success\n\n"
    "Then create test_safe_json.py with pytest tests:\n"
    "- test_load_valid_json: write a temp JSON file and load it\n"
    "- test_load_missing_returns_default: load non-existent file, expect default\n"
    "- test_load_invalid_returns_default: load corrupt JSON, expect default\n"
    "- test_write_read_roundtrip: write data, read it back, verify equality\n"
    "- test_write_creates_parent_dirs: write to nested path, verify dirs created\n"
    "- test_atomic_write: verify write succeeds and file is valid JSON\n\n"
    "Write Python code only. Do not run tests yourself."
)

print("[EXEC] L1 task — safe_json.py + test_safe_json.py")
print(f"[EXEC] Sandbox: {SANDBOX}")
start_time = time.time()

from ilma_coding_worker_adapter import CodingWorkerAdapter, CodingTaskSpec

try:
    adapter = CodingWorkerAdapter()
    spec = CodingTaskSpec(
        description=TASK,
        files_to_edit=["safe_json.py", "test_safe_json.py"],
        tier="L1_light",
        run_tests=True,
        repo=str(SANDBOX),
    )
    result = adapter.execute(spec)
    print(f"[RESULT] model={result.model_used} provider={result.provider_used}")
    print(f"[RESULT] free_policy={result.free_policy_passed} confidence={result.confidence_score}")
    print(f"[RESULT] production_ready={result.production_ready}")
    if result.error_type:
        print(f"[RESULT] error={result.error_type}: {result.error_message}")
except Exception as e:
    print(f"[FATAL] {e}")
    traceback.print_exc()
    result = None

elapsed = time.time() - start_time
print(f"[TIME] {elapsed:.1f}s")

# Verify files
safe_exists = Path("safe_json.py").exists()
test_exists = Path("test_safe_json.py").exists()
print(f"\n[VERIFY] safe_json.py: {safe_exists} | test_safe_json.py: {test_exists}")

if safe_exists:
    content = Path("safe_json.py").read_text()
    print(f"safe_json.py: {len(content)} bytes | first 80: {content[:80]!r}")

# Run pytest
actual_passed = actual_failed = 0
pytest_rc = -1
if test_exists:
    pr = subprocess.run(
        ["python3", "-m", "pytest", "test_safe_json.py", "-v", "--tb=short"],
        capture_output=True, text=True, timeout=60, cwd=SANDBOX
    )
    pytest_rc = pr.returncode
    output = pr.stdout + "\n" + pr.stderr
    print(f"[PYTEST] RC={pytest_rc}")
    print(output[:600])
    for line in output.split("\n"):
        for i, w in enumerate(line.split()):
            if w == "passed": 
                try: actual_passed = int(line.split()[i-1])
                except: pass
            if w == "failed":
                try: actual_failed = int(line.split()[i-1])
                except: pass

# Git diff
diff_text = subprocess.run(
    ["git", "diff", "--", "safe_json.py", "test_safe_json.py"],
    capture_output=True, text=True, timeout=10
).stdout

# Write artifacts
trace = {
    "phase": "4C", "task": "L1 retry",
    "timestamp": subprocess.run(["date","+%Y-%m-%dT%H:%M:%S"], capture_output=True, text=True).stdout.strip(),
    "elapsed_seconds": round(elapsed, 1),
    "result": {
        "model_used": result.model_used if result else "FAILED",
        "provider_used": result.provider_used if result else "FAILED",
        "routed_via_subagent_router": result.routed_via_subagent_router if result else False,
        "free_policy_passed": result.free_policy_passed if result else False,
        "paid_provider_bypass": result.paid_provider_bypass if result else True,
        "used_fallback": result.used_fallback if result else False,
        "original_model": result.original_model if result else "",
        "confidence_score": result.confidence_score if result else 0.0,
        "production_ready": result.production_ready if result else False,
    } if result else {"error": "no result"},
    "files": {
        "safe_json_exists": safe_exists,
        "test_safe_json_exists": test_exists,
        "safe_json_size": len(Path("safe_json.py").read_text()) if safe_exists else 0,
    },
    "tests": {"passed": actual_passed, "failed": actual_failed, "pytest_rc": pytest_rc},
}
out = Path(ILMA_PROFILE) / "ILMA_PHASE_4C_L1_MODEL_TRACE.json"
with open(out, "w") as f:
    json.dump(trace, f, indent=2)
print(f"\n[WROTE] {out}")

with open(Path(ILMA_PROFILE) / "ILMA_PHASE_4C_L1_TEST_RESULTS.json", "w") as f:
    json.dump({"phase": "4C", "tests_passed": actual_passed, "tests_failed": actual_failed,
               "pytest_rc": pytest_rc, "production_ready": (actual_failed == 0 and pytest_rc == 0)}, f, indent=2)

with open(Path(ILMA_PROFILE) / "ILMA_PHASE_4C_L1_DIFF.patch", "w") as f:
    f.write(diff_text)

print(f"""
=== Final ===
model:     {result.model_used if result else 'FAILED'}
provider:  {result.provider_used if result else 'FAILED'}
free:      {result.free_policy_passed if result else False}
tests:     {actual_passed}/{actual_passed+actual_failed}
ready:     {'YES' if actual_failed == 0 and pytest_rc == 0 else 'NO'}
time:      {elapsed:.1f}s
""")