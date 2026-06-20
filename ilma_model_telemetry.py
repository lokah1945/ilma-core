#!/usr/bin/env python3
"""
ILMA Model Telemetry Sidecar v1.0  (2026-06-01)
===============================================
Records every MIL decision + outcome into a SEPARATE SQLite DB so the system can
learn (update registry reliability/latency/success) WITHOUT touching Hermes
state.db, sessions, memory, or persona.

DB: ilma_model_router_data/model_intelligence.sqlite   (additive, isolated)

Public API:
  log_decision(decision_dict) -> str(decision_id)
  log_outcome(decision_id, **metrics) -> None
  aggregate_to_registry() -> dict   # learning loop: telemetry -> registry signals
  stats() -> dict
"""
from __future__ import annotations
import sqlite3, json, time, os
from pathlib import Path
from typing import Any, Dict

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
DB_PATH = ILMA_ROOT / "ilma_model_router_data" / "model_intelligence.sqlite"
MASTER_DB = ILMA_ROOT / "ilma_model_router_data" / "PROVIDER_INTELLIGENCE_MASTER.json"


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH), timeout=10)
    c.execute("PRAGMA journal_mode=WAL")
    return c


def _init():
    c = _conn()
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS decisions (
            decision_id TEXT PRIMARY KEY, ts TEXT,
            task_id TEXT, parent_task_id TEXT, workflow_id TEXT,
            agent_role TEXT, task_type TEXT, scoring_task_key TEXT,
            selected_provider TEXT, selected_model TEXT,
            selection_score REAL, is_free INTEGER,
            fallbacks TEXT, rationale TEXT, profile TEXT,
            bound_mode TEXT, bound_applied INTEGER
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS outcomes (
            decision_id TEXT, ts TEXT,
            actual_latency_ms REAL, actual_cost REAL,
            input_tokens INTEGER, output_tokens INTEGER,
            validation_result TEXT, retry_count INTEGER,
            fallback_used INTEGER, task_success INTEGER,
            post_quality REAL, error TEXT
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_dec_model ON decisions(selected_provider, selected_model)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_out_dec ON outcomes(decision_id)")
        c.commit()
    finally:
        c.close()


def log_decision(d: Dict[str, Any]) -> str:
    _init()
    rec = d.get("recommended", {}) or {}
    prof = d.get("task_profile", {}) or {}
    bound = d.get("bound") or {}
    did = d.get("decision_id") or os.urandom(8).hex()
    c = _conn()
    try:
        c.execute("""INSERT OR REPLACE INTO decisions VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            did, d.get("ts") or time.strftime("%Y-%m-%dT%H:%M:%S"),
            prof.get("task_id"), prof.get("parent_task_id"), prof.get("workflow_id"),
            prof.get("agent_role"), prof.get("task_type"), prof.get("scoring_task_key"),
            rec.get("provider"), rec.get("model"),
            float(rec.get("score") or 0.0), 1 if rec.get("is_free", True) else 0,
            json.dumps(d.get("fallbacks", [])), d.get("rationale", ""),
            json.dumps(prof), bound.get("mode"), 1 if bound.get("applied") else 0,
        ))
        c.commit()
    finally:
        c.close()
    return did


def log_outcome(decision_id: str, **m) -> None:
    _init()
    c = _conn()
    try:
        c.execute("""INSERT INTO outcomes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (
            decision_id, time.strftime("%Y-%m-%dT%H:%M:%S"),
            m.get("actual_latency_ms"), m.get("actual_cost"),
            m.get("input_tokens"), m.get("output_tokens"),
            json.dumps(m.get("validation_result")) if m.get("validation_result") is not None else None,
            m.get("retry_count", 0), 1 if m.get("fallback_used") else 0,
            1 if m.get("task_success") else 0, m.get("post_quality"), m.get("error"),
        ))
        c.commit()
    finally:
        c.close()


def aggregate_to_registry() -> Dict[str, Any]:
    """Learning loop: compute per-model success/latency from outcomes and write
    historical_success + measured signals back into the JSON registry (additive)."""
    _init()
    c = _conn()
    agg = {}
    try:
        rows = c.execute("""
            SELECT d.selected_provider, d.selected_model,
                   AVG(o.task_success) AS succ, AVG(o.actual_latency_ms) AS lat,
                   COUNT(*) AS n
            FROM decisions d JOIN outcomes o ON d.decision_id=o.decision_id
            GROUP BY d.selected_provider, d.selected_model
            HAVING n >= 3
        """).fetchall()
    finally:
        c.close()
    for prov, model, succ, lat, n in rows:
        agg[f"{prov}/{model}"] = {"historical_success": round(succ or 0, 3),
                                  "avg_latency_ms": round(lat or 0, 1), "samples": n}
    # write back into registry (additive fields only)
    if agg and MASTER_DB.exists():
        try:
            data = json.loads(MASTER_DB.read_text())
            for prov, pv in data.get("providers", {}).items():
                for mid, mi in pv.get("models", {}).items():
                    key = f"{prov}/{mid}"
                    if key in agg:
                        mi["historical_success"] = agg[key]["historical_success"]
                        mi["telemetry_samples"] = agg[key]["samples"]
            MASTER_DB.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            return {"updated": 0, "error": str(e)}
    return {"updated": len(agg), "models": list(agg.keys())[:10]}


def stats() -> Dict[str, Any]:
    _init()
    c = _conn()
    try:
        d = c.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        o = c.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
        top = c.execute("""SELECT selected_provider, selected_model, COUNT(*) n
                           FROM decisions GROUP BY 1,2 ORDER BY n DESC LIMIT 5""").fetchall()
    finally:
        c.close()
    return {"decisions": d, "outcomes": o,
            "top_models": [f"{p}/{m} x{n}" for p, m, n in top]}


if __name__ == "__main__":
    import sys
    if "--aggregate" in sys.argv:
        print(json.dumps(aggregate_to_registry(), indent=2))
    else:
        print(json.dumps(stats(), indent=2))
