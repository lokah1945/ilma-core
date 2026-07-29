# Python Venv / Path Inconsistency Across Wrappers — 2026-07-29

## Symptom
Wrappers use different Python execution environments:
- wrapper-openrouter: `.venv` + explicit `PYTHONPATH=/root/wrapper` in systemd
- wrapper-nous: system python + implicit path (flat `wrapper_nous.py` at repo root)
- wrapper-opencode: system python + `src/main.py` structure
- wrapper-blackbox: system python + `src/main.py` structure
- wrapper-vercel: system python + `src/main.py` structure
- wrapper-nvidia-python: system python + `src/main.py` structure
- wrapper-model-registry: system python + explicit `PYTHONPATH=/root/wrapper`

## Root Cause
No standardized deployment template. Each wrapper evolved independently.

## Impact
- `import common` fails on some wrappers (PYTHONPATH missing)
- Dependency versions drift (no shared `requirements.txt`)
- Security patches not uniformly applied
- Debugging harder (different import paths)
- `common/middleware.py` security fix not active on some wrappers

## Fix Required
Standardize on per-wrapper virtualenv + repo-root PYTHONPATH:

### Systemd unit template (apply to all):
```ini
[Service]
WorkingDirectory=/root/wrapper/<svc>
Environment=PYTHONPATH=/root/wrapper
ExecStart=/root/wrapper/<svc>/.venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port <PORT>
```

### Each wrapper gets `.venv/` with pinned requirements:
```bash
cd /root/wrapper/<svc>
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt  # pinned versions with hashes
```

### Shared `common/` imports work because PYTHONPATH=/root/wrapper

## Verification
After fix:
```bash
# All wrappers should have .venv/
ls -la /root/wrapper/*/.venv/bin/python

# All should import common successfully
for svc in nvidia-python nous opencode blackbox vercel model-registry openrouter; do
  /root/wrapper/$svc/.venv/bin/python -c "import common; print('$svc OK')"
done
```

## Related
- `references/wrapper-bind-host-inconsistency.md`
- `references/wrapper-free-only-inconsistency.md`
- `references/wrapper-nous-missing-endpoints.md`