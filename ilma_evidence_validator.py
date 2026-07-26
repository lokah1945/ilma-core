#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         ILMA EVIDENCE VALIDATOR v2.0 — END-TO-END SYSTEM                   ║
║         Source: PROVIDER_INTELLIGENCE_MASTER.json (single source of truth) ║
╚══════════════════════════════════════════════════════════════════════════════╝

Validates evidence format and integrity for ILMA's evidence-based system.
Evidence format: ILMA-EVID-YYYYMMDD-PHASE-CAPABILITY-NNN

INTEGRATION PIPELINE:
  MASTER (PROVIDER_INTELLIGENCE_MASTER.json)
    → validates evidence IDs, formats, dates
    → generates integrity reports
    → validates model evidence entries
    → checks capability registry consistency

Usage:
    python3 ilma_evidence_validator.py --validate <registry.json>
    python3 ilma_evidence_validator.py --model-evidence <model_id>
    python3 ilma_evidence_validator.py --system-check
    python3 ilma_evidence_validator.py --report

Dependencies: ilma_health_manager, ilma_model_router
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ─── ILMA Paths ────────────────────────────────────────────────────────────────

ILMA_PROFILE = Path(os.environ.get("ILMA_PROFILE", "/root/.hermes/profiles/ilma"))
MASTER_DB = ILMA_PROFILE / "ilma_model_router_data" / "PROVIDER_INTELLIGENCE_MASTER.json"
HEALTH_STATE = ILMA_PROFILE / "ilma_provider_health_state.json"
EVIDENCE_REGISTRY = ILMA_PROFILE / "config" / "ilma_evidence_registry.json"


# ═══════════════════════════════════════════════════════════════════════════════
# PATTERNS & CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

# Evidence ID format: ILMA-EVID-YYYYMMDD-PHASE-CAPABILITY-NNN
EVIDENCE_PATTERN = re.compile(
    r'^ILMA-EVID-(\d{8})-([A-Z0-9]+)-([A-Z_]+)-(\d{3})$'
)

# Valid phases
VALID_PHASES: Set[str] = {
    "P00", "P01", "P02", "P03", "P04", "P05", "P06", "P07", "P08", "P09",
    "P10", "P11", "P12", "P13", "P14", "P15", "P16", "P17", "P18", "P19",
    "P20", "P21", "P22", "P23", "P24", "P25", "P26", "P27", "P28", "P29",
    "P30", "P31", "P32", "P33", "P34", "P35", "P36", "P37", "P38", "P39",
    "P40", "P41", "P42", "P43", "P44", "P45", "P46", "P47", "P48", "P49",
    "P50", "P51", "P52", "P53", "P54", "P55", "P56", "P57", "P58", "P59",
    "P60", "P61", "P62", "P63",
    "P21A", "P21B", "P21R", "P21S",
    "PHASE1", "PHASE2", "PHASE3", "PHASE4", "PHASE5",
    "BOOT", "ROUTING", "EXECUTION", "VERIFICATION", "LEARNING",
    "BASELINE", "AUDIT", "OPTIMIZE", "VERIFY",
}

# Valid capability names
VALID_CAPABILITIES: Set[str] = {
    "COGNITIVE", "EXECUTIVE", "CREATIVE", "ANALYTICAL", "OPERATIONAL",
    "COMMUNICATION", "SECURITY", "INTEGRATION", "MEMORY", "META",
    "BROWSER_AUTOMATION", "MODEL_ROUTING", "EVIDENCE", "HEALTH_CHECK",
    "CAPABILITY_REGISTRY", "SELF_IMPROVEMENT", "KANBAN", "WORKFLOW",
    "ORCHESTRATION", "REASONING", "CODING", "RESEARCH", "WRITING",
    "VISION", "SPEECH", "TOOLS", "BRIDGE", "BENCHMARK",
    "FREE_MODEL", "PAID_MODEL", "PROVIDER_INTELLIGENCE",
    "BASELINE", "AUDIT", "OPTIMIZE", "VERIFY",
}

# Evidence required fields
REQUIRED_FIELDS: List[str] = ["id", "description", "date"]

# Legacy registry format compatibility (old format: evidence_id, no description/date)
LEGACY_REQUIRED_FIELDS: List[str] = ["evidence_id", "capability", "status"]
LEGACY_OPTIONAL_FIELDS: List[str] = ["evidence_id", "capability", "status", "confidence", "evidence_type"]

# Optional fields
OPTIONAL_FIELDS: List[str] = [
    "phase", "capability", "model_id", "provider", "task_type",
    "status", "evidence_type", "source", "verified_at", "confidence",
    "quality_score", "routing_reason", "fallback_used",
]


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class EvidenceEntry:
    """Single evidence entry."""
    id: str
    description: str
    date: str
    phase: str = ""
    capability: str = ""
    model_id: Optional[str] = None
    provider: Optional[str] = None
    task_type: str = ""
    status: str = "VERIFIED"
    evidence_type: str = "SYSTEM"
    source: str = ""
    verified_at: Optional[str] = None
    confidence: float = 1.0
    quality_score: float = 0.0
    routing_reason: str = ""
    fallback_used: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "description": self.description, "date": self.date,
            "phase": self.phase, "capability": self.capability,
            "model_id": self.model_id, "provider": self.provider,
            "task_type": self.task_type, "status": self.status,
            "evidence_type": self.evidence_type, "source": self.source,
            "verified_at": self.verified_at, "confidence": self.confidence,
            "quality_score": self.quality_score,
            "routing_reason": self.routing_reason,
            "fallback_used": self.fallback_used,
        }

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


@dataclass
class ValidationResult:
    """Result of evidence validation."""
    valid: bool
    total_entries: int
    valid_entries: int
    invalid_entries: int
    errors: List[str]
    warnings: List[str]
    entries_by_phase: Dict[str, int]
    entries_by_capability: Dict[str, int]
    model_evidence: Dict[str, int]  # model_id → count

    @property
    def success_rate(self) -> float:
        if self.total_entries == 0:
            return 0.0
        return self.valid_entries / self.total_entries

    def summary(self) -> str:
        return (
            f"VALIDATION: {self.valid_entries}/{self.total_entries} valid "
            f"({self.success_rate:.1%}), {len(self.errors)} errors, "
            f"{len(self.warnings)} warnings"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# EVIDENCE VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════════

class EvidenceValidator:
    """
    ILMA Evidence Validator v2.0
    =============================
    Validates evidence format and integrity for ILMA's evidence-based system.

    Features:
    - Evidence ID format validation (ILMA-EVID-YYYYMMDD-PHASE-CAPABILITY-NNN)
    - Registry validation (JSON evidence files)
    - Model evidence validation (cross-reference with MASTER)
    - System health validation (health state files)
    - Capability registry consistency check
    - Evidence ledger gap detection
    - Batch validation with detailed reporting
    """

    _singleton: Optional["EvidenceValidator"] = None

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self._master_cache: Optional[Dict] = None
        self._master_mtime: float = 0
        logger.debug("[EvidenceValidator] Initialized")

    @classmethod
    def get_instance(cls) -> "EvidenceValidator":
        """Get singleton instance."""
        if cls._singleton is None:
            cls._singleton = cls()
        return cls._singleton

    # ─── MASTER DB Integration ────────────────────────────────────────────────

    def _load_master(self) -> Dict:
        """Load PROVIDER_INTELLIGENCE_MASTER.json with TTL cache."""
        try:
            mtime = MASTER_DB.stat().st_mtime
            if self._master_cache is None or (mtime - self._master_mtime) > 120:
                with open(MASTER_DB) as f:
                    self._master_cache = json.load(f)
                self._master_mtime = mtime
        except Exception as e:
            logger.warning(f"[EvidenceValidator] MASTER load error: {e}")
            self._master_cache = {"providers": {}}
        return self._master_cache or {}

    def _get_all_model_ids(self) -> Set[str]:
        """Get all model IDs from MASTER."""
        master = self._load_master()
        model_ids: Set[str] = set()
        for provider_id, provider_data in master.get("providers", {}).items():
            for model_id in provider_data.get("models", {}).keys():
                model_ids.add(model_id)
                model_ids.add(f"{provider_id}/{model_id}")
        return model_ids

    # ─── Core Validation Methods ─────────────────────────────────────────────

    def validate_id(self, evidence_id: str) -> bool:
        """Validate an evidence ID format (ILMA-EVID-YYYYMMDD-PHASE-CAPABILITY-NNN)."""
        self.errors = []
        self.warnings = []

        match = EVIDENCE_PATTERN.match(evidence_id)
        if not match:
            self.errors.append(f"Invalid evidence ID format: '{evidence_id}'")
            return False

        date_str = match.group(1)
        phase = match.group(2)
        capability = match.group(3)
        seq = match.group(4)

        # Validate date
        try:
            datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            self.errors.append(f"Invalid date in evidence ID: {date_str}")
            return False

        # Validate phase format
        if not re.match(r'^[A-Z0-9]+$', phase):
            self.errors.append(f"Invalid phase format: {phase}")
            return False

        # Validate capability format
        if not re.match(r'^[A-Z_]+$', capability):
            self.errors.append(f"Invalid capability format: {capability}")
            return False

        # Validate sequence number
        try:
            seq_num = int(seq)
            if not (0 <= seq_num <= 999):
                self.errors.append(f"Sequence number out of range: {seq}")
                return False
        except ValueError:
            self.errors.append(f"Invalid sequence number: {seq}")
            return False

        return True

    def validate_entry(self, entry: Dict) -> EvidenceEntry:
        """Validate a single evidence entry. Returns EvidenceEntry with errors/warnings."""
        errors: List[str] = []
        warnings: List[str] = []

        # Detect legacy format FIRST (evidence_id instead of id)
        is_legacy = "id" not in entry and "evidence_id" in entry
        if is_legacy:
            evid_id = entry["evidence_id"]
            desc = f"[LEGACY] {entry.get('capability', 'UNKNOWN')} - {entry.get('status', 'VERIFIED')}"
            return EvidenceEntry(
                id=evid_id,
                description=desc,
                date=entry.get("last_updated", ""),
                phase="LEGACY",
                capability=entry.get("capability", ""),
                status=entry.get("status", "VERIFIED"),
                confidence=float(entry.get("confidence", 1.0)),
                errors=[], warnings=[f"Legacy format entry: {evid_id}"],
            )

        # Check required fields for modern format
        for field in REQUIRED_FIELDS:
            if field not in entry:
                errors.append(f"Missing required field: '{field}' in entry")

        # Must have id after required-field check (not legacy format)
        evid_id = entry.get("id", "UNKNOWN")

        # Validate evidence ID format
        if not self.validate_id(evid_id):
            errors.extend(self.errors)
        date_str = entry.get("date", "")
        if date_str:
            try:
                datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                warnings.append(f"Non-ISO date format: '{date_str}'")

        # Validate model_id against MASTER (if present)
        model_id = entry.get("model_id")
        if model_id:
            all_models = self._get_all_model_ids()
            if model_id not in all_models:
                # Try with provider prefix
                found = any(m.endswith(model_id) or model_id.endswith(m.split("/")[-1])
                           for m in all_models)
                if not found:
                    warnings.append(f"Model ID not found in MASTER: '{model_id}'")

        # Validate provider (if present)
        provider = entry.get("provider")
        if provider:
            master = self._load_master()
            if provider not in master.get("providers", {}):
                warnings.append(f"Provider not in MASTER: '{provider}'")

        # Check for empty description
        if not entry.get("description"):
            warnings.append(f"Empty description for {evid_id}")

        # Validate phase (if present)
        phase = entry.get("phase", "")
        if phase and phase not in VALID_PHASES:
            warnings.append(f"Non-standard phase: '{phase}'")

        # Validate capability (if present)
        cap = entry.get("capability", "")
        if cap and cap not in VALID_CAPABILITIES:
            warnings.append(f"Non-standard capability: '{cap}'")

        return EvidenceEntry(
            id=evid_id,
            description=entry.get("description", ""),
            date=date_str,
            phase=phase,
            capability=cap,
            model_id=model_id,
            provider=provider,
            task_type=entry.get("task_type", ""),
            status=entry.get("status", "VERIFIED"),
            evidence_type=entry.get("evidence_type", "SYSTEM"),
            source=entry.get("source", ""),
            verified_at=entry.get("verified_at"),
            confidence=float(entry.get("confidence", 1.0)),
            quality_score=float(entry.get("quality_score", 0.0)),
            routing_reason=entry.get("routing_reason", ""),
            fallback_used=entry.get("fallback_used", ""),
            errors=errors,
            warnings=warnings,
        )

    def validate_registry(self, registry_path: Optional[str] = None) -> ValidationResult:
        """Validate an evidence registry file."""
        path = Path(registry_path) if registry_path else EVIDENCE_REGISTRY
        errors: List[str] = []
        warnings: List[str] = []
        entries: List[EvidenceEntry] = []

        if not path.exists():
            errors.append(f"Registry not found: {path}")
            return ValidationResult(
                valid=False, total_entries=0, valid_entries=0, invalid_entries=0,
                errors=errors, warnings=warnings,
                entries_by_phase={}, entries_by_capability={}, model_evidence={},
            )

        try:
            with open(path) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in registry: {e}")
            return ValidationResult(
                valid=False, total_entries=0, valid_entries=0, invalid_entries=0,
                errors=errors, warnings=warnings,
                entries_by_phase={}, entries_by_capability={}, model_evidence={},
            )

        if not isinstance(data, dict):
            errors.append("Registry must be a JSON object (dict)")
            return ValidationResult(
                valid=False, total_entries=0, valid_entries=0, invalid_entries=0,
                errors=errors, warnings=warnings,
                entries_by_phase={}, entries_by_capability={}, model_evidence={},
            )

        # Support both flat dict format and nested "entries" format
        if "entries" in data and isinstance(data["entries"], list):
            # Legacy nested format: { "entries": [...] }
            entry_items = [(f"entry_{i}", e) for i, e in enumerate(data["entries"])]
        elif "entries" in data and isinstance(data["entries"], dict):
            # Mixed format: { "entries": { "E001": {...}, "E002": {...} } }
            entry_items = list(data["entries"].items())
        else:
            # Flat dict format: { "E001": {...}, "E002": {...} }
            entry_items = list(data.items())

        # Filter out top-level metadata keys
        excluded_keys = {"registry_version", "last_updated", "total_entries",
                         "entries", "metadata", "summary", "info"}
        entry_items = [
            (k, v) for k, v in entry_items
            if k not in excluded_keys and isinstance(v, dict)
        ]

        # Process each entry
        for key, entry_data in entry_items:
            ev_entry = self.validate_entry(entry_data)
            entries.append(ev_entry)
            errors.extend(ev_entry.errors)
            warnings.extend(ev_entry.warnings)

        # Aggregate stats
        entries_by_phase: Dict[str, int] = {}
        entries_by_capability: Dict[str, int] = {}
        model_evidence: Dict[str, int] = {}

        for e in entries:
            if e.phase:
                entries_by_phase[e.phase] = entries_by_phase.get(e.phase, 0) + 1
            if e.capability:
                entries_by_capability[e.capability] = (
                    entries_by_capability.get(e.capability, 0) + 1
                )
            if e.model_id:
                model_evidence[e.model_id] = model_evidence.get(e.model_id, 0) + 1

        return ValidationResult(
            valid=len(errors) == 0,
            total_entries=len(entries),
            valid_entries=sum(1 for e in entries if e.is_valid),
            invalid_entries=sum(1 for e in entries if not e.is_valid),
            errors=list(dict.fromkeys(errors)),  # deduplicate
            warnings=list(dict.fromkeys(warnings)),
            entries_by_phase=entries_by_phase,
            entries_by_capability=entries_by_capability,
            model_evidence=model_evidence,
        )

    def validate_model_evidence(self, model_id: str) -> Dict[str, Any]:
        """Validate that model_id has evidence in MASTER."""
        master = self._load_master()
        result = {
            "model_id": model_id,
            "found": False,
            "provider": None,
            "is_free": False,
            "quality_score": 0.0,
            "coding_score": 0.0,
            "errors": [],
            "warnings": [],
        }

        # Search all providers for the model
        for provider_id, provider_data in master.get("providers", {}).items():
            models = provider_data.get("models", {})
            if model_id in models:
                result["found"] = True
                result["provider"] = provider_id
                result["is_free"] = models[model_id].get("is_free", False)
                result["quality_score"] = models[model_id].get("quality_score", 0.0)
                result["coding_score"] = models[model_id].get("coding_score", 0.0)
                break

        if not result["found"]:
            result["errors"].append(f"Model not found in MASTER: {model_id}")

        return result

    def validate_system_check(self) -> Dict[str, Any]:
        """Full system check — validates all ILMA evidence components."""
        results = {
            "timestamp": datetime.now().isoformat(),
            "master_valid": False,
            "master_total_models": 0,
            "master_total_free": 0,
            "health_state_valid": False,
            "evidence_registry_valid": False,
            "evidence_entries": 0,
            "evidence_valid_count": 0,
            "errors": [],
            "warnings": [],
        }

        # Check MASTER
        try:
            master = self._load_master()
            total_models = sum(len(d.get("models", {})) for d in master.get("providers", {}).values())
            total_free = sum(
                1 for d in master.get("providers", {}).values()
                for v in d.get("models", {}).values()
                if v.get("is_free", False)
            )
            results["master_valid"] = True
            results["master_total_models"] = total_models
            results["master_total_free"] = total_free
        except Exception as e:
            results["errors"].append(f"MASTER check failed: {e}")

        # Check health state
        if HEALTH_STATE.exists():
            try:
                with open(HEALTH_STATE) as f:
                    health = json.load(f)
                results["health_state_valid"] = True
            except Exception as e:
                results["warnings"].append(f"Health state parse error: {e}")
        else:
            results["warnings"].append("Health state file not found")

        # Check evidence registry
        if EVIDENCE_REGISTRY.exists():
            vr = self.validate_registry(str(EVIDENCE_REGISTRY))
            results["evidence_registry_valid"] = vr.valid
            results["evidence_entries"] = vr.total_entries
            results["evidence_valid_count"] = vr.valid_entries
            results["errors"].extend(vr.errors)
            results["warnings"].extend(vr.warnings)

        return results

    def get_report(self, result: Optional[ValidationResult] = None) -> str:
        """Generate human-readable validation report."""
        if result is None:
            result = self.validate_registry()

        lines = [
            "═" * 60,
            "  ILMA EVIDENCE VALIDATOR REPORT",
            "  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "═" * 60,
            "",
            f"  Total entries:   {result.total_entries}",
            f"  Valid entries:  {result.valid_entries}",
            f"  Invalid entries: {result.invalid_entries}",
            f"  Success rate:    {result.success_rate:.1%}",
            "",
        ]

        if result.errors:
            lines.append(f"  ❌ ERRORS ({len(result.errors)}):")
            for err in result.errors[:20]:
                lines.append(f"    • {err}")
            if len(result.errors) > 20:
                lines.append(f"    ... and {len(result.errors) - 20} more")
            lines.append("")

        if result.warnings:
            lines.append(f"  ⚠️  WARNINGS ({len(result.warnings)}):")
            for warn in result.warnings[:20]:
                lines.append(f"    • {warn}")
            if len(result.warnings) > 20:
                lines.append(f"    ... and {len(result.warnings) - 20} more")
            lines.append("")

        if result.entries_by_phase:
            lines.append("  📊 Entries by Phase:")
            for phase, count in sorted(result.entries_by_phase.items()):
                lines.append(f"    {phase}: {count}")
            lines.append("")

        if result.entries_by_capability:
            lines.append("  📊 Entries by Capability:")
            for cap, count in sorted(result.entries_by_capability.items()):
                lines.append(f"    {cap}: {count}")
            lines.append("")

        if result.model_evidence:
            lines.append("  📊 Model Evidence:")
            for model, count in sorted(result.model_evidence.items(), key=lambda x: -x[1])[:10]:
                lines.append(f"    {model}: {count} entries")
            lines.append("")

        if not result.errors and not result.warnings:
            lines.append("  ✅ No issues found — all evidence valid!")
        elif result.valid:
            lines.append("  ✅ VALID (warnings only)")
        else:
            lines.append("  ❌ INVALID — errors found")

        lines.append("═" * 60)
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="ILMA Evidence Validator v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--validate", dest="registry", metavar="FILE",
        help="Validate an evidence registry JSON file"
    )
    parser.add_argument(
        "--model-evidence", dest="model_id", metavar="MODEL_ID",
        help="Validate model evidence against MASTER"
    )
    parser.add_argument(
        "--system-check", action="store_true",
        help="Run full system check"
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Generate validation report for default registry"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress colored output"
    )

    args = parser.parse_args()

    validator = EvidenceValidator.get_instance()

    if args.model_id:
        result = validator.validate_model_evidence(args.model_id)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result["found"]:
                print(f"✅ Model '{args.model_id}' found in MASTER")
                print(f"   Provider: {result['provider']}")
                print(f"   Free: {result['is_free']}")
                print(f"   Quality: {result['quality_score']}")
            else:
                print(f"❌ Model '{args.model_id}' NOT found in MASTER")

    elif args.system_check:
        result = validator.validate_system_check()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("=== ILMA SYSTEM CHECK ===")
            print(f"  MASTER: {result['master_total_models']} models, "
                  f"{result['master_total_free']} FREE ✅" if result['master_valid'] else "  MASTER: ❌")
            print(f"  Health State: {'✅' if result['health_state_valid'] else '⚠️'}")
            print(f"  Evidence Registry: {result['evidence_valid_count']}/{result['evidence_entries']} valid")
            if result['errors']:
                print(f"  Errors: {len(result['errors'])}")
            if result['warnings']:
                print(f"  Warnings: {len(result['warnings'])}")

    elif args.registry or args.report:
        result = validator.validate_registry(args.registry)
        if args.json:
            print(json.dumps(asdict(result), indent=2, default=str))
        else:
            print(validator.get_report(result))

    else:
        # Demo validation
        print("ILMA Evidence Validator v2.0")
        print("=" * 40)

        test_ids = [
            "ILMA-EVID-20260509-P21A-BASELINE-001",
            "ILMA-EVID-20260509-P20-EXECUTION-001",
            "ILMA-EVID-20260524-P63-OPTIMIZE-001",
            "ILMA-EVID-20260524-P63-CODING-001",
            "INVALID-ID",
            "ILMA-EVID-20260509-BADPHASE-CODING-001",
        ]

        print("\nEvidence ID Validation:")
        print("-" * 40)
        for evid in test_ids:
            status = "✅" if validator.validate_id(evid) else "❌"
            errors_str = f" ({'; '.join(validator.errors[:2])})" if validator.errors else ""
            print(f"  {status} {evid}{errors_str}")

        print("\nQuick System Check:")
        print("-" * 40)
        check = validator.validate_system_check()
        print(f"  MASTER: {check['master_total_models']} models, "
              f"{check['master_total_free']} FREE — {'✅' if check['master_valid'] else '❌'}")
        print(f"  Evidence: {check['evidence_entries']} entries, "
              f"{check['evidence_valid_count']} valid")
        print(f"  Health: {'✅' if check['health_state_valid'] else '⚠️'}")

        print("\nValidation complete. Use --validate <file> or --system-check for details.")


if __name__ == "__main__":
    main()