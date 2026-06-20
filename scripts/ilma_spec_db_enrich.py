#!/usr/bin/env python3
"""
ILMA Specialization DB Enricher v1.0  (2026-06-01)
==================================================
Promotes model_specialization_database.json to the active profile root and
upgrades per-task specialization scores from INFERRED -> MEASURED using REAL
signals already present in PROVIDER_INTELLIGENCE_MASTER.json (AA benchmarks,
callability, latency, free-only).

16 task categories scored from measured benchmark dimensions where available.
Non-destructive: writes a NEW enriched file + keeps original; sets evidence_level
per-model based on whether real benchmark data backed the score.
"""
import json
from pathlib import Path
from datetime import datetime

ROOT = Path("/root/.hermes/profiles/ilma")
SRC = ROOT / "hermes_profile_ilma" / "model_specialization_database.json"
DST = ROOT / "model_specialization_database.json"   # active location
MASTER = ROOT / "ilma_model_router_data" / "PROVIDER_INTELLIGENCE_MASTER.json"

# task category -> which AA/benchmark dims drive the score (weights)
TASK_DIMS = {
    "planner_model":            {"ai_index": 0.6, "reasoning": 0.4},
    "research_model":           {"ai_index": 0.5, "reasoning": 0.3, "mmlu_pro": 0.2},
    "search_synthesis_model":   {"ai_index": 0.5, "reasoning": 0.5},
    "coding_model":             {"coding_index": 0.7, "ai_index": 0.3},
    "debugging_model":          {"coding_index": 0.6, "reasoning": 0.4},
    "refactor_model":           {"coding_index": 0.7, "reasoning": 0.3},
    "long_context_model":       {"ai_index": 0.5, "context": 0.5},
    "longform_writing_model":   {"ai_index": 0.5, "reasoning": 0.3, "context": 0.2},
    "indonesian_writing_model": {"ai_index": 0.6, "mmlu_pro": 0.4},
    "multilingual_model":       {"ai_index": 0.6, "mmlu_pro": 0.4},
    "judge_model":              {"reasoning": 0.5, "ai_index": 0.5},
    "security_review_model":    {"reasoning": 0.5, "coding_index": 0.5},
    "browser_task_model":       {"ai_index": 0.6, "coding_index": 0.4},
    "json_schema_model":        {"coding_index": 0.6, "ai_index": 0.4},
    "cheap_parallel_model":     {"speed": 0.7, "ai_index": 0.3},
    "final_synthesis_model":    {"ai_index": 0.6, "reasoning": 0.4},
}


def _norm(v, hi):
    try:
        return max(0.0, min(1.0, float(v) / hi))
    except (TypeError, ValueError):
        return None


def build_measured_index(master: dict) -> dict:
    """provider/model_id -> measured dims (0..1)."""
    idx = {}
    for prov, pv in master.get("providers", {}).items():
        for mid, mi in pv.get("models", {}).items():
            aa = mi.get("benchmark_aa") or {}
            dims = {}
            ai = _norm(aa.get("ai_index"), 70.0)
            code = _norm(aa.get("coding_index"), 70.0)
            math = _norm(aa.get("math_index"), 70.0)
            mmlu = _norm(aa.get("mmlu_pro"), 100.0)
            ctx = _norm(mi.get("context_window") or 0, 200000.0)
            lat = mi.get("measured_latency_s")
            spd = None
            if lat is not None:
                try:
                    spd = max(0.0, min(1.0, 1.0 - (float(lat) / 30.0)))  # faster -> higher
                except (TypeError, ValueError):
                    spd = None
            if ai is not None:   dims["ai_index"] = ai
            if code is not None: dims["coding_index"] = code
            if math is not None: dims["math_index"] = math
            if mmlu is not None: dims["mmlu_pro"] = mmlu
            if ctx:              dims["context"] = ctx
            if spd is not None:  dims["speed"] = spd
            # reasoning proxy = avg(ai, math) when present
            r_parts = [x for x in (ai, math) if x is not None]
            if r_parts:
                dims["reasoning"] = sum(r_parts) / len(r_parts)
            callable_ok = not mi.get("unavailable") and (mi.get("is_free") or mi.get("free_tier"))
            for key in (f"{prov}/{mid}", mid, mi.get("canonical_model_id", "")):
                if key:
                    idx[key] = {"dims": dims, "callable_free": callable_ok}
    return idx


def main():
    src = SRC if SRC.exists() else (DST if DST.exists() else None)
    if not src:
        print("ERROR: no specialization DB found")
        return 1
    db = json.loads(src.read_text())
    master = json.loads(MASTER.read_text()) if MASTER.exists() else {"providers": {}}
    midx = build_measured_index(master)

    models = db.get("models", {})
    upgraded = measured = inferred = 0
    for key, mrec in models.items():
        if not isinstance(mrec, dict):
            continue
        prov = mrec.get("provider", "")
        mid = mrec.get("model_id", key)
        cand = midx.get(f"{prov}/{mid}") or midx.get(mid) or midx.get(mrec.get("canonical_model_id", ""))
        spec = mrec.setdefault("specialization_scores", {})
        if cand and cand["dims"]:
            dims = cand["dims"]
            for task, weights in TASK_DIMS.items():
                num = 0.0
                wsum = 0.0
                for dim, w in weights.items():
                    if dim in dims:
                        num += dims[dim] * w
                        wsum += w
                if wsum > 0:
                    spec[task] = round(num / wsum, 3)
            mrec["evidence_level"] = "MEASURED_AA" if any(
                d in cand["dims"] for d in ("ai_index", "coding_index")) else mrec.get("evidence_level")
            mrec["callable_free"] = cand["callable_free"]
            if mrec["evidence_level"] == "MEASURED_AA":
                measured += 1
            upgraded += 1
        else:
            inferred += 1

    db["_meta"] = db.get("_meta", {})
    db["_meta"]["enriched_at"] = datetime.now().isoformat()
    db["_meta"]["enrichment"] = {"upgraded": upgraded, "measured_aa": measured, "still_inferred": inferred}
    db["routing_policy"] = db.get("routing_policy", {})
    db["routing_policy"]["measured_bonus"] = 0.03

    DST.write_text(json.dumps(db, indent=2, ensure_ascii=False))
    print(f"Specialization DB enriched -> {DST.name}")
    print(f"  models: {len(models)}  upgraded: {upgraded}  measured_AA: {measured}  still_inferred: {inferred}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
