# Wrapper Python/Venv Inconsistency — 2026-07-29

## Current State
| Wrapper | Python | Venv | PYTHONPATH | systemd ExecStart |
|---------|--------|------|------------|-------------------|
| wrapper-nous | system python3 | NONE | implicit (cwd) | `python3 wrapper_nous.py` |
| wrapper-openrouter | .venv | `/root/wrapper/openrouter/.venv` | explicit `PYTHONPATH=/root/wrapper` | `.venv/bin/python -m uvicorn src.main:app` |
| wrapper-opencode | system python3 | NONE | implicit | `python3 -m uvicorn src.main:app` |
| wrapper-blackbox | system python3 | NONE | implicit | `python3 src/main.py` |
| wrapper-vercel | system python3 | NONE | implicit | `python3 -m uvicorn src.main:app` |
| wrapper-nvidia-python | N/A | N/A | N/A | NOT DEPLOYED |

## Problems
1. **Inconsistent dependency isolation**: Only openrouter uses venv
2. **PYTHONPATH magic**: openrouter requires explicit `PYTHONPATH=/root/wrapper` for `common/` imports; others rely on cwd or sys.path hacks in code
3. **System python risk**: `pip install` affects all wrappers; version conflicts likely
4. **No reproducibility**: Can't pin deps per-wrapper without venv

## Standard
**Each wrapper gets its own `.venv`** with pinned `requirements.txt` (with hashes).

Systemd unit template:
```ini
WorkingDirectory=/root/wrapper/<svc>
Environment=PYTHONPATH=/root/wrapper
ExecStart=/root/wrapper/<svc>/.venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port <PORT>
```

## Migration Steps (per wrapper)
```bash
cd /root/wrapper/<svc>
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt  # with hashes preferred
# Test:
.venv/bin/python -c "import common; print('common ok')"
```

## Related
- `references/wrapper-common-import-fix.md` — the sys.path hack in wrapper-nous/nvidia for `common/`
- `ilma-wrapper-production-audit` — checks venv existence in audit