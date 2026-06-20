#!/usr/bin/env python3
"""
ILMA SOT Integrity Layer
========================
Author: ILMA v3.30 (Phase 73)
Date:   2026-06-07

Purpose
-------
PROVIDER_INTELLIGENCE_MASTER.json is the SINGLE SOURCE OF TRUTH (SOT) for ILMA's
routing/scoring. If the SOT is corrupt, empty, or drifts badly, every consumer
(router, selector, benchmark autoloop, self-healing) breaks.

This module provides:
  1. SCHEMA VALIDATION — required top-level keys, per-provider shape, per-model required fields, type checks, value ranges
  2. DRIFT DETECTION — compare current SOT against last known-good backup:
       - provider count drop > DRIFT_PROVIDER_PCT  -> CRITICAL
       - model count drop > DRIFT_MODEL_PCT      -> CRITICAL
       - size shrink > DRIFT_SIZE_PCT            -> CRITICAL
  3. AUTO-ROLLBACK — if SOT fails validation, atomically restore from latest valid backup
  4. REPORT — JSON-friendly IntegrityReport with verdict (PASS/WARN/FAIL), issues, action taken

Usage
-----
    # Validate current SOT, print report, no rollback
    python3 ilma_sot_integrity.py --check

    # Validate + auto-rollback if invalid
    python3 ilma_sot_integrity.py --check --rollback

    # Validate a specific file
    python3 ilma_sot_integrity.py --check --file /path/to/sot.json

    # Run as dry-run pre-build gate (exits 0=ok, 1=rollback needed, 2=corrupt no backup)
    python3 ilma_sot_integrity.py --gate

Exit codes
----------
    0  SOT valid
    1  SOT invalid, rollback successful
    2  SOT invalid, NO valid backup to roll back to
    3  Internal error (bug)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ILMA_PROFILE = Path(__file__).resolve().parents[1]
DATA_DIR = ILMA_PROFILE / "ilma_model_router_data"
SOT_PATH = DATA_DIR / "PROVIDER_INTELLIGENCE_MASTER.json"
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_PATTERN = "PROVIDER_INTELLIGENCE_MASTER_*.json"
LOG_PATH = DATA_DIR / "sot_integrity_log.jsonl"

# ---------------------------------------------------------------------------
# Schema spec — derived from empirical inspection of SOT + consumer usage
# ---------------------------------------------------------------------------
# CRITICAL fields: SOT is fundamentally broken if these are missing.
# WARN fields: nice-to-have; missing means partial enrichment, still usable.
# This matches real-world state where the enrich step doesn't cover all
# freshly-synced models (a known characteristic of the full-sync pipeline).
REQUIRED_TOP_KEYS = {
    "providers": dict,
    "_version": str,
    "_last_updated": str,
    "_sot_lifecycle": dict,
}
OPTIONAL_TOP_KEYS = {
    "_enriched_at", "last_updated", "_enricher_version", "_enrichment_stats",
}
# A model is a dict.  CRITICAL = must have model_id (lookup key) + provider field
# matching parent.  Everything else is WARN (score range, status, etc.)
CRITICAL_MODEL_KEYS = {
    "model_id": str,
    "provider": str,
}
WARN_MODEL_KEYS = {
    # Cloud-only
    "model_name": str, "is_free": bool, "quality_score": (int, float),
    "status": str, "billing": str, "context_window": int,
    # Provider-only
    "disabled": bool, "free_tier": bool, "has_thinking": bool,
}
SCORE_RANGE = (0.0, 1.0)
CONTEXT_WINDOW_RANGE = (0, 10_000_000)

# ---------------------------------------------------------------------------
# Drift thresholds — failure = percentage drop vs last known-good backup
# ---------------------------------------------------------------------------
DRIFT_PROVIDER_PCT = 20.0   # 20% drop in provider count => CRITICAL
DRIFT_MODEL_PCT = 30.0      # 30% drop in model count => CRITICAL
DRIFT_SIZE_PCT = 40.0       # 40% drop in file size => CRITICAL
MIN_PROVIDERS = 5           # absolute minimum: 5 providers (we have 25)
MIN_MODELS = 50             # absolute minimum: 50 models (we have 434)
MIN_SIZE_BYTES = 50_000     # 50 KB minimum


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class IntegrityIssue:
    severity: str   # "CRITICAL" | "WARN" | "INFO"
    code: str       # short stable code
    message: str
    context: dict = field(default_factory=dict)


@dataclass
class IntegrityReport:
    sot_path: str
    timestamp: float
    verdict: str = ""            # "PASS" | "WARN" | "FAIL" — set after check
    issues: list[IntegrityIssue] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    action_taken: str = "none"   # "none" | "rollback" | "rollback_failed"
    rolled_back_from: str | None = None
    rolled_back_to: str | None = None
    baseline: dict = field(default_factory=dict)  # last known-good stats

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp
        d["issues"] = [asdict(i) for i in self.issues]
        return d


# ---------------------------------------------------------------------------
# Validation primitives
# ---------------------------------------------------------------------------
def _is_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _check_required_keys(obj: dict, required: dict, path: str, issues: list) -> bool:
    """Check obj has all required keys with correct types. Returns True if all OK."""
    ok = True
    for k, expected in required.items():
        if k not in obj:
            issues.append(IntegrityIssue("CRITICAL", "MISSING_KEY",
                f"{path} missing required key '{k}'", {"path": path, "key": k}))
            ok = False
        elif not isinstance(obj[k], expected):
            issues.append(IntegrityIssue("CRITICAL", "WRONG_TYPE",
                f"{path}.{k} expected {expected}, got {type(obj[k]).__name__}",
                {"path": path, "key": k, "got": type(obj[k]).__name__}))
            ok = False
    return ok


def _validate_top_level(db: dict, issues: list) -> bool:
    if not isinstance(db, dict):
        issues.append(IntegrityIssue("CRITICAL", "NOT_A_DICT",
            f"SOT root must be dict, got {type(db).__name__}"))
        return False
    return _check_required_keys(db, REQUIRED_TOP_KEYS, "$", issues)


def _validate_providers(providers: dict, issues: list) -> dict:
    """Returns stats dict.  ENRICHMENT_GAP is reported once per provider as a
    summary, not once per model, to keep report readable."""
    stats = {"providers": 0, "models": 0, "models_disabled": 0, "models_free": 0}
    if not isinstance(providers, dict):
        issues.append(IntegrityIssue("CRITICAL", "PROVIDERS_NOT_DICT",
            f"providers must be dict, got {type(providers).__name__}"))
        return stats
    for pname, pdata in providers.items():
        stats["providers"] += 1
        if not isinstance(pdata, dict):
            issues.append(IntegrityIssue("CRITICAL", "PROVIDER_NOT_DICT",
                f"providers.{pname} not dict"))
            continue
        models = pdata.get("models", {})
        if not isinstance(models, dict):
            issues.append(IntegrityIssue("CRITICAL", "MODELS_NOT_DICT",
                f"providers.{pname}.models not dict"))
            continue
        # Per-model CRITICAL checks
        gap_counts: dict[str, int] = {}  # field -> count of models missing it
        for mid, m in models.items():
            if not isinstance(m, dict):
                issues.append(IntegrityIssue("CRITICAL", "MODEL_NOT_DICT",
                    f"providers.{pname}.models.{mid} not dict"))
                continue
            _validate_model_critical(m, pname, issues)
            stats["models"] += 1
            if m.get("disabled"):
                stats["models_disabled"] += 1
            if m.get("is_free"):
                stats["models_free"] += 1
            # Per-model enrichment gap tally (no per-model issue, just count)
            for fld in WARN_MODEL_KEYS:
                if fld not in m:
                    gap_counts[fld] = gap_counts.get(fld, 0) + 1
        # Per-provider ENRICHMENT_GAP summary
        if gap_counts and models:
            # Only report fields where >10% of provider's models are missing
            threshold = max(2, len(models) * 0.10)
            big_gaps = {f: c for f, c in gap_counts.items() if c >= threshold}
            if big_gaps:
                issues.append(IntegrityIssue("WARN", "ENRICHMENT_GAP",
                    f"providers.{pname}: {len(big_gaps)} field(s) with >10% models missing enrichment",
                    {"provider": pname, "model_count": len(models),
                     "gap_fields": big_gaps}))
    return stats


def _validate_model_critical(m: dict, provider: str, issues: list) -> bool:
    """Per-model CRITICAL checks only.  WARN-level checks are aggregated separately."""
    path = f"providers.{provider}.models.{m.get('model_id', '?')}"
    ok = _check_required_keys(m, CRITICAL_MODEL_KEYS, path, issues)
    if not m.get("model_id"):
        issues.append(IntegrityIssue("CRITICAL", "MISSING_MODEL_ID",
            f"{path} has empty model_id", {"path": path}))
        ok = False
    mid = m.get("model_id")
    if mid is not None and not isinstance(mid, str):
        issues.append(IntegrityIssue("CRITICAL", "MODEL_ID_NOT_STR",
            f"{path}.model_id must be str, got {type(mid).__name__}",
            {"path": path, "got": type(mid).__name__}))
        ok = False
    if m.get("provider") != provider:
        issues.append(IntegrityIssue("WARN", "PROVIDER_MISMATCH",
            f"{path}.provider={m.get('provider')!r} != parent key {provider!r}",
            {"model_id": mid, "model_provider": m.get("provider"),
             "parent_provider": provider}))
    qs = m.get("quality_score")
    if isinstance(qs, (int, float)) and not (SCORE_RANGE[0] <= qs <= SCORE_RANGE[1]):
        issues.append(IntegrityIssue("WARN", "SCORE_OUT_OF_RANGE",
            f"{path}.quality_score={qs} outside {SCORE_RANGE}",
            {"model_id": mid, "quality_score": qs}))
    cw = m.get("context_window")
    if cw is not None and _is_int(cw) and not (CONTEXT_WINDOW_RANGE[0] <= cw <= CONTEXT_WINDOW_RANGE[1]):
        issues.append(IntegrityIssue("WARN", "CONTEXT_OUT_OF_RANGE",
            f"{path}.context_window={cw} outside {CONTEXT_WINDOW_RANGE}",
            {"model_id": mid, "context_window": cw}))
    return ok


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------
def _load_backup_stats(backup_path: Path) -> dict | None:
    """Try to load stats from a backup file. Returns None if corrupt."""
    try:
        db = json.loads(backup_path.read_text())
    except Exception:
        return None
    if not isinstance(db, dict) or "providers" not in db or not isinstance(db["providers"], dict):
        return None
    stats = {"providers": 0, "models": 0, "size_bytes": backup_path.stat().st_size,
             "timestamp": backup_path.stat().st_mtime}
    for p, pd in db["providers"].items():
        if not isinstance(pd, dict):
            continue
        stats["providers"] += 1
        models = pd.get("models", {})
        if isinstance(models, dict):
            stats["models"] += len(models)
    return stats


def _find_last_known_good() -> tuple[Path, dict] | tuple[None, None]:
    """Scan backups newest-first for first valid one."""
    if not BACKUP_DIR.exists():
        return None, None
    backups = sorted(BACKUP_DIR.glob(BACKUP_PATTERN),
                      key=lambda p: p.stat().st_mtime, reverse=True)
    for b in backups:
        # Skip non-timestamped files like _pre_repair_
        if not any(c.isdigit() for c in b.stem.split("_")[-1]):
            continue
        s = _load_backup_stats(b)
        if s and s["providers"] >= MIN_PROVIDERS and s["models"] >= MIN_MODELS:
            return b, s
    return None, None


def _check_drift(stats: dict, baseline: dict, issues: list) -> None:
    if not baseline:
        return
    for key, threshold in [("providers", DRIFT_PROVIDER_PCT),
                           ("models", DRIFT_MODEL_PCT)]:
        cur = stats.get(key, 0)
        base = baseline.get(key, 1)
        if base == 0:
            continue
        drop_pct = 100.0 * (base - cur) / base
        if drop_pct > threshold:
            issues.append(IntegrityIssue("CRITICAL", "DRIFT_DROP",
                f"{key} count dropped {drop_pct:.1f}% (threshold {threshold}%): "
                f"{cur} vs baseline {base}",
                {"key": key, "current": cur, "baseline": base,
                 "drop_pct": round(drop_pct, 2), "threshold_pct": threshold}))
    # Size drift
    cur_size = stats.get("size_bytes", 0)
    base_size = baseline.get("size_bytes", 1)
    if base_size > 0:
        size_drop_pct = 100.0 * (base_size - cur_size) / base_size
        if size_drop_pct > DRIFT_SIZE_PCT:
            issues.append(IntegrityIssue("CRITICAL", "DRIFT_SIZE",
                f"file size dropped {size_drop_pct:.1f}% (threshold {DRIFT_SIZE_PCT}%): "
                f"{cur_size} vs baseline {base_size}",
                {"current_bytes": cur_size, "baseline_bytes": base_size,
                 "drop_pct": round(size_drop_pct, 2)}))


def _check_absolute_minimums(stats: dict, issues: list) -> None:
    if stats.get("providers", 0) < MIN_PROVIDERS:
        issues.append(IntegrityIssue("CRITICAL", "BELOW_MIN_PROVIDERS",
            f"provider count {stats['providers']} < minimum {MIN_PROVIDERS}",
            {"current": stats["providers"], "min": MIN_PROVIDERS}))
    if stats.get("models", 0) < MIN_MODELS:
        issues.append(IntegrityIssue("CRITICAL", "BELOW_MIN_MODELS",
            f"model count {stats['models']} < minimum {MIN_MODELS}",
            {"current": stats["models"], "min": MIN_MODELS}))
    if stats.get("size_bytes", 0) < MIN_SIZE_BYTES:
        issues.append(IntegrityIssue("CRITICAL", "BELOW_MIN_SIZE",
            f"file size {stats['size_bytes']} < minimum {MIN_SIZE_BYTES}",
            {"current_bytes": stats["size_bytes"], "min_bytes": MIN_SIZE_BYTES}))


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------
def _atomic_replace(src: Path, dst: Path) -> None:
    """Atomically replace dst with src via temp file + os.replace."""
    fd, tmp = tempfile.mkstemp(prefix="." + dst.name + ".", suffix=".tmp", dir=str(dst.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(src.read_bytes())
        os.replace(tmp, dst)
    except Exception:
        try: os.unlink(tmp)
        except FileNotFoundError: pass
        raise


def _rollback(from_sot: Path, to_backup: Path, report: IntegrityReport) -> None:
    """Copy backup -> SOT atomically. Preserves the corrupt file as .corrupt_<ts>."""
    ts = int(time.time())
    corrupt_marker = from_sot.with_suffix(f".corrupt_{ts}.json")
    try:
        shutil.copy2(from_sot, corrupt_marker)
        report.rolled_back_from = str(corrupt_marker)
    except Exception as e:
        report.issues.append(IntegrityIssue("WARN", "CORRUPT_PRESERVE_FAILED",
            f"could not preserve corrupt file: {e}"))
    _atomic_replace(to_backup, from_sot)
    report.rolled_back_to = str(to_backup)
    report.action_taken = "rollback"


# ---------------------------------------------------------------------------
# Top-level check
# ---------------------------------------------------------------------------
def check(sot_path: Path = SOT_PATH,
          do_rollback: bool = False) -> IntegrityReport:
    report = IntegrityReport(sot_path=str(sot_path), timestamp=time.time())
    # 1) File exists & parseable
    if not sot_path.exists():
        report.issues.append(IntegrityIssue("CRITICAL", "FILE_MISSING",
            f"SOT file not found: {sot_path}", {"path": str(sot_path)}))
        report.verdict = "FAIL"
        return _maybe_rollback(report, do_rollback)
    try:
        raw = sot_path.read_bytes()
        db = json.loads(raw)
    except json.JSONDecodeError as e:
        report.issues.append(IntegrityIssue("CRITICAL", "JSON_PARSE_ERROR",
            f"SOT not valid JSON: {e}", {"line": e.lineno, "col": e.colno}))
        report.verdict = "FAIL"
        return _maybe_rollback(report, do_rollback)
    except Exception as e:
        report.issues.append(IntegrityIssue("CRITICAL", "READ_ERROR",
            f"could not read SOT: {e}"))
        report.verdict = "FAIL"
        return _maybe_rollback(report, do_rollback)

    # 2) Schema
    _validate_top_level(db, report.issues)
    stats = _validate_providers(db.get("providers", {}), report.issues)
    stats["size_bytes"] = len(raw)

    # 3) Absolute minimums (no baseline needed)
    _check_absolute_minimums(stats, report.issues)

    # 4) Drift vs last known-good backup
    baseline_path, baseline_stats = _find_last_known_good()
    if baseline_stats:
        report.baseline = {"path": str(baseline_path), **baseline_stats}
        _check_drift(stats, baseline_stats, report.issues)
    else:
        report.issues.append(IntegrityIssue("WARN", "NO_BASELINE",
            "no valid baseline backup found; drift check skipped"))

    report.stats = stats
    crit = [i for i in report.issues if i.severity == "CRITICAL"]
    warn = [i for i in report.issues if i.severity == "WARN"]
    if crit:
        report.verdict = "FAIL"
    elif warn:
        report.verdict = "WARN"
    else:
        report.verdict = "PASS"
    return _maybe_rollback(report, do_rollback)


def _maybe_rollback(report: IntegrityReport, do_rollback: bool) -> IntegrityReport:
    if report.verdict != "FAIL" or not do_rollback:
        return report
    backup_path, _ = _find_last_known_good()
    if not backup_path:
        report.issues.append(IntegrityIssue("CRITICAL", "NO_BACKUP",
            "FAIL detected but no valid backup to roll back to"))
        report.action_taken = "rollback_failed"
        return report
    try:
        _rollback(Path(report.sot_path), backup_path, report)
        report.issues.append(IntegrityIssue("INFO", "ROLLBACK_OK",
            f"rolled back to {backup_path.name}"))
    except Exception as e:
        report.issues.append(IntegrityIssue("CRITICAL", "ROLLBACK_FAILED",
            f"rollback attempt failed: {e}"))
        report.action_taken = "rollback_failed"
    return report


def _log_report(report: IntegrityReport) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a") as f:
            f.write(json.dumps(report.to_dict()) + "\n")
    except Exception:
        pass  # logging is best-effort


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _print_report(report: IntegrityReport) -> None:
    print("=" * 64)
    print(f"SOT INTEGRITY CHECK — verdict: {report.verdict}")
    print(f"  path:  {report.sot_path}")
    print(f"  stats: providers={report.stats.get('providers', 0)}, "
          f"models={report.stats.get('models', 0)}, "
          f"size={report.stats.get('size_bytes', 0)}B")
    if report.baseline:
        print(f"  baseline: {Path(report.baseline['path']).name} "
              f"(providers={report.baseline.get('providers')}, "
              f"models={report.baseline.get('models')})")
    if report.action_taken != "none":
        print(f"  action: {report.action_taken}")
        if report.rolled_back_to:
            print(f"  rolled_back_to: {report.rolled_back_to}")
        if report.rolled_back_from:
            print(f"  corrupt_preserved: {report.rolled_back_from}")
    if report.issues:
        print(f"  issues ({len(report.issues)}):")
        for i in report.issues:
            print(f"    [{i.severity}] {i.code}: {i.message}")
    print("=" * 64)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ILMA SOT Integrity Layer")
    ap.add_argument("--check", action="store_true", help="validate SOT")
    ap.add_argument("--rollback", action="store_true",
                    help="auto-rollback to last valid backup if FAIL")
    ap.add_argument("--file", type=Path, default=SOT_PATH,
                    help=f"path to SOT (default: {SOT_PATH})")
    ap.add_argument("--gate", action="store_true",
                    help="CI gate mode: exit 0=ok 1=rolled_back 2=no_backup")
    ap.add_argument("--quiet", action="store_true", help="suppress print, only exit code")
    args = ap.parse_args(argv)

    if not (args.check or args.gate):
        ap.print_help()
        return 0

    report = check(args.file, do_rollback=args.rollback or args.gate)
    _log_report(report)
    if not args.quiet:
        _print_report(report)
    if args.gate:
        # Pre-rollback verdict decides the gate outcome:
        #   PASS/WARN  -> 0 (proceed)
        #   FAIL + rollback succeeded -> 1 (rolled back, push was skipped)
        #   FAIL + rollback failed -> 2 (no backup, manual intervention)
        if report.verdict in ("PASS", "WARN"):
            return 0
        if report.action_taken == "rollback":
            return 1
        if report.action_taken == "rollback_failed":
            return 2
        return 2  # FAIL with no rollback attempted
    return 0 if report.verdict in ("PASS", "WARN") else 1


if __name__ == "__main__":
    sys.exit(main())
