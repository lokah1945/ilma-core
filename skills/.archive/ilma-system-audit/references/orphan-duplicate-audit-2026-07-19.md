# Orphan & Duplicate Module Audit — 2026-07-19

## Scope
- 112 root `.py` files — import-graph analysis (who imports whom)
- 274 scripts — cross-reference scan for orphan/deprecated/duplicate
- Goal: zero orphan files without purpose, merge duplicates, wire library modules

## Import-Graph Analysis Technique

Build the import graph with a Python one-liner (run via `terminal`, NOT `execute_code` — cron-safety blocks it):

```python
cd /root/.hermes/profiles/ilma && python3 -c "
import re
from pathlib import Path
from collections import defaultdict

root_pys = sorted([f.name for f in Path('.').glob('*.py')])
importers = defaultdict(list)  # module -> [files that import it]

for fname in root_pys:
    content = Path(fname).read_text(errors='replace')
    for m in re.finditer(r'^\s*(?:from\s+(\S+)\s+import|import\s+(\S+))', content, re.MULTILINE):
        mod = m.group(1) or m.group(2)
        mod_name = mod.split('.')[0].lstrip('.')
        if mod_name.startswith('ilma_'):
            importers[mod_name].append(fname)

# Orphans = root .py files NEVER imported by any other root file
orphans = [f for f in root_pys if not importers.get(f.replace('.py', ''))]
print(f'Potential orphans (zero importers): {len(orphans)}')
for f in sorted(orphans): print(f'  {f}')
"
```

## Categorization — 3-Tier Classification

Raw "zero importers" is NOT enough. Categorize each orphan:

| Category | Detection | Action |
|----------|-----------|--------|
| **CLI tools** (has `__main__`) | `grep -l '__main__' <file>` | KEEP — entry points, not orphans |
| **Wired** (referenced in wiring/orchestrator) | `grep <module> ilma_runtime_wiring.py ilma_orchestrator.py` | KEEP — already wired |
| **True orphans** (no `__main__`, not wired) | both checks fail | Investigate → wire or archive |

### Bridge Pattern (NOT orphan)
Root files that are small (25-50L) and delegate to `scripts/<same-name>.py` are **import bridges** — they exist so `from ilma_X import ...` works from profile root without sys.path hacks. Pattern:
```python
_scripts = str(Path(__file__).resolve().parent / "scripts")
if _scripts not in sys.path: sys.path.insert(0, _scripts)
_mod = importlib.import_module("ilma_X")  # loads scripts/ilma_X.py
```
**Keep these** — they are the canonical import path for browser/human_interaction modules.

## Duplicate Detection

### Same-name root vs scripts
```bash
for f in *.py; do
  if [ -f "scripts/$f" ]; then
    echo "DUP: $f (root=$(wc -l < "$f")L, scripts=$(wc -l < "scripts/$f")L)"
  fi
done
```
Classification:
- **Bridge** (root small → scripts large): KEEP both (e.g. `ilma_browser_engine.py` 50L → scripts 2183L)
- **True duplicate** (both full implementations): Compare with `diff`, check which is canonical (imported/referenced by active code), DELETE the orphan one
- **Deprecated shim** (scripts version marked DEPRECATED/SHIM): DELETE scripts version

### Same function/class name across files
```python
python3 -c "
import re
from pathlib import Path
from collections import defaultdict
func_locations = defaultdict(list)
for f in sorted(Path('.').glob('*.py')):
    for m in re.finditer(r'^(class|def)\s+(\w+)', f.read_text(errors='replace'), re.MULTILINE):
        func_locations[m.group(2)].append((f.name, m.group(1)))
dups = {n: l for n, l in func_locations.items() if len(l) > 1}
for name, locs in sorted(dups.items()):
    print(f'{name}: {locs}')
"
```
Most "duplicates" are **singleton factory pattern** (`get_router()`, `get_registry()`) returning different class types — NOT real duplication. Only merge if the function bodies are truly identical.

## Orphan-Wiring for Library Modules

Library modules (no `__main__`, no CLI entry) that are sophisticated but unwired should be registered in `ilma_orphan_wiring.py`:

```python
# In _ORPHAN_SPECS list:
{"module": "ilma_dag_pipeline",     "layer": "LAYER_3", "purpose": "DAG pipeline engine",
 "callable": "DAGPipelineEngine",   "cli": None},
{"module": "ilma_fallback_cascade", "layer": "LAYER_3", "purpose": "Multi-tier fallback cascade",
 "callable": "FallbackCascadeEngine", "cli": None},
{"module": "ilma_quality_gate",     "layer": "LAYER_4", "purpose": "L1-L10 quality gate",
 "callable": "ILMAQualityGate",     "cli": None},
```

### Pitfalls when wiring library modules
1. **`cli: None` breaks sorted()**: `sorted(self.capabilities.items())` crashes with `'<' not supported between 'NoneType' and 'str'`. Fix: `sorted(..., key=lambda x: (x[0] or ""))`.
2. **`cli: None` causes dict key collision**: All library modules use `None` as dict key → overwrite each other. Fix: `key = spec["cli"] or spec["module"]` — use module_name as fallback key.
3. **Type annotation**: `List[Dict[str, str]]` rejects `None` values. Use `List[Dict[str, Optional[str]]]`.

## Orphan Scripts Removed (14 files, commit 23e8cb5)

| File | Reason | Size |
|------|--------|------|
| `scripts/ilma.py` | Duplikat root `ilma.py` (Phase 56 lama) | 1510L |
| `scripts/ilma_health_check.py` | Duplikat root (canonical in orphan_wiring) | 615L |
| `scripts/ilma_self_healing.py` | Duplikat root, beda implementasi | 186L |
| `scripts/ilma_circuit_breaker.py` | Duplikat root (root lebih sophisticated) | 55L |
| `scripts/ilma_ab_testing.py` | Duplikat root (root lebih lengkap) | 64L |
| `scripts/ilma_evidence_validator.py` | DEPRECATED SHIM (→ non-existent path) | 25L |
| `scripts/bug_hunter.py` | Orphan, zero importers | — |
| `scripts/ilma_browser_automation.py` | Orphan | — |
| `scripts/ilma_memory_layer.py` | Orphan | — |
| `scripts/ilma_problem_solve_engine.py` | Orphan | — |
| `scripts/ilma_registry_integrity_monitor.py` | Orphan | — |
| `scripts/ilma_report_generator.py` | Orphan | — |
| `scripts/ilma_capability_health_dashboard.py` | Orphan | — |
| `scripts/ilma_command_center.py` | Orphan, duplikat `ilma_dashboard_server.py` | — |
| `scripts/ilma_system_optimizer.py` | Orphan | — |

## Verification
- 24/24 orphan_wiring modules import OK
- All root + scripts compile clean
- Bridge pattern (3 pairs) preserved: `ilma_browser_engine`, `ilma_browser_runtime`, `ilma_human_interaction`
- Commit: `23e8cb5` pushed
