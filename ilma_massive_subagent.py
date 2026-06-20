#!/usr/bin/env python3
"""
ILMA Massive Subagent Acceleration v1.0  (2026-06-01)
=====================================================
Real LLM subagent fan-out: maps N task-units -> N subagents executed concurrently
with bounded workers, per-task model selection (via subagent_router), failure
isolation, automatic retry/fallback, and aggregation.

This wires together the two halves that previously existed separately:
  - parallel infra (ThreadPoolExecutor, bounded workers, failure isolation)
  - LLM subagent execution (ilma_subagent_router.route_and_execute, free-only)

Public API:
  fan_out(units, *, role=None, max_workers=6, allow_paid=False,
          per_task_timeout=120, aggregate=None) -> dict

  units: list[str] (task texts) OR list[dict{"task":..., "role":..., "id":...}]
"""
from __future__ import annotations
import sys, os, time, json
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
if str(ILMA_ROOT) not in sys.path:
    sys.path.insert(0, str(ILMA_ROOT))

MAX_WORKERS_CAP = 12  # safety cap on a 3.8GB box


def _exec_one(unit: Dict[str, Any], allow_paid: bool, timeout: int) -> Dict[str, Any]:
    """Execute one subagent task via the existing free-only subagent router."""
    t0 = time.time()
    task = unit.get("task", "")
    role = unit.get("role") or None
    uid = unit.get("id")
    try:
        from ilma_subagent_router import SubAgentRouter
        sa = SubAgentRouter()
        # role hint -> task_type_or_desc for routing
        desc = role if role else task
        res = sa.route_and_execute(message=task, task_type_or_desc=desc,
                                   allow_paid=allow_paid)
        try:
            sa.close()
        except Exception:
            pass
        ok = bool(res.get("success")) and bool((res.get("content") or "").strip())
        return {
            "id": uid, "ok": ok, "model": res.get("model"),
            "content": res.get("content", ""),
            "error": res.get("error", "") if not ok else "",
            "latency_s": round(time.time() - t0, 1),
            "used_fallback": res.get("used_fallback", False),
        }
    except Exception as e:
        return {"id": uid, "ok": False, "model": None, "content": "",
                "error": str(e)[:160], "latency_s": round(time.time() - t0, 1)}


def fan_out(units: List[Any], *, role: Optional[str] = None, max_workers: int = 6,
            allow_paid: bool = False, per_task_timeout: int = 120,
            aggregate: Optional[Callable[[List[Dict]], Any]] = None) -> Dict[str, Any]:
    # normalize units
    norm: List[Dict[str, Any]] = []
    for i, u in enumerate(units):
        if isinstance(u, str):
            norm.append({"id": i, "task": u, "role": role})
        elif isinstance(u, dict):
            norm.append({"id": u.get("id", i), "task": u.get("task", ""),
                         "role": u.get("role", role)})
    workers = max(1, min(max_workers, MAX_WORKERS_CAP, len(norm) or 1))
    t0 = time.time()
    results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_exec_one, u, allow_paid, per_task_timeout): u for u in norm}
        for fut in as_completed(futs):
            try:
                results.append(fut.result(timeout=per_task_timeout + 30))
            except Exception as e:
                u = futs[fut]
                results.append({"id": u.get("id"), "ok": False, "model": None,
                                "content": "", "error": f"future: {e}", "latency_s": 0})

    results.sort(key=lambda r: (r.get("id") if isinstance(r.get("id"), int) else 0))
    ok_n = sum(1 for r in results if r["ok"])
    wall = round(time.time() - t0, 1)
    summary = {
        "total": len(norm), "succeeded": ok_n, "failed": len(norm) - ok_n,
        "workers": workers, "wall_clock_s": wall,
        "models_used": sorted({r["model"] for r in results if r.get("model")}),
        "results": results,
    }
    if aggregate:
        try:
            summary["aggregated"] = aggregate(results)
        except Exception as e:
            summary["aggregate_error"] = str(e)
    return summary


def _demo():
    units = [
        "Name one prime number.", "Capital of France in one word?",
        "Translate 'cat' to Spanish.", "What is 6*7?",
        "One word for happy.", "Reverse the word 'dog'.",
    ]
    out = fan_out(units, role="bulk_low_cost", max_workers=6)
    print(json.dumps({k: v for k, v in out.items() if k != "results"}, indent=2))
    for r in out["results"]:
        print(f"  [{'OK ' if r['ok'] else 'ERR'}] {r['latency_s']}s {str(r['model'])[:28]:30} {r['content'][:40]!r}")


if __name__ == "__main__":
    _demo()
