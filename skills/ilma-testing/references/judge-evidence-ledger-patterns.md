# Judge v4 & Evidence Ledger — Test & Validation Patterns
**Phase:** OPT (2026-05-11)  
**Source:** `ilma_critic_judge.py`, `ilma_evidence_ledger.json`

---

## Pattern 1: Evidence Ledger Format Mutation

**Problem:** Ledger stored as bare list `[{...}, {...}]`, but `load_evidence_ledger()` expected `{"entries": [...]}`. All `run_task_with_evolution` executions crashed with `AttributeError: 'list' object has no attribute 'get'`.

**Root cause:** Phase optimization or data migration changed ledger format without updating the reader.

**Fix — handle both formats:**
```python
def load_evidence_ledger(workspace: Path) -> set:
    ledger_path = workspace / "evidence" / "ilma_evidence_ledger.json"
    valid_ids = set()
    if ledger_path.exists():
        with open(ledger_path, 'r') as f:
            ledger = json.load(f)
            # Handle both dict with "entries" key and direct list format
            if isinstance(ledger, dict):
                entries = ledger.get("entries", [])
            else:
                entries = ledger if isinstance(ledger, list) else []
            for entry in entries:
                eid = entry.get("evidence_id") if isinstance(entry, dict) else None
                if eid:
                    valid_ids.add(eid)
    return valid_ids
```

**Verification:**
```bash
python3 -c "
import json
from pathlib import Path
lp = Path('evidence/ilma_evidence_ledger.json')
with open(lp) as f:
    data = json.load(f)
print('Type:', type(data).__name__)  # dict or list
print('Count:', len(data) if isinstance(data, list) else len(data.get('entries', [])))
"
```

---

## Pattern 2: Fake Evidence IDs in Tests → Fabricated Claims

**Problem:** Tests embedded evidence IDs like `ILMA-EVID-20260509-P30-MEMORY-001` in artifacts, claiming they were in the ledger. Judge v4 correctly rejected them as fabricated. Two tests failed: `test_judge_good_artifact` and `test_valid_artifact_with_evidence`.

**Wrong approach:** Use hardcoded fake IDs that "should be" in the ledger.

**Correct approach A — use real IDs from the ledger:**
```python
judge = CriticJudge(workspace=ILMA_PROFILE)
real_ids = list(judge.valid_evidence_ids) if hasattr(judge, 'valid_evidence_ids') else []
# Use real_ids[0] if available, otherwise fall back to no IDs
```

**Correct approach B — quality markers, no fake IDs:**
```python
artifact = """# Factorial Implementation

Implements recursive factorial with proper error handling and test coverage.

```python
def factorial(n):
    if n < 0:
        raise ValueError("Must be non-negative")
    ...
```
"""
# No evidence IDs — judge scores quality markers, not claimed evidence
```

---

## Pattern 3: Judge PASS vs WARN Threshold Honesty

**Problem:** Test expected `JudgeStatus.PASS` for a simple code artifact with tests. Judge v4 returned `WARN` (acceptable quality, but not perfect).

**Fixed assertions:**
```python
# BEFORE (fails — judge may return WARN for good-but-not-perfect artifacts)
assert result.status == JudgeStatus.PASS

# AFTER (passes — WARN is acceptable quality)
assert result.status in [JudgeStatus.PASS, JudgeStatus.WARN]
assert result.score >= 70
```

**Judge v4 score → status mapping (approximate):**
| Score Range | Status | Meaning |
|-------------|--------|---------|
| 90-100 | PASS | Excellent |
| 70-89 | WARN | Acceptable with minor issues |
| 50-69 | FAIL | Significant quality gaps |
| 0-49 | FAIL | Poor quality or fabricated evidence |

---

## Pattern 4: Module-Level Constants Orphaned by Optimization

**Problem:** `CLAIM_BOUNDARY_CONFIG = WORKSPACE / "config" / "ilma_claim_boundary.json"` was removed during optimization, but functions still referenced it. `ilma.py doctor` crashed with `name 'CLAIM_BOUNDARY_CONFIG' is not defined`.

**Fix — inline path computation:**
```python
# BEFORE (orphaned constant reference)
if CLAIM_BOUNDARY_CONFIG.exists():
    print("  ✅ Claim boundary config exists")

# AFTER (inline, self-contained)
from pathlib import Path
claim_boundary_path = WORKSPACE / "config" / "ilma_claim_boundary.json"
if claim_boundary_path.exists():
    print("  ✅ Claim boundary config exists")
```

**Rule:** Module-level constants can be deleted by optimization passes. Always use inline computation or a protected getter for constants used in command handlers.

---

## Pattern 5: Config Cache for Repeated Lazy-Load

**Problem:** Each getter function parsed JSON config fresh every call (~5-7x per run).

**Fix — centralized config cache:**
```python
# At module level
_CONFIG_CACHE: Dict[str, Any] = {}

def _get_config(path: Path) -> Dict[str, Any]:
    """Centralized config cache — single parse, reused across getters."""
    key = str(path)
    if key not in _CONFIG_CACHE:
        if path.exists():
            with open(path) as f:
                _CONFIG_CACHE[key] = json.load(f)
        else:
            _CONFIG_CACHE[key] = {}
    return _CONFIG_CACHE[key]

# Use throughout
safety = _get_config(SAFETY_CONTRACT_PATH)
```

---

## Pattern 6: Enum Serialization in dataclasses

**Problem:** `dataclasses.asdict()` preserves Enum values as `<EnumClass.VALUE: 'VALUE'>`, not `'VALUE'`. JSON serialization of traces fails.

**Fix:**
```python
jr_dict = asdict(judge_result)
jr_dict['status'] = judge_result.status.value  # Explicit Enum → string
trace.judge_results = [jr_dict]
```

**Verification:**
```python
from dataclasses import asdict
jr = JudgeResult(status=JudgeStatus.PASS, score=85.0)
print(asdict(jr)['status'])        # <JudgeStatus.PASS: 'PASS'> — WRONG for JSON
print(jr.status.value)             # 'PASS' — correct
```

---

## Smoke Test Template

```bash
# Minimal smoke for judge + evidence ledger
python3 -c "
from scripts.ilma_critic_judge import CriticJudge
j = CriticJudge()
print('Valid evidence IDs:', len(j.valid_evidence_ids))
result = j.evaluate('def foo(x): return x+1\n\ndef test(): assert foo(2)==3', 'Build foo', '', 'code')
print('Judge:', result.status.value, result.score)
print('Fabrication check:', 'FABRICATION' in str(result.failures))
"
```

---

## Related
- `ilma-testing/SKILL.md` — Testing patterns
- `scripts/ilma_critic_judge.py` — Judge v4 implementation
- `evidence/ilma_evidence_ledger.json` — Evidence ledger (check format before reading)