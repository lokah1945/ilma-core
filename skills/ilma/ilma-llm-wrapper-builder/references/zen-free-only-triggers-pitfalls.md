# Triggers & Pitfalls — OpenCode Zen Free-Only Wrapper

## When this applies (ADD to skill triggers)
- `opencode zen proxy`
- `zen free-only wrapper`
- `audit wrapper routing`
- `free-only llm proxy`
- Bos asks to build/audit a proxy targeting `opencode.ai/zen/v1`

## Pitfalls (ADD to skill pitfalls)
1. **ZEN FREE-MODEL ROUTING BUG** — In FREE_ONLY mode the model→endpoint
   router MUST send free / openai-compatible ids to `{base}/chat/completions`,
   NOT `{base}/responses`. Zen's `/responses` is GPT-only and 400s on free ids
   (`"Upstream request failed"`). Codex v0.145 (primary client) speaks the
   Responses API, so the proxy must translate Responses→Chat→Responses and hit
   `/chat/completions`. Wrong `return 'responses'` default = 100% failure for
   Codex in free-only mode. See `opencode-zen-free-only-audit-2026-07-24.md`
   for wrong-vs-right `_zen_family()` snippet + live verification recipe.
2. **systemd path mismatch** — `WorkingDirectory`/`EnvironmentFile` must equal the
   real dir (`/root/wrapper/opencode`, NOT `/root/wrappers/opencode`) or the
   unit loads the wrong `.env` / module path.
3. **Unverified "100/100" claims** — Never claim a wrapper verified until you
   live-test the actual upstream path the main client uses (Responses for Codex).
   A passing unit test that never hits `/v1/responses` against a free model
   will miss the routing bug above.

## Note on SKILL.md size
The main SKILL.md for `ilma-llm-wrapper-builder` exceeds the 100k-char
patch limit, so trigger/pitfall extensions live here in `references/` rather
than inline in the body. The skill description already lists `opencode zen`
as a trigger; this file is the detailed correction record.
