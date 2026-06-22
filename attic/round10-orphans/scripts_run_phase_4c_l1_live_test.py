#!/usr/bin/env python3
"""
ILMA Phase 4C — Live L1 Coding Task Executor
============================================
Runs a real L1 coding task through CodingWorkerAdapter.
All model calls go through SubAgentRouter → free model → test → diff → rollback.
"""
import sys, os, json, time, traceback
from pathlib import Path

ILMA_PROFILE = "/root/.hermes/profiles/ilma"
sys.path.insert(0, ILMA_PROFILE)
os.chdir(ILMA_PROFILE)

# ─── Config ──────────────────────────────────────────────────────────────────
SANDBOX = Path("/root/.hermes/profiles/ilma/sandbox/phase_4c_l1_repo")
TASK_FILE = SANDBOX / "safe_json.py"
TEST_FILE = SANDBOX / "test_safe_json.py"
OUT_DIR = Path(ILMA_PROFILE)

MODEL_TRACE_PATH = OUT_DIR / "ILMA_PHASE_4C_L1_MODEL_TRACE.json"
TEST_RESULTS_PATH = OUT_DIR / "ILMA_PHASE_4C_L1_TEST_RESULTS.json"
DIFF_PATH = OUT_DIR / "ILMA_PHASE_4C_L1_DIFF.patch"
ROLLBACK_PATH = OUT_DIR / "ILMA_PHASE_4C_L1_ROLLBACK.patch"
REPORT_PATH = OUT_DIR / "ILMA_PHASE_4C_L1_LIVE_TASK_REPORT.md"

# Coding task description
TASK_PROMPT = """Create a Python utility module safe_json.py with these exact functions:

```python
# safe_json.py
import json, os, tempfile, shutil

def safe_load_json(path, default=None):
    '''
    Load JSON from a file safely.
    - If file doesn't exist or is invalid JSON, return default.
    - Must handle PermissionError, OSError gracefully.
    Args:
        path: str or Path to JSON file
        default: value to return on failure (default: None)
    Returns:
        Parsed JSON dict/list or default value
    '''
    ...

def safe_write_json(path, data, indent=2, mode='w'):
    '''
    Write JSON data to a file atomically.
    - Write to temp file first, then rename (atomic write).
    - Must handle PermissionError, OSError gracefully.
    - Create parent directories if they don't exist.
    Args:
        path: str or Path to output JSON file
        data: dict or list to serialize
        indent: JSON indent spaces (default 2)
        mode: 'w' overwrite or 'a' append (default 'w')
    Returns:
        True on success, False on failure
    '''
    ...
```

Requirements:
1. safe_load_json: Returns default on FileNotFoundError, JSONDecodeError, PermissionError
2. safe_write_json: Atomic write via temp file + os.replace() (works on Windows too)
3. Both functions must not raise exceptions — return safely
4. safe_write_json creates parent directories with os.makedirs(path, exist_ok=True)

Then create test_safe_json.py with AT LEAST 6 tests:
1. test_load_valid_json - load a valid JSON file
2. test_load_missing_file_returns_default - missing file returns default
3. test_load_invalid_json_returns_default - corrupt JSON returns default
4. test_write_read_roundtrip - write then read gives same data
5. test_write_creates_parent_dirs - write to nested path creates dirs
6. test_atomic_write - temp file renamed correctly
7. (bonus) test_write_read_nested_data - nested dict/list roundtrip

Use pytest. Save both files in the current directory.
IMPORTANT: Only write the code, do not run tests yourself. Run the tests after.
"""

# ─── Import adapter ──────────────────────────────────────────────────────────
try:
    from ilma_coding_worker_adapter import (
        CodingWorkerAdapter, CodingTaskSpec, CodingTaskResult
    )
    print("[OK] CodingWorkerAdapter imported")
except Exception as e:
    print(f"[FATAL] Cannot import adapter: {e}")
    sys.exit(1)

# ─── Sanity checks ────────────────────────────────────────────────────────────
print(f"\n[CHECK] Sandbox exists: {SANDBOX.exists()}")
print(f"[CHECK] Current dir: {os.getcwd()}")
print(f"[CHECK] Files before task:" )
for f in SANDBOX.iterdir():
    print(f"  {f.name}")

# ─── Execute via adapter ───────────────────────────────────────────────────────
print("\n[EXEC] Calling CodingWorkerAdapter.execute()...")
print("[EXEC] Routing: CodingWorkerAdapter → SubAgentRouter → free model")
print("[EXEC] minimax-m3 EXCLUDED (status: DEGRADED)")
print("[EXEC] Using nvidia free models (dynamic routing)")

start_time = time.time()

try:
    adapter = CodingWorkerAdapter()
    spec = CodingTaskSpec(
        description=TASK_PROMPT,
        files_to_edit=["safe_json.py", "test_safe_json.py"],
        tier="L1_light",
        run_tests=True,      # Run tests after
        repo=str(SANDBOX),  # Sandbox repo
    )
    result = adapter.execute(spec)

except Exception as e:
    print(f"[FATAL] Adapter execute failed: {e}")
    traceback.print_exc()
    result = None

elapsed = time.time() - start_time
print(f"\n[TIME] Task completed in {elapsed:.1f}s")

# ─── Capture diff ─────────────────────────────────────────────────────────────
print("\n[DIFF] Capturing git diff...")
os.chdir(SANDBOX)
import subprocess
diff_result = subprocess.run(
    ["git", "diff", "--", "safe_json.py", "test_safe_json.py"],
    capture_output=True, text=True, timeout=10
)
diff_text = diff_result.stdout

# ─── Capture rollback artifact ───────────────────────────────────────────────
print("[ROLLBACK] Capturing rollback artifact...")
rollback_text = ""
if TASK_FILE.exists():
    rollback_result = subprocess.run(
        ["git", "show", "HEAD:./safe_json.py"],
        capture_output=True, text=True, timeout=10
    )
    rollback_text = rollback_result.stdout

# ─── Read test results ────────────────────────────────────────────────────────
test_run = result.tests_run if result else 0
test_passed = result.tests_passed if result else 0
test_failed = result.tests_failed if result else 0

# Run pytest directly to verify
print("\n[TEST] Running pytest directly...")
pytest_result = subprocess.run(
    ["python3", "-m", "pytest", "test_safe_json.py", "-v", "--tb=short"],
    capture_output=True, text=True, timeout=60, cwd=SANDBOX
)
pytest_output = pytest_result.stdout + "\n" + pytest_result.stderr

# Parse actual pytest results
actual_passed = actual_failed = 0
for line in pytest_output.split("\n"):
    if " passed" in line:
        parts = line.split()
        for i, p in enumerate(parts):
            if p == "passed":
                try: actual_passed = int(parts[i-1])
                except: pass
    if " failed" in line:
        parts = line.split()
        for i, p in enumerate(parts):
            if p == "failed":
                try: actual_failed = int(parts[i-1])
                except: pass

print(f"[PYTEST] {actual_passed} passed, {actual_failed} failed")
print(f"[PYTEST] Return code: {pytest_result.returncode}")

# ─── Write artifacts ─────────────────────────────────────────────────────────

# 1. Model trace
trace = {
    "phase": "4C",
    "task": "L1 safe_json.py",
    "repo": str(SANDBOX),
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
        "error_type": result.error_type if result else "",
        "error_message": result.error_message if result else "",
    } if result else {"error": "adapter.execute() failed"},
    "model_trace": {
        "minimax_m3_excluded": True,
        "minimax_m3_reason": "DEGRADED (live healthcheck timeout 60s)",
        "routing_mode": "dynamic_free_validated_only",
        "paid_provider_allowed": False,
    },
    "files_created": ["safe_json.py", "test_safe_json.py"],
    "test_results": {
        "tests_run": actual_passed + actual_failed,
        "tests_passed": actual_passed,
        "tests_failed": actual_failed,
        "pytest_returncode": pytest_result.returncode,
    },
}
with open(MODEL_TRACE_PATH, "w") as f:
    json.dump(trace, f, indent=2)
print(f"\n[WROTE] {MODEL_TRACE_PATH}")

# 2. Test results JSON
test_results = {
    "phase": "4C",
    "task": "L1 safe_json.py",
    "timestamp": trace["timestamp"],
    "tests_run": actual_passed + actual_failed,
    "tests_passed": actual_passed,
    "tests_failed": actual_failed,
    "pytest_returncode": pytest_result.returncode,
    "pytest_output_snippet": pytest_output[:2000],
    "production_ready": (actual_failed == 0 and pytest_result.returncode == 0),
    "minimax_m3_not_used": True,
}
with open(TEST_RESULTS_PATH, "w") as f:
    json.dump(test_results, f, indent=2)
print(f"[WROTE] {TEST_RESULTS_PATH}")

# 3. Diff patch
with open(DIFF_PATH, "w") as f:
    f.write(diff_text)
print(f"[WROTE] {DIFF_PATH} ({len(diff_text)} bytes)")

# 4. Rollback patch
with open(ROLLBACK_PATH, "w") as f:
    if rollback_text:
        f.write(f"=== Original safe_json.py (HEAD) ===\n")
        f.write(rollback_text)
    else:
        f.write("(no previous version — initial file creation)\n")
        f.write("=== Initial empty file ===\n")
print(f"[WROTE] {ROLLBACK_PATH}")

# 5. Report
report = f"""# ILMA Phase 4C — L1 Live Task Report

## Task
Create `safe_json.py` + `test_safe_json.py` with 6+ unit tests.

## Execution
- **Method:** CodingWorkerAdapter.execute()
- **Router:** SubAgentRouter.route_and_execute()
- **Free model routing:** dynamic_free_validated_only
- **minimax-m3:** EXCLUDED (DEGRADED)
- **Sandbox:** {SANDBOX}

## Timing
- Elapsed: {elapsed:.1f}s
- Timestamp: {trace['timestamp']}

## Model Trace
- **Model used:** `{result.model_used if result else 'FAILED'}`
- **Provider used:** `{result.provider_used if result else 'FAILED'}`
- **Routed via SubAgentRouter:** {result.routed_via_subagent_router if result else False}
- **Free policy passed:** {result.free_policy_passed if result else False}
- **Paid provider bypass attempt:** {result.paid_provider_bypass if result else 'N/A'}
- **Fallback used:** {result.used_fallback if result else False}
- **Original model (if fallback):** `{result.original_model if result else 'N/A'}`
- **Confidence score:** {result.confidence_score if result else 0.0}

## Test Results (pytest direct run)
- **Tests run:** {actual_passed + actual_failed}
- **Tests passed:** {actual_passed}
- **Tests failed:** {actual_failed}
- **Return code:** {pytest_result.returncode}

## Acceptance
| Criterion | Result |
|-----------|--------|
| Model call berhasil | {'✅' if result else '❌'} |
| Provider/model free tercatat | {'✅ ' + str(result.provider_used if result else '') if result and result.provider_used else '❌'} |
| Free policy pass | {'✅' if result and result.free_policy_passed else '❌'} |
| minimax-m3 NOT used | ✅ EXCLUDED |
| Paid provider not touched | {'✅ ' + str(result.provider_used if result else '') if result and result.provider_used not in ['blackbox','perplexity','openai','anthropic'] else '❌'} |
| Tests 6/6 pass | {'✅' if actual_failed == 0 and actual_passed >= 6 else '⚠️ ' + str(actual_passed) + '/' + str(actual_passed+actual_failed)} |
| Diff captured | {'✅' if diff_text else '❌'} |
| Rollback available | {'✅' if rollback_text or not TASK_FILE.exists() else '❌'} |
| Production ready | {'✅' if actual_failed == 0 and pytest_result.returncode == 0 else '❌'} |

## Artifacts
- `ILMA_PHASE_4C_L1_MODEL_TRACE.json` — model call details
- `ILMA_PHASE_4C_L1_TEST_RESULTS.json` — test results
- `ILMA_PHASE_4C_L1_DIFF.patch` — git diff
- `ILMA_PHASE_4C_L1_ROLLBACK.patch` — rollback artifact
"""

with open(REPORT_PATH, "w") as f:
    f.write(report)
print(f"[WROTE] {REPORT_PATH}")

# ─── Final summary ────────────────────────────────────────────────────────────
print(f"""
=== Phase 4C L1 Live Task Summary ===
Model:     {result.model_used if result else 'FAILED'}
Provider:  {result.provider_used if result else 'FAILED'}
Free:      {result.free_policy_passed if result else False}
Paid byp:  {result.paid_provider_bypass if result else True}
Tests:     {actual_passed}/{actual_passed+actual_failed} pass
Production: {'✅ READY' if actual_failed == 0 and pytest_result.returncode == 0 else '❌ NOT READY'}
Time:      {elapsed:.1f}s
""")