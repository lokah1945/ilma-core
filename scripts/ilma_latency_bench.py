#!/usr/bin/env python3
"""
ILMA Latency Benchmark v1.0  (2026-06-01)
=========================================
Probes the top-N free models with a real chat call, measures latency, and writes
a persistent `latency_penalty` (0..0.30) into PROVIDER_INTELLIGENCE_MASTER.json so
the router prefers models that are BOTH high-IQ AND fast.

Penalty curve (per-call wall-clock):
    <  6s  -> 0.00   (fast)
    < 12s  -> 0.05
    < 25s  -> 0.12
    < 45s  -> 0.20
    >=45s  -> 0.30   (slow / near-timeout)
  timeout/err -> 0.30

Free-only. Safe: small max_tokens, per-call timeout, only writes latency fields.
"""
import json, time, sys, os
from pathlib import Path

sys.path.insert(0, "/root/.hermes/profiles/ilma")
os.chdir("/root/.hermes/profiles/ilma")

from ilma_provider_kernel import ProviderKernel

MASTER = Path("/root/.hermes/profiles/ilma/ilma_model_router_data/PROVIDER_INTELLIGENCE_MASTER.json")
TOP_N = int(os.environ.get("LAT_TOP_N", "15"))
PROBE_TIMEOUT = 50

# providers we can execute directly + that are callable
PROBE_PROVIDERS = {"nvidia", "minimax", "ollama", "openrouter"}


def penalty_for(latency, ok):
    if not ok:
        return 0.30
    if latency < 6:
        return 0.0
    if latency < 12:
        return 0.05
    if latency < 25:
        return 0.12
    if latency < 45:
        return 0.20
    return 0.30


def main():
    d = json.load(open(MASTER))
    # collect top-N free models by score across probe providers
    rows = []
    for pn, pv in d["providers"].items():
        if pn not in PROBE_PROVIDERS:
            continue
        for mid, mi in pv.get("models", {}).items():
            if mi.get("is_free") or mi.get("free_tier"):
                rows.append((mi.get("score") or 0, pn, mid))
    rows.sort(reverse=True)
    candidates = rows[:TOP_N]

    kernel = ProviderKernel()
    msgs = [{"role": "user", "content": "Reply with exactly: OK"}]
    print(f"=== Latency benchmark: top {len(candidates)} free models ===")
    results = {}
    for score, pn, mid in candidates:
        t0 = time.time()
        try:
            out = kernel.call(pn, mid, msgs, max_tokens=16, timeout=PROBE_TIMEOUT)
            dt = round(time.time() - t0, 1)
            ok = bool(out) and "Error" not in str(out)[:14]
        except Exception:
            dt = round(time.time() - t0, 1)
            ok = False
        pen = penalty_for(dt, ok)
        results[(pn, mid)] = (dt, ok, pen)
        print(f"  [{'OK ' if ok else 'ERR'}] {dt:>5}s pen={pen:<4} {pn}/{mid[:42]}")

    # apply penalties to DB
    applied = 0
    for pn, pv in d["providers"].items():
        for mid, mi in pv.get("models", {}).items():
            if (pn, mid) in results:
                dt, ok, pen = results[(pn, mid)]
                mi["latency_penalty"] = pen
                mi["measured_latency_s"] = dt
                mi["latency_benchmarked_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                applied += 1
    json.dump(d, open(MASTER, "w"), indent=2, ensure_ascii=False)
    print(f"\napplied latency_penalty to {applied} models -> {MASTER.name}")
    fast = sum(1 for v in results.values() if v[2] == 0.0)
    print(f"fast(<6s): {fast}/{len(results)}")


if __name__ == "__main__":
    main()
