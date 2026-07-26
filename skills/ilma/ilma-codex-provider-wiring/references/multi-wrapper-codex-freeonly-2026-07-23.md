# Multi-wrapper Codex wiring + FREE_ONLY session (2026-07-23)

## Wrapper matrix (VERIFIED — do not conflate)

| Wrapper | Port | Backend | Service unit | API key env pattern | FREE_ONLY |
|---------|------|---------|--------------|---------------------|-----------|
| wrapper-nous | 9106 | Nous Research (dynamic alias → tencent/hy3:free) | wrapper-nous.service | reads token from /root/.hermes/profiles/ilma/auth.json | **yes** |
| wrapper-nvidia-python | 9101 | NVIDIA NIM (100% free upstream) | wrapper-nvidia-python.service | BEARER_TOKEN (local) | **NO (not needed)** |
| wrapper-opencode | 9107 | OpenCode cloud (integrate.api.OPENCODE.com, Zen backend = NVIDIA) | wrapper-opencode.service | OPENCODE_API_KEY_1/2/3 | **yes** |
| wrapper-nvidia (Node.js) | 9100 | NVIDIA NIM (legacy) | — | — | DEPRECATED / stopped+disabled |

## Code structure differences (fixes do NOT copy-paste)

- **nous**: `wrapper_nous.py` — all Responses logic inline. Already fully fixed + e2e green.
- **nvidia-py**: `src/responses_compat.py` (ResponsesHandler) + `src/main.py` (`_handle_chat_completions`, `DEFAULT_PARAMS`).
  Fixes applied: `DEFAULT_PARAMS` values cast to float at load; `build_chat_body` casts temperature/top_p/max_tokens; `input_to_messages` normalizes `arguments` (parse str→object→clean json.dumps so ints stay ints, not "250"); `_handle_chat_completions` casts temperature/top_p.
- **opencode**: `src/main.py` only (`responses_to_chat()` inline, no `responses_compat.py`).
  Fixes applied: `responses_to_chat` casts temperature/top_p to float; `LISTEN_PORT` env corrected 9102→9107 to match service.

## Root-cause bugs found & fixed (non-nous)

1. **nvidia-py 400 `invalid type: string "0.7", expected f32`** — `DEFAULT_PARAMS` loaded from env as STRING (`DEFAULT_TEMPERATURE=0.7` → `"0.7"`), then `proxy_openai` injected it into body as string → NVIDIA rejected. Fix: cast `DEFAULT_PARAMS` values to float at load (main.py ~line 259).
2. **nvidia-py 400 `string "10000", expected usize` on tool args** — Codex generated `max_output_tokens:"10000"` (string) in tool `arguments`. The wrapper relayed it to NVIDIA. Also `arguments` double-encoded in round-trip. Fix: `input_to_messages` parses `arguments` JSON string → re-serializes with correct types (`json.dumps` of dict, so `250` stays int).
3. **opencode float temperature** — same class as #1 but in `responses_to_chat` (line 471). Fixed by casting.

## FREE_ONLY verification recipe (run after editing .env)

```bash
# nous: free passes, paid blocked, /v1/models only free
TOKN=$(grep '^BEARER_TOKEN=' /root/wrapper/nous/.env | cut -d= -f2)
curl -s -X POST http://127.0.0.1:9106/v1/responses -H "Authorization: Bearer $TOKN" \
  -d '{"model":"tencent/hy3:free","input":"hi","stream":false,"max_output_tokens":20}'   # → 200
curl -s -X POST http://127.0.0.1:9106/v1/responses -H "Authorization: Bearer $TOKN" \
  -d '{"model":"nvidia/llama-3.3-nemotron-super-49b-v1","input":"hi","stream":false}'    # → 400 blocked
curl -s -H "Authorization: Bearer $TOKN" http://127.0.0.1:9106/v1/models \
  | python3 -c "import sys,json;d=json.load(sys.stdin);ids=[m['id'] for m in d['data']];print('all_free:',all('free' in i.lower() for i in ids),ids)"

# opencode: same shape, but its backend is OpenCode Zen (NVIDIA-backed, NO ":free" suffix in cloud list)
# → with FREE_ONLY=yes and no allowlist, /v1/models returns only the "-free" Zen curated ids
#   (mimo-v2.5-free, nemotron-3-ultra-free, deepseek-v4-flash-free, laguna-s-2.1-free) from fallback_all.
```

## Codex e2e per wrapper (use a FREE model under FREE_ONLY)

```bash
# nous (free model)
CODEX_HOME=/root/.codex-homes/nous codex exec --model tencent/hy3:free \
  "create file /tmp/codex_nous.txt with exact text OK_nous, then confirm"

# nvidia-py (NVIDIA free-tier model — note: NVIDIA has no ":free" suffix; use a known free NIM model)
CODEX_HOME=/root/.codex-homes/nvidia-py codex exec --model nvidia/llama-3.3-nemotron-super-49b-v1 \
  "create file /tmp/codex_nvidia-py.txt with exact text OK_nvidia-py, then confirm"

# opencode (OpenCode Zen free model — NOT a NVIDIA paid model)
CODEX_HOME=/root/.codex-homes/opencode codex exec --model mimo-v2.5-free \
  "create file /tmp/codex_opencode.txt with exact text OK_opencode, then confirm"
```

## systemd orphan-process kill (safe)

```bash
# Find PID holding the port WITHOUT self-killing (avoid pkill -f "port 910X")
for p in $(ls /proc | grep -E '^[0-9]+$'); do
  if grep -qa "9101" /proc/$p/cmdline 2>/dev/null; then kill -9 $p; fi
done
systemctl --user reset-failed wrapper-nvidia-python.service
systemctl --user start wrapper-nvidia-python.service
```

## Unresolved at session end
- opencode `/health` reported `free_only=None` (not True) despite `.env` line `FREE_ONLY=yes` — env may not be re-read by the running process, or `load_dotenv()` ordering vs `EnvironmentFile=`. Needs a clean restart + re-probe. The `fallback_all` Zen `-free` models prove the intent; verification of actual filtering on opencode was interrupted.
- OpenCode cloud direct `/v1/models` returned empty (network/auth/path), so the wrapper relies on `fallback_all` curated list — meaning a true upstream "price=0" fetch was never confirmed; only the `"free"` substring is operative.
