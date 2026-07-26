# Standalone Script Execution vs Module Import Path Patterns

## Phase 56CLOSE Finding

**Problem:** Scripts that work when imported as modules fail when run standalone as scripts.

### The Pattern

```python
# module_a.py
class Foo:
    def method(self):
        pass

# Works when imported:
from module_a import Foo  # OK

# Fails when run standalone:
# python3 module_a.py → runs but no output (if no main guard)
```

### Why This Matters

When auditing imports, a successful `from module import ClassName` does NOT guarantee the module works as a standalone script. The import path and execution path are different.

### Detection

```python
# Test import path
try:
    from module_a import Foo
    import_ok = True
except ImportError as e:
    import_ok = False

# Test standalone execution
import subprocess
result = subprocess.run(['python3', 'module_a.py'], capture_output=True, text=True)
# exit_code == 0 + no stderr = works standalone
```

### The Key Lesson

**Scripts that work when imported fail standalone if they:**
1. Have side effects at module level (DB connections, class instantiations)
2. Lack `if __name__ == "__main__":` guards
3. Depend on relative imports that break when run as `__main__`

**Always test BOTH paths:**
- Import path: `python3 -c "from module import something"`
- Standalone path: `python3 module.py`

---

*Last updated: 2026-05-15 (Phase 56CLOSE)*