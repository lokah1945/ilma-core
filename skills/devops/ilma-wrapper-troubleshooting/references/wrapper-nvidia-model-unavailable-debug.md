# Reference: wrapper-nvidia "model unavailable" debug — real repro (moonshotai/kimi-k2.6)

Reproduced 2026-07-24, wrapper-nvidia on port **9101** (pid 2251922, `uvicorn src.main:app`).
Audit mode: READ-ONLY (no fix). Client: Claude Code v2.1.202.

## Symptom
Claude Code: `There's an issue with the selected model (moonshotai/kimi-k2.6). It may not exist or you may not have access to it. Run /model to pick a different model.`

## Exact reproduction commands
```bash
# 0. locate live wrapper ports
(ss -tlnp 2>/dev/null || netstat -tlnp) | grep -E '910[0-9]'

# 1. client config (Claude Code)
cat ~/.claude/settings.json
#   ANTHROPIC_BASE_URL=http://localhost:9101
#   ANTHROPIC_MODEL=moonshotai/kimi-k2.6
#   CLAUDE_CODE_GATEWAY_MODEL_DISCOVERY_URL=http://localhost:9101/v1/models

# 2. gateway LISTS the model (catalog-level, keyless-public sourced)
curl -s http://127.0.0.1:9101/v1/models -H "Authorization: Bearer wrapper-local-key" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print([m['id'] for m in d['data'] if 'kimi' in m['id'].lower()])"
# -> ['moonshotai/kimi-k2.6']   (note "verified":false)

# 3. gateway BLOCKS it at /v1/messages  (THIS is the error Claude Code sees)
curl -s http://127.0.0.1:9101/v1/messages -H "Authorization: Bearer wrapper-local-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"moonshotai/kimi-k2.6","max_tokens":8,"messages":[{"role":"user","content":"hi"}]}'
# -> {"type":"error","error":{"type":"not_found_error","message":"Model moonshotai/kimi-k2.6 is retired or unavailable"}}

# 4. NVIDIA itself, using WRAPPER's own key (from /root/wrapper/nvidia-python/.env)
K=$(grep -i "NVIDIA_API_KEY" /root/wrapper/nvidia-python/.env | head -1 | cut -d= -f2)
curl -s https://integrate.api.nvidia.com/v1/chat/completions \
  -H "Authorization: Bearer $K" -H "Content-Type: application/json" \
  -d '{"model":"moonshotai/kimi-k2.6","messages":[{"role":"user","content":"hi"}],"max_tokens":1,"stream":false}'
# -> {"status":404,"title":"Not Found","detail":"Function '23d4f03a-...': Not found for account 'SVfYs4vEaUV3WYvz_...'"}

# 5. verify sweep log confirms membership in retired set
grep "verify" /root/wrapper/nvidia-python/nvidia_py.log | tail -3
# -> [verify] sweep done: 68 unavailable, 53 retired
```

## NVIDIA 404/410 response-shape table (key = diagnosis)
| NVIDIA response | Meaning | Wrapper action |
|---|---|---|
| `404 {"detail":"Function '<uuid>': Not found for account '<acct>'"}` | Account hasn't deployed this model | → `_retired_models` (HARD block) |
| `404 page not found` | Wrong model id format / route missing | → `_retired_models` (HARD block) |
| `410 Gone {"detail":"... reached its end of life on <date>"}` | Globally retired | → `_retired_models` (HARD block) |
| `200` | Deployed & callable in this account | → available |

For `moonshotai/kimi-k2.6` the wrapper key account `SVfYs4vEaUV3...` returns the account-scoped 404 → falsely "retired". Public catalog (keyless) DOES list it, so `/v1/models` advertises it. Mismatch = root cause.

## Source-code anchors (wrapper-nvidia)
- `src/main.py:1610-1614` — `is_model_unavailable()` gate returns 404 for `/v1/messages`.
- `src/main.py:735-748` — `is_model_unavailable()`: hard-block on `_retired_models` (default; `STRICT_BLOCK_UNAVAILABLE_MODELS` off).
- `src/main.py:96-120` — `verify_models()` / `_probe()`: status ∈ {404,410} → `_retired_models.add(mid)`.
- `src/main.py:77-94` — `probe_model()`: posts to `BASE_LLM=/v1/chat/completions` with key-pool key.
- `src/key_pool.py:_fetch_models()` — catalog fetched **keylessly** from public `/v1/models` (118 models), no account filter.

## Why "model aman di NIM" can be true AND the wrapper still blocks
NVIDIA NIM availability is per-account. The user likely tested with a DIFFERENT key/account (or NVIDIA Playground) where `moonshotai/kimi-k2.6` is deployed → 200 there. The wrapper's configured account has not deployed it → 404 there → hard-block.
