#!/usr/bin/env python3
"""
ILMA Model Intelligence Layer (MIL) v1.0  (2026-06-01)
======================================================
NON-DESTRUCTIVE advisory layer for dynamic, per-task model selection.

Design contract:
  * ILMA stays the orchestrator/persona/final-composer.
  * Hermes runtime stays the executor (auth, api_mode, call, native fallback).
  * MIL is ADVISORY ONLY: it builds a task profile, asks the existing
    ILMAUnifiedRouter to score FREE callable candidates, and returns a
    recommendation dict. It NEVER calls a model and NEVER mutates state.
  * Kill switch: config `model_intelligence.enabled: false` -> recommend() returns
    a passthrough recommendation (provider=None) so Hermes native resolution wins.
  * Single source of truth for scoring = ilma_model_router (no new engine).

Public API:
  build_task_profile(task_text, role=None, workflow_ctx=None, **overrides) -> dict
  recommend(task_text=None, role=None, task_profile=None, allow_paid=False,
            n_fallbacks=5, bind=False, bind_mode=None) -> dict
  record_outcome(decision_id, **metrics) -> None   (delegates to telemetry sidecar)

Returns from recommend():
  {
    "enabled": bool,
    "decision_id": str,
    "task_profile": {...},
    "recommended": {"provider": str|None, "model": str|None,
                    "is_free": bool, "score": float},
    "fallbacks": [{"provider","model","score"}...],
    "rationale": str,
    "bound": {"mode": str, "applied": bool, "backup": str}|None,
  }
"""
from __future__ import annotations
import os, sys, json, time, uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
CONFIG_YAML = ILMA_ROOT / "config.yaml"
if str(ILMA_ROOT) not in sys.path:
    sys.path.insert(0, str(ILMA_ROOT))

# ── Config flag (default: shadow mode = log only, no binding) ────────────────
def _load_mil_config() -> Dict[str, Any]:
    cfg = {"enabled": True, "bind": False, "bind_mode": "none",
           "shadow": True, "allow_paid": False}
    try:
        import yaml  # hermes ships pyyaml
        with open(CONFIG_YAML) as f:
            y = yaml.safe_load(f) or {}
        mil = (y.get("model_intelligence") or {})
        cfg.update({k: mil[k] for k in cfg.keys() if k in mil})
    except Exception:
        pass
    return cfg


# ── Task type -> scoring task key (maps to ilma_model_router TASK_WEIGHTS) ────
_ROLE_TO_TASK = {
    "main_conversation": "general", "planner": "reasoning_xhigh",
    "researcher": "research", "coder": "heavy_coding", "reviewer": "reasoning_xhigh",
    "critic": "reasoning_xhigh", "memory": "fast_tasks", "compression": "fast_tasks",
    "web_extract": "research", "extraction": "medium_coding", "tool_heavy": "medium_coding",
    "structured_extraction": "medium_coding", "summarization": "fast_tasks",
    "long_context": "research", "high_risk": "reasoning_xhigh", "bulk_low_cost": "fast_tasks",
    "vision": "vision", "kanban": "general", "subprocess": "general",
    "delegated": "general", "subagent": "general", "parallel": "fast_tasks",
    "validation": "reasoning_xhigh", "security_review": "security_review",
    "writing": "writing",
}

_KEYWORDS = [
    ("vision", ["image", "vision", "screenshot", "ocr", "diagram", "foto", "gambar"]),
    ("coder", ["code", "function", "bug", "refactor", "python", "javascript", "compile", "kode"]),
    ("extraction", ["extract", "parse", "json", "schema", "table", "ekstrak"]),
    ("researcher", ["research", "find", "search", "investigate", "riset", "cari"]),
    ("summarization", ["summarize", "summary", "ringkas", "tl;dr"]),
    ("planner", ["plan", "strategy", "roadmap", "rencana", "design"]),
    ("reviewer", ["review", "validate", "verify", "critique", "audit", "periksa"]),
    ("high_risk", ["production", "deploy", "migrate", "security", "delete", "irreversible"]),
]


def build_task_profile(task_text: Optional[str] = None, role: Optional[str] = None,
                       workflow_ctx: Optional[str] = None, **overrides) -> Dict[str, Any]:
    """Lightweight, non-destructive metadata builder. Never alters task_text."""
    text = (task_text or "").lower()
    task_type = role
    if not task_type:
        task_type = "main_conversation"
        for tt, kws in _KEYWORDS:
            if any(k in text for k in kws):
                task_type = tt
                break
    complexity = "high" if len(text) > 600 or any(
        k in text for k in ["complex", "multi", "architecture", "end-to-end", "comprehensive"]
    ) else ("low" if len(text) < 60 else "med")

    profile = {
        "task_id": overrides.get("task_id") or uuid.uuid4().hex[:12],
        "parent_task_id": overrides.get("parent_task_id"),
        "workflow_id": overrides.get("workflow_id"),
        "task_type": task_type,
        "complexity": complexity,
        "needs_structured_output": ("json" in text or "schema" in text
                                    or task_type in ("extraction", "structured_extraction")),
        "needs_json_validity": "json" in text,
        "needs_tool_use": task_type in ("tool_heavy", "coder", "researcher"),
        "needs_low_latency": task_type in ("bulk_low_cost", "summarization", "parallel",
                                           "compression", "memory"),
        "cost_sensitivity": 0.8 if task_type in ("bulk_low_cost", "parallel", "summarization",
                                                 "compression", "memory") else 0.3,
        "quality_sensitivity": 0.9 if task_type in ("high_risk", "planner", "reviewer",
                                                    "critic", "coder") else 0.5,
        "safety_risk": 0.8 if task_type in ("high_risk", "security_review") else 0.2,
        "required_modality": ["image", "text"] if task_type == "vision" else ["text"],
        "parallelizable": task_type in ("parallel", "bulk_low_cost", "subagent"),
        "reviewer_required": task_type in ("high_risk", "security_review")
                              or overrides.get("reviewer_required", False),
        "auxiliary_or_main": overrides.get("auxiliary_or_main", "main"),
        "parent_agent_or_subagent": overrides.get("parent_agent_or_subagent", "main"),
        "agent_role": role or task_type,
        "workflow_context": workflow_ctx or "main",
        "scoring_task_key": _ROLE_TO_TASK.get(task_type, "general"),
    }
    profile.update({k: v for k, v in overrides.items() if k in profile})
    return profile


def _get_router(allow_paid: bool):
    from ilma_model_router import ILMAUnifiedRouter
    return ILMAUnifiedRouter(allow_paid=allow_paid)


def recommend(task_text: Optional[str] = None, role: Optional[str] = None,
              task_profile: Optional[Dict[str, Any]] = None, allow_paid: bool = False,
              n_fallbacks: int = 5, bind: bool = False,
              bind_mode: Optional[str] = None, workflow_ctx: Optional[str] = None) -> Dict[str, Any]:
    """Produce a per-task model recommendation. Advisory by default."""
    cfg = _load_mil_config()
    decision_id = uuid.uuid4().hex[:16]

    if not cfg.get("enabled", True):
        return {"enabled": False, "decision_id": decision_id,
                "recommended": {"provider": None, "model": None},
                "rationale": "MIL disabled -> Hermes native resolution",
                "fallbacks": [], "bound": None}

    profile = task_profile or build_task_profile(task_text, role=role, workflow_ctx=workflow_ctx)
    allow_paid = bool(allow_paid or cfg.get("allow_paid", False))
    task_key = profile.get("scoring_task_key", "general")

    rec = {"provider": None, "model": None, "is_free": True, "score": None}
    fallbacks: List[Dict[str, Any]] = []
    rationale = ""
    try:
        router = _get_router(allow_paid)
        result = router.get_best_model(task_key, allow_paid=allow_paid)
        rec = {
            "provider": result.get("provider"),
            "model": result.get("model_id"),
            "is_free": result.get("is_free", True),
            "score": result.get("composite_score") or result.get("score"),
        }
        for fb in (result.get("fallbacks") or [])[:n_fallbacks]:
            if isinstance(fb, dict):
                fallbacks.append({"provider": fb.get("provider"),
                                  "model": fb.get("model_id"),
                                  "score": fb.get("composite_score") or fb.get("score")})
        rationale = result.get("routing_reason", f"best free model for {task_key}")
    except Exception as e:
        rationale = f"router error -> passthrough: {e}"

    out = {
        "enabled": True, "decision_id": decision_id,
        "task_profile": profile, "recommended": rec,
        "fallbacks": fallbacks, "rationale": rationale, "bound": None,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    # Telemetry (shadow always logs the decision)
    try:
        from ilma_model_telemetry import log_decision
        log_decision(out)
    except Exception:
        pass

    # Optional binding (only if explicitly enabled AND requested)
    do_bind = (bind or cfg.get("bind", False)) and not cfg.get("shadow", True)
    if do_bind and rec.get("provider") and rec.get("model"):
        mode = bind_mode or cfg.get("bind_mode", "none")
        try:
            from ilma_model_binder import bind_recommendation
            out["bound"] = bind_recommendation(profile, rec, fallbacks, mode=mode)
        except Exception as e:
            out["bound"] = {"mode": mode, "applied": False, "error": str(e)}

    return out


def record_outcome(decision_id: str, **metrics) -> None:
    try:
        from ilma_model_telemetry import log_outcome
        log_outcome(decision_id, **metrics)
    except Exception:
        pass


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="ILMA Model Intelligence Layer (advisory)")
    ap.add_argument("task", nargs="?", default="write a python function to sort a list")
    ap.add_argument("--role", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = recommend(a.task, role=a.role)
    if a.json:
        print(json.dumps(r, indent=2, default=str))
    else:
        rc = r["recommended"]
        print(f"=== MIL recommendation (enabled={r['enabled']}) ===")
        print(f"  task_type={r.get('task_profile',{}).get('task_type')} "
              f"key={r.get('task_profile',{}).get('scoring_task_key')}")
        print(f"  -> {rc.get('provider')}/{rc.get('model')} free={rc.get('is_free')} score={rc.get('score')}")
        print(f"  rationale: {r['rationale']}")
        print(f"  fallbacks: {[f.get('provider','')+'/'+str(f.get('model','')) for f in r['fallbacks'][:3]]}")
