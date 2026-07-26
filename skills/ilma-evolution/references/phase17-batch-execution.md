# Phase 17 Batch Execution — Key Patterns and Pitfalls

**Date:** 2026-05-09
**Phase:** 17 (350-file stability gate)

## Heredoc Marker Contamination

### Problem
Using `cat > file << 'PYEOF'` for batch file generation causes `PYEOF` to appear as literal content in Python files.

### Detection
```bash
grep -l "PYEOF" target_dir/**/*.py
```

### Fix
```python
# Instead of heredoc, use Python file writing:
with open(fpath, 'w') as f:
    f.write(content)  # content has Python code as string
```

## sys.path for Test Files

### Problem
Test files in `test_projects/phase17_350file_codebase/tests/` used relative path calculation from `__file__`:
```python
ilma_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # WRONG
```
This resolves to `'test_projects'` not `/root/.hermes/profiles/ilma/`.

### Fix
```python
sys.path.insert(0, '/root/.hermes/profiles/ilma/scripts')  # ALWAYS absolute
```

## Compile Before Tests

### Pattern
Always compile all Python files before running pytest:
```bash
python3 -m compileall test_projects/phase17_350file_codebase/ -q
python3 -m pytest test_projects/phase17_350file_codebase/tests/ -q --tb=no
```

## File Count Methodology

| Metric | Count Method |
|--------|-------------|
| Total Python | All `.py` files |
| Non-test Python | Exclude `test_*.py` and `tests/` dir |
| Purposeful | Non-test excluding `__pycache__`, `fixtures` |

```python
import os
purposeful = [f for root, dirs, files in os.walk(base) 
              for f in files 
              if f.endswith('.py') and not f.startswith('test_') 
              and 'tests' not in root]
```

## Evidence Validator Regex Fix

```python
# BEFORE (wrong)
pattern = r'^ILMA-EVID-\d{8}-P\d+-[A-Z]+-0\d{3}$'

# AFTER (correct)
pattern = r'^ILMA-EVID-\d{8}-P\d+-[A-Z]+-\d{3}$'
```

## Module Interface Discovery

Always verify actual interface before writing tests:
```python
from ilma_workflow_ecc import WorkflowEngine
wf = WorkflowEngine()
print('Methods:', [m for m in dir(wf) if not m.startswith('_')])
```

## 350-File Stability Gate

- Fork stable source → `test_projects/phase17_350file_codebase/`
- Never modify source during expansion
- Run tests against fork, not source
- Compile check after every batch
- Stop: `purposeful_count >= 350`
- Verify: `find . -name "*.py" -not -path "./tests/*" -not -name "test_*.py" | wc -l`