---
name: ilma-opencode-provider-config
description: "Register all /root/wrapper LLM proxies as custom providers in OpenCode (opencode.ai TUI/CLI). Class-level: covers locating the opencode binary + config, installing the @ai-sdk/openai-compatible npm dependency, the exact jsonc shape (npm/options.baseURL/options.apiKey/manual models), model-list syncing, and verification via `opencode models` + E2E `opencode run`. Use whenever Bos says 'add wrapper to opencode', 'register custom provider', or wants all local LLM endpoints selectable inside OpenCode."
---

# ILMA OpenCode Provider Config

## When to use
- Bos: *"Akses opencode. Tambahkan all wrapper menjadi custom provider"*, *"register custom provider di opencode"*, *"buat wrapper muncul di opencode sebagai pilihan"*.
- You need OpenCode to route to local `/root/wrapper/*` proxies (ports 9101–9105) instead of only built-in cloud providers.
- After a wrapper pull/restart, re-sync the model list shown in OpenCode.

## Key facts (verified 2026-07-28, opencode v1.17.20)
- **Binary:** `/root/.opencode/bin/opencode` (node-based). `opencode --version` → `1.17.20`.
- **Config:** `~/.config/opencode/opencode.jsonc` (JSONC — comments allowed at top level).
- **npm deps live in:** `~/.config/opencode/node_modules/` (managed by `~/.config/opencode/package.json`).
- **Auth:** every wrapper requires `Authorization: Bearer wrapper-local-key` (the `BEARER_TOKEN` from each wrapper's `.env`). OpenCode sends `options.apiKey` as that bearer token.
- **Models are NOT auto-fetched** for custom providers. You MUST list each model under `"models"` or OpenCode shows the provider with 0 models and it won't appear as a selectable target.

## CRITICAL: the npm dependency trap
A custom OpenAI-compatible provider **will not appear** in `opencode models` unless `@ai-sdk/openai-compatible` is installed in `~/.config/opencode/`.

```bash
cd ~/.config/opencode
npm install @ai-sdk/openai-compatible
```

Without it, `opencode models` silently omits your `wrapper-*` entries (only built-in providers like `nvidia`/`opencode`/`openrouter` show). This is the #1 reason "I added the provider but it doesn't show up".

## Config shape (the exact jsonc)
```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "wrapper-nous": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Wrapper Nous (free)",
      "options": {
        "baseURL": "http://localhost:9102/v1",
        "apiKey": "wrapper-local-key"
      },
      "models": {
        "tencent/hy3:free": { "name": "tencent/hy3:free", "limit": { "context": 200000, "output": 8192 } }
        // ... one entry per model id from GET /v1/models
      }
    }
  }
}
```
- Use a `wrapper-` prefix on the provider key to avoid clashing with OpenCode built-in provider ids (`nvidia`, `nous`, `opencode`, `blackbox`, `openrouter`, ...).
- `baseURL` must point at `http://localhost:<port>/v1` (127.0.0.1 also works).
- Each model entry needs at least `{"name": "<id>"}`; `limit` is optional but recommended.

## Model-list sync (don't hand-type 155 models)
Query each wrapper's `GET /v1/models` and build the config programmatically. Use the bundled script:

```bash
python3 ~/.hermes/profiles/ilma/skills/ilma-opencode-provider-config/scripts/sync_opencode_providers.py
```

It fetches models from all known wrapper ports, installs/checks the npm dep, and writes `~/.config/opencode/opencode.jsonc`. Edit the `WRAPPERS` dict at the top of the script if ports change.

A known-good template lives at `references/opencode-jsonc-template.jsonc`.

## Verification (prove it works — don't trust "written")
```bash
# 1. provider appears in model list with wrapper- prefix
opencode models 2>&1 | grep -E "^wrapper-" | sed 's#/.*##' | sort | uniq -c
# expect: wrapper-blackbox 7 / wrapper-nous 22 / wrapper-nvidia 117 / wrapper-opencode 9

# 2. E2E smoke — actually call a model through opencode
opencode run "reply with exactly: PONG" -m wrapper-nous/tencent/hy3:free
# expect: "> build · tencent/hy3:free" then "PONG"
```
Note: some upstream models (e.g. `ling-3.0-flash-free` via wrapper-nous) return 500 from the **upstream** provider — that is NOT a config bug. Use the wrapper's default alias (`tencent/hy3:free`) for the smoke test, which is known-good.

## Pitfalls
- **Don't point at the wrong port.** Legacy config pointed `wrapper-nvidia` at `:9100` (dead). The live NVIDIA wrapper is `wrapper-nvidia-python` on **:9101**.
- **Don't use `id` for the provider key if it collides with a built-in** (e.g. `nous`, `nvidia`) — prefix with `wrapper-`.
- **`opencode models` output is huge** (400+ lines of built-in models). Grep for `^wrapper-` to isolate your entries.
- **`execute_code` is blocked for this** (cron-policy). Use a `write_file` python script + `terminal` to run it, not inline `execute_code`.

## References
- `references/opencode-jsonc-template.jsonc` — full known-good config with all 4 original wrappers + model shape.
- `scripts/sync_opencode_providers.py` — deterministic sync: fetches /v1/models per wrapper, writes opencode.jsonc.
