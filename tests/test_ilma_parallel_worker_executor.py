#!/usr/bin/env python3
"""Tests for ilma_parallel_worker_executor.py"""

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "scripts")
from ilma_parallel_worker_executor import (
    ParallelWorkerExecutor, FORBIDDEN_JOBS, JOB_HANDLERS
)

def test_forbidden_jobs():
    ex = ParallelWorkerExecutor(max_workers=4)
    for job_type in FORBIDDEN_JOBS:
        r = ex.submit(job_type, {})
        assert r["status"] == "FORBIDDEN", f"{job_type} should be FORBIDDEN"
    print(f"✅ test_forbidden_jobs: {len(FORBIDDEN_JOBS)} forbidden jobs blocked")

def test_compile_file():
    ex = ParallelWorkerExecutor(max_workers=4)
    # Canonical path: ilma_workflow_ecc.py at project root
    workflow_ecc = Path("ilma_workflow_ecc.py")
    r = ex.submit("compile_file", {"file_path": str(workflow_ecc)})
    assert r["status"] == "PASS", f"compile_file should PASS: {r}"
    print("✅ test_compile_file PASS")

def test_validate_json():
    ex = ParallelWorkerExecutor(max_workers=4)
    # Valid JSON
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        f.write('{"test": true}')
        path = f.name
    try:
        r = ex.submit("validate_json", {"file_path": path})
        assert r["status"] == "PASS", f"valid JSON should PASS: {r}"
        print("✅ test_validate_json PASS")
    finally:
        Path(path).unlink()

def test_validate_json_broken():
    ex = ParallelWorkerExecutor(max_workers=4)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        f.write('{"broken":')  # Invalid JSON
        path = f.name
    try:
        r = ex.submit("validate_json", {"file_path": path})
        assert r["status"] == "FAIL", f"invalid JSON should FAIL: {r}"
        print("✅ test_validate_json_broken PASS")
    finally:
        Path(path).unlink()

def test_registry_check():
    ex = ParallelWorkerExecutor(max_workers=4)
    r = ex.submit("registry_check", {})
    assert r["status"] == "PASS", f"registry_check should PASS: {r}"
    assert "entries" in r, f"entries should be in result: {r}"
    print(f"✅ test_registry_check: {r['entries']} entries")

def test_search_text():
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
        f.write("hello world hello ILMA hello")
        path = f.name
    try:
        ex = ParallelWorkerExecutor(max_workers=4)
        r = ex.submit("search_text", {"file_path": path, "pattern": "hello"})
        assert r["status"] == "PASS", f"search_text should PASS: {r}"
        assert r["count"] == 3, f"expected 3 matches, got {r['count']}"
        print(f"✅ test_search_text: {r['count']} matches")
    finally:
        Path(path).unlink()

def test_parallel_map():
    scripts = list(Path("scripts").glob("ilma_*.py"))[:8]
    jobs = [{"job_type": "compile_file", "data": {"file_path": str(s)}} for s in scripts]

    ex = ParallelWorkerExecutor(max_workers=4)
    start = time.perf_counter()
    results = ex.map(jobs)
    elapsed = time.perf_counter() - start

    passed = sum(1 for r in results if r.get("status") == "PASS")
    assert passed >= len(scripts) - 2, f"expected most to pass, got {passed}/{len(scripts)}"
    print(f"✅ test_parallel_map: {passed}/{len(scripts)} passed in {elapsed:.2f}s")

def test_unknown_job():
    ex = ParallelWorkerExecutor(max_workers=4)
    r = ex.submit("unknown_job_type_xyz", {})
    assert r["status"] == "UNKNOWN_JOB", f"unknown job should return UNKNOWN_JOB: {r}"
    print("✅ test_unknown_job PASS")

def test_summary():
    ex = ParallelWorkerExecutor(max_workers=4)
    ex.submit("compile_file", {"file_path": "scripts/ilma_workflow_ecc.py"})
    ex.submit("registry_check", {})
    ex.submit("delete", {})  # forbidden
    s = ex.get_summary()
    assert s["total_jobs"] >= 2, f"total_jobs should be >= 2: {s}"
    assert s["forbidden"] >= 1, f"forbidden should be >= 1: {s}"
    print(f"✅ test_summary: {s}")

def main():
    print("Testing ILMA Parallel Worker Executor...\n")
    test_forbidden_jobs()
    test_compile_file()
    test_validate_json()
    test_validate_json_broken()
    test_registry_check()
    test_search_text()
    test_parallel_map()
    test_unknown_job()
    test_summary()
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    main()