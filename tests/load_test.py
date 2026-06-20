#!/usr/bin/env python3
"""
ILMA Load Test v1.0 (Phase 1.1 Block 6.2)
==========================================
Three scenarios:
  A. 10 concurrent requests to ilma.py --status
  B. 5 concurrent route_task_simple calls
  C. 20 concurrent /health requests (in-process)

Run for 60 seconds (configurable).

Output: p50, p95, p99 latency, error rate, throughput (req/s).
"""
from __future__ import annotations

import concurrent.futures
import statistics
import subprocess
import sys
import time
from pathlib import Path

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")


def measure_latency(fn, n_requests: int, max_workers: int) -> list:
    """Run fn() n times with up to max_workers in parallel, return latencies."""
    latencies = []
    errors = 0
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(fn) for _ in range(n_requests)]
        for f in concurrent.futures.as_completed(futures):
            try:
                f.result()
            except Exception:
                errors += 1
    elapsed = time.time() - start
    return latencies, errors, elapsed


def scenario_a(n=10, max_workers=10):
    """10 concurrent `ilma.py --status` calls."""
    def call():
        start = time.perf_counter()
        subprocess.run(
            ["python3", "ilma.py", "--status"],
            cwd=ILMA_ROOT, capture_output=True, text=True, timeout=60,
        )
        return (time.perf_counter() - start) * 1000
    return _run_scenario("A. ilma.py --status", call, n, max_workers)


def scenario_b(n=5, max_workers=5):
    """5 concurrent route_task_simple calls."""
    def call():
        start = time.perf_counter()
        sys.path.insert(0, str(ILMA_ROOT))
        from ilma_model_router import route_task_simple
        route_task_simple("test query for load")
        return (time.perf_counter() - start) * 1000
    return _run_scenario("B. route_task_simple", call, n, max_workers)


def scenario_c(n=20, max_workers=20):
    """20 concurrent unified cache reads."""
    def call():
        start = time.perf_counter()
        sys.path.insert(0, str(ILMA_ROOT))
        from ilma_unified_cache import get_cache
        cache = get_cache()
        cache.get("root", namespace="benchmark.aa")
        return (time.perf_counter() - start) * 1000
    return _run_scenario("C. unified cache read", call, n, max_workers)


def _run_scenario(name, fn, n, max_workers):
    latencies = []
    errors = 0
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(fn) for _ in range(n)]
        for f in concurrent.futures.as_completed(futures):
            try:
                lat = f.result()
                latencies.append(lat)
            except Exception:
                errors += 1
    elapsed = time.time() - start
    return {
        "name": name,
        "n_requests": n,
        "max_workers": max_workers,
        "errors": errors,
        "total_time_s": round(elapsed, 3),
        "throughput_rps": round(n / elapsed, 2) if elapsed > 0 else 0,
        "latency_p50_ms": round(statistics.median(latencies), 1) if latencies else 0,
        "latency_p95_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 1) if latencies else 0,
        "latency_p99_ms": round(sorted(latencies)[int(len(latencies) * 0.99)], 1) if latencies else 0,
        "latency_mean_ms": round(statistics.mean(latencies), 1) if latencies else 0,
    }


def main() -> int:
    print("=" * 60)
    print("ILMA Load Test — Phase 1.1 Block 6.2")
    print("=" * 60)
    results = []
    for scen in [scenario_a, scenario_b, scenario_c]:
        try:
            r = scen()
            results.append(r)
            print(f"\n[{r['name']}]")
            print(f"  n={r['n_requests']}, errors={r['errors']}, throughput={r['throughput_rps']} req/s")
            print(f"  p50={r['latency_p50_ms']}ms, p95={r['latency_p95_ms']}ms, p99={r['latency_p99_ms']}ms, mean={r['latency_mean_ms']}ms")
        except Exception as e:
            print(f"\n[Scenario] ERROR: {e}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
