# wrapper-nous Codex-Hang Verification (BUG-CODEX1 / BUG-CODEX2)

**Date:** 2026-07-27
**Symptom reported by Bos:** "wrapper-nous dipakai di Codex, proses berhenti sebelum final response / final process berhasil dijalankan."
**Outcome:** Verified FIXED (commit `f5bfeea`). Both bugs resolved; stream completes.

---

## Root cause (from CROSS_WRAPPER_BUG_POLICY.md)

- **BUG-CODEX1 (stream finalization):** `store_conversation` called after stream could block generator finalization → process stops before final response.
  - Fix location: `nous/wrapper_nous.py:1876` — wrapped in `try/finally`.
- **BUG-CODEX2 (heartbeat):** `stream_with_heartbeat` only fired heartbeats when upstream was sending data → Codex times out on idle upstream.
  - Fix location: `nous/wrapper_nous.py:1035/1044` — `asyncio.wait_for(timeout)` to fire heartbeats even when upstream idle.

Cross-wrapper policy mandates the same pattern be checked in nvidia-python / opencode / blackbox (they share the architecture). The nvidia-python `forward_headers`+`sanitize_header_value` path got its own guard via the 500 fix (see `wrapper-nvidia-500-nameerror-debug.md`).

---

## Verification recipe (proven 2026-07-27)

### Step 1 — Log must be clean post-restart
wrapper-nous logs to a FILE, not journald:
```bash
tail -80 /root/wrapper/nous/wrapper_nous.log
```
Expected after the restart that includes `f5bfeea`:
- `POST /v1/responses HTTP/1.1" 200 OK`
- `GET /v1/models?client_version=0.145.0 HTTP/1.1" 200 OK` (Codex v0.145.0 startup discovery)
- **ZERO** Traceback / NameError / timeout / "store_conversation" block / hang.

Real 2026-07-27 result: `grep -ciE "error|exception|traceback"` over the post-restart window = **0**. 5× `/v1/responses → 200`.

### Step 2 — Reproduce the exact Codex traffic shape
Codex CLI uses the **Responses API** (`/v1/responses`) with `stream:true`. Reproduce with curl:
```bash
curl -s -N -o /tmp/nous_r.txt -w "HTTP %{http_code} time=%{time_total}s\n" \
  -X POST http://127.0.0.1:9102/v1/responses \
  -H "Authorization: Bearer wrapper-local-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"poolside/laguna-s-2.1:free","input":"say hi in one word","stream":true}' \
  --max-time 90
```
Expected: `HTTP 200`, ~4.8s, 2209 bytes received = complete streamed response. **No hang.**

### Step 3 — Confirm Codex config targets the live port
```bash
grep -E "base_url" /root/.codex/config.toml
# → base_url = "http://127.0.0.1:9102/v1"   ✅ (NOT 9100)
```
Also check `model` / `model_provider`:
```
model = "poolside/laguna-s-2.1:free"
model_reasoning_effort = "xhigh"
model_provider = "nous"
```

---

## Auth pitfall (cost a 401 in this session)

When reproducing with curl, use the **local BEARER_TOKEN**, NOT the upstream key:
- ✅ `Authorization: Bearer wrapper-local-key`  (from `nous/.env` → `BEARER_TOKEN=wrapper-local-key`)
- ❌ `Authorization: Bearer <NOUS_API_KEY_1 value>` → **401 Unauthorized**

The wrapper authenticates the client with its local bearer token, then internally rotates the upstream `NOUS_API_KEY_1..5` (or reads OAuth from `AUTH_PATH=/root/.hermes/profiles/ilma/auth.json`). This applies to ALL wrappers: nvidia-python / opencode / blackbox also expect `Bearer wrapper-local-key` for local curl repro.

---

## Port-mismatch findings (2026-07-27)

| Finding | Detail | Severity |
|---------|--------|----------|
| blackbox `.env` vs service | `.env LISTEN_PORT=9108` but `wrapper-blackbox.service` ExecStart hardcodes `--port 9104`. 9108 CLOSED, 9104 OPEN. CLI overrides `.env` → not fatal, but misleading. | ⚠️ MED |
| legacy 9100 in codex config | `/root/.codex/config.openrouter-nemotron.toml:14` → `base_url=http://127.0.0.1:9100/v1`. Legacy `wrapper-nvidia` (9100) was REMOVED; replaced by `wrapper-nvidia-python` (9101). This Codex profile will fail to connect. | ⚠️ LOW |
| memory note obsolete | Bos memory "wrapper-nvidia:9100" is stale. Active NVIDIA wrapper = `wrapper-nvidia-python` on **9101**. | ℹ️ INFO |

**Live port map (verify with `ss -tlnp | grep 910` at every audit start — ports drift):**
```
nous            9102  ✅
wrapper-nvidia-python  9101  ✅
opencode        9103  ✅
blackbox        9104  ✅
model-registry  9200  ✅
legacy 9100     ❌ REMOVED
```

---

## If the hang returns

1. Read `/root/wrapper/nous/wrapper_nous.log` for `store_conversation` / `stream_with_heartbeat` tracebacks.
2. Confirm `f5bfeea` is in the running process's commit: `cat /root/wrapper/runtime/nous.commit` should equal `git rev-parse HEAD` (or be an ancestor). If stale → `systemctl --user restart wrapper-nous.service`.
3. Re-run Step 2 above. A return of HTTP 200 + complete stream = fixed. A hang / mid-stream disconnect = regression — inspect the traceback and re-apply the `try/finally` + `asyncio.wait_for` guards.
