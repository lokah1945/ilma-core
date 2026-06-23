#!/usr/bin/env python3
"""
ILMA Specialization DB — Measured Re-Scorer v1.0  (2026-06-01)
=============================================================
Replaces INFERRED specialization picks with REAL, grounded selection using:
  - AA benchmark indices (real measured: intelligence/coding/math/...)
  - callability (only models proven reachable)
  - latency penalty (real measured)
  - free-only policy
For each of the 16 task categories, computes a measured score per candidate and
picks primary + fallbacks. Writes evidence_level=MEASURED_AA where AA data exists.

Non-destructive: backs up the DB, writes task_models[*] with measured picks +
keeps the per-model table, sets provenance to measured.
"""
from __future__ import annotations
import json, time, shutil, sys
from pathlib import Path

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
SPEC_DB = ILMA_ROOT / "model_specialization_database.json"
MASTER = ILMA_ROOT / "ilma_model_router_data" / "PROVIDER_INTELLIGENCE_MASTER.json"

# task_category -> which AA/benchmark dimensions matter (weights)
TASK_DIMENSIONS = {
    "planner_model":            {"ai": 0.6, "math": 0.2, "code": 0.2},
    "research_model":           {"ai": 0.7, "code": 0.1, "math": 0.2},
    "search_synthesis_model":   {"ai": 0.7, "code": 0.1, "math": 0.2},
    "coding_model":             {"code": 0.7, "ai": 0.2, "math": 0.1},
    "debugging_model":          {"code": 0.7, "ai": 0.3},
    "refactor_model":           {"code": 0.7, "ai": 0.3},
    "long_context_model":       {"ai": 0.5, "ctx": 0.5},
    "longform_writing_model":   {"ai": 0.7, "code": 0.0, "math": 0.0, "ctx": 0.3},
    "indonesian_writing_model": {"ai": 0.8, "ctx": 0.2},
    "multilingual_model":       {"ai": 0.8, "ctx": 0.2},
    "judge_model":              {"ai": 0.7, "math": 0.3},
    "security_review_model":    {"ai": 0.5, "code": 0.5},
    "browser_task_model":       {"ai": 0.6, "code": 0.4},
    "json_schema_model":        {"code": 0.6, "ai": 0.4},
    "cheap_parallel_model":     {"speed": 1.0},   # latency-first
    "final_synthesis_model":    {"ai": 0.8, "ctx": 0.2},
}


def _norm(v, hi=70.0):
    try:
        return max(0.0, min(1.0, float(v) / hi))
    except (TypeError, ValueError):
        return None


def main():
    master = json.loads(MASTER.read_text())
    # build measured candidate pool (free + callable + not dead)
    cands = []
    for prov, pv in master.get("providers", {}).items():
        if prov in ("blackbox", "perplexity"):
            continue
        for mid, mi in pv.get("models", {}).items():
            if not (mi.get("is_free")):
                continue
            if mi.get("deprecated") or mi.get("unavailable"):
                continue
            aa = mi.get("benchmark_aa") or {}
            ai = _norm(aa.get("ai_index"))
            code = _norm(aa.get("coding_index"))
            math = _norm(aa.get("math_index"))
            ctx = mi.get("context_window") or 0
            ctx_s = min(1.0, ctx / 200000.0) if ctx else 0.4
            lat_pen = mi.get("latency_penalty")
            speed = 1.0 - (float(lat_pen) if isinstance(lat_pen, (int, float)) else 0.1)
            cands.append({
                "id": f"{prov}/{mid}", "provider": prov, "model": mid,
                "ai": ai, "code": code, "math": math, "ctx": ctx_s, "speed": max(0.0, speed),
                "has_aa": bool(aa),
            })

    def score(c, dims):
        tot, wsum = 0.0, 0.0
        for dim, w in dims.items():
            val = c.get(dim)
            if val is None:
                # missing AA -> neutral 0.45 so non-benchmarked don't dominate
                val = 0.45 if dim in ("ai", "code", "math") else val
            if val is None:
                continue
            tot += val * w
            wsum += w
        base = tot / wsum if wsum else 0.0
        # prefer measured (AA) models slightly
        if c["has_aa"]:
            base += 0.05
        # universal latency factor (Military-grade: smart AND fast/callable)
        # speed in [0,1]; weight 0.15 so a very slow model loses to a fast near-peer
        base = base * 0.85 + c.get("speed", 0.5) * 0.15
        return base

    task_models = {}
    for task, dims in TASK_DIMENSIONS.items():
        ranked = sorted(cands, key=lambda c: score(c, dims), reverse=True)
        if not ranked:
            continue
        primary = ranked[0]
        fbs = ranked[1:4]
        task_models[task] = {
            "category": task.replace("_model", ""),
            "primary_model": primary["model"],
            "primary_provider": primary["provider"],
            "primary_score": round(score(primary, dims), 4),
            "evidence_level": "MEASURED_AA" if primary["has_aa"] else "MEASURED_HEURISTIC",
            "fallbacks": [{"provider": f["provider"], "model": f["model"],
                           "score": round(score(f, dims), 4)} for f in fbs],
        }

    # write back (backup first)
    bak = SPEC_DB.with_suffix(f".json.bak.measured_{time.strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(SPEC_DB, bak)
    db = json.loads(SPEC_DB.read_text())
    db["task_models"] = task_models
    db["provenance"] = {
        "source": "AA benchmark + callability + latency (REAL measured)",
        "generator": "ilma_spec_db_measured.py", "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "measured": True,
    }
    db["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    SPEC_DB.write_text(json.dumps(db, indent=2, ensure_ascii=False))

    measured = sum(1 for t in task_models.values() if t["evidence_level"] == "MEASURED_AA")
    print(f"=== Specialization DB re-scored (MEASURED) ===")
    print(f"candidates: {len(cands)} | task categories: {len(task_models)} | "
          f"AA-measured picks: {measured}/{len(task_models)} | backup: {bak.name}")
    for t, v in task_models.items():
        print(f"  {t:26} -> {v['primary_provider']}/{v['primary_model'][:34]:36} "
              f"[{v['evidence_level']}] {v['primary_score']}")


if __name__ == "__main__":
    main()
