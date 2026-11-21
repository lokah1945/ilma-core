# Reference: Nous portal → Codex wiring (verified 2026-07-22)

## Provider facts (curl-probed, not assumed)
- Base: `https://inference-api.nousresearch.com/v1`
- `GET /v1/models` → 200
- `POST /v1/chat/completions` → 200 (OpenAI chat protocol; needs auth)
- `POST /v1/responses` → **404** (Responses API NOT implemented)
- Auth: OAuth `access_token` in `/root/.hermes/profiles/ilma/auth.json`
  `providers.nous.access_token` (scope `inference:invoke`), expires ~1h.
  `agent_key` also present as fallback.

## Model used by active ILMA session
- `tencent/hy3:free` — a **reasoning model**: final answer lands in
  `content`, intermediate thought in `reasoning`. With a small `max_tokens`
  the `content` arrives `null` and only `reasoning` is populated. Proxy must
  fall back to `reasoning`.

## Codex CLI facts
- Version: `codex-cli 0.144.5` (npm global).
- `wire_api = "chat"` → rejected ("no longer supported"). Must be `"responses"`.
- Runs only inside a **trusted dir** (listed under `[projects]` or a git repo),
  else "Not inside a trusted directory and --skip-git-repo-check was not specified."
- `model_catalog.json` entries need the full schema (e.g.
  `supports_reasoning_summaries`, `support_verbosity`, `apply_patch_tool_type`).
  Hand-built minimal entries fail schema validation — clone an existing entry.

## Live test transcript (final, passing)
```
$ cd /root/wrapper && codex exec --model tencent/hy3:free "What is 2+2? Reply with just the number."
OpenAI Codex v0.144.5
model: tencent/hy3:free
provider: nous
...
user
What is 2+2? Reply with just the number.
codex
4
```

## SSE event order Codex requires (proxy must emit exactly this)
1. response.created
2. response.in_progress
3. response.output_item.added
4. response.content_part.added
5. response.output_text.delta
6. response.output_text.done
7. response.content_part.done
8. response.output_item.done
9. response.completed

Missing `output_item.added` / `content_part.added` before `delta` →
`ERROR codex_core::util: OutputTextDelta without active item`.

## Components (verified working)
- Proxy: `/root/.codex/nous_proxy.py` (port 9191, stdlib only)
- Setup: `/root/.codex/setup_nous_codex.py`
- systemd: `/root/.config/systemd/user/nous-proxy.service`
  (`systemctl --user enable --now nous-proxy.service` → active, auto-restart)
- Backups: `/root/.codex/config.toml.bak.20260722-211500`,
  `/root/.codex/model_catalog.json.bak.20260722-211500`
