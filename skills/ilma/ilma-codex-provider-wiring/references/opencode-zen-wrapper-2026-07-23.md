# OpenCode Zen Wrapper — Condensed Knowledge Bank (2026-07-23)

## Authoritative source
- Docs: https://opencode.ai/docs/zen/#endpoints
- Base URL (CORRECT): `https://opencode.ai/zen/v1`
- WRONG base seen in the wild: `https://integrate.api.OPENCODE.com` (NVIDIA-backed fallback; returns NVIDIA model ids → misleads you into thinking "opencode is nvidia")

## Endpoints (Zen native)
- Responses (OpenAI): `POST {base}/responses`
- Messages (Anthropic): `POST {base}/messages`
- Chat completions: `POST {base}/chat/completions`
- Models: `GET {base}/models`

## Model id format
- Doc says `opencode/<model-id>` (e.g. `opencode/gpt-5.5`). Wrapper strips the `opencode/` prefix before proxying.
- Both `opencode/gpt-5.5` and `gpt-5.5` work if the wrapper strips the prefix.

## Free models (token price = 0) — verified list
- `mimo-v2.5-free`
- `laguna-s-2.1-free`
- `nemotron-3-ultra-free`
- `deepseek-v4-flash-free`
- `north-mini-code-free`
- Also `big-pickle` (free, no `-free` suffix — rare)

Paid examples (must be BLOCKED when `FREE_ONLY=yes`):
- `gpt-5.5`, `gpt-5.4-mini`, `claude-sonnet-4-6`, `gemini-3.6-flash`, `deepseek-v4-flash` (no `-free`), `grok-4.5`, `minimax-m3`, `glm-5.2`, `kimi-k2.7-code`, `qwen3.7-max`

## API keys
- Prefix: `OPENCODE_API_KEY_1`, `OPENCODE_API_KEY_2`, `OPENCODE_API_KEY_3` (NOT `BEARER_TOKEN` for the upstream; `BEARER_TOKEN` is the local wrapper auth)
- 3 keys observed → all subject to Zen free-tier rate limits (429 `FreeUsageLimitError` / `Provider rate limit exceeded`)

## Critical request headers
- `Accept-Encoding: identity` — Zen REJECTS `br`/`gzip` with `400 Can not decode content-encoding: br`. Set this in the wrapper's `_auth_headers()`.
- `Authorization: Bearer <key>`

## Tool-call routing (wrapper-side)
- Zen Responses API supports tool calls for ALL models. Route every model except `claude-*` (→messages) and `gemini-*` (→google) to the `responses` family. Returning `chat` for non-GPT models drops the `function_call` item during Responses→Chat→Responses translation.
- Verify forwarding with direct curl (tools → expect `function_call` in `output`).

## Known upstream instability (2026-07-23)
- All 5 Zen free models returned errors at the Zen side during audit:
  - `FreeUsageLimitError` / `Provider rate limit exceeded` (429)
  - `Internal server error` (Zen-side 500)
  - `Upstream request failed` (invalid_request_error)
- This is UPSTREAM, not wrapper. Wrapper must pass Zen errors through as JSON (status + body), never return a bare 500.

## FREE_ONLY detection (no hardcoded allowlist — Bos mandate)
- `is_free_model(id)` → `id` contains `"free"` (substring).
- Upstream `/v1/models` metadata carries NO price field, so "price = 0" cannot be computed from metadata; the `free` substring is the operative signal.
- `FREE_ONLY=yes` in `.env` → `model_allowed()` blocks any model not free.
- NEVER add `FREE_MODEL_ALLOWLIST` with hardcoded ids (Bos rejected this).
- `wrapper-nvidia-python` needs NO `FREE_ONLY` (NVIDIA NIM upstream is 100% free by default).

## Module-conflict trap (editable pip install)
- `pip install -e` any wrapper writes a `.pth` injecting its root into `sys.path`.
- Symptom: `wrapper-opencode` loads `wrapper-nvidia-python/src/main.py` (both named `src`), logs `[wrapper-nvidia]`, proxies to NVIDIA.
- Fix: remove `/usr/local/lib/python3.11/dist-packages/_editable_impl_wrapper_*.pth`; add `src/__init__.py` to every wrapper; never `pip install -e` wrappers.

## Verification recipe (opencode as Codex provider)
```bash
TOK=$(grep '^BEARER_TOKEN=' /root/wrapper/opencode/.env | cut -d= -f2)
# identity
curl -s http://127.0.0.1:9107/health | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['base'],d['free_only'])"
# free-only models
curl -s -H "Authorization: Bearer $TOK" http://127.0.0.1:9107/v1/models | python3 -c "import sys,json;d=json.load(sys.stdin);print([m['id'] for m in d['data']])"
# tool forward (bypass Codex quota)
curl -s -X POST http://127.0.0.1:9107/v1/responses -H "Authorization: Bearer $TOK" -H "Content-Type: application/json" \
 -d '{"model":"opencode/mimo-v2.5-free","input":"use calculator","tools":[{"type":"function","name":"calculator","description":"add","parameters":{"type":"object","properties":{"a":{"type":"number},{"type":"number}},"required":["a","b"]}}]}' \
 | python3 -c "import sys,json;d=json.load(sys.stdin);print([o.get('type') for o in d.get('output',[])])"
# Codex e2e (may 429 if Zen quota exhausted)
CODEX_HOME=/root/.codex-homes/opencode codex exec --model opencode/mimo-v2.5-free "Use the Bash tool to run exactly: echo OK > /tmp/x.txt" </dev/null
```
