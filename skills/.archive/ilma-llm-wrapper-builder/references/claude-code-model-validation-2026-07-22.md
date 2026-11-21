# Claude Code / Codex Client-Side Model Validation — Audit Findings (2026-07-22)

## Symptom

Pointing Claude Code (v2.1.202) at a working local proxy (e.g. `wrapper-nous` on
`:9106`) with `ANTHROPIC_MODEL=tencent/hy3:free` produces:

```
● There's an issue with the selected model (tencent/hy3:free). It may not exist
  or you may not have access to it. Run /model to pick a different model.
```

The SAME error appears in Codex when using the OpenAI Responses API path.

## What is NOT the cause (ruled out by evidence)

| Hypothesis | How disproven |
|------------|---------------|
| Proxy is broken / returns bad format | `curl -X POST .../v1/messages` to the proxy returns valid Anthropic-shaped JSON (`type:message`, `role:assistant`, `content:[{type:text}]`, `stop_reason`, `usage`). Works. |
| `/v1/models` missing the model | `curl .../v1/models` returns 292 models including `tencent/hy3:free`. |
| Wrong config pattern | Config matched `wrapper-nvidia`/`ori`/`settings.json.wrapper` exactly (provider/model + `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` + same-port discovery URL). Still failed. |
| Wrong alias used | Tried `sonnet`, `opus`, `claude-sonnet-4-6`, `claude-opus-4-8`, `claude-3-5-sonnet`, `claude-3-7-sonnet` — ALL failed identically. |
| Auth token rejected | `.claude.json` had `wrapper-local-key`/`bearer-token-clone` in `customApiKeyResponses.rejected`, but using a FRESH token (`nous-local-key`, not in rejected list) ALSO failed. |
| OpenRouter works so proxy should | OpenRouter `ANTHROPIC_BASE_URL=https://openrouter.ai/api` FAILED too when tested live (401 on redacted key). "It works" was based on a stale assumption, not a live test. |

## Root cause (proven)

**Claude Code 2.1.202 validates the model CLIENT-SIDE, before any network call.**
The proxy receives ZERO requests when the error fires (verified by clearing the
proxy access log, running `claude -p`, and confirming 0 new log lines).

Internals from `strings` on `/root/.local/bin/claude`:
- Allowlist `sDd` contains ONLY Anthropic model IDs:
  `claude-3-opus`, `claude-3-sonnet`, `claude-3-haiku`, `claude-3-5-sonnet`,
  `claude-3-5-haiku`, `claude-3-7-sonnet`, `claude-opus-4-0`, `claude-opus-4-1`,
  `claude-opus-4-5`, `claude-opus-4-6`, `claude-sonnet-4-0`, `claude-sonnet-4-5`,
  `claude-sonnet-4-6`, `claude-haiku-4-5`.
- `hbs(e)` checks regex `^(<region>\.)?(anthropic\.|claude-)` — a model MUST
  match `claude-*` or `anthropic.` to even be considered.
- Retired-model check: even valid `claude-*` IDs (e.g. `claude-sonnet-4-20250514`)
  are rejected if the client cannot fetch the current Anthropic model list
  (requires OAuth Anthropic login). Error text differs ("was retired on ...")
  but the failure is still client-side.

**Conclusion:** A model that is not an Anthropic `claude-*` ID (or is Anthropic but
the client has no OAuth session to validate it) is rejected by Claude Code
regardless of how correct the upstream proxy is.

## The empirical proof technique (reusable)

```bash
# 1. Clear proxy access log
: > /tmp/proxy_manual.log

# 2. Run claude -p — if error is client-side, proxy log stays at 0 lines
timeout 70 claude -p "say hi" --settings /path/to/settings.json 2>&1 | head
wc -l /tmp/proxy_manual.log     # 0 = rejected before request left the client

# 3. Confirm proxy itself works (control test)
curl -s -X POST http://127.0.0.1:PORT/v1/messages \
  -H "Content-Type: application/json" -H "x-api-key: wrapper-local-key" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"tencent/hy3:free","max_tokens":20,"messages":[{"role":"user","content":"hi"}]}'
# -> valid JSON message object proves proxy is fine
```

If `wc -l` is 0 → the bug is in the CLIENT, not the proxy. Stop editing the proxy.

## Config patterns that matter (for a working client)

For Claude Code to accept a model, TWO things must hold:
1. `ANTHROPIC_MODEL` (and the `*_DEFAULT_*_MODEL` vars) must be an ID the client
   recognizes — i.e. an Anthropic `claude-*` ID, OR a model the client can
   validate via its gateway discovery fetch.
2. The client must have a valid session/credential to perform that validation
   (OAuth Anthropic login, or a gateway base_url it trusts).

The `wrapper-nvidia` / `ori` / `settings.json.wrapper` configs in
`/root/.claude/` use `moonshotai/kimi-k2.6`, `deepseek-ai/deepseek-v4-pro`,
`meta/llama-3.1-8b-instruct` — these are NOT `claude-*` IDs, so they only work
on OLDER Claude Code versions that lacked client-side validation, OR when the
client has an active Anthropic OAuth session that enables gateway discovery.

## What actually fixes it (decision needed from owner)

- **Option A — Login Anthropic:** `claude login` (OAuth). Then a real
  `claude-sonnet-4-6` is accepted; proxy translates `claude-sonnet-4-6` →
  `tencent/hy3:free` via `MODEL_ALIASES`. Free tier exists.
- **Option B — Use OpenRouter as base_url** with an Anthropic model ID
  (`anthropic/claude-*`), not `tencent/hy3:free`. OpenRouter is a trusted
  gateway the client will validate against.
- **Option C — Downgrade Claude Code** to a version without client-side
  validation (security risk; not recommended).

You CANNOT make `tencent/hy3:free` (or any non-`claude-*` model) pass Claude
Code 2.1.202 model validation without one of the above. The proxy is correct;
the client is the gatekeeper.

## Pitfall for future sessions

When Bos says "error di wrapper-X" and the error is a client model-validation
message, DO NOT immediately start patching the proxy. First run the proxy-log
proof (above). If proxy hits = 0, the failure is client-side and the fix is in
client config / login / model-ID choice — not proxy code. This session burned
~15 proxy edits (alias maps, `/v1/models` injection, discovery toggles) before
this was established.
