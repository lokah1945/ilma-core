#!/usr/bin/env python3
"""
ILMA Orphan Wiring — Phase 70 Autonomous-Autonomy
==================================================
Single canonical entry point that imports, registers, and exposes the
22 previously-orphan root-level ILMA modules. Each is wired to the
ILMA system via a stable Python API + CLI subcommand, so they are no
longer standalone scripts but first-class system capabilities.

LAYER MAPPING (matches ilma_runtime_wiring.py layers):
  LAYER_0_BOOT          → ilma_disable_manager, ilma_optimize_db
  LAYER_1_ROUTING       → (none — already in wiring)
  LAYER_2_EXECUTION     → ilma_chart_generator, ilma_longform_generator,
                          ilma_mil_apply, ilma_release_manager
  LAYER_3_WORKFLOW      → ilma_log_maintenance
  LAYER_4_VERIFICATION  → ilma_capability_drift_detector,
                          ilma_capability_improvement_miner,
                          ilma_reviewer_layer, ilma_shadow_evaluator,
                          ilma_self_improve, ilma_spec_db_measured
  LAYER_5_REASONING     → (none — already in wiring)
  LAYER_6_KNOWLEDGE     → ilma_skill_indexer, ilma_skill_ingestion
  LAYER_7_AUTONOMY      → ilma_optimizer_daemon
  LAYER_8_SPECIALIZED   → ilma_health_check,
                          ilma_production_monitor, ilma_telemetry_analyzer,
                          ilma_safe_rollback, ilma_notification_dispatcher

CLI:
    python3 ilma_orphan_wiring.py --list
    python3 ilma_orphan_wiring.py --invoke <capability> [args]
    python3 ilma_orphan_wiring.py --health
    python3 ilma_orphan_wiring.py --verify
"""
from __future__ import annotations

import importlib
import inspect
import json
import logging
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("ILMA.OrphanWiring")

# ============================================================
# CAPABILITY REGISTRY — the 22 orphan modules wired here
# ============================================================

@dataclass
class OrphanCapability:
    """A single previously-orphan module, now wired into ILMA."""
    module_name: str      # ilma_xxx
    layer: str            # LAYER_X
    purpose: str          # one-line description
    callable_obj: Optional[Any] = None  # the main function/class
    cli_command: Optional[str] = None  # the CLI subcommand this exposes
    imported_ok: bool = False
    last_invoked: Optional[float] = None
    invocation_count: int = 0
    last_error: Optional[str] = None


# The canonical list of orphan modules with their layer + purpose
_ORPHAN_SPECS: List[Dict[str, str]] = [
    # LAYER_0 — boot/config management
    {"module": "ilma_disable_manager",         "layer": "LAYER_0",  "purpose": "Tiered disable flags (provider/model cascading)",   "callable": "main",         "cli": "disable"},
    {"module": "ilma_optimize_db",             "layer": "LAYER_0",  "purpose": "Optimize SQLite databases (VACUUM, ANALYZE)",       "callable": "main",         "cli": "optimize-db"},

    # LAYER_2 — execution
    {"module": "ilma_chart_generator",         "layer": "LAYER_2",  "purpose": "Free matplotlib chart generation (PNG output)",   "callable": "make_chart",   "cli": "chart"},
    {"module": "ilma_longform_generator",      "layer": "LAYER_2",  "purpose": "Long-form document generation pipeline",          "callable": "main",         "cli": "longform"},
    {"module": "ilma_mil_apply",               "layer": "LAYER_2",  "purpose": "Military-grade standard application to artifacts", "callable": "main",         "cli": "mil-apply"},
    {"module": "ilma_release_manager",         "layer": "LAYER_2",  "purpose": "ILMA release/version management",                 "callable": "main",         "cli": "release"},

    # LAYER_3 — workflow
    {"module": "ilma_log_maintenance",         "layer": "LAYER_3",  "purpose": "Rotate JSONL logs to prevent disk bloat",          "callable": "main",         "cli": "log-maintenance"},

    # LAYER_4 — verification
    {"module": "ilma_capability_drift_detector",     "layer": "LAYER_4",  "purpose": "Detect capability degradation from quality logs", "callable": "detect_drift",        "cli": "drift-check"},
    {"module": "ilma_capability_improvement_miner",  "layer": "LAYER_4",  "purpose": "Mine telemetry into product backlog",             "callable": "mine_improvements",    "cli": "mine-improvements"},
    {"module": "ilma_reviewer_layer",                 "layer": "LAYER_4",  "purpose": "Reviewer layer for code/output verification",     "callable": "main",                 "cli": "review"},
    {"module": "ilma_shadow_evaluator",               "layer": "LAYER_4",  "purpose": "Shadow evaluation against historical decisions",  "callable": "main",                 "cli": "shadow-eval"},
    {"module": "ilma_self_improve",                   "layer": "LAYER_4",  "purpose": "Self-improvement runner (Phase 16 daily cron)",  "callable": "main",                 "cli": "self-improve"},
    {"module": "ilma_spec_db_measured",               "layer": "LAYER_4",  "purpose": "Spec database with measured evidence",            "callable": "main",                 "cli": "spec-measured"},

    # LAYER_6 — knowledge
    {"module": "ilma_skill_indexer",            "layer": "LAYER_6",  "purpose": "Index all installed skills (frontmatter scan)",   "callable": "main",         "cli": "skill-index"},
    {"module": "ilma_skill_ingestion",          "layer": "LAYER_6",  "purpose": "Ingest new skills into the registry",            "callable": "main",         "cli": "skill-ingest"},

    # LAYER_7 — autonomy
    {"module": "ilma_optimizer_daemon",         "layer": "LAYER_7",  "purpose": "Comprehensive optimizer daemon (8-step cycle)",   "callable": "main",         "cli": "optimize-all"},

    # LAYER_8 — specialized/admin tools
    {"module": "ilma_health_check",             "layer": "LAYER_8",  "purpose": "One-shot system health check",                   "callable": "main",         "cli": "health-check"},
    {"module": "ilma_production_monitor",       "layer": "LAYER_8",  "purpose": "Production-readiness monitor",                  "callable": "main",         "cli": "prod-monitor"},
    {"module": "ilma_telemetry_analyzer",       "layer": "LAYER_8",  "purpose": "Telemetry analysis and trend reports",           "callable": "main",         "cli": "telemetry-analyze"},
    {"module": "ilma_safe_rollback",            "layer": "LAYER_8",  "purpose": "Safe rollback for failed system changes",        "callable": "main",         "cli": "rollback"},
    {"module": "ilma_notification_dispatcher",  "layer": "LAYER_8",  "purpose": "Multi-channel notification dispatcher",           "callable": "main",         "cli": "notify"},
]


class OrphanWiring:
    """
    Phase 70-Autonomy: wire all 22 previously-orphan root-level ILMA
    modules into the system. Provides:
      - lazy import on first invocation (avoids boot-time overhead)
      - invocation tracking (last_invoked, count, last_error)
      - stable CLI surface (subcommands)
      - health probe
      - verification (import-test all 22)
    """
    def __init__(self):
        self.capabilities: Dict[str, OrphanCapability] = {}
        self._register_specs()

    def _register_specs(self) -> None:
        for spec in _ORPHAN_SPECS:
            self.capabilities[spec["cli"]] = OrphanCapability(
                module_name=spec["module"],
                layer=spec["layer"],
                purpose=spec["purpose"],
                cli_command=spec["cli"],
            )

    # ----- import helpers -----
    def _safe_import(self, module_name: str) -> Optional[Any]:
        try:
            return importlib.import_module(module_name)
        except Exception as e:
            logger.debug(f"Import failed for {module_name}: {e}")
            return None

    def get_module(self, cli_name: str) -> Optional[Any]:
        """Lazy-import the module backing a CLI subcommand."""
        cap = self.capabilities.get(cli_name)
        if not cap:
            return None
        mod = self._safe_import(cap.module_name)
        if mod is None:
            cap.last_error = "import failed"
            return None
        return mod

    def get_callable(self, cli_name: str) -> Optional[Callable]:
        """Get the main callable for a CLI subcommand."""
        cap = self.capabilities.get(cli_name)
        if not cap:
            return None
        mod = self.get_module(cli_name)
        if mod is None:
            return None
        # Find the spec for this CLI
        spec = next((s for s in _ORPHAN_SPECS if s["cli"] == cli_name), None)
        if not spec:
            return None
        call_name = spec.get("callable", "main")
        callable_obj = getattr(mod, call_name, None)
        if callable_obj is None:
            cap.last_error = f"callable {call_name} not found"
            return None
        cap.imported_ok = True
        return callable_obj

    # ----- invocation -----
    def invoke(self, cli_name: str, *args, **kwargs) -> Dict[str, Any]:
        """Invoke a capability by CLI name. Returns structured result."""
        cap = self.capabilities.get(cli_name)
        if not cap:
            return {"ok": False, "error": f"unknown capability: {cli_name}"}
        try:
            callable_obj = self.get_callable(cli_name)
            if callable_obj is None:
                return {
                    "ok": False,
                    "cli": cli_name,
                    "module": cap.module_name,
                    "error": cap.last_error or "callable not found",
                }
            # Run
            t0 = time.time()
            result = callable_obj(*args, **kwargs)
            elapsed = round(time.time() - t0, 3)
            cap.last_invoked = t0
            cap.invocation_count += 1
            cap.last_error = None
            return {
                "ok": True,
                "cli": cli_name,
                "module": cap.module_name,
                "layer": cap.layer,
                "elapsed_s": elapsed,
                "result": result,
            }
        except Exception as e:
            cap.last_error = f"{type(e).__name__}: {e}"
            cap.invocation_count += 1
            return {
                "ok": False,
                "cli": cli_name,
                "module": cap.module_name,
                "error": cap.last_error,
                "traceback": traceback.format_exc()[:500],
            }

    # ----- introspection -----
    def list_capabilities(self) -> List[Dict[str, Any]]:
        """List all wired capabilities."""
        out = []
        for cli, cap in sorted(self.capabilities.items()):
            out.append({
                "cli": cli,
                "module": cap.module_name,
                "layer": cap.layer,
                "purpose": cap.purpose,
                "imported_ok": cap.imported_ok,
                "invocation_count": cap.invocation_count,
                "last_invoked": cap.last_invoked,
                "last_error": cap.last_error,
            })
        return out

    def verify_all(self) -> Dict[str, Any]:
        """Test-import all 22 modules. Returns pass/fail per capability."""
        results = {"ok": 0, "fail": 0, "details": []}
        for cli, cap in self.capabilities.items():
            mod = self.get_module(cli)
            if mod is None:
                cap.imported_ok = False
                cap.last_error = "import failed"
                results["fail"] += 1
                results["details"].append({
                    "cli": cli, "module": cap.module_name, "ok": False,
                    "error": cap.last_error,
                })
            else:
                cap.imported_ok = True
                results["ok"] += 1
                results["details"].append({
                    "cli": cli, "module": cap.module_name, "ok": True,
                })
        results["total"] = len(self.capabilities)
        return results

    def health_snapshot(self) -> Dict[str, Any]:
        """Light health probe of the wiring layer."""
        return {
            "wiring": "ok",
            "capability_count": len(self.capabilities),
            "imported": sum(1 for c in self.capabilities.values() if c.imported_ok),
            "with_errors": sum(1 for c in self.capabilities.values() if c.last_error),
            "total_invocations": sum(c.invocation_count for c in self.capabilities.values()),
        }


# ============================================================
# Singleton
# ============================================================
_singleton: Optional[OrphanWiring] = None

def get_orphan_wiring() -> OrphanWiring:
    """Get the singleton OrphanWiring instance."""
    global _singleton
    if _singleton is None:
        _singleton = OrphanWiring()
    return _singleton


# ============================================================
# CLI
# ============================================================
def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="ILMA Orphan Wiring — connect 22 previously-orphan modules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--list", action="store_true", help="List all wired capabilities")
    parser.add_argument("--invoke", metavar="CLI", help="Invoke a capability by CLI name")
    parser.add_argument("--invoke-args", nargs=argparse.REMAINDER, help="Args to pass to the capability")
    parser.add_argument("--verify", action="store_true", help="Test-import all 22 modules")
    parser.add_argument("--health", action="store_true", help="Health snapshot")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    wiring = get_orphan_wiring()

    if args.list:
        result = wiring.list_capabilities()
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"{'CLI':<25} {'Module':<40} {'Layer':<12} {'Imports':<8}")
            print("-" * 90)
            for c in result:
                print(f"{c['cli']:<25} {c['module']:<40} {c['layer']:<12} {'✓' if c['imported_ok'] else '✗'}")
            print(f"\nTotal: {len(result)} capabilities wired")

    elif args.invoke:
        kwargs = {}
        if args.invoke_args:
            kwargs = {"args": args.invoke_args}
        result = wiring.invoke(args.invoke, **kwargs)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"OK: {result.get('ok')}")
            if result.get("ok"):
                print(f"  module:  {result.get('module')}")
                print(f"  layer:   {result.get('layer')}")
                print(f"  elapsed: {result.get('elapsed_s')}s")
            else:
                print(f"  error:   {result.get('error')}")
        return 0 if result.get("ok") else 1

    elif args.verify:
        result = wiring.verify_all()
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"Orphan wiring verification: {result['ok']}/{result['total']} imported OK")
            for d in result["details"]:
                marker = "✓" if d["ok"] else "✗"
                extra = f" — {d.get('error', '')}" if not d["ok"] else ""
                print(f"  {marker} {d['cli']:<25} {d['module']:<40}{extra}")
        return 0 if result["fail"] == 0 else 1

    elif args.health:
        result = wiring.health_snapshot()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            for k, v in result.items():
                print(f"  {k}: {v}")
        return 0

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
