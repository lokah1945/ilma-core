# Health & Validation System — Optimization Reference

Created: 2026-05-24
Session: Restore + optimize ilma_evidence_validator.py + scripts/ilma_health_check.py

## Legacy Evidence Registry Format Detection

The evidence registry at `config/ilma_evidence_registry.json` uses a LEGACY format:
```json
{
  "evidence_id": "E001",
  "capability": "system_awareness",
  "status": "VERIFIED",
  "confidence": 1.0
}
```

Modern format (ILMA-EVID):
```json
{
  "id": "ILMA-EVID-001",
  "description": "Task completed successfully",
  "date": "2026-05-24T10:00:00",
  "capability": "coding",
  "phase": "PHASE_01"
}
```

**CRITICAL: Detect BEFORE checking required fields.** The validator checks `REQUIRED_FIELDS = ["id", "description", "date"]` first — legacy entries will fail immediately unless format is detected first:

```python
def validate_entry(self, entry: Dict[str, Any]) -> EvidenceEntry:
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

    # Modern format — check required fields
    for field in REQUIRED_FIELDS:
        if field not in entry:
            errors.append(f"Missing required field: '{field}' in entry")

    evid_id = entry.get("id", "UNKNOWN")
    if not self.validate_id(evid_id):
        errors.extend(self.errors)
    # ... rest of modern validation
```

**Also handle registry file structure variants:**

```python
def validate_evidence_registry(self, filepath: Path) -> ValidationResult:
    with open(filepath) as f:
        data = json.load(f)

    # Support 3 registry formats:
    # 1. Flat dict: { "E001": {...}, "E002": {...} }
    # 2. Nested "entries" list: { "entries": [...] }
    # 3. Nested "entries" dict: { "entries": { "E001": {...} } }

    excluded_keys = {"registry_version", "last_updated", "total_entries",
                     "entries", "metadata", "summary", "info"}

    if "entries" in data and isinstance(data["entries"], list):
        entry_items = [(f"entry_{i}", e) for i, e in enumerate(data["entries"])]
    elif "entries" in data and isinstance(data["entries"], dict):
        entry_items = list(data["entries"].items())
    else:
        entry_items = list(data.items())

    entry_items = [
        (k, v) for k, v in entry_items
        if k not in excluded_keys and isinstance(v, dict)
    ]

    for key, entry_data in entry_items:
        ev_entry = self.validate_entry(entry_data)
        # ...
```

## Unified Health Check Script Architecture

`scripts/ilma_health_check.py` consolidates 9 checks into one CLI:

| Check | Source | What it verifies |
|-------|--------|-----------------|
| MASTER_DB | DIRECT file read | 1341 models, 1236 FREE across 25 providers |
| MODEL_HEALTH | ilma_health_manager | 16 tracked, 7 available, 0 rate-limited |
| PROVIDER_HEALTH | ilma_health_manager | Provider status + rate-limit state |
| BRIDGE_PROXY | httpx GET http://127.0.0.1:8001/health | Port 8001 responding |
| CAPABILITY_REGISTRY | filesystem check | 2/2 registry files present |
| EVIDENCE_SYSTEM | EvidenceValidator | 68/68 legacy entries valid |
| PIPELINE_WIRING | filesystem check | 8 critical files present |
| RUNTIME_IMPORTS | import test | 4 core modules importable |
| FREE_MODEL_ROUTING | ilma_model_router | get_best_model() returns FREE model |

**CLI flags:**
- `--full` — all 9 checks
- `--quick` (default) — MASTER_DB, MODEL_HEALTH, BRIDGE_PROXY, PIPELINE_WIRING
- `--dashboard` — ASCII dashboard with model/provider stats
- `--json` — JSON output for programmatic consumption
- `--model <id>` — single model health check
- `--provider <p>` — single provider health check
- `--stats` — model/provider stats from health manager only

**Singleton pattern for health check engine:**
```python
class ILMAHealthCheck:
    _singleton: Optional["ILMAHealthCheck"] = None

    def __init__(self):
        self.hm = get_health_manager()
        self.ev = EvidenceValidator.get_instance()

    @classmethod
    def get_instance(cls) -> "ILMAHealthCheck":
        if cls._singleton is None:
            cls._singleton = cls()
        return cls._singleton
```

**Evidence system integration in health check:**
```python
def check_evidence_system(self) -> HealthCheckResult:
    ev_path = ILMA_PROFILE / "ilma_evidence_validator.py"
    if not ev_path.exists():
        return HealthCheckResult(
            name="EVIDENCE_SYSTEM", status="ERROR",
            details="Evidence validator not found",
            timestamp=datetime.now().isoformat(),
            errors=["ilma_evidence_validator.py not found"], warnings=[],
        )

    check = self.ev.validate_system_check()
    errors.extend(check["errors"])
    warnings.extend(check["warnings"])

    entries = check["evidence_entries"]
    valid = check["evidence_valid_count"]
    details = f"Evidence: {valid}/{entries} valid entries"
    status = "ERROR" if errors else ("WARNING" if warnings else "OK")

    return HealthCheckResult(
        name="EVIDENCE_SYSTEM", status=status, details=details,
        timestamp=datetime.now().isoformat(), errors=errors, warnings=warnings,
    )
```

## Public API Access Pattern

Always use public methods instead of private state:

```python
# BAD — accesses private dict
model_states = len(hm._models)

# GOOD — uses public method
stats = hm.get_stats()
model_states = stats['model_count']
```

This prevents silent breakage when internal implementation changes.

## MASTER DB TTL Cache Pattern

Evidence validator and health check both read MASTER.json. Use TTL cache:

```python
def _load_master(self) -> Dict:
    try:
        mtime = MASTER_DB.stat().st_mtime
        if self._master_cache is None or (mtime - self._master_mtime) > 120:
            with open(MASTER_DB) as f:
                self._master_cache = json.load(f)
            self._master_mtime = mtime
    except Exception:
        self._master_cache = {"providers": {}}
    return self._master_cache or {}
```

## Cross-Module Wiring Verification Script

```python
import sys
sys.path.insert(0, "/root/.hermes/profiles/ilma")

from ilma_health_manager import get_health_manager
from ilma_evidence_validator import EvidenceValidator
from ilma_model_router import get_best_model
from ilma_orchestrator import ILMAOrchestrator
from ilma_workflow_ecc import analyze_4w1h
from scripts.ilma_health_check import ILMAHealthCheck

# Module imports (8 core modules)
modules = [
    "ilma_model_router", "ilma_canonical_router", "ilma_smart_model_router",
    "ilma_health_manager", "ilma_evidence_validator", "ilma_capability_registry",
    "ilma_orchestrator", "ilma_workflow_ecc",
]
for mod in modules:
    __import__(mod)  # raises if fails

# Cross-module wiring
r = get_best_model("general", prefer_free=True)  # model router → MASTER
hm = get_health_manager(); stats = hm.get_stats()  # health → MASTER
ev = EvidenceValidator.get_instance()  # evidence → MASTER
orch = ILMAOrchestrator(); result = orch.route_intent("coding")  # orchestrator → model_router
hc = ILMAHealthCheck.get_instance(); report = hc.run_all(quick=True)  # health_check → all above

print(f"Models: {r.get('model_id')}")
print(f"Health: {stats['model_count']} tracked")
print(f"Evidence: {ev.validate_system_check()['master_total_models']} models in MASTER")
print(f"Routing: {result.get('handler')}")
print(f"Health check: {report.overall_status} ({report.passed}/{report.total_checks})")
```

## Restoration Priority

When root-level module is broken/missing:
1. Check root `ilma_X.py` — the one that `import ilma_X` resolves to
2. Check `hermes_profile_ilma/ilma_X.py` — most complete version usually here
3. Check `fabric_archive/stale_hermes_profile_ilma_*/` — backup version
4. Check `scripts_archive/` — temporal backups
5. **Extend, don't replace** — add missing capabilities (TTL cache, CLI, validators) rather than wholesale replace

Never use subdirectory shim (hermes_profile_ilma) as root without verifying it has all public APIs the caller expects.