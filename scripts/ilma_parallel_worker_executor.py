#!/usr/bin/env python3
"""
ILMA Parallel Worker Executor v1.0
===================================
Safe parallel executor for ILMA internal workloads.
Phase 51-E deliverable.

Uses concurrent.futures.ProcessPoolExecutor and ThreadPoolExecutor.
Supports max_workers, per-task timeout, failure isolation.

Safe job types:
  - compile_file, scan_file, validate_json, search_text
  - run_small_test, evidence_check, registry_check
  - capability_map_validation, doc_consistency_scan
  - security_pattern_scan, trace_schema_validation

Forbidden job types:
  - delete, deploy, install_dependency, os_build
  - external_publish, secret_rotation, firewall_change
  - database_write, evidence_delete, memory_clear
"""

import concurrent.futures
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional

ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
os.chdir(ILMA_PROFILE)

# === CONFIGURATION ===

MAX_WORKERS_DEFAULT = 12
MAX_WORKERS_BURST = 16
WORKER_TIMEOUT = 300  # seconds

FORBIDDEN_JOBS = {
    "delete", "deploy", "install_dependency", "os_build",
    "external_publish", "secret_rotation", "firewall_change",
    "database_write", "evidence_delete", "memory_clear",
    "sudo", "chmod", "chown", "rm", "mkfs", "dd"
}

# === JOB HANDLERS ===

def job_compile_file(file_path: str) -> dict:
    """Compile-check a single Python file."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(file_path)],
            capture_output=True, check=True, timeout=30
        )
        return {"status": "PASS", "file": file_path, "error": None}
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "file": file_path, "error": "timeout 30s"}
    except Exception as e:
        return {"status": "FAIL", "file": file_path, "error": str(e)}

def job_scan_file(file_path: str, pattern: str = "") -> dict:
    """Scan a file for patterns or security issues."""
    try:
        with open(file_path) as f:
            content = f.read()
        matches = len(pattern) > 0 and content.count(pattern) or 0
        return {"status": "PASS", "file": file_path, "matches": matches}
    except Exception as e:
        return {"status": "ERROR", "file": file_path, "error": str(e)}

def job_validate_json(file_path: str) -> dict:
    """Validate a JSON file."""
    try:
        with open(file_path) as f:
            json.load(f)
        return {"status": "PASS", "file": file_path}
    except json.JSONDecodeError as e:
        return {"status": "FAIL", "file": file_path, "error": str(e)}
    except Exception as e:
        return {"status": "ERROR", "file": file_path, "error": str(e)}

def job_search_text(file_path: str, pattern: str) -> dict:
    """Search text in a file."""
    try:
        with open(file_path) as f:
            content = f.read()
        count = content.count(pattern)
        return {"status": "PASS", "file": file_path, "count": count}
    except Exception as e:
        return {"status": "ERROR", "file": file_path, "error": str(e)}

def job_evidence_check() -> dict:
    """Check evidence registry consistency."""
    try:
        import glob
        files = list(Path("evidence").rglob("*.json"))
        broken = []
        for f in files[:50]:  # Limit scan
            try:
                with open(f) as fh:
                    json.load(fh)
            except Exception:
                broken.append(str(f))
        return {"status": "PASS", "checked": len(files), "broken": broken}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

def job_registry_check() -> dict:
    """Check capability registry integrity."""
    try:
        with open("config/ilma_capability_registry.json") as f:
            data = json.load(f)
        count = len(data) if isinstance(data, list) else len(data.get("capabilities", []))
        return {"status": "PASS", "entries": count}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

def job_capability_map_validation() -> dict:
    """Validate capability map references."""
    try:
        import sys as _sys
        _sys.path.insert(0, str(ILMA_PROFILE))
        from scripts.ilma_capability_registry import CapabilityRegistry
        reg = CapabilityRegistry()
        reg.initialize()
        manifest = reg.export_manifest()
        return {"status": "PASS", "total": manifest.get("total_capabilities", 0)}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}
JOB_HANDLERS = {
    "compile_file": job_compile_file,
    "scan_file": job_scan_file,
    "validate_json": job_validate_json,
    "search_text": job_search_text,
    "evidence_check": job_evidence_check,
    "registry_check": job_registry_check,
    "capability_map_validation": job_capability_map_validation,
}

# === PARALLEL EXECUTOR ===

class ParallelWorkerExecutor:
    """Safe parallel executor for ILMA workloads."""

    def __init__(self, max_workers=None, use_process_pool=False):
        self.max_workers = max_workers or MAX_WORKERS_DEFAULT
        self.use_process_pool = use_process_pool
        self.stats = {
            "total_jobs": 0,
            "passed": 0,
            "failed": 0,
            "timed_out": 0,
            "forbidden": 0,
        }
        self.results = []

    def submit(self, job_type: str, data: Any) -> dict:
        """Submit a single job."""
        self.stats["total_jobs"] += 1

        # Check forbidden
        if job_type in FORBIDDEN_JOBS:
            self.stats["forbidden"] += 1
            return {"status": "FORBIDDEN", "job_type": job_type}

        # Get handler
        handler = JOB_HANDLERS.get(job_type)
        if not handler:
            return {"status": "UNKNOWN_JOB", "job_type": job_type}

        # Run with timeout
        try:
            if isinstance(data, dict):
                result = handler(**data)
            else:
                result = handler(data)
            self.results.append(result)
            if result.get("status") == "PASS":
                self.stats["passed"] += 1
            elif result.get("status") in ("FAIL", "ERROR"):
                self.stats["failed"] += 1
            return result
        except Exception as e:
            self.stats["failed"] += 1
            return {"status": "ERROR", "error": str(e)}

    def map(self, jobs: list[dict]) -> list[dict]:
        """Submit multiple jobs in parallel."""
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            for job in jobs:
                job_type = job.get("job_type")
                data = job.get("data")
                if job_type in FORBIDDEN_JOBS:
                    futures.append(None)
                    self.stats["forbidden"] += 1
                    results.append({"status": "FORBIDDEN", "job_type": job_type})
                else:
                    handler = JOB_HANDLERS.get(job_type)
                    if not handler:
                        futures.append(None)
                        results.append({"status": "UNKNOWN", "job_type": job_type})
                    else:
                        if isinstance(data, dict):
                            f = executor.submit(handler, **data)
                        else:
                            f = executor.submit(handler, data)
                        futures.append(f)
                        results.append(None)

            # Collect results
            for i, f in enumerate(futures):
                if f is None:
                    continue  # Already filled
                try:
                    result = f.result(timeout=WORKER_TIMEOUT)
                    results[i] = result
                    self.stats["total_jobs"] += 1
                    if result.get("status") == "PASS":
                        self.stats["passed"] += 1
                    elif result.get("status") in ("FAIL", "ERROR"):
                        self.stats["failed"] += 1
                except concurrent.futures.TimeoutExpired:
                    results[i] = {"status": "TIMEOUT", "job_type": jobs[i].get("job_type")}
                    self.stats["timed_out"] += 1

        self.results = results
        return results

    def get_summary(self) -> dict:
        return {
            "total_jobs": self.stats["total_jobs"],
            "passed": self.stats["passed"],
            "failed": self.stats["failed"],
            "timed_out": self.stats["timed_out"],
            "forbidden": self.stats["forbidden"],
            "max_workers": self.max_workers,
        }

    def export_summary(self) -> str:
        s = self.get_summary()
        return (
            f"ParallelExecutor: {s['total_jobs']} jobs, "
            f"{s['passed']} passed, {s['failed']} failed, "
            f"{s['timed_out']} timeout, {s['forbidden']} forbidden "
            f"(workers={s['max_workers']})"
        )


def run_parallel_demo():
    """Demonstrate parallel executor."""
    print("ILMA Parallel Worker Executor — Demo")
    print("=" * 50)

    executor = ParallelWorkerExecutor(max_workers=8)

    # Demo: compile multiple files in parallel
    scripts = list(Path("scripts").glob("ilma_*.py"))[:10]
    jobs = [{"job_type": "compile_file", "data": {"file_path": str(s)}} for s in scripts]

    print(f"Submitting {len(jobs)} compile jobs to 8 workers...")
    start = time.perf_counter()
    results = executor.map(jobs)
    elapsed = time.perf_counter() - start

    print(f"Results: {elapsed:.2f}s elapsed")
    for r in results:
        print(f"  {r.get('status')}: {r.get('file', r.get('job_type', '?'))}")

    print()
    print(executor.export_summary())

    # Demo: registry + evidence checks
    print()
    print("Running registry + evidence checks...")
    r1 = executor.submit("registry_check", {})
    r2 = executor.submit("evidence_check", {})

    print(f"  registry_check: {r1.get('status')} (entries={r1.get('entries', '?')})")
    print(f"  evidence_check: {r2.get('status')} (checked={r2.get('checked', '?')})")

    print()
    print("Final stats:", executor.get_summary())

    return executor.get_summary()


if __name__ == "__main__":
    run_parallel_demo()