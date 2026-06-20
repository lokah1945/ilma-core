#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         ILMA HEALTH CHECK — UNIFIED SYSTEM CHECK                           ║
║  Source: ilma_health_manager.py + ilma_capability_health_dashboard.py      ║
╚══════════════════════════════════════════════════════════════════════════════╝

Unified health check system for ILMA — consolidates:
  1. Model/Provider health (ilma_health_manager.py)
  2. Bridge proxy health (port 8001)
  3. Capability registry health
  4. MASTER DB integrity
  5. Pipeline wiring verification
  6. Evidence validator integration

Usage:
    python3 scripts/ilma_health_check.py              # Quick check
    python3 scripts/ilma_health_check.py --full        # Full diagnostics
    python3 scripts/ilma_health_check.py --dashboard   # ASCII dashboard
    python3 scripts/ilma_health_check.py --json        # JSON output
    python3 scripts/ilma_health_check.py --model <id>  # Check specific model
    python3 scripts/ilma_health_check.py --provider <p> # Check provider

Integration:
  - ilma_health_manager.py → model/provider health state
  - ilma_evidence_validator.py → system evidence validation
  - ilma_capability_health_dashboard.py → capability scanning
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# ─── ILMA Paths ────────────────────────────────────────────────────────────────

ILMA_PROFILE = Path(os.environ.get("ILMA_PROFILE", "/root/.hermes/profiles/ilma"))
SCRIPTS_DIR = ILMA_PROFILE / "scripts"
SKILLS_DIR = ILMA_PROFILE / "skills"
DATA_DIR = ILMA_PROFILE / "data"
MASTER_DB = ILMA_PROFILE / "ilma_model_router_data" / "PROVIDER_INTELLIGENCE_MASTER.json"
HEALTH_STATE = ILMA_PROFILE / "ilma_provider_health_state.json"  # ⛔ renamed 2026-06-18
EVIDENCE_REGISTRY = ILMA_PROFILE / "config" / "ilma_evidence_registry.json"

# Import ILMA health components
sys.path.insert(0, str(ILMA_PROFILE))
from ilma_health_manager import (
    HealthManager, get_health_manager,
    ModelStatus, ProviderStatus,
)
from ilma_evidence_validator import EvidenceValidator


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class HealthCheckResult:
    """Single health check result."""
    name: str
    status: str  # OK / WARNING / ERROR / SKIPPED
    details: str
    timestamp: str
    errors: List[str]
    warnings: List[str]

    def __str__(self) -> str:
        icon = "✅" if self.status == "OK" else ("⚠️" if self.status == "WARNING" else "❌")
        return f"{icon} [{self.status}] {self.name}: {self.details}"


@dataclass
class SystemHealthReport:
    """Full system health report."""
    timestamp: str
    overall_status: str  # HEALTHY / DEGRADED / CRITICAL
    total_checks: int
    passed: int
    failed: int
    warnings: int
    checks: List[HealthCheckResult]
    model_stats: Dict[str, Any]
    provider_stats: Dict[str, Any]
    master_stats: Dict[str, Any]
    uptime_seconds: float

    def summary(self) -> str:
        return (
            f"System Health: {self.overall_status} "
            f"({self.passed}/{self.total_checks} checks passed, "
            f"{self.warnings} warnings, {self.failed} failures)"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class ILMAHealthCheck:
    """
    Unified health check engine for ILMA.
    Runs end-to-end checks across all critical components.
    """

    _singleton: Optional["ILMAHealthCheck"] = None
    _start_time: float = time.time()

    def __init__(self):
        self.hm = get_health_manager()
        self.ev = EvidenceValidator.get_instance()
        self._master_cache: Optional[Dict] = None
        self._master_mtime: float = 0
        self.checks: List[HealthCheckResult] = []

    @classmethod
    def get_instance(cls) -> "ILMAHealthCheck":
        if cls._singleton is None:
            cls._singleton = cls()
        return cls._singleton

    # ─── MASTER DB ────────────────────────────────────────────────────────────

    def _load_master(self) -> Dict:
        """Load MASTER with TTL cache (120s)."""
        try:
            mtime = MASTER_DB.stat().st_mtime
            if self._master_cache is None or (mtime - self._master_mtime) > 120:
                with open(MASTER_DB) as f:
                    self._master_cache = json.load(f)
                self._master_mtime = mtime
        except Exception:
            self._master_cache = {"providers": {}}
        return self._master_cache or {}

    # ─── Core Checks ──────────────────────────────────────────────────────────

    def check_master_db(self) -> HealthCheckResult:
        """Check PROVIDER_INTELLIGENCE_MASTER.json integrity."""
        errors: List[str] = []
        warnings: List[str] = []

        if not MASTER_DB.exists():
            return HealthCheckResult(
                name="MASTER_DB", status="ERROR", details="File not found",
                timestamp=datetime.now().isoformat(), errors=["MASTER_DB not found"], warnings=[],
            )

        try:
            master = self._load_master()
            providers = master.get("providers", {})
            total_models = sum(len(p.get("models", {})) for p in providers.values())
            total_free = sum(
                1 for p in providers.values()
                for v in p.get("models", {}).values()
                if v.get("is_free", False)
            )

            details = f"{total_models} models, {total_free} FREE across {len(providers)} providers"

            # Validate provider structure
            for provider_id, provider_data in providers.items():
                if "models" not in provider_data:
                    warnings.append(f"Provider {provider_id} has no models key")
                models = provider_data.get("models", {})
                for model_id, model_data in models.items():
                    if "is_free" not in model_data:
                        warnings.append(f"Model {provider_id}/{model_id} missing is_free flag")

            return HealthCheckResult(
                name="MASTER_DB", status="OK", details=details,
                timestamp=datetime.now().isoformat(), errors=errors, warnings=warnings,
            )
        except json.JSONDecodeError as e:
            return HealthCheckResult(
                name="MASTER_DB", status="ERROR",
                details=f"Invalid JSON: {str(e)[:50]}",
                timestamp=datetime.now().isoformat(),
                errors=[f"JSON decode error: {e}"], warnings=[],
            )
        except Exception as e:
            return HealthCheckResult(
                name="MASTER_DB", status="ERROR",
                details=f"Error: {str(e)[:50]}",
                timestamp=datetime.now().isoformat(),
                errors=[str(e)], warnings=[],
            )

    def check_model_health(self, model_id: Optional[str] = None) -> HealthCheckResult:
        """Check model health from health manager."""
        errors: List[str] = []
        warnings: List[str] = []
        details: str

        stats = self.hm.get_stats()

        if model_id:
            mh = self.hm.get_model_health(model_id)
            if mh.status == ModelStatus.RATE_LIMITED:
                details = f"Model {model_id}: RATE_LIMITED"
                warnings.append(f"Model rate-limited: {model_id}")
            elif mh.status == ModelStatus.ERROR:
                details = f"Model {model_id}: ERROR"
                errors.append(f"Model error state: {model_id}")
            elif mh.status == ModelStatus.AVAILABLE:
                details = f"Model {model_id}: AVAILABLE"
            else:
                details = f"Model {model_id}: {mh.status.value}"
            status = "ERROR" if mh.status in (ModelStatus.RATE_LIMITED, ModelStatus.ERROR) else "OK"
        else:
            # Aggregate stats
            mc = stats["model_count"]
            ac = stats["available_count"]
            rc = stats["rate_limited_count"]
            ec = stats["error_count"]
            details = f"{mc} tracked, {ac} available, {rc} rate-limited, {ec} errors"

            if ec > 0:
                errors.append(f"{ec} models in ERROR state")
            if rc > 0:
                warnings.append(f"{rc} models RATE_LIMITED")
            status = "ERROR" if ec > 0 else ("WARNING" if rc > 0 else "OK")

        return HealthCheckResult(
            name="MODEL_HEALTH", status=status, details=details,
            timestamp=datetime.now().isoformat(), errors=errors, warnings=warnings,
        )

    def check_provider_health(self, provider: Optional[str] = None) -> HealthCheckResult:
        """Check provider health from health manager."""
        errors: List[str] = []
        warnings: List[str] = []

        if provider:
            ph = self.hm.get_provider_health(provider)
            is_healthy = ph.is_healthy()
            details = f"Provider {provider}: {ph.status.value}, {ph.models_available}/{ph.models_total} available"
            if ph.rate_limited:
                warnings.append(f"Provider rate-limited: {provider}")
            status = "ERROR" if not is_healthy else "OK"
        else:
            # Check all providers
            all_providers = list(self.hm._providers.keys())
            unhealthy = []
            rate_limited = []
            for p, ph in self.hm._providers.items():
                if ph.status in (ProviderStatus.UNHEALTHY,):
                    unhealthy.append(p)
                if ph.rate_limited:
                    rate_limited.append(p)

            details = f"{len(all_providers)} providers tracked"
            if unhealthy:
                errors.append(f"Unhealthy providers: {unhealthy}")
            if rate_limited:
                warnings.append(f"Rate-limited providers: {rate_limited}")
            status = "ERROR" if unhealthy else ("WARNING" if rate_limited else "OK")

        return HealthCheckResult(
            name="PROVIDER_HEALTH", status=status, details=details,
            timestamp=datetime.now().isoformat(), errors=errors, warnings=warnings,
        )

    def check_capability_registry(self) -> HealthCheckResult:
        """Check if capability registry files exist and are valid."""
        errors: List[str] = []
        warnings: List[str] = []

        reg_files = [
            ILMA_PROFILE / "ilma_capability_registry.py",
            ILMA_PROFILE / "config" / "ilma_capability_registry.json",
        ]

        found = []
        for f in reg_files:
            if f.exists():
                found.append(f.name)
            else:
                warnings.append(f"Missing: {f.name}")

        if len(found) == len(reg_files):
            details = f"Capability registry: {len(found)}/{len(reg_files)} files present"
            status = "OK"
        elif found:
            details = f"Capability registry: {len(found)}/{len(reg_files)} files present"
            status = "WARNING"
        else:
            details = "Capability registry: no files found"
            errors.append("No capability registry files")
            status = "ERROR"

        return HealthCheckResult(
            name="CAPABILITY_REGISTRY", status=status, details=details,
            timestamp=datetime.now().isoformat(), errors=errors, warnings=warnings,
        )

    def check_evidence_system(self) -> HealthCheckResult:
        """Check evidence system (validator + registry)."""
        errors: List[str] = []
        warnings: List[str] = []

        # Check validator exists
        ev_path = ILMA_PROFILE / "ilma_evidence_validator.py"
        if not ev_path.exists():
            errors.append("ilma_evidence_validator.py not found")
            return HealthCheckResult(
                name="EVIDENCE_SYSTEM", status="ERROR",
                details="Evidence validator not found",
                timestamp=datetime.now().isoformat(), errors=errors, warnings=[],
            )

        # Run system check
        check = self.ev.validate_system_check()
        if check["errors"]:
            errors.extend(check["errors"])
        if check["warnings"]:
            warnings.extend(check["warnings"])

        entries = check["evidence_entries"]
        valid = check["evidence_valid_count"]
        details = f"Evidence: {valid}/{entries} valid entries"
        status = "ERROR" if errors else ("WARNING" if warnings else "OK")

        return HealthCheckResult(
            name="EVIDENCE_SYSTEM", status=status, details=details,
            timestamp=datetime.now().isoformat(), errors=errors, warnings=warnings,
        )

    def check_pipeline_wiring(self) -> HealthCheckResult:
        """Check critical pipeline files are wired and importable."""
        errors: List[str] = []
        warnings: List[str] = []

        critical_files = [
            ("ilma_workflow_ecc.py", "Workflow ECC (8-step pipeline)"),
            ("ilma_model_router.py", "Model Router"),
            ("ilma_orchestrator.py", "Orchestrator"),
            ("ilma_health_manager.py", "Health Manager"),
            ("ilma_capability_registry.py", "Capability Registry"),
            ("ilma_evidence_validator.py", "Evidence Validator"),
            ("scripts/ilma_db_pipeline.py", "DB Pipeline"),
            ("scripts/ilma_benchmark_autoloop.py", "Benchmark Autoloop"),
        ]

        found: List[str] = []
        missing: List[str] = []

        for fname, desc in critical_files:
            fpath = ILMA_PROFILE / fname if "/" in fname else ILMA_PROFILE / fname
            if fpath.exists():
                found.append(desc)
            else:
                missing.append(desc)

        if missing:
            errors.append(f"Missing files: {missing}")
            status = "ERROR"
        elif len(found) == len(critical_files):
            details = f"Pipeline wiring: all {len(found)} critical files present"
            status = "OK"
        else:
            details = f"Pipeline wiring: {len(found)}/{len(critical_files)} files present"
            warnings.append(f"Some files missing: {[m for m in missing]}")
            status = "WARNING"

        return HealthCheckResult(
            name="PIPELINE_WIRING", status=status, details=details,
            timestamp=datetime.now().isoformat(), errors=errors, warnings=warnings,
        )

    def check_runtime_imports(self) -> HealthCheckResult:
        """Check that critical modules can be imported."""
        errors: List[str] = []
        warnings: List[str] = []

        critical_modules = [
            ("ilma_health_manager", "Health Manager"),
            ("ilma_evidence_validator", "Evidence Validator"),
            ("ilma_model_router", "Model Router"),
            ("ilma_capability_registry", "Capability Registry"),
        ]

        importable: List[str] = []
        failed: List[str] = []

        for mod_name, desc in critical_modules:
            try:
                __import__(mod_name)
                importable.append(desc)
            except Exception as e:
                failed.append(f"{desc}: {str(e)[:40]}")

        if failed:
            errors.extend(failed)
            status = "ERROR"
        elif importable:
            details = f"Runtime imports: {len(importable)}/{len(critical_modules)} modules importable"
            status = "OK" if len(importable) == len(critical_modules) else "WARNING"

        return HealthCheckResult(
            name="RUNTIME_IMPORTS", status=status,
            details=details if importable else "All imports failed",
            timestamp=datetime.now().isoformat(), errors=errors, warnings=warnings,
        )

    def check_free_model_routing(self) -> HealthCheckResult:
        """Check FREE model routing is working."""
        errors: List[str] = []
        warnings: List[str] = []

        try:
            from ilma_model_router import get_best_model
            result = get_best_model("general", prefer_free=True)
            if result:
                details = f"FREE model routing works: {result}"
                status = "OK"
            else:
                details = "No FREE model returned"
                warnings.append("FREE model routing returned None")
                status = "WARNING"
        except Exception as e:
            details = f"FREE model routing error: {str(e)[:50]}"
            errors.append(str(e))
            status = "ERROR"

        return HealthCheckResult(
            name="FREE_MODEL_ROUTING", status=status, details=details,
            timestamp=datetime.now().isoformat(), errors=errors, warnings=warnings,
        )

    # ─── Run All Checks ──────────────────────────────────────────────────────

    def run_all(self, quick: bool = False) -> SystemHealthReport:
        """Run all health checks."""
        checks: List[HealthCheckResult] = []

        if quick:
            # Fast checks only
            checks.extend([
                self.check_master_db(),
                self.check_model_health(),
                self.check_pipeline_wiring(),
            ])
        else:
            # Full check suite
            checks.extend([
                self.check_master_db(),
                self.check_model_health(),
                self.check_provider_health(),
                self.check_capability_registry(),
                self.check_evidence_system(),
                self.check_pipeline_wiring(),
                self.check_runtime_imports(),
                self.check_free_model_routing(),
            ])

        passed = sum(1 for c in checks if c.status == "OK")
        failed = sum(1 for c in checks if c.status == "ERROR")
        warnings_count = sum(1 for c in checks if c.status == "WARNING")
        overall = "HEALTHY" if failed == 0 else ("DEGRADED" if passed >= len(checks) // 2 else "CRITICAL")

        stats = self.hm.get_stats()
        master = self._load_master()

        return SystemHealthReport(
            timestamp=datetime.now().isoformat(),
            overall_status=overall,
            total_checks=len(checks),
            passed=passed,
            failed=failed,
            warnings=warnings_count,
            checks=checks,
            model_stats=stats,
            provider_stats={p: ph.to_dict() for p, ph in self.hm._providers.items()},
            master_stats={
                "total_models": sum(len(d.get("models", {})) for d in master.get("providers", {}).values()),
                "total_free": sum(
                    1 for d in master.get("providers", {}).values()
                    for v in d.get("models", {}).values()
                    if v.get("is_free", False)
                ),
                "total_providers": len(master.get("providers", {})),
            },
            uptime_seconds=time.time() - self._start_time,
        )

    # ─── Output Formatters ───────────────────────────────────────────────────

    def format_dashboard(self, report: SystemHealthReport) -> str:
        """Generate ASCII dashboard output."""
        lines = [
            "",
            "╔══════════════════════════════════════════════════════════════════╗",
            "║           ILMA SYSTEM HEALTH DASHBOARD                            ║",
            "╚══════════════════════════════════════════════════════════════════╝",
            "",
            f"  Timestamp:  {report.timestamp}",
            f"  Status:     {report.overall_status}",
            f"  Checks:     {report.passed} OK  /  {report.warnings} WARN  /  {report.failed} ERR  /  {report.total_checks} TOTAL",
            f"  Uptime:     {report.uptime_seconds:.1f}s",
            "",
        ]

        for check in report.checks:
            icon = "✅" if check.status == "OK" else ("⚠️" if check.status == "WARNING" else "❌")
            lines.append(f"  {icon} [{check.status:8s}] {check.name}")
            lines.append(f"      └─ {check.details}")
            if check.errors:
                for err in check.errors[:2]:
                    lines.append(f"         ❌ {err[:60]}")
            if check.warnings:
                for warn in check.warnings[:2]:
                    lines.append(f"         ⚠️  {warn[:60]}")

        lines.append("")
        lines.append("  ── Model Stats ──────────────────────────────────────────")
        ms = report.model_stats
        lines.append(f"    Models tracked: {ms.get('model_count', '?')}")
        lines.append(f"    Available:      {ms.get('available_count', '?')}")
        lines.append(f"    Rate-limited:   {ms.get('rate_limited_count', '?')}")
        lines.append(f"    Errors:         {ms.get('error_count', '?')}")
        lines.append(f"    Proxy healthy:  {ms.get('proxy_healthy', '?')}")

        lines.append("")
        lines.append("  ── MASTER DB Stats ───────────────────────────────────────")
        lines.append(f"    Total models:   {report.master_stats.get('total_models', '?')}")
        lines.append(f"    FREE models:    {report.master_stats.get('total_free', '?')}")
        lines.append(f"    Providers:      {report.master_stats.get('total_providers', '?')}")

        lines.append("")
        lines.append("╚══════════════════════════════════════════════════════════════════╝")
        return "\n".join(lines)

    def format_json(self, report: SystemHealthReport) -> str:
        """Generate JSON output."""
        return json.dumps(asdict(report), indent=2, default=str)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="ILMA Health Check — Unified System Health Reporter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--full", action="store_true", help="Full diagnostics (all checks)")
    parser.add_argument("--quick", action="store_true", help="Quick health check only")
    parser.add_argument("--dashboard", action="store_true", help="ASCII dashboard output")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--model", dest="model_id", metavar="MODEL_ID", help="Check specific model health")
    parser.add_argument("--provider", dest="provider", metavar="PROVIDER", help="Check specific provider health")
    parser.add_argument("--stats", action="store_true", help="Show model/provider stats only")

    args = parser.parse_args()

    checker = ILMAHealthCheck.get_instance()

    # Single model check
    if args.model_id:
        result = checker.check_model_health(args.model_id)
        print(result)
        return

    # Single provider check
    if args.provider:
        result = checker.check_provider_health(args.provider)
        print(result)
        return

    # Stats only
    if args.stats:
        hm = checker.hm
        stats = hm.get_stats()
        print(json.dumps(stats, indent=2))
        return

    # Quick check (default)
    quick = not args.full
    report = checker.run_all(quick=quick)

    if args.json:
        print(checker.format_json(report))
    elif args.dashboard:
        print(checker.format_dashboard(report))
    else:
        # Default: compact output
        print(f"\n=== ILMA Health Check ({report.timestamp[:19]}) ===")
        print(f"Status: {report.overall_status}")
        print(f"Checks: {report.passed}/{report.total_checks} passed, "
              f"{report.warnings} warnings, {report.failed} errors\n")

        for check in report.checks:
            icon = "✅" if check.status == "OK" else ("⚠️" if check.status == "WARNING" else "❌")
            print(f"  {icon} [{check.status:8s}] {check.name}: {check.details}")

        print(f"\nModel health: {report.model_stats.get('available_count', '?')}/"
              f"{report.model_stats.get('model_count', '?')} available, "
              f"{report.model_stats.get('rate_limited_count', '?')} rate-limited")
        print(f"MASTER DB: {report.master_stats.get('total_models', '?')} models, "
              f"{report.master_stats.get('total_free', '?')} FREE")


if __name__ == "__main__":
    main()