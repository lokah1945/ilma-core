# Phase 48C-CLOSE Bug Fixes Reference
**Date:** 2026-05-10
**Source:** Phase 48C-CLOSE — Truth Locked

---

## Bug #1: create_session() API Mismatch (CRITICAL)

**Symptom:** `TypeError: create_session() got an unexpected keyword argument 'owner_command'`
**Exit code:** 1 (crash)
**Effect:** Runner crashed on exit, but report falsely declared COMPLETE

**Root cause:** Phase 48C runner called:
```python
session = mgr.create_session(trigger, owner_command=TRIGGER_CMD)
```
But `create_session()` signature was `create_session(trigger)` — no `owner_command` param.

**Fix applied to `scripts/ilma_autolearning_session_manager.py`:**
```python
def create_session(self, trigger: TriggerResult, owner_command: str | None = None) -> SessionData:
    """Create a new session from parsed trigger.

    Args:
        trigger: Parsed TriggerResult from the trigger parser
        owner_command: Optional explicit owner command string. If not provided,
                       defaults to trigger.raw_command.
    """
    session_id = str(uuid.uuid4())[:8]
    start_time = datetime.now()
    
    # Use provided owner_command or fall back to trigger.raw_command
    actual_owner_command = owner_command if owner_command else trigger.raw_command
    
    # Duration
    duration_min = trigger.duration_minutes or 60
    
    # Session state
    state = SessionState.ARMED
    
    session = SessionData(
        session_id=session_id,
        owner_command=actual_owner_command,
        duration_minutes=duration_min,
        ...
    )
    return session
```

**Both calling styles now work:**
```python
session = mgr.create_session(trigger)                          # uses trigger.raw_command
session = mgr.create_session(trigger, owner_command="...")    # uses explicit
```

---

## Bug #2: Negative Scope Parser (CRITICAL)

**Symptom:** "jangan external_publish" → `external_publish` in `scope` (wrong!)
**Effect:** Forbidden action appeared as active scope

**Root cause:** `_extract_scope()` matched keywords regardless of negation context. The word "publish" matched the pattern, "jangan" was ignored.

**Fix applied to `scripts/ilma_autolearning_trigger.py`:**

### Step 1: Added `forbidden_scope` field to `TriggerResult`
```python
@dataclass
class TriggerResult:
    is_trigger: bool = False
    action: TriggerAction = TriggerAction.NONE
    duration_minutes: Optional[int] = None
    scope: List[str] = field(default_factory=list)
    forbidden_scope: List[str] = field(default_factory=list)  # NEW
    requires_confirmation: bool = False
    ...
```

### Step 2: Rewrote `_extract_scope()` to detect negative context
```python
def _extract_scope(self, cmd: str) -> tuple[List[str], List[str]]:
    """Extract scope keywords from command.

    Handles negative patterns (jangan, don't, no, etc.) to classify
    forbidden vs. allowed scope.

    Returns:
        Tuple of (active_scope, forbidden_scope)
    """
    NEGATIVE_PATTERNS = [
        r'\bjangan\b', r'\bjanganlah\b',
        r"\bdon't\b", r"\bdo\s*not\b",
        r"\bno\b", r"\bnot\b",
        r"\btidak\b", r"\btidaklah\b",
        r"\bwithout\b", r"\bavoid\b", r"\bprevent\b",
        r"\bforbidden\b", r"\bblocked\b",
        r"\bstop\b", r"\bhentikan\b",
        r"\bdisallow\b", r"\bdeny\b",
    ]

    active_scope = []
    forbidden_scope = []

    for scope_name, pattern, start, end in all_matches:
        # Check 20 chars before match for negative pattern
        prefix = cmd[max(0, start-20):start].lower()
        is_negative = any(n.search(prefix) for n in NEGATIVE_PATTERNS)

        if is_negative:
            forbidden_scope.append(scope_name)
        else:
            active_scope.append(scope_name)

    return active_scope, forbidden_scope
```

### Step 3: Updated `parse()` to use new tuple return
```python
active_scope, forbidden_scope = self._extract_scope(cmd)
result.scope = active_scope
result.forbidden_scope = forbidden_scope
```

### Step 4: Fixed confirmation gate logic
```python
# Check for forbidden scopes that appear in active scope (non-negative)
legacy_forbidden = self._check_forbidden_scope(active_scope)
if legacy_forbidden:
    all_forbidden = list(set(legacy_forbidden + forbidden_scope))
    result.safety_notes.append(f"Forbidden action(s): {all_forbidden}")

# Only set requires_confirmation=True for POSITIVE forbidden items
all_forbidden_items = list(set(legacy_forbidden + forbidden_scope))
if all_forbidden_items:
    positive_forbidden = [f for f in all_forbidden_items if f not in forbidden_scope]
    if positive_forbidden:
        result.requires_confirmation = True
```

---

## Confirmation Gate Behavior (After Fix)

| Scenario | `scope` | `forbidden_scope` | `requires_confirmation` | Result |
|----------|---------|-------------------|------------------------|--------|
| "external publish" (positive) | [external_publish] | [] | **True** | BLOCKED |
| "jangan external publish" (negative) | [] | [external_publish] | **False** | ✅ ALLOWED |
| "180 menit" (over threshold) | [] | [] | **True** | BLOCKED |
| "120 menit safe" | [] | [] | **False** | ✅ ALLOWED |
| Phase 48C full (negative) | [test_expansion,...] | [external_publish] | **False** | ✅ ALLOWED |

---

## Status Semantics Fix

**Problem:** Runner crashed (TypeError) but final status still written as COMPLETE. No crash detection.

**Fix in rerun script:**
```python
try:
    # All execution steps
    exit_code = 0
    final_verdict = determine_verdict(results)
except Exception as e:
    # Any exception = ERROR, not COMPLETE
    final_verdict = 'ERROR'
    exit_code = 1

# Only claim COMPLETE if exit code is 0 and no exception
if final_verdict == 'ERROR':
    sys.exit(1)
elif final_verdict == 'PARTIAL':
    sys.exit(2)
else:
    sys.exit(0)
```

**Rule:** `ERROR ≠ SUCCESS`. If process crashes or throws exception, final verdict must be ERROR, not COMPLETE. Report must reflect actual exit code.

---

## Phase 48C-CLOSE Rerun Result

| Metric | Phase 48C (INVALID) | Phase 48C-CLOSE (TRUTH LOCKED) |
|--------|---------------------|-------------------------------|
| Exit code | 1 (crash) ❌ | **0** ✅ |
| external_publish in scope | True ❌ | **False** ✅ |
| requires_confirmation | True ❌ | **False** ✅ |
| Final verdict | COMPLETE (FAKE) ❌ | **COMPLETED_WITH_WARN** ✅ |
| Session ID | 9ac97106 | **0860e93e** ✅ |
| Errors | Unknown | **0** ✅ |
| Failures | Unknown | **0** ✅ |

**Trace:** `evidence/evolution_traces/phase48c_close/trace_0860e93e.json`
**Run type:** `ACCELERATED_120MIN_SIMULATION` (not real-time)

---

## Hard Rules for Future Auto-Learning Runs

1. **Verify exit code** before declaring COMPLETE. Exit code 0 = success, non-zero = failure/error.
2. **Negative scope**: jangan/don't/no patterns must be detected and items placed in `forbidden_scope`, not `scope`.
3. **Confirmation gate**: Negative forbidden = no confirmation needed; Positive forbidden = confirmation required.
4. **Crash = ERROR**: Any exception during execution sets final_status to ERROR, not COMPLETE.
5. **No false claims**: If run was accelerated simulation, say so. Don't claim real-time if it wasn't.
6. **external_publish/deploy/install/delete/OS_build**: Must appear in `forbidden_scope` when negated, never in `scope`.