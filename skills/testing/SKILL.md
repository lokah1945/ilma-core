---
name: testing
description: "ILMA Integration Testing Patterns — Best practices for writing integration tests for unfamiliar codebases, API introspection-first patterns, and test automation strategies."
triggers:
  - testing
  - integration test
  - write integration tests
  - test for unfamiliar code
  - api surface discovery
  - test patterns
  - e2e testing
category: ilma-testing
version: 1.0.0
tier: SSS
last_updated: 2026-05-09
type: category
---

# ILMA Integration Testing Patterns

## Overview

This category contains skills for integration testing patterns and best practices specific to ILMA development. The key lesson: **always discover actual runtime API before writing integration tests**.

**Critical Lesson:** When ILMA wrote 3 integration tests for the LARMA 100-file codebase (Phase 9), ALL 3 failed because ILMA assumed API method names from class names rather than discovering actual runtime signatures.

## The Correct Pattern: Introspection-First

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
        method = getattr(cls, method_name)
        if callable(method):
            try:
                sig = inspect.signature(method)
                print(f"  {method_name}{sig}")
            except (ValueError, TypeError):
                print(f"  {method_name}(...)")
```

### Example API Discovery Results

| Assumed API | Actual API |
|-------------|------------|
| `WorkflowRegistry.create_workflow()` | `WorkflowRegistry.create()` |
| `EvidenceLogger.log_evidence()` | `EvidenceLogger.log()` |
| `Task.transition_to()` | `Task.mark_running()`, `Task.mark_completed()` |
| `ArtifactManager.register_artifact()` | `ArtifactManager.store_content()` |
| `WorkflowRegistry.close()` | (didn't exist) |
| `ArtifactManager.get(workflow_id, name)` | `ArtifactManager.get(name)` only |

## Included Skills

### 1. ilma-integration-testing-pattern

**Description:** API-introspection-first integration testing pattern for unfamiliar codebases.

**Triggers:**
- integration test
- write integration tests
- test for unfamiliar code
- api surface discovery

**Key Pattern:**
1. Never assume API names from class names
2. Always introspect runtime signatures first
3. Write a discovery script before writing tests
4. Validate assumptions in REPL before committing to tests

## Testing Strategies

### 1. Discovery Phase

Before writing any test code, explore the actual API surface:

```python
# discovery.py
import sys
sys.path.insert(0, target_dir)

from target_module import TargetClass

# Get all public methods
public_methods = [m for m in dir(TargetClass) if not m.startswith('_')]
print(f"Public methods: {public_methods}")

# Inspect signatures
import inspect
for method in public_methods:
    attr = getattr(TargetClass, method)
    if callable(attr):
        try:
            sig = inspect.signature(attr)
            print(f"{method}{sig}")
        except ValueError:
            print(f"{method}: (cannot inspect signature)")
```

### 2. Validation Phase

Test your discoveries in a REPL before writing tests:

```python
# validate.py
from target_module import TargetClass

instance = TargetClass()

# Test the methods you think exist
try:
    result = instance.create()
    print(f"✓ create() works: {result}")
except AttributeError as e:
    print(f"✗ create() doesn't exist: {e}")
except Exception as e:
    print(f"? create() error: {type(e).__name__}: {e}")
```

### 3. Test Writing Phase

Only after validation, write actual tests:

```python
# test_target.py
import pytest
from target_module import TargetClass

class TestTargetClass:
    def test_create_returns_workflow(self):
        instance = TargetClass()
        result = instance.create()
        assert result is not None
        assert hasattr(result, 'id')
    
    def test_log_evidence(self):
        instance = TargetClass()
        result = instance.log("test evidence")
        assert result is True
```

## Best Practices

1. **API Introspection First** — Always use `dir()` and `inspect.signature()` before writing tests
2. **REPL Validation** — Test assumptions interactively before writing test code
3. **Document Discovered APIs** — Keep a running list of actual vs assumed APIs
4. **Iterate** — If tests fail, go back to introspection
5. **Use Type Hints** — When available, they provide documentation

## Running Tests

```bash
# Run all tests in a skill directory
cd /root/.hermes/profiles/ilma/skills/[skill-name]
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run integration tests only
pytest tests/ -m integration
```

## Test Automation

For CI/CD integration:

```bash
# Auto-discover and run tests
python3 scripts/discover_api.py --target /path/to/codebase
python3 scripts/generate_tests.py --discovered api_discovery.json
pytest tests/ -v --tb=short
```

---
Generated by ILMA v5 Skill System
