---
name: ilma-integration-testing-pattern
description: "API-introspection-first integration testing pattern for unfamiliar codebases. Critical lesson: always discover actual runtime API before writing integration tests."
triggers:
  - integration test
  - write integration tests
  - test for unfamiliar code
  - api surface discovery
version: 1.0.0
tier: SSS
last_updated: 2026-05-08
---

# ILMA Integration Testing: Introspection-First Pattern

## Context

When ILMA wrote 3 integration tests for the LARMA 100-file codebase (Phase 9), ALL 3 failed because ILMA assumed API method names from class names rather than discovering actual runtime signatures. This wasted iterations.

**Example failures:**
- Assumed `WorkflowRegistry.create_workflow()` — actual: `WorkflowRegistry.create()`
- Assumed `EvidenceLogger.log_evidence()` — actual: `EvidenceLogger.log()`
- Assumed `Task.transition_to()` — actual: `Task.mark_running()`, `Task.mark_completed()`
- Assumed `ArtifactManager.register_artifact()` — actual: `ArtifactManager.store_content()`
- Assumed `WorkflowRegistry.close()` — didn't exist
- Assumed `ArtifactManager.get(workflow_id, name)` — actual: `ArtifactManager.get(name)` only

## The Correct Pattern

### Step 1: Introspect BEFORE writing tests

```python
import sys
sys.path.insert(0, '/path/to/codebase')

# For each class you want to test, list actual public methods
from services.workflow_registry import WorkflowRegistry
from services.evidence_logger import EvidenceLogger
from services.artifact_manager import ArtifactManager
from models.task import Task

for cls, name in [(WorkflowRegistry, "WorkflowRegistry"),
                   (EvidenceLogger, "EvidenceLogger"),
                   (ArtifactManager, "ArtifactManager"),
                   (Task, "Task")]:
    print(f"\n=== {name} ===")
    methods = [m for m in dir(cls) if not m.startswith('_')]
    print("Methods:", methods)
    import inspect
    for method_name in methods:
        try:
            method = getattr(cls, method_name)
            if callable(method):
                sig = inspect.signature(method)
                print(f"  {method_name}{sig}")
        except:
            pass
```

### Step 2: Test ONE method at a time

```python
# BEFORE: Write all tests then run
# AFTER: Write one test, run, verify, repeat

def test_workflow_create():
    registry = WorkflowRegistry()
    wf = registry.create("test", {"version": "1.0"})  # Use actual API
    assert wf.id is not None
    print("PASSED: test_workflow_create")
```

### Step 3: Discover data model fields

```python
# For dataclasses, check __dict__ or field names
task = Task(workflow_id="wf-1", name="test", priority=TaskPriority.HIGH)
print("Task fields:", [k for k in vars(task) if not k.startswith('_')])
# Sample: ['id', 'workflow_id', 'name', 'priority', '_status', ...]
```

### Step 4: For dataclasses with private state

Many ILMA models use dataclasses with private `_status` fields and public `mark_*()` / `from_dict()` / `to_dict()` methods rather than direct `transition_to()`.

```
Common patterns:
- mark_running(), mark_completed(), mark_failed() — not transition_to()
- from_dict() / to_dict() — for serialization
- validate() — for model validation
- update() — for field updates
- _private_field — internal state pattern
```

### Step 5: Store API reference card

```python
# API Reference Card (update after each discovery)
API_REFERENCE = {
    "WorkflowRegistry": {
        "create(name, metadata)": "returns Workflow",
        "get(workflow_id)": "returns Workflow or None",
        "get_status(workflow_id)": "returns dict",
        "list()": "returns list of Workflow",
        "delete(workflow_id)": "bool",
    },
    "EvidenceLogger": {
        "log(task_id, evidence_type, content, metadata=None)": "returns evidence_id",
        "get_evidence(evidence_id)": "dict or None",
        "list_evidence(task_id)": "List[dict]",
        "count(task_id)": "int",
    },
    "ArtifactManager": {
        "store(name, artifact_type, source_path, workflow_id=None)": "ArtifactInfo",
        "store_content(name, artifact_type, content_str, workflow_id=None)": "ArtifactInfo",
        "get(artifact_id)": "Artifact or None",
        "list_artifacts(workflow_id)": "List[dict]",
    },
    "Task": {
        "mark_running()": "None",
        "mark_completed()": "None",
        "mark_failed()": "None",
        "to_dict()": "dict",
        "from_dict(data)": "Task",
    }
}
```

## Meaningful File Count Pattern

When assessing a codebase for "X-file" claims, distinguish purposeful files from data/cache:

```python
from pathlib import Path

base = Path("/path/to/codebase")
purposeful = []
data_files = []
cache_files = []

for p in sorted(base.rglob("*")):
    if not p.is_file():
        continue
    rel = str(p.relative_to(base))
    if "__pycache__" in rel or ".pytest_cache" in rel:
        cache_files.append(rel)
        continue
    if "data/workflows/" in rel:  # Generated data, not source
        data_files.append(rel)
        continue
    purposeful.append(rel)

print(f"Purposeful files: {len(purposeful)}")  # Use this for claims
print(f"Data files (excluded): {len(data_files)}")
print(f"Cache files (excluded): {len(cache_files)}")
```

**Rule:** Only count purposeful files for capability claims. Data/cache/artifacts don't count.

## Anti-Patterns to Avoid

1. **DON'T** assume method names from class names or documentation
2. **DON'T** write all tests at once before running any
3. **DON'T** assume all models use `transition_to()` for state changes
4. **DON'T** use high-level names like `log_evidence` without verifying
5. **DON'T** claim file count includes generated data files

## Verification Checklist

Before claiming integration tests are written:
- [ ] Introspected actual class methods and signatures
- [ ] Tested ONE method manually before writing formal tests
- [ ] Verified Task model uses `mark_*()` not `transition_to()`
- [ ] Verified EvidenceLogger uses `log()` not `log_evidence()`
- [ ] Verified ArtifactManager uses `get(name)` not `get(workflow_id, name)`
- [ ] Checked Task model has `_private` state fields
- [ ] Ran the test and it passes on first attempt

## Evidence ID

E-2026-0508-012
