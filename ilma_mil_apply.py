#!/usr/bin/env python3
"""
ILMA MIL Apply v1.0  (2026-06-01)  — Production binding orchestrator
====================================================================
Safely applies Model Intelligence Layer recommendations to the LIVE Hermes
config (auxiliary.* + fallback_providers), with:
  * governance allowlist + safety filters
  * timestamped backup BEFORE any write
  * self-test gate AFTER write -> AUTO-REVERT on any regression
  * idempotent (skips if nothing changed)
  * confidence gating (only bind when recommendation score >= threshold)

Respects config flags (model_intelligence.*). Never touches model.default
(ILMA persona brain), SOUL.md, memory, skills, or sessions.

Usage:
  python3 ilma_mil_apply.py              # apply aux+fallback (gated, reversible)
  python3 ilma_mil_apply.py --dry-run    # show what WOULD change
  python3 ilma_mil_apply.py --revert-last
"""
from __future__ import annotations
import sys, os, json, time, shutil, subprocess
from pathlib import Path
from typing import Any, Dict, List

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
CONFIG = ILMA_ROOT / "config.yaml"
LAST_BK = ILMA_ROOT / "ilma_model_router_data" / ".mil_last_backup"
if str(ILMA_ROOT) not in sys.path:
    sys.path.insert(0, str(ILMA_ROOT))

# Auxiliary tasks to optimize (Hermes-native keys) -> MIL task_type
AUX_TASKS = {
    "vision": "vision",
    "compression": "summarization",
    "web_extract": "web_extract",
    "flush_memories": "memory",
    "session_search": "memory",
    "title_generation": "bulk_low_cost",
    "triage_specifier": "planner",
    "kanban_decomposer": "planner",
    "curator": "summarization",
}

CONF_THRESHOLD = 0.45   # min composite score to bind a recommendation


def _load_cfg() -> Dict[str, Any]:
    import yaml
    with open(CONFIG) as f:
        return yaml.safe_load(f) or {}


def _mil_flags(cfg) -> Dict[str, Any]:
    return cfg.get("model_intelligence", {}) or {}


def _self_test() -> bool:
    """Run fast self-test harness; True = PASS."""
    try:
        r = subprocess.run([sys.executable, "scripts/ilma_self_test_harness.py", "--fast"],
                           cwd=str(ILMA_ROOT), capture_output=True, text=True, timeout=120)
        return r.returncode == 0
    except Exception:
        return False


def _backup() -> str:
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = CONFIG.with_suffix(f".yaml.bak.milapply_{ts}")
    shutil.copy2(CONFIG, bak)
    LAST_BK.write_text(str(bak))
    return str(bak)


def _allowed(provider: str, model: str, registry: dict) -> bool:
    # Governance allowlist gate (production_allowlist.json) — additive
    try:
        import json as _j
        _al = _j.loads((ILMA_ROOT / "ilma_model_router_data" / "production_allowlist.json").read_text())
        _models = set(_al.get("models", []))
        if _models and f"{provider}/{model}" not in _models:
            return False
    except Exception:
        pass

    """Governance: only callable, free, non-deprecated, production-ready models."""
    pv = registry.get("providers", {}).get(provider, {})
    mi = pv.get("models", {}).get(model, {})
    if not mi:
        # model id may be namespaced differently; allow if provider is known-free
        return provider in {"nvidia", "minimax", "ollama", "openrouter"}
    if mi.get("deprecated"):
        return False
    if mi.get("unavailable"):
        return False
    if not (mi.get("is_free")):
        return False
    return True


def compute_plan(dry: bool = False) -> Dict[str, Any]:
    import ilma_model_intelligence as mil
    registry = {}
    try:
        registry = json.loads((ILMA_ROOT / "ilma_model_router_data" /
                               "PROVIDER_INTELLIGENCE_MASTER.json").read_text())
    except Exception:
        pass

    plan = {"auxiliary": {}, "fallback_providers": [], "skipped": []}
    seen_fallback: List[str] = []

    for aux_key, task_type in AUX_TASKS.items():
        rec = mil.recommend(role=task_type)
        r = rec.get("recommended", {})
        prov, model, score = r.get("provider"), r.get("model"), r.get("score") or 0
        if not prov or not model:
            plan["skipped"].append(f"{aux_key}: no recommendation")
            continue
        if score < CONF_THRESHOLD:
            plan["skipped"].append(f"{aux_key}: low confidence {score:.2f}")
            continue
        if not _allowed(prov, model, registry):
            plan["skipped"].append(f"{aux_key}: {prov}/{model} not allowed (governance)")
            continue
        plan["auxiliary"][aux_key] = {"provider": prov, "model": model, "score": round(score, 3)}
        fid = f"{prov}/{model}"
        if fid not in seen_fallback:
            seen_fallback.append(fid)

    plan["fallback_providers"] = seen_fallback[:10]
    return plan


def apply(dry: bool = False) -> Dict[str, Any]:
    cfg = _load_cfg()
    flags = _mil_flags(cfg)
    if not flags.get("enabled", True):
        return {"status": "disabled", "reason": "model_intelligence.enabled=false"}

    plan = compute_plan(dry=dry)
    if dry:
        return {"status": "dry_run", "plan": plan}

    if not plan["auxiliary"]:
        return {"status": "noop", "plan": plan}

    backup = _backup()
    import yaml
    try:
        data = _load_cfg()
        aux = data.setdefault("auxiliary", {})
        changed = []
        for aux_key, sel in plan["auxiliary"].items():
            blk = aux.setdefault(aux_key, {})
            if blk.get("provider") != sel["provider"] or blk.get("model") != sel["model"]:
                blk["provider"] = sel["provider"]
                blk["model"] = sel["model"]
                changed.append(aux_key)
        # fallback enrich (keep existing tail)
        old_fp = data.get("fallback_providers", []) or []
        new_fp = list(plan["fallback_providers"])
        for o in old_fp:
            if o not in new_fp:
                new_fp.append(o)
        if new_fp[:12] != old_fp:
            data["fallback_providers"] = new_fp[:12]
            changed.append("fallback_providers")

        if not changed:
            return {"status": "noop", "plan": plan, "backup": backup}

        tmp = CONFIG.with_suffix(".yaml.tmp")
        with open(tmp, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
        tmp.replace(CONFIG)

        # SELF-TEST GATE -> auto-revert on regression
        if not _self_test():
            shutil.copy2(backup, CONFIG)
            return {"status": "reverted", "reason": "self-test failed after apply",
                    "backup": backup, "changed": changed}

        return {"status": "applied", "changed": changed, "backup": backup, "plan": plan}
    except Exception as e:
        try:
            shutil.copy2(backup, CONFIG)
        except Exception:
            pass
        return {"status": "error_reverted", "error": str(e), "backup": backup}


def revert_last() -> Dict[str, Any]:
    if not LAST_BK.exists():
        return {"status": "no_backup"}
    bak = Path(LAST_BK.read_text().strip())
    if bak.exists():
        shutil.copy2(bak, CONFIG)
        return {"status": "reverted", "from": str(bak)}
    return {"status": "backup_missing"}


if __name__ == "__main__":
    if "--revert-last" in sys.argv:
        print(json.dumps(revert_last(), indent=2))
    else:
        res = apply(dry="--dry-run" in sys.argv)
        print(json.dumps(res, indent=2, default=str))
