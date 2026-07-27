# wrapper-nvidia HTTP 500 — `NameError: sanitize_header_value` (2026-07-27)

## Symptom
Claude Code (and any client) gets **HTTP 500 Internal Server Error** on every request
to `wrapper-nvidia-python` (port 9101) after a `git pull` from `github` updated the
wrapper code (commits `f5bfeea`, `92893e7`).

## Reproduction
```bash
curl -s -o /tmp/nv.json -w "HTTP %{http_code}\n" -X POST http://127.0.0.1:9101/v1/chat/completions \
  -H "Authorization: Bearer wrapper-local-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"nvidia/meta/llama-3.3-70b-instruct","messages":[{"role":"user","content":"ping"}],"max_tokens":16}' --max-time 30
# → HTTP 500
# → {"error":{"message":"Internal server error","type":"server_error"}}
```

## Root cause (confirmed via traceback in `/root/wrapper/nvidia-python/nvidia_py.log`)
```
File "src/main.py", line 1069, in forward_headers
    sanitized = sanitize_header_value(val)
NameError: name 'sanitize_header_value' is not defined
```

- `src/main.py:62` does `from common.middleware import RequestSizeLimiter, sanitize_header_value`.
- `common` package lives at **`/root/wrapper/common/`** (repo root), NOT inside `nvidia-python/`.
- The systemd unit sets a NARROW `PYTHONPATH=/root/wrapper/nvidia-python` only:
  ```
  Environment=PYTHONPATH=/root/wrapper/nvidia-python
  ```
  (`/root/.config/systemd/user/wrapper-nvidia-python.service`)
- So the import FAILS → caught by `except ImportError` → `_HAS_SIZE_LIMITER = False` (startup does NOT crash).
- But `forward_headers()` (line 1069) still CALLS `sanitize_header_value()` with no guard → `NameError` → **500 on every request** (`/v1/messages` AND `/chat/completions`).

## Confirmation commands
```bash
# 1. common is at repo root, not in service PYTHONPATH
grep PYTHONPATH /root/.config/systemd/user/wrapper-nvidia-python.service
#    → Environment=PYTHONPATH=/root/wrapper/nvidia-python
find /root/wrapper -name middleware.py | grep -v pyc
#    → /root/wrapper/common/middleware.py   (def sanitize_header_value @ line 88)

# 2. import fails outside /root/wrapper
cd /tmp && python3 -c "import common" 2>&1 | head -1
#    → ModuleNotFoundError: No module named 'common'

# 3. common.model_state import (line 80) is guarded with sys.path.insert(parents[2]),
#    but the common.middleware import (line 62) was NOT — that's the gap.
```

## Fix (surgical, applied & verified)
In `src/main.py`, add the repo root to `sys.path` BEFORE the `common.middleware` import,
plus a fallback guard:
```python
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # /root/wrapper
    from common.middleware import RequestSizeLimiter, sanitize_header_value
    _HAS_SIZE_LIMITER = True
except ImportError:
    _HAS_SIZE_LIMITER = False
    def sanitize_header_value(value):  # safety net: never 500 if import fails
        if not isinstance(value, str):
            value = str(value)
        return re_module.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value).strip()
```
(`import sys` and `import re as re_module` already exist at top of main.py.)

Restart:
```bash
systemctl --user restart wrapper-nvidia-python.service
sleep 3
```

## Post-fix verification (PROVES fix, don't trust "restarted OK")
```bash
# Before fix: HTTP 500. After fix: request reaches validation/upstream (400/404/200).
curl -s -o /tmp/r.json -w "HTTP %{http_code}\n" -X POST http://127.0.0.1:9101/v1/chat/completions \
  -H "Authorization: Bearer wrapper-local-key" -d '{"model":"meta/llama-3.3-70b-instruct","messages":[{"role":"user","content":"hi"}],"max_tokens":16}'
# → HTTP 400 model_not_found  (the 500 is GONE — request now past forward_headers)

# NameError count must be ZERO after restart timestamp
grep "NameError: name" /root/wrapper/nvidia-python/nvidia_py.log | grep -o '"ts": "[^"]*"' | tail -3
# tail of log: "... Application startup complete"  +  400/404/200 entries, NO 500
```

## What the 400/404 mean AFTER the fix (not a code bug)
- `400 model_not_found` → wrong model id. Fix the NAME, not the code. The `nvidia/` prefix
  only applies to Nemotron-super models:
  - ❌ `nvidia/meta/llama-3.3-70b-instruct`
  - ✅ `meta/llama-3.3-70b-instruct`
  - ✅ `nvidia/llama-3.3-nemotron-super-49b-v1`
- `404 Function '<uuid>': Not found for account '<id>'` → upstream NVIDIA NIM: that model is
  NOT deployed/subscribed under the wrapper's NVIDIA account. Per-account availability
  (see SKILL.md taxonomy), NOT a wrapper defect.
- A long timeout (curl `--max-time 120` → HTTP 000) on a valid id = upstream NVIDIA latency /
  model not currently served — not a wrapper 500.

## Gotcha: model-name prefix
Wrapper catalog ids mostly have NO provider prefix; `nvidia/` is reserved for the
Nemotron-super subset only. Enumerate real ids:
```bash
curl -s http://127.0.0.1:9101/v1/models -H "Authorization: Bearer wrapper-local-key" \
  | python3 -c "import sys,json; [print(m['id']) for m in json.load(sys.stdin)['data']]"
```

## Note on git state
The fix was applied to the WORKING TREE only (unstaged) during this session. To persist,
commit + push to `github` (the cloud remote), NOT `origin` (local bare `/root/wrapper_remote.git`).
Pull rule for this repo: always `git pull github main` — never from `origin`.
