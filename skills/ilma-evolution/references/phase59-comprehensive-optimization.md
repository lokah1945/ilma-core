# Phase 59: Comprehensive End-to-End Optimization

**Session:** 2026-05-17  
**Context:** Deep systematic optimization of all ILMA files — one-per-one, ensuring solid unity

---

## Methodology

### Phase 1: Quick Wins
- `grep -rn "except:" --include="*.py" | grep -v "except Exception"` — find bare except
- Context-aware exception typing:
  - `ValueError` → parse/conversion errors
  - `IOError`/`OSError` → file/filesystem operations
  - `RuntimeError` → subprocess calls
  - `Exception` → psutil, generic recovery

### Phase 2: Import Audit
```python
# AST-based unused import detection
import ast
for fname in root_files:
    tree = ast.parse(content)
    imported = {alias.asname or alias.name.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.Import)}
    used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
    unused = imported - used
```

### Phase 3: Security Scan
```python
# Real security issues only (not false positives like file I/O)
- Hardcoded secrets: re.search(r'(api_key|password|secret|token)\s*=\s*["\'][a-zA-Z0-9+/=]{20,}', line)
- shell=True: 'shell=True' in stripped and 'subprocess' in content
- yaml.load without SafeLoader: 'yaml.load' in stripped and 'SafeLoader' not in stripped
```

### Phase 4: Type Safety
```python
# Inconsistent return types (None mixed with values)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        returns = [r for r in ast.walk(node) if isinstance(r, ast.Return)]
        if 'None' in types and len(set(types)) > 1: flag it
```

### Phase 5: Dead Code
- Private functions (`_name`) never called within same file
- Public functions are NOT dead code — they are public API designed for external calls

### Phase 6: Circular Import Detection
- Build import graph via AST, check bidirectional edges between ILMA modules

---

## Findings Summary

| Category | Files Affected | Action |
|----------|--------------|--------|
| Bare `except:` | 47 files, 73 instances | Fixed → `except Exception:` or specific |
| Unused imports | 17 files, 23 imports | Removed |
| Security | 0 real issues | Clean |
| Type safety | 0 issues | Clean |
| Circular imports | 0 issues | Clean |
| Scripts syntax | 10 critical | All pass |

---

## Git Workflow
- `/tmp/ilma-core-update` → git-tracked copy of `hermes_profile_ilma/`
- Workspace `/root/.hermes/profiles/ilma` is source of truth (not a git repo)
- Commit strategy: batch commit when phase complete

## Key Lessons
1. Context matters: `except: pass` in recovery paths returning empty results is CORRECT behavior
2. AST parsing finds bugs grep misses (type consistency, unused params)
3. False positive discipline: most "dead code" in ILMA is public API
4. Grep `except:` flags comments and multi-exception tuples — must validate each match