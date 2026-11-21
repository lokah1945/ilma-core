---
name: ilma-opencode-provider-wiring
description: Register all /root/wrapper LLM proxies (nvidia/nous/opencode/blackbox) as custom OpenAI-compatible providers in OpenCode so they appear in the model picker. Use when Bos says "add wrapper to opencode", "register all wrappers as opencode providers", or wants local wrapper models selectable inside the OpenCode TUI/CLI.
---

# ILMA OpenCode ↔ /root/wrapper Provider Wiring

Wire the local `/root/wrapper` LLM proxies into OpenCode as selectable custom providers.
This makes every wrapper model appear in OpenCode's provider/model picker (`Leader+m`, `/provider`, or `opencode models`).

## When to use
- Bos: "Akses opencode. Tambahkan all wrapper menjadi custom provider."
- Any request to make wrapper models usable from OpenCode.
- Re-syncing the model list after wrappers add/remove models.

## Prerequisites (verify, don't assume)
- OpenCode binary present: `/root/.opencode/bin/opencode` (check `opencode --version`).
- Wrappers running and listening (see `references/wrapper-endpoints.md`):
  - nvidia :9101, nous :9102, opencode :9103, blackbox :9104
  - Client auth: `Authorization: Bearer wrapper-local-key`
- Config file: `~/.config/opencode/opencode.jsonc`

## Steps
1. **Back up existing config** before editing:
   `cp ~/.config/opencode/opencode.jsonc ~/.config/opencode/opencode.jsonc.bak.$(date +%Y%m%d_%H%M%S)`
2. **Install the OpenAI-compatible adapter** in OpenCode's config dir (this is the #1 silent failure):
   `cd ~/.config/opencode && npm install @ai-sdk/openai-compatible`
   (OpenCode bundles a plugin but does NOT ship this adapter by default — without it, custom providers never appear.)
3. **Scrape live model lists** from each wrapper's `/v1/models` (with `Bearer wrapper-local-key`).
4. **Generate the config** with one entry per wrapper. Each entry MUST contain:
   - `"npm": "@ai-sdk/openai-compatible"`  ← REQUIRED, otherwise provider is silently dropped
   - `"name"`: human label
   - `"options": { "baseURL": "http://localhost:<port>/v1", "apiKey": "wrapper-local-key" }`
   - `"models": { "<model-id>": { "name": "<model-id>", "limit": {"context": N, "output": M} } }`
   Use `scripts/build_oc_config.py` to generate this deterministically.
5. **Write** the result to `~/.config/opencode/opencode.jsonc` (jsonc: top-level `//` comments allowed, but keep JSON valid inside).

## Verification (do this before reporting done)
1. List providers/models: `opencode models 2>&1 | grep -E "^wrapper-"`
   Expect 4 distinct prefixes: `wrapper-nvidia` (117), `wrapper-nous` (22), `wrapper-opencode` (9), `wrapper-blackbox` (7).
2. **E2E smoke test** (proves routing + auth actually work, not just listing):
   `opencode run "reply with exactly: PONG" -m wrapper-nous/tencent/hy3:free`
   Expect output containing `PONG`. (Use the default alias model `tencent/hy3:free` — it is the most reliable upstream.)

## Pitfalls (durable — these bite every time)
- **Missing `"npm": "@ai-sdk/openai-compatible"`** → provider does NOT appear in `opencode models` and no error is shown. This was the actual root cause the first time. Always include it.
- **`@ai-sdk/openai-compatible` not installed** → same silent absence. Install it in `~/.config/opencode`.
- **Custom providers do NOT auto-fetch models** from `/v1/models`. You must register every model id manually in the `models` block. `opencode models` will show 0 models for a wrapper if the block is empty.
- **Wrong port**: an older config pointed `wrapper-nvidia` at `:9100` (dead). The real port is `:9101`. Always verify with `ss -ltnp | grep 127.0.0.1:9`.
- **Upstream model 500s are NOT config bugs.** Some specific upstream models (e.g. nous `ling-3.0-flash-free`) return `Internal Server Error` at the wrapper level (`ClientPayloadError: 400` from upstream). Confirm the config is fine by testing the default alias model via direct curl:
  `curl -s -X POST http://127.0.0.1:9102/v1/chat/completions -H "Authorization: Bearer wrapper-local-key" -H "Content-Type: application/json" -d '{"model":"tencent/hy3:free","messages":[{"role":"user","content":"reply exactly: PONG"}],"max_tokens":10}'`
  If the default alias works, the OpenCode wiring is correct.
- **Do NOT add `model-registry` (:9200)** — it is a control-plane, not an LLM provider.

## Support files
- `references/wrapper-endpoints.md` — port map, auth, health endpoints, gotchas.
- `scripts/build_oc_config.py` — scrapes `/v1/models` from all wrappers and regenerates `opencode.jsonc`. Re-run after any model list change.

## Re-sync automation (optional)
If Bos wants the model list always fresh, run `scripts/build_oc_config.py` on a cron (e.g. every 12h). It is idempotent and overwrites the provider block only.
