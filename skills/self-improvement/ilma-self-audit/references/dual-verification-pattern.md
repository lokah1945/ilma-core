# Dual Verification Pattern — Wiring + Syntax

**Created:** 2026-05-25  
**Reason:** 2026-05-24 audit found wiring shows 29/30 OK but missed 4 IndentationErrors in `ilma_capability_health_dashboard.py`.

## The Pattern

Every self-audit session must run BOTH checks in sequence. Neither alone is sufficient.

### Check 1 — Module wiring (fast, ~5s)

```bash
cd /root/.hermes/profiles/ilma && python3 ilma_runtime_wiring.py --verify
```
- Verifies 30 core modules are present and exportable
- Checks LAYER_1 through LAYER_8 coverage
- **Limitation:** Does NOT check Python syntax validity

### Check 2 — Syntax compilation (comprehensive, ~30s)

```python
import py_compile
from pathlib import Path
errors = []
ok = 0
for f in sorted(Path('/root/.hermes/profiles/ilma').rglob('*.py')):
    if '__pycache__' in str(f): continue
    try:
        py_compile.compile(str(f), doraise=True)
        ok += 1
    except py_compile.PyCompileError as e:
        errors.append(f'{f}: {e}')
print(f'OK: {ok}, Errors: {len(errors)}')
if errors:
    for e in errors[:30]: print(f'  {e}')
```

- Compiles ALL .py files in ILMA tree
- Catches IndentationError, SyntaxError, SyntaxWarning
- **Limitation:** Slow (~30s for 6000+ files), no module export validation

## Why Both Are Needed

In the 2026-05-24 session:
- `ilma_runtime_wiring.py --verify` → **29/30 OK, 0 missing** ← looks green
- `py_compile` across all files → **4 IndentationErrors** ← would crash workflows

The 4 errors were all in `scripts/ilma_capability_health_dashboard.py` — except blocks with wrong indentation (lines 778, 798, 810, 821, 839). Wiring checked file existence and export counts, but never executed the Python code to find indentation crimes.

## Common Fix Patterns

| Error Pattern | Fix |
|---|---|
| `IndentationError: unexpected indent` (except at wrong depth) | Align except to same level as try body (4 spaces in class method) |
| Missing root-level file (e.g. `ilma_model_registry.py`) | Restore from `hermes_profile_ilma/` backup, commit + push |
| Non-ILMA syntax errors | Ignore — external plugins (huggingface, codex tmp), not ILMA runtime |

## Integration

Referenced from `ilma-self-audit/SKILL.md` Step 2. Load via:
```
skill_view(name='ilma-self-audit', file_path='references/dual-verification-pattern.md')
```