# Pre-auth / Open LAN Access — Wrapper Fleet

User preference (recurring): "akses user tanpa auth" / "pre-auth saja" / "buka untuk user".
All wrappers (9101–9105) + model-registry (9200) + dashboards (3000/8000) must be reachable
from the LAN IP WITHOUT a bearer token.

## GOTCHA #1 — do NOT blank BEARER_TOKEN
`nvidia-python/src/main.py::validate_config()`:
```python
for var in ['NVIDIA_API_KEY_1', 'BEARER_TOKEN']:
    if not os.environ.get(var):
        missing.append(var)
if missing:
    print(f"❌ ERROR: Missing required environment variables: {', '.join(missing)}")
    sys.exit(1)
```
Blanking `BEARER_TOKEN` → wrapper exits 1 on startup → `systemctl --user` shows
`activating (auto-restart)`, port curl returns `000`. **Keep the token, disable auth another way.**

## GOTCHA #2 — model-registry .env overrides service.py
`/root/wrapper/model-registry/service.py`:
```python
host=os.environ.get("MODEL_REGISTRY_HOST", "0.0.0.0"),
```
But `/root/wrapper/model-registry/.env` has `MODEL_REGISTRY_HOST=127.0.0.1` which WINS.
Patches to service.py alone have NO effect — edit the `.env`.

## Procedure (verified 2026-07-28)
1. In each wrapper `.env` (`nous`, `nvidia-python`, `opencode`, `blackbox`, `vercel`):
   keep `BEARER_TOKEN=wrapper-local-key`, ADD:
   ```
   # Pre-auth mode: set DISABLE_AUTH=1 to allow access without bearer token (LAN/open)
   DISABLE_AUTH=1
   ```
2. Patch each wrapper's auth gate (locations differ — see below).
3. `model-registry/.env`: `MODEL_REGISTRY_HOST=0.0.0.0` (and keep `MODEL_REGISTRY_PORT=9200`).
4. `systemctl --user restart wrapper-<name>.service` for all 6. (No `daemon-reload` needed
   for `.env` changes — `EnvironmentFile` re-read on restart.)
5. Verify (see below).

## Exact gate diffs

### nvidia-python  (src/main.py, auth_middleware)
```python
# BEFORE
if BEARER_TOKEN and not is_public:
# AFTER
if BEARER_TOKEN and not is_public and not os.environ.get('DISABLE_AUTH'):
```

### nous  (src/main.py, _auth_check)
```python
# BEFORE
    if not BEARER_TOKEN: return
# AFTER
    if not BEARER_TOKEN: return
    if os.environ.get('DISABLE_AUTH'): return
```

### opencode / vercel  (src/main.py, _auth_check — identical pattern)
```python
# BEFORE
    if request.method == 'OPTIONS':
        return  # CORS preflight passes without auth
# AFTER
    if request.method == 'OPTIONS':
        return  # CORS preflight passes without auth
    if os.environ.get('DISABLE_AUTH'):
        return  # pre-auth mode: allow all (LAN/open)
```

### blackbox  (src/main.py, _auth_check)
```python
# BEFORE
    if request.method == 'OPTIONS':
        return
# AFTER
    if request.method == 'OPTIONS':
        return
    if os.environ.get('DISABLE_AUTH'):
        return  # pre-auth mode: allow all (LAN/open)
```

## Verification recipe
From the LAN IP (what the user's browser / client does):
```bash
# Auth bypassed = chat works WITHOUT Authorization header
curl -s -X POST "http://172.16.102.11:9102/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"tencent/hy3:free","messages":[{"role":"user","content":"reply with: OK"}]}'
# → {"choices":[{"message":{"content":"OK",...}}]}  (200, no token sent)

# 9101 (nvidia) WITHOUT auth → expect 400/404 from upstream, NOT 401
curl -s -o /dev/null -w "%{http_code}\n" -X POST "http://172.16.102.11:9101/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"nvidia/meta/llama-3.3-70b-instruct","messages":[{"role":"user","content":"hi"}]}'
# → 400/404 = auth bypassed OK; 401 = auth still enforced (DISABLE_AUTH not honored)
```
A `400`/`404` from upstream (e.g. NVIDIA "Function '...' Not found for account '...'") means
auth was successfully bypassed — only `401` means auth is still on.

## Reversing (re-enable auth)
Remove `DISABLE_AUTH=1` from the `.env` files (or set `DISABLE_AUTH=0`) and restart.
The gate code can stay patched — with `DISABLE_AUTH` unset the original behavior returns.

## Security note
Open + `0.0.0.0` exposes all LLM wrappers to the network. If the machine is internet-reachable
(CloudflareWARP / public IP), recommend nginx reverse proxy + basic-auth/TLS, or firewall-limit
to the Bos IP. Don't leave pre-auth open on a public host.
