#!/usr/bin/env python3
"""
ilma_system_map.py — ILMA whole-system self-awareness map (2026-06-22)
=======================================================================
Single source of truth describing the ENTIRE ILMA system so that (a) ILMA itself
can reason about its own components during optimization, and (b) the web dashboard
(ilma_dashboard_server.py) can render wiring / pipeline / runtime / file inventory.

Introspects, with NO heavy deps (stdlib + pymongo only):
  - modules (root ilma_*.py), scripts/, sot/**, skills/ (name+description+purpose)
  - import/reference graph -> LIVE vs ORPHAN classification
  - capability registry + runtime executor status (from MongoDB _meta)
  - SOT stats (models/providers, free counts, endpoint histogram, field list)
  - systemd units / timers / daemons + live gateway state

Writes: data/ilma_system_map.json  (consumed by the dashboard + autonomy loop).
CLI:  python3 ilma_system_map.py            # generate + write
      python3 ilma_system_map.py --print     # also print summary
"""
from __future__ import annotations
import os, re, ast, json, sys, subprocess, glob
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/root/.hermes/profiles/ilma")
OUT = ROOT / "data" / "ilma_system_map.json"

# Roots that count as "live" entrypoints for the reachability closure.
LIVE_ROOTS = [
    "ilma.py", "ilma_orchestrator.py", "ilma_master_orchestrator.py",
    "ilma_runtime_wiring.py", "ilma_autonomous_loop_engine.py", "ilma_optimizer_daemon.py",
    "ilma_subagent_router.py", "ilma_model_router.py", "ilma_provider_kernel.py",
    "ilma_hermes_skills_router.py", "ilma_workflow_ecc.py", "ilma_health_manager.py",
    "ilma_orphan_wiring.py", "ilma_sot_dispatcher.py", "ilma_system_map.py",
    "sot/sync/sot_sync_daemon.py", "sot/sync/sot_auto_sync.py",
]


def _doc_first_line(path: Path) -> str:
    """Return the first non-empty line of the module docstring (or a comment)."""
    try:
        tree = ast.parse(path.read_text(errors="ignore"))
        d = ast.get_docstring(tree)
        if d:
            for ln in d.splitlines():
                if ln.strip():
                    return ln.strip()[:200]
    except Exception:
        pass
    # fall back to first comment line
    try:
        for ln in path.read_text(errors="ignore").splitlines()[:15]:
            s = ln.strip()
            if s.startswith("#") and len(s) > 3:
                return s.lstrip("# ").strip()[:200]
    except Exception:
        pass
    return ""


def _defs(path: Path):
    """Top-level classes + functions."""
    classes, funcs = [], []
    try:
        tree = ast.parse(path.read_text(errors="ignore"))
        for n in tree.body:
            if isinstance(n, ast.ClassDef):
                classes.append(n.name)
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs.append(n.name)
    except Exception:
        pass
    return classes, funcs


def _imports(path: Path):
    """Local ilma_* module imports (for the wiring graph)."""
    out = set()
    try:
        tree = ast.parse(path.read_text(errors="ignore"))
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    out.add(a.name.split(".")[0])
            elif isinstance(n, ast.ImportFrom) and n.module:
                out.add(n.module.split(".")[0])
    except Exception:
        pass
    return {m for m in out if m.startswith("ilma_") or m.startswith("sot_")}


def scan_modules():
    """All python files in root + scripts/ + sot/, with metadata + import edges."""
    files = {}
    patterns = ["ilma_*.py"] + ["scripts/*.py", "scripts/**/*.py", "sot/**/*.py",
                "capabilities/**/*.py", "ilma_core/*.py"]
    seen = set()
    for pat in patterns:
        for p in ROOT.glob(pat):
            if "__pycache__" in str(p) or "/attic/" in str(p) or p.name in seen:
                continue
            rel = str(p.relative_to(ROOT))
            cls, fns = _defs(p)
            files[rel] = {
                "name": p.stem, "rel": rel, "size": p.stat().st_size,
                "doc": _doc_first_line(p), "classes": cls[:12], "functions": fns[:18],
                "imports": sorted(_imports(p)),
            }
    return files


def reachability(files: dict):
    """Mark each module LIVE if transitively imported from a LIVE_ROOT, else ORPHAN.
    Also scans configs/skills/sh for basename references (CLI-invoked tools count as live)."""
    by_stem = {}
    for rel, m in files.items():
        by_stem.setdefault(m["name"], []).append(rel)
    # textual reference set (configs, sh, json, md, systemd, cron)
    ref_text = ""
    for pat in ("*.sh", "*.json", "*.yaml", "*.yml", "systemd/*", "cron/*",
                "skills/**/SKILL.md", "scripts/*.sh", "*.md"):
        for p in ROOT.glob(pat):
            if "/attic/" in str(p) or "node_modules" in str(p):
                continue
            try:
                ref_text += p.read_text(errors="ignore")
            except Exception:
                pass
    live = set()
    stack = [r for r in LIVE_ROOTS if r in files]
    while stack:
        rel = stack.pop()
        if rel in live:
            continue
        live.add(rel)
        for imp in files.get(rel, {}).get("imports", []):
            for tgt in by_stem.get(imp, []):
                if tgt not in live:
                    stack.append(tgt)
    # CLI/text-referenced files are live too
    for rel, m in files.items():
        if rel in live:
            continue
        if re.search(rf"\b{re.escape(m['name'])}\.py\b", ref_text):
            live.add(rel)
    orphans = [r for r in files if r not in live]
    return sorted(live), sorted(orphans)


def scan_skills():
    out = []
    for d in sorted(ROOT.glob("skills/*/")):
        sk = d / "SKILL.md"
        meta = {"name": d.name, "description": "", "triggers": []}
        if sk.exists():
            txt = sk.read_text(errors="ignore")
            mname = re.search(r"^name:\s*(.+)$", txt, re.M)
            mdesc = re.search(r"^description:\s*(.+)$", txt, re.M)
            if mname:
                meta["name"] = mname.group(1).strip()
            if mdesc:
                meta["description"] = mdesc.group(1).strip()[:240]
            meta["triggers"] = re.findall(r'^\s*-\s*"?([^"\n]+?)"?\s*$', txt, re.M)[:6]
        out.append(meta)
    return out


def sot_snapshot():
    snap = {"available": False}
    try:
        sys.path.insert(0, str(ROOT))
        from ilma_mongo_connection import get_mongo_manager
        db = get_mongo_manager().get_client()["credentials"]
        M = db.models
        snap["available"] = True
        snap["models_total"] = M.count_documents({})
        snap["models_active"] = M.count_documents({"is_active": True})
        snap["models_free"] = M.count_documents({"is_free_final": True, "is_active": True})
        snap["providers"] = db.providers.count_documents({})
        snap["llm_providers"] = db.llm_providers.count_documents({})
        snap["fields"] = sorted({k for d in M.find({}, {"_id": 0}).limit(60) for k in d})
        snap["endpoint_histogram"] = {
            r["_id"]: {"n": r["n"], "free": r["free"]} for r in M.aggregate([
                {"$match": {"endpoint_type": {"$exists": True}, "is_active": True}},
                {"$group": {"_id": "$endpoint_type", "n": {"$sum": 1},
                            "free": {"$sum": {"$cond": ["$is_free_final", 1, 0]}}}},
                {"$sort": {"n": -1}}])}
        cr = db["_meta"].find_one({"_id": "capability_registry"}) or {}
        snap["capability_registry"] = {
            "version": cr.get("version"), "count": cr.get("count"),
            "counts_by_layer": cr.get("counts_by_layer"),
            "runtime_executors": {k: v.get("status") if isinstance(v, dict) else v
                                  for k, v in (cr.get("runtime_executors") or {}).items()
                                  if isinstance(v, dict) and "status" in v},
        }
    except Exception as e:
        snap["error"] = str(e)[:200]
    return snap


def runtime_snapshot():
    rt = {}
    try:
        gs = json.loads((ROOT / "gateway_state.json").read_text())
        rt["gateway"] = {"pid": gs.get("pid"), "state": gs.get("gateway_state"),
                         "platforms": {k: v.get("state") for k, v in gs.get("platforms", {}).items()}}
    except Exception:
        rt["gateway"] = {"state": "unknown"}
    try:
        r = subprocess.run(["systemctl", "list-units", "--no-legend", "--plain"],
                           capture_output=True, text=True, timeout=10)
        rt["units"] = [ln.split()[0] for ln in r.stdout.splitlines()
                       if "ilma" in ln.lower() and (".service" in ln or ".timer" in ln)][:20]
    except Exception:
        rt["units"] = []
    rt["autonomy_paused"] = (ROOT / ".autonomy_paused").exists()
    return rt


def build():
    files = scan_modules()
    live, orphans = reachability(files)
    skills = scan_skills()
    m = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "concept": ("ILMA: evidence-based, free-tier-first autonomous Hermes agent. "
                    "Routes tasks to the best free model among ~2000 (SOT), executes via "
                    "orchestrator->subagent router->provider kernel/capability executors, "
                    "verifies (judge/grounding/coding-sandbox), and self-optimizes. "
                    "Target: military-grade generalist."),
        "counts": {
            "modules_total": len(files), "live": len(live), "orphan": len(orphans),
            "skills": len(skills), "root_modules": len([f for f in files if "/" not in f]),
            "scripts": len([f for f in files if f.startswith("scripts/")]),
            "sot_modules": len([f for f in files if f.startswith("sot/")]),
        },
        "pipeline": [
            {"stage": "entry", "what": "Hermes gateway (Telegram/WhatsApp/API) → claude-opus-4-8 @9102; or ilma_orchestrator.execute (CLI/delegated)"},
            {"stage": "route", "what": "ilma_model_router.get_best_model — SOT-scored best FREE model; self-heals past failed models (avoid_models)"},
            {"stage": "dispatch", "what": "media capability → ilma_subagent_router.execute_capability → sot_dispatch (free pick) → transport executor"},
            {"stage": "execute", "what": "chat → _call_direct (wrapper-nvidia/openrouter/...); media → nvidia genai/groq/edge/wrapper"},
            {"stage": "verify", "what": "coding: sandbox(bwrap)+ruff/bandit+repair+adjudicator; academic: grounding gate + citation consistency"},
            {"stage": "autonomy", "what": "ilma-autonomy.timer (30m) → optimizer daemon; sot-sync daemon (change-stream) keeps models live"},
        ],
        "files": files,
        "live": live,
        "orphans": orphans,
        "skills": skills,
        "sot": sot_snapshot(),
        "runtime": runtime_snapshot(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(m, indent=2, default=str))
    return m


if __name__ == "__main__":
    mp = build()
    print(f"✓ system map -> {OUT}")
    print(f"  modules={mp['counts']['modules_total']} live={mp['counts']['live']} "
          f"orphan={mp['counts']['orphan']} skills={mp['counts']['skills']}")
    if mp["sot"].get("available"):
        print(f"  SOT: {mp['sot']['models_active']} active models, "
              f"{mp['sot']['models_free']} free; {mp['sot']['providers']} providers")
    if "--print" in sys.argv:
        print(json.dumps({k: mp[k] for k in ("counts", "pipeline", "runtime")}, indent=2, default=str))
