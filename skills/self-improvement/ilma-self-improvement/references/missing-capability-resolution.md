# Missing Module Resolution — Capability Gap Closure
**Source:** Phase 16D (memory layer) / Phase 16E (QA critic) — 2026-05-09

---

## The Pattern

When capability registry says PARTIAL and the reason is "script missing":
1. Search broadly — the script may be wrapped by another module, split across files, or exist at a different path
2. Look in skill execution directories (scripts/skills_exec/)
3. Look for modules with matching function/class names that could satisfy the capability
4. Build compatibility shim or wrapper — integration is not cheating

---

## Two Successful Patterns

### Pattern A: Compatibility Shim (aggregates existing modules)

Used for `memory` capability. 4 memory modules existed but no unified interface.

```python
#!/usr/bin/env python3
"""Memory Layer — integrates analytics/cleanup/persistence/search"""

import sys, importlib.util
from pathlib import Path

_sub_modules = {}
for name, path in MODULE_PATHS.items():
    spec = importlib.util.spec_from_file_location(f"mod_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"mod_{name}"] = mod
    spec.loader.exec_module(mod)
    _sub_modules[name] = mod

class MemoryLayer:
    def store_event(self, key, data): ...
    def retrieve_event(self, key): ...
    def search_memory(self, query): ...
    def list_recent(self, n=10): ...
    def persist(self): ...
    def load(self): ...
```

### Pattern B: Wrapper (extends existing executor)

Used for `qa_critic` capability. Underlying `ilma_exec_qa_critic.py` (103 lines, running since Phase 2) existed but no module-level interface.

```python
#!/usr/bin/env python3
"""QA Critic — wraps ilma_exec_qa_critic.py with extended interface"""

import sys, importlib.util
spec = importlib.util.spec_from_file_location("exec_qa", SKILLS_EXEC_PATH)
_exec_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_exec_mod)

def critique_text(text):
    raw_issues = _exec_mod.find_issues(text)
    score = max(0, 1.0 - (len(raw_issues) * 0.15))
    return {"issues": raw_issues, "score": score, "passed": score >= 0.7}

def critique_code(code, language="python"): ...  # Added, not in original
def score_output(text): ...                      # Added, not in original
def suggest_revision(text): ...                  # Added, not in original
```

---

## Key Test Discipline

Always test actual behavior, not just file existence:

```python
# Test all 6 interface methods
ml = MemoryLayer()
assert ml.store_event('test', {'data': 1}) == True
assert ml.retrieve_event('test') is not None
assert len(ml.search_memory('data')) >= 1
assert len(ml.list_recent(5)) >= 1
assert ml.persist() == True
assert ml.load() == True
```

---

## When to Deprecate

If no script exists AND no equivalent exists anywhere:
- Mark `DEPRECATED`, not `VERIFIED`
- No fake evidence
- Document the honest reason

`mutation_bug_cycle` → DEPRECATED: no script, no equivalent, concept not viable.

---

## When to Keep PARTIAL

If:
- Orchestrator class is referenced but doesn't exist
- Module exists but no runtime behavior verified
- File exists but 0 bytes
- Depends on external dependencies

Don't force upgrade. Keep PARTIAL with documented reason.

---

## Registry Update Template

```python
cap['capability_name'] = {
    'status': 'VERIFIED',
    'confidence_score': 0.72,
    'last_verified': '2026-05-09',
    'evidence': 'Module implements full interface. All N methods tested.',
    'primary_module': 'module_name'
}
```