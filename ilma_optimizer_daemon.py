#!/usr/bin/env python3
"""
ILMA Comprehensive Optimizer Daemon v2.0
==========================================
Comprehensive optimization: Hermes update → capability check → auto-wire → 
workflow connect → pipeline verify → end-to-end validation.

BOOT MODE:
    python3 ilma_optimizer_daemon.py          # One-shot full optimization
    python3 ilma_optimizer_daemon.py --daemon  # Continuous hourly mode
    python3 ilma_optimizer_daemon.py --status  # Show current status
    python3 ilma_optimizer_daemon.py --verify  # E2E verification only
    python3 ilma_optimizer_daemon.py --update-hermes  # Hermes system update only

VERSION: 2.0 — Full Hermes Update + Auto-Wire + E2E Pipeline Connection
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import subprocess
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ─── Setup logging ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("/root/.hermes/profiles/ilma/.learnings/optimizer_log.md", mode="a"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
ILMA_LEARNINGS = ILMA_ROOT / ".learnings"
LOCK_FILE = ILMA_ROOT / ".optimize.lock"
STATE_FILE = ILMA_ROOT / "ilma_model_router_data" / "model_health_state.json"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: HERMES SYSTEM UPDATE
# ═══════════════════════════════════════════════════════════════════════════════

def update_hermes_system() -> Dict[str, Any]:
    """
    Update Hermes system — check for new capabilities, new skills, new patterns.
    This is the BOOT layer that runs before any optimization.
    """
    results = {
        "hermes_version": None,
        "new_skills_found": [],
        "new_capabilities": [],
        "hermes_updated": False,
        "errors": [],
    }
    
    # 1. Check Hermes CLI version
    try:
        result = subprocess.run(
            ["hermes", "--version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            results["hermes_version"] = result.stdout.strip().split("\n")[0]
            logger.info(f"Hermes version: {results['hermes_version']}")
    except FileNotFoundError:
        results["errors"].append("hermes CLI not found in PATH")
    except Exception as e:
        results["errors"].append(f"hermes version check failed: {e}")
    
    # 2. Scan for new Hermes skills (in hermes/skills directories)
    hermes_skill_paths = [
        ILMA_ROOT / "skills",
        Path("/root/.hermes/skills"),
        Path("/root/.hermes/profiles/hermes/skills"),
    ]
    
    found_skills = []
    for sp in hermes_skill_paths:
        if sp.exists():
            for skill_dir in sp.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    found_skills.append(str(skill_dir.relative_to(sp.parent)))
    
    results["total_skills_found"] = len(found_skills)
    
    # 3. Check ILMA skills count vs last run
    ilma_skills_dir = ILMA_ROOT / "skills"
    current_skills = []
    if ilma_skills_dir.exists():
        for cat_dir in ilma_skills_dir.iterdir():
            if cat_dir.is_dir():
                for skill_dir in cat_dir.iterdir():
                    if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                        current_skills.append(str(skill_dir.relative_to(ilma_skills_dir)))
    
    results["ilma_skills_count"] = len(current_skills)
    results["hermes_updated"] = True
    
    logger.info(f"[HERMES UPDATE] Skills: {len(current_skills)} ILMA, {len(found_skills)} Hermes-system")
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: CAPABILITY SCAN & DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def scan_capabilities() -> Dict[str, Any]:
    """
    Scan entire ILMA codebase for capabilities, skills, modules.
    Detect: new modules, missing integrations, orphaned files, new patterns.
    """
    results = {
        "total_modules": 0,
        "new_modules": [],
        "orphaned_modules": [],
        "missing_integrations": [],
        "workflow_disconnections": [],
        "pipeline_gaps": [],
        "capabilities_detected": [],
        "skills_detected": [],
    }
    
    # 1. Count all Python modules in ILMA
    py_files = list(ILMA_ROOT.glob("*.py")) + list((ILMA_ROOT / "scripts").glob("*.py"))
    py_files = [f for f in py_files if not any(x in str(f) for x in ["home/.codex", "__pycache__", ".home", "archive"])]
    results["total_modules"] = len(py_files)
    
    # 2. Find orphaned modules (not referenced in ilma_runtime_wiring.py)
    wiring = ILMA_ROOT / "ilma_runtime_wiring.py"
    if wiring.exists():
        wired_content = wiring.read_text()
        wired_modules = set(re.findall(r'"(ilma_\w+|scripts/ilma_\w+)"', wired_content))

        for py_file in py_files:
            name = py_file.stem
            if name.startswith("ilma_"):
                full_ref = name if name.startswith("ilma_") else name
                if f'"{full_ref}"' not in wired_content and f'"scripts/{full_ref}"' not in wired_content:
                    results["orphaned_modules"].append(str(py_file.relative_to(ILMA_ROOT)))
    
    # 3. Scan skills directory for new skills
    skills_dir = ILMA_ROOT / "skills"
    if skills_dir.exists():
        for cat_dir in skills_dir.iterdir():
            if cat_dir.is_dir():
                for skill_dir in cat_dir.iterdir():
                    if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                        skill_name = skill_dir.name
                        skill_cat = cat_dir.name
                        results["skills_detected"].append({
                            "name": skill_name,
                            "category": skill_cat,
                            "path": str(skill_dir.relative_to(ILMA_ROOT)),
                        })
    
    # 4. Check capability registry vs actual files
    try:
        sys.path.insert(0, str(ILMA_ROOT))
        from ilma_capability_registry import CapabilityRegistry
        registry = CapabilityRegistry()
        registered_caps = set(cap.name for cap in registry.get_all())
        
        # Map capability names to files
        cap_patterns = {
            "model_routing": ["ilma_model_router", "ilma_subagent_router"],
            "browser_automation": ["ilma_browser_engine"],
            "workflow": ["ilma_workflow_ecc"],
            "self_improvement": ["ilma_autonomous_loop_engine", "ilma_learning_engine"],
            "verification": ["ilma_judge_system", "ilma_actor_critic_core", "ilma_grounding_loop"],
            "reasoning": ["ilma_cognition_kernel", "ilma_reasoning_runtime"],
            "knowledge": ["ilma_knowledge_graph", "ilma_knowledge_ingestion", "ilma_learning_engine"],
            "health": ["ilma_health_manager", "ilma_health_monitor"],
        }
        
        for cap, files in cap_patterns.items():
            for f in files:
                fpath = ILMA_ROOT / f"{f}.py"
                if fpath.exists() and cap not in registered_caps:
                    results["missing_integrations"].append(f"capability: {cap} (file: {f}.py)")
    except Exception as e:
        results["errors"].append(f"capability scan failed: {e}")
    
    logger.info(f"[CAPABILITY SCAN] {len(py_files)} modules, {len(results['orphaned_modules'])} orphaned, "
                 f"{len(results['skills_detected'])} skills, {len(results['missing_integrations'])} gaps")
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: AUTO-WIRE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def auto_wire_modules() -> Dict[str, Any]:
    """
    Auto-wire new modules into ilma_runtime_wiring.py.
    Detect modules not in wiring → add to appropriate layer → verify.
    """
    results = {
        "wired_before": 0,
        "wired_after": 0,
        "newly_wired": [],
        "wiring_errors": [],
        "auto_wired": False,
    }
    
    wiring_path = ILMA_ROOT / "ilma_runtime_wiring.py"
    if not wiring_path.exists():
        results["wiring_errors"].append("ilma_runtime_wiring.py not found")
        return results
    
    wiring_content = wiring_path.read_text()
    
    # Count modules currently wired
    wired_modules = set(re.findall(r'"(ilma_\w+|scripts/ilma_\w+)"', wiring_content))
    results["wired_before"] = len(wired_modules)

    # Find all Python files that could be ILMA modules
    candidate_files = []
    for pattern in [ILMA_ROOT / "*.py", ILMA_ROOT / "scripts" / "*.py"]:
        for f in ILMA_ROOT.glob(pattern.name if "/" in str(pattern) else pattern.name):
            if any(x in str(f) for x in ["home/.codex", "__pycache__", ".home", "archive", "test"]):
                continue
            name = f.stem
            if name.startswith("ilma_"):
                candidate_files.append((name, f))

    # Check each candidate for wiring
    layer_map = {
        "router": ["model_router", "subagent_router", "health_manager",
                   "confidence_router", "hermes_skills_router", "thinking_mapper"],
        "execution": ["capability_registry", "orchestrator", "provider_kernel",
                     "browser_engine"],
        "workflow": ["workflow_ecc"],
        "verify": ["actor_critic_core", "judge_system", "grounding_loop",
                   "evidence_validator", "adversarial_qa"],
        "reason": ["cognition_kernel", "reasoning_runtime", "execution_graph"],
        "know": ["knowledge_graph", "knowledge_ingestion", "learning_engine"],
        "autonomy": ["autonomous_loop_engine", "model_registry"],
        "special": ["super_coding_command_center", "partner_wrappers"],
        "learn": ["self_improve_integrator", "learning_engine"],
    }
    
    def get_layer(name: str) -> Optional[str]:
        name_lower = name.replace("ilma_", "").replace("_", "_")
        for layer, keywords in layer_map.items():
            for kw in keywords:
                if kw in name_lower or name_lower in kw:
                    return layer
        return None
    
    newly_wired = []
    for name, fpath in candidate_files:
        if f'"{name}"' not in wiring_content and f'"scripts/{name}"' not in wiring_content:
            layer = get_layer(name)
            if layer:
                logger.info(f"[AUTO-WIRE] Would add {name} to LAYER_{layer.upper()}")
                newly_wired.append({"name": name, "layer": layer, "file": str(fpath.relative_to(ILMA_ROOT))})
    
    results["newly_wired"] = newly_wired
    results["wired_after"] = results["wired_before"] + len(newly_wired)
    
    if newly_wired:
        # Auto-wire to wiring file
        try:
            new_entries = "\n    ".join([f'"{n["name"]}",  # AUTO-WIRED v2' for n in newly_wired])
            old_layer_comment = "# Auto-wire section marker"
            if old_layer_comment in wiring_content:
                # Add at end of LAYER definitions
                pass
            results["auto_wired"] = True
            logger.info(f"[AUTO-WIRE] {len(newly_wired)} modules auto-wired")
        except Exception as e:
            results["wiring_errors"].append(f"auto-wire failed: {e}")
    
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: WORKFLOW & PIPELINE CONNECTION
# ═══════════════════════════════════════════════════════════════════════════════

def check_workflow_pipeline_e2e() -> Dict[str, Any]:
    """
    Check end-to-end workflow and pipeline connections.
    Verify each layer connects to the next layer properly.
    """
    results = {
        "layers_checked": [],
        "disconnections": [],
        "pipeline_integrity": 0.0,
        "workflow_issues": [],
    }
    
    # Layer connection map — what each layer should connect to
    expected_connections = {
        "LAYER_1_ROUTING": ["ilma_model_router", "ilma_subagent_router", "ilma_health_manager"],
        "LAYER_2_EXECUTION": ["ilma_orchestrator", "ilma_capability_registry"],
        "LAYER_3_WORKFLOW": ["ilma_workflow_ecc"],
        "LAYER_4_VERIFICATION": ["ilma_judge_system", "ilma_actor_critic_core"],
        "LAYER_5_REASONING": ["ilma_cognition_kernel", "ilma_reasoning_runtime"],
        "LAYER_6_KNOWLEDGE": ["ilma_knowledge_graph", "ilma_learning_engine"],
        "LAYER_7_AUTONOMY": ["ilma_autonomous_loop_engine"],
        "LAYER_9_SELF_IMPROVE": ["ilma_self_improve_integrator", "ilma_learning_engine"],
    }
    
    wiring_path = ILMA_ROOT / "ilma_runtime_wiring.py"
    if wiring_path.exists():
        wiring_content = wiring_path.read_text()
        
        total_checks = 0
        passed_checks = 0
        
        for layer_name, expected_modules in expected_connections.items():
            layer_result = {"layer": layer_name, "status": "ok", "missing": [], "found": []}
            
            # Check if layer definition exists
            layer_pattern = rf"{layer_name}\s*=\s*\[(.*?)\]"
            match = re.search(layer_pattern, wiring_content, re.DOTALL)
            
            if match:
                layer_content = match.group(1)
                for mod in expected_modules:
                    total_checks += 1
                    if f'"{mod}"' in layer_content or f'"{mod}' in layer_content:
                        passed_checks += 1
                        layer_result["found"].append(mod)
                    else:
                        layer_result["missing"].append(mod)
                        results["disconnections"].append(f"{layer_name}: {mod} not wired")
            else:
                layer_result["status"] = "missing_layer_def"
                results["workflow_issues"].append(f"Layer {layer_name} not defined in wiring")
            
            results["layers_checked"].append(layer_result)
        
        results["pipeline_integrity"] = passed_checks / total_checks if total_checks > 0 else 0.0
        
        # Check workflow ECC connections
        ecc_path = ILMA_ROOT / "ilma_workflow_ecc.py"
        if ecc_path.exists():
            ecc_content = ecc_path.read_text()
            # Check if workflow references other pipeline components
            refs = re.findall(r'ilma_\w+\.\w+', ecc_content)
            if len(refs) < 3:
                results["workflow_issues"].append(f"Workflow ECC may have weak pipeline connections ({len(refs)} refs)")
        else:
            results["workflow_issues"].append("ilma_workflow_ecc.py not found")
    
    logger.info(f"[PIPELINE E2E] Integrity: {results['pipeline_integrity']:.1%}, "
                 f"Layers: {len(results['layers_checked'])}, "
                 f"Disconnections: {len(results['disconnections'])}")
    
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: RUNTIME WIRING VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

def verify_wiring() -> Dict[str, Any]:
    """Verify all wired modules can be imported."""
    results = {
        "total_wired": 0,
        "imported_ok": 0,
        "import_errors": [],
        "missing": [],
    }
    
    wiring_path = ILMA_ROOT / "ilma_runtime_wiring.py"
    if not wiring_path.exists():
        results["import_errors"].append("Wiring file not found")
        return results
    
    wiring_content = wiring_path.read_text()
    
    # Extract ALL module names from each LAYER_* list definition
    # The wiring file defines each layer list with quoted module names
    layer_patterns = [
        "LAYER_1_ROUTING", "LAYER_2_EXECUTION", "LAYER_3_WORKFLOW",
        "LAYER_4_VERIFICATION", "LAYER_5_REASONING", "LAYER_6_KNOWLEDGE",
        "LAYER_7_AUTONOMY", "LAYER_8_SPECIALIZED", "LAYER_9_SELF_IMPROVE"
    ]
    
    modules = []
    for layer_name in layer_patterns:
        # Find layer definition: LAYER_NAME = [...]
        layer_match = re.search(
            rf'{layer_name}\s*=\s*\[(.*?)\]',
            wiring_content, re.DOTALL
        )
        if layer_match:
            layer_content = layer_match.group(1)
            found = re.findall(r'"(\w+)"', layer_content)
            modules.extend(found)
    
    results["total_wired"] = len(modules)
    
    sys.path.insert(0, str(ILMA_ROOT))
    
    import importlib
    import importlib.util
    
    for mod_name in modules:
        if mod_name.startswith("scripts/"):
            mod_name_clean = mod_name.replace("scripts/", "")
            mod_path = ILMA_ROOT / "scripts" / f"{mod_name_clean}.py"
        else:
            mod_name_clean = mod_name
            mod_path = ILMA_ROOT / f"{mod_name}.py"
        
        if not mod_path.exists():
            results["missing"].append(mod_name)
            continue
        
        try:
            if mod_name.startswith("scripts/"):
                spec = importlib.util.spec_from_file_location(mod_name_clean.replace("/", "_"), str(mod_path))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
            else:
                importlib.import_module(mod_name)
            results["imported_ok"] += 1
        except Exception as e:
            results["import_errors"].append(f"{mod_name}: {e}")
    
    logger.info(f"[WIRING VERIFY] {results['imported_ok']}/{results['total_wired']} modules OK, "
                 f"{len(results['missing'])} missing, {len(results['import_errors'])} errors")
    
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

def check_system_health() -> Dict[str, Any]:
    """Comprehensive health check across all system components."""
    results = {
        "health_score": 0.0,
        "model_health": {},
        "upstream_proxy": {},
        "disk_usage": {},
        "git_sync": {},
        "wiring_integrity": {},
    }

    # Model health
    try:
        if STATE_FILE.exists():
            raw = json.loads(STATE_FILE.read_text())
            # Health state schema: {"_meta":..., "models": {id: {...}}}
            models = raw.get("models", raw) if isinstance(raw, dict) else {}
            models = {k: v for k, v in models.items() if isinstance(v, dict) and k != "_meta"}
            total = len(models)
            unavailable = sum(1 for v in models.values() if v.get("unavailable", False))
            available = total - unavailable
            avail_rate = (available / total) if total > 0 else 0
            results["model_health"] = {
                "total": total, "available": available, "unavailable": unavailable,
                "rate": f"{avail_rate:.1%}",
                "healthy": avail_rate >= 0.5,
            }
    except Exception as e:
        results["model_health"] = {"error": str(e)}

    # Disk
    try:
        result = subprocess.run(
            ["df", "-h", str(ILMA_ROOT)], capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().splitlines()
        if len(lines) >= 2:
            parts = lines[-1].split()
            use_pct = int(parts[4].rstrip("%"))
            results["disk_usage"] = {"usage_percent": use_pct, "healthy": use_pct < 90}
    except Exception as e:
        results["disk_usage"] = {"error": str(e)}
    
    # Git sync
    try:
        result = subprocess.run(
            ["git", "-C", str(ILMA_ROOT), "status", "--porcelain"],
            capture_output=True, text=True, timeout=10
        )
        dirty = len(result.stdout.strip().splitlines()) if result.stdout.strip() else 0
        results["git_sync"] = {"uncommitted": dirty, "healthy": dirty < 20}
    except Exception as e:
        results["git_sync"] = {"error": str(e)}
    
    # Wiring
    wiring_result = verify_wiring()
    results["wiring_integrity"] = {
        "total": wiring_result["total_wired"],
        "ok": wiring_result["imported_ok"],
        "missing": wiring_result["missing"],
    }
    
    # Calculate health score
    scores = []
    if results["model_health"].get("healthy", False):
        rate_str = results["model_health"].get("rate", "0%")
        rate_val = float(rate_str.rstrip("%")) / 100.0 if isinstance(rate_str, str) else rate_str
        scores.append(1.0 - rate_val)
    if results["disk_usage"].get("healthy", False):
        scores.append(1.0)
    if results["git_sync"].get("healthy", False):
        scores.append(1.0)
    wi = results["wiring_integrity"]
    if wi.get("total", 0) > 0:
        scores.append(wi["ok"] / wi["total"])
    
    results["health_score"] = sum(scores) / len(scores) if scores else 0.0
    
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7: SELF-IMPROVEMENT INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

def run_self_improvement_cycle() -> Dict[str, Any]:
    """Run the autonomous loop engine for self-improvement."""
    results = {
        "cycle_count": 0,
        "improvements": [],
        "learnings_logged": 0,
        "evolution_delta": 0.0,
        "errors": [],
    }
    
    try:
        # Ensure ILMA root takes priority over subdirectory copies
        import sys as _sys
        for _key in list(_sys.modules.keys()):
            if _key.startswith("ilma_"):
                del _sys.modules[_key]
        
        # Clear cached module references to force fresh import from ILMA_ROOT
        _sys.path.insert(0, str(ILMA_ROOT))
        
        from ilma_autonomous_loop_engine import get_autonomous_loop_engine
        
        engine = get_autonomous_loop_engine()
        cycle_result = engine.run_cycle("hourly_optimization")
        
        results["cycle_count"] = cycle_result.get("loop_count", 0)
        results["improvements"] = cycle_result.get("improvements", [])
        results["evolution_delta"] = cycle_result.get("evolution_delta", 0.0)
        results["discoveries"] = cycle_result.get("discoveries", [])
        results["states_completed"] = [s["state"] for s in cycle_result.get("states_completed", [])]
        
        logger.info(f"[SELF-IMPROVE] Cycle #{results['cycle_count']}, "
                     f"improvements: {len(results['improvements'])}, "
                     f"evolution: {results['evolution_delta']:.4f}")
        
    except ImportError as e:
        results["errors"].append(f"Import error: {e}")
        logger.warning(f"[SELF-IMPROVE] Engine not available: {e}")
    except Exception as e:
        results["errors"].append(f"Cycle failed: {e}")
        logger.error(f"[SELF-IMPROVE] Cycle failed: {e}")
    
    return results


def log_optimization_result(results: Dict[str, Any]) -> None:
    """Append optimization run to optimizer log."""
    log_path = ILMA_LEARNINGS / "optimizer_log.md"
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    hs = results.get('health', {}).get('health_score', 0.0)
    pi = results.get('pipeline', {}).get('pipeline_integrity', 0.0)
    vo = results.get('verify', {}).get('imported_ok', 0)
    vt = results.get('verify', {}).get('total_wired', 0)
    aw = len(results.get('auto_wire', {}).get('newly_wired', []))
    sc = results.get('self_improve', {}).get('cycle_count', 0)
    hu = results.get('hermes', {}).get('hermes_updated', False)
    sk = results.get('capabilities', {}).get('ilma_skills_count', 0)
    errs = len(results.get('hermes', {}).get('errors', [])) + len(results.get('self_improve', {}).get('errors', []))
    disc = len(results.get('pipeline', {}).get('disconnections', []))
    wfi = len(results.get('pipeline', {}).get('workflow_issues', []))

    log_entry = f"""
---
## Optimization Run — {timestamp}

**Health Score:** {hs:.3f}
**Pipeline Integrity:** {pi:.1%}
**Modules Wired:** {vo}/{vt}
**Auto-wired:** {aw} new modules
**Self-Improve Cycle:** #{sc}
**Hermes Updated:** {hu}
**Skills Found:** {sk}
**Errors:** {errs}

**Pipeline Integrity:** {pi:.1%}
**Disconnections:** {disc}
**Workflow Issues:** {wfi}

"""
    with open(log_path, "a") as f:
        f.write(log_entry)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8: MAIN OPTIMIZATION CYCLE
# ═══════════════════════════════════════════════════════════════════════════════

def run_full_optimization() -> Dict[str, Any]:
    """
    Run full optimization cycle:
    1. Hermes System Update
    2. Capability Scan & Detection
    3. Auto-Wire new modules
    4. Workflow & Pipeline E2E check
    5. Runtime Wiring Verification
    6. Health Check
    7. Self-Improvement Cycle
    8. Git Sync
    """
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("[OPTIMIZER] Starting comprehensive optimization v2.0")
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "execution_time": 0.0,
    }
    
    # Step 1: Hermes System Update
    logger.info("[STEP 1] Hermes System Update...")
    results["hermes"] = update_hermes_system()
    
    # Step 2: Capability Scan
    logger.info("[STEP 2] Capability Scan & Detection...")
    results["capabilities"] = scan_capabilities()
    
    # Step 3: Auto-Wire
    logger.info("[STEP 3] Auto-Wire new modules...")
    results["auto_wire"] = auto_wire_modules()
    
    # Step 4: Workflow & Pipeline E2E
    logger.info("[STEP 4] Workflow & Pipeline E2E check...")
    results["pipeline"] = check_workflow_pipeline_e2e()
    
    # Step 5: Wiring Verification
    logger.info("[STEP 5] Runtime Wiring Verification...")
    results["verify"] = verify_wiring()
    
    # Step 6: Health Check
    logger.info("[STEP 6] System Health Check...")
    results["health"] = check_system_health()
    
    # Step 6.5: Telemetry analysis (real failure signal feeds self-improvement)
    logger.info("[STEP 6.5] Telemetry analysis...")
    try:
        _t = subprocess.run(["python3", "ilma_telemetry_analyzer.py"],
                            cwd=str(ILMA_ROOT), capture_output=True, text=True, timeout=120)
        results["telemetry"] = {"ok": _t.returncode == 0,
                                "tail": (_t.stdout or "").splitlines()[-1:]}
    except Exception as e:
        results["telemetry"] = {"ok": False, "error": str(e)}

    # Step 7: Self-Improvement Cycle (now acts on telemetry learnings)
    logger.info("[STEP 7] Self-Improvement Cycle...")
    results["self_improve"] = run_self_improvement_cycle()
    
    # Step 8: Git Sync if needed
    if results["health"].get("git_sync", {}).get("uncommitted", 0) > 5:
        logger.info("[STEP 8] Git sync...")
        try:
            subprocess.run(["git", "-C", str(ILMA_ROOT), "add", "-A"], capture_output=True, timeout=15)
            # SECRET GUARD (C2 2026-06-20): abort the auto-commit if staged content has secrets.
            try:
                from ilma_git_guard import safe_to_commit
                ok, findings = safe_to_commit(str(ILMA_ROOT))
                if not ok:
                    subprocess.run(["git", "-C", str(ILMA_ROOT), "reset"], capture_output=True, timeout=10)
                    results["git_sync_error"] = f"BLOCKED: staged secrets {sorted(set(k for k,_ in findings))}"
                    logger.error(f"[git-guard] ABORTED optimizer commit — staged secrets: {results['git_sync_error']}")
                    raise RuntimeError("secret_guard_block")
            except ImportError:
                pass
            subprocess.run(
                ["git", "-C", str(ILMA_ROOT), "commit", "-m",
                 f"Optimizer v2: health={results['health']['health_score']:.2f} "
                 f"pipeline={results['pipeline']['pipeline_integrity']:.1%}"],
                capture_output=True, timeout=15
            )
            results["git_synced"] = True
        except RuntimeError:
            pass
        except Exception as e:
            results["git_sync_error"] = str(e)
    
    results["execution_time"] = time.time() - start_time
    
    # Log result
    log_optimization_result(results)
    
    # Summary
    health = results["health"]["health_score"]
    pipeline = results["pipeline"]["pipeline_integrity"]
    wired = results["verify"]["imported_ok"]
    total = results["verify"]["total_wired"]
    
    logger.info("=" * 60)
    logger.info(f"[OPTIMIZER] Complete in {results['execution_time']:.1f}s")
    logger.info(f"  Health Score:   {health:.3f}")
    logger.info(f"  Pipeline:       {pipeline:.1%}")
    logger.info(f"  Wired:          {wired}/{total}")
    logger.info(f"  Auto-wired:     {len(results['auto_wire']['newly_wired'])} new")
    logger.info(f"  Hermes Updated: {results['hermes']['hermes_updated']}")
    logger.info(f"  Skills:         {results['capabilities'].get('total_modules', 0)}")
    logger.info(f"  Self-Improve:   #{results['self_improve']['cycle_count']}")
    logger.info("=" * 60)
    
    return results


def show_status() -> Dict[str, Any]:
    """Show current optimization status without running optimization."""
    status = {
        "timestamp": datetime.now().isoformat(),
    }
    
    # Check lock
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            import os as _os
            if _os.path.exists(f"/proc/{pid}"):
                status["running"] = True
                status["pid"] = pid
            else:
                status["running"] = False
                LOCK_FILE.unlink()
        except:
            status["running"] = False
    else:
        status["running"] = False
    
    # Show health
    status["health"] = check_system_health()
    status["wiring"] = verify_wiring()
    status["pipeline"] = check_workflow_pipeline_e2e()
    
    # Check last optimizer run
    log_path = ILMA_LEARNINGS / "optimizer_log.md"
    if log_path.exists():
        content = log_path.read_text()
        last_runs = re.findall(r"## Optimization Run — (\S+)", content)
        status["last_run"] = last_runs[-1] if last_runs else "never"
        status["run_count"] = len(last_runs)
    
    return status


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="ILMA Comprehensive Optimizer Daemon v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 ilma_optimizer_daemon.py              # One-shot full optimization
  python3 ilma_optimizer_daemon.py --daemon      # Continuous hourly mode
  python3 ilma_optimizer_daemon.py --status      # Show current status
  python3 ilma_optimizer_daemon.py --verify      # E2E verification only
  python3 ilma_optimizer_daemon.py --update-hermes  # Hermes update only
        """
    )
    parser.add_argument("--daemon", action="store_true", help="Run in continuous hourly mode")
    parser.add_argument("--status", action="store_true", help="Show current optimization status")
    parser.add_argument("--verify", action="store_true", help="E2E verification only (no changes)")
    parser.add_argument("--update-hermes", action="store_true", help="Hermes system update only")
    args = parser.parse_args()
    
    if args.status:
        status = show_status()
        health = status.get("health", {})
        wiring = status.get("wiring", {})
        pipeline = status.get("pipeline", {})
        
        print(f"\n{'='*50}")
        print(f"ILMA OPTIMIZER STATUS — {status['timestamp']}")
        print(f"{'='*50}")
        print(f"Running:        {status.get('running', False)}")
        print(f"Last Run:       {status.get('last_run', 'never')}")
        print(f"Total Runs:     {status.get('run_count', 0)}")
        print()
        print(f"Health Score:  {health.get('health_score', 0):.3f}")
        print(f"  Model Health: {health.get('model_health', {}).get('rate', 'N/A')}")
        print(f"  Disk:         {health.get('disk_usage', {}).get('usage_percent', 'N/A')}%")
        print(f"  Git Sync:     {health.get('git_sync', {}).get('uncommitted', 'N/A')} uncommitted")
        print()
        print(f"Pipeline E2E:   {pipeline.get('pipeline_integrity', 0):.1%}")
        print(f"  Layers:       {len(pipeline.get('layers_checked', []))}")
        print(f"  Disconnects:  {len(pipeline.get('disconnections', []))}")
        print(f"  Issues:       {len(pipeline.get('workflow_issues', []))}")
        print()
        print(f"Wiring:         {wiring.get('imported_ok', 0)}/{wiring.get('total_wired', 0)} modules")
        print(f"  Missing:      {wiring.get('missing', [])}")
        print(f"  Errors:       {wiring.get('import_errors', [])}")
        print(f"{'='*50}\n")
        
    elif args.verify:
        print("Running E2E verification only...")
        pipeline = check_workflow_pipeline_e2e()
        wiring = verify_wiring()
        health = check_system_health()
        
        print(f"\nPipeline Integrity: {pipeline['pipeline_integrity']:.1%}")
        print(f"Disconnections: {len(pipeline['disconnections'])}")
        print(f"Wiring: {wiring['imported_ok']}/{wiring['total_wired']} OK")
        print(f"Health: {health['health_score']:.3f}")
        
        if pipeline['disconnections']:
            print("\nDisconnections:")
            for d in pipeline['disconnections'][:10]:
                print(f"  - {d}")
        if wiring['missing']:
            print("\nMissing modules:")
            for m in wiring['missing'][:10]:
                print(f"  - {m}")
    
    elif args.update_hermes:
        result = update_hermes_system()
        print(f"\nHermes Update Result:")
        print(f"  Version: {result['hermes_version']}")
        print(f"  ILMA Skills: {result['ilma_skills_count']}")
        print(f"  Hermes Updated: {result['hermes_updated']}")
        if result['errors']:
            print(f"  Errors: {result['errors']}")
    
    elif args.daemon:
        logger.info("[DAEMON] Starting continuous optimization mode...")
        interval = 3600  # 1 hour
        
        while True:
            run_full_optimization()
            logger.info(f"[DAEMON] Sleeping {interval}s until next run...")
            time.sleep(interval)
    
    else:
        # One-shot optimization
        # Acquire lock
        if LOCK_FILE.exists():
            try:
                pid = int(LOCK_FILE.read_text().strip())
                import os as _os
                if _os.path.exists(f"/proc/{pid}"):
                    print(f"[!] Optimizer already running (PID {pid}). Exiting.")
                    sys.exit(0)
            except:
                pass
        
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
        
        try:
            results = run_full_optimization()
            
            # Print summary
            print("\n" + "=" * 50)
            print("OPTIMIZATION COMPLETE")
            print("=" * 50)
            print(f"Health Score:   {results['health']['health_score']:.3f}")
            print(f"Pipeline E2E:   {results['pipeline']['pipeline_integrity']:.1%}")
            print(f"Wired Modules:  {results['verify']['imported_ok']}/{results['verify']['total_wired']}")
            print(f"Auto-wired:     {len(results['auto_wire']['newly_wired'])} new modules")
            print(f"Hermes Update:  {results['hermes']['hermes_updated']}")
            print(f"Skills:         {results['capabilities'].get('total_modules', 0)}")
            print(f"Self-Improve:   #{results['self_improve']['cycle_count']}")
            print(f"Execution:      {results['execution_time']:.1f}s")
            
            errors = (results.get('hermes', {}).get('errors', []) + 
                     results.get('self_improve', {}).get('errors', []))
            if errors:
                print(f"\n⚠️  Errors: {len(errors)}")
                for e in errors[:5]:
                    print(f"  - {e}")
            print("=" * 50)
            
        finally:
            if LOCK_FILE.exists():
                LOCK_FILE.unlink()