#!/usr/bin/env python3
"""
ILMA Model Binder v1.0  (2026-06-01)
====================================
Safe, REVERSIBLE adapter that applies a MIL recommendation to Hermes config
WITHOUT touching state/memory/persona. Every write makes a timestamped backup.

Binding modes (all additive, all reversible):
  - "aux"      : fill auxiliary.<task>.provider/model  (lowest risk)
  - "fallback" : re-rank fallback_providers[] for the session
  - "subagent" : set delegation.model/provider (pre-spawn advisory)
  - "all"      : aux + fallback + subagent
  - "none"     : no-op (shadow)

NEVER writes model.default (that is ILMA's main persona brain — left to user).
"""
from __future__ import annotations
import json, time, shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
CONFIG_YAML = ILMA_ROOT / "config.yaml"

# task_type -> hermes auxiliary key (only map ones Hermes actually supports)
_AUX_MAP = {
    "vision": "vision", "compression": "compression", "summarization": "compression",
    "web_extract": "web_extract", "extraction": "web_extract",
    "memory": "flush_memories", "structured_extraction": "web_extract",
}


def _backup() -> str:
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = CONFIG_YAML.with_suffix(f".yaml.bak.mil_{ts}")
    shutil.copy2(CONFIG_YAML, bak)
    return bak.name


def _load_yaml() -> Dict[str, Any]:
    import yaml
    with open(CONFIG_YAML) as f:
        return yaml.safe_load(f) or {}


def _save_yaml(data: Dict[str, Any]) -> None:
    import yaml
    tmp = CONFIG_YAML.with_suffix(".yaml.tmp")
    with open(tmp, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    tmp.replace(CONFIG_YAML)


def bind_recommendation(profile: Dict[str, Any], rec: Dict[str, Any],
                        fallbacks: List[Dict[str, Any]], mode: str = "none") -> Dict[str, Any]:
    if mode in (None, "none"):
        return {"mode": "none", "applied": False, "backup": None}
    provider, model = rec.get("provider"), rec.get("model")
    if not provider or not model:
        return {"mode": mode, "applied": False, "reason": "no recommendation"}

    backup = _backup()
    try:
        data = _load_yaml()
        applied = []

        if mode in ("aux", "all"):
            ttype = profile.get("task_type")
            aux_key = _AUX_MAP.get(ttype)
            if aux_key:
                aux = data.setdefault("auxiliary", {})
                blk = aux.setdefault(aux_key, {})
                # only set if currently auto/empty -> never clobber explicit user choice
                if not blk.get("model") or blk.get("provider") in (None, "", "auto"):
                    blk["provider"] = provider
                    blk["model"] = model
                    applied.append(f"auxiliary.{aux_key}")

        if mode in ("fallback", "all"):
            # prepend recommendation + fallbacks (deduped) into fallback_providers
            fp = data.get("fallback_providers", []) or []
            new_chain = [f"{provider}/{model}"]
            for fb in fallbacks:
                if fb.get("provider") and fb.get("model"):
                    new_chain.append(f"{fb['provider']}/{fb['model']}")
            for old in fp:
                if old not in new_chain:
                    new_chain.append(old)
            data["fallback_providers"] = new_chain[:12]
            applied.append("fallback_providers")

        if mode in ("subagent", "all"):
            # advisory: only when this profile is a subagent/delegated task
            if profile.get("parent_agent_or_subagent") == "subagent" or \
               profile.get("workflow_context") in ("delegate", "subagent", "kanban", "parallel"):
                deleg = data.setdefault("delegation", {})
                deleg["model"] = model
                deleg["provider"] = provider
                applied.append("delegation")

        if applied:
            _save_yaml(data)
            return {"mode": mode, "applied": True, "backup": backup, "targets": applied}
        return {"mode": mode, "applied": False, "backup": backup, "reason": "nothing to change"}
    except Exception as e:
        # auto-rollback on any error
        try:
            shutil.copy2(CONFIG_YAML.with_suffix(f".yaml.bak.mil_{backup.split('mil_')[-1]}"
                                                 if "mil_" in backup else backup), CONFIG_YAML)
        except Exception:
            pass
        return {"mode": mode, "applied": False, "backup": backup, "error": str(e)}


def rollback(backup_name: str) -> bool:
    bak = CONFIG_YAML.parent / backup_name
    if bak.exists():
        shutil.copy2(bak, CONFIG_YAML)
        return True
    return False


if __name__ == "__main__":
    print("ILMA Model Binder v1.0 — use via MIL recommend(bind=True).")
