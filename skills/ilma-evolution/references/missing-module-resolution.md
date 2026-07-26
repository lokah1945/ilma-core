# ILMA Phase Execution Pattern — Capability Resolution
**Source:** Phase 16D/16E (2026-05-09)

---

## Problem Pattern

ILMA capability registry claims capabilities that map to specific script files. But some capabilities are PARTIAL because the script is:
1. Missing entirely (file not on disk)
2. Empty (0 bytes)
3. Present but orchestrator class/method missing
4. Wrapped by another script (not at expected location)

Just having the script exist doesn't mean the capability is verified. But absence of a script doesn't mean the capability doesn't exist — it may be:
- Wrapped by another module
- Split across multiple files
- Served by a sub-agent
- Embedded in a larger module

---

## Resolution Patterns

### Pattern 1: Missing Script, Equivalent Exists

**Situation:** `ilma_memory_layer.py` is missing but `ilma_memory_analytics.py`, `ilma_memory_persistence.py`, `ilma_memory_search.py`, `ilma_memory_cleanup.py` all exist.

**Resolution:** Create a compatibility shim that integrates the existing modules.

```python
#!/usr/bin/env python3
"""
ILMA Memory Layer — Compatibility Integration Module
Wraps 4 existing memory modules under one unified interface.
"""
from pathlib import Path
import importlib.util

# Lazy-load underlying modules
_sub_modules = {}
for name, path in [("analytics", ANALYTICS_PATH), ...]:
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

### Pattern 2: Missing Script, Underlying Executor Exists

**Situation:** `ilma_qa_critic.py` is missing but `scripts/skills_exec/ilma_exec_qa_critic.py` exists and has been running since Phase 2.

**Resolution:** Create wrapper with extended interface that delegates to underlying executor.

```python
#!/usr/bin/env python3
"""ILMA QA Critic — wraps ilma_exec_qa_critic.py"""
import sys; sys.path.insert(0, 'scripts')
import importlib.util
spec = importlib.util.spec_from_file_location("ilma_exec_qa_critic", SKILLS_EXEC_PATH)
_exec_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_exec_mod)

def critique_text(text):
    raw_issues = _exec_mod.find_issues(text)
    score = max(0, 1.0 - (len(raw_issues) * 0.15))
    return {"issues": raw_issues, "score": score, "passed": score >= 0.7}
```

### Pattern 3: PARTIAL Due to Missing Orchestrator

**Situation:** `evidence_validation` capability PARTIAL because `EvidenceValidatorOrchestrator` is referenced but doesn't exist as a standalone class. The validator itself (`ClaimValidator`) exists in `ilma_evidence_validator.py`.

**Resolution:** For single-method capabilities, locate the method in the larger module and test it directly:
```python
from services.evidence.validator import ClaimValidator
validator = ClaimValidator()
result = validator.validate(...)  # test the actual method
```

### Pattern 4: Empty Script (0 bytes)

**Situation:** `ilma_inspector.py`, `ilma_qa_critic.py` were 0 bytes or file missing.

**Resolution:** Check if equivalent functionality exists elsewhere. If not, implement properly (see Pattern 1/2).

---

## Verification Steps

For any resolved capability, always verify:

```python
# 1. Import works
from module_name import ClassName

# 2. Instantiation works
instance = ClassName()

# 3. At least 3 methods work (tested, not just checked for existence)
result = instance.method_name(args)
assert result is not None

# 4. No fatal errors on any interface method
for method in ['method1', 'method2', 'method3']:
    try: getattr(instance, method)()
    except AttributeError: fail("method missing")
```

---

## Registry Update

After resolution, update capability registry:

```python
import json
with open('config/ilma_capability_registry.json') as f:
    reg = json.load(f)
cap = reg['capabilities']
m = cap.get('capability_name', {})
m['status'] = 'VERIFIED'
m['confidence_score'] = 0.72  # or appropriate score
m['last_verified'] = '2026-05-09'
m['evidence'] = 'Brief description of what was tested'
m['primary_module'] = 'module_name'
with open('config/ilma_capability_registry.json', 'w') as f:
    json.dump(reg, f, indent=2)
```

---

## Key Lessons

1. **Check underlying scripts before creating new ones** — the capability may already exist
2. **Look for wrapped modules** — skill loaders often delegate to other scripts
3. **Test actual methods, not file existence** — grep for classes/functions before claiming verification
4. **Compatibility shims are valid** — wrapping existing modules is not cheating, it's integration
5. **Deprecate honestly** — if no script exists and no equivalent, mark DEPRECATED, don't fake VERIFIED