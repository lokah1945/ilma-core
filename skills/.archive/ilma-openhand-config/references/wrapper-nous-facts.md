# wrapper-nous Facts (verified 2026-07-27)

## Endpoint
- Base URL: `http://127.0.0.1:9102/v1`  (OpenAI-compatible; **verify port — moved 9106→9102**)
- Auth: "open" mode → any bearer accepted; `wrapper-local-key` is documented default.
- Systemd: `wrapper-nous.service` (user), enabled, active.

## Live model list (GET /v1/models)
Returns `{ "object":"list", "data": [ { "slug": "...", "display_name": "...",
"description": "...", "default_reasoning_level":"medium",
"supported_reasoning_levels":[{effort,description}...], "shell_type":"shell_command",
"visibility":"list", "supported_in_api":true, "priority":N }, ... ] }`.

Sample slugs (22 total, 2026-07-27):
```
inclusionai/ling-3.0-flash:free
poolside/laguna-s-2.1:free
poolside/laguna-xs-2.1:free
stepfun/step-3.7-flash:free
tencent/hy3:free          <-- default / proven working
claude-3-5-haiku-20241022
claude-opus-4-8
claude-sonnet-4-6
... (claude-* aliases, haiku/opus/sonnet)
```
- `tencent/hy3:free` confirmed reachable & returns real completions through the
  wrapper (test: `LLM(model='openai/tencent/hy3:free', base_url=..., api_key=...)`).

## OpenHand integration notes
- OpenHand = LiteLLM. Custom endpoint ⇒ `model="openai/<slug>"` + `base_url`.
- `openhands acp --override-with-envs` reads `LLM_MODEL`/`LLM_BASE_URL`/`LLM_API_KEY`.
- No console TUI; `acp` has no `-t` flag.

## Local venv corruption symptom (environmental — use Docker instead)
`python -m openhands.agent_server` fails with missing symbols, e.g.:
```
ImportError: cannot import name 'LLM_SECRET_FIELDS' from 'openhands.sdk.llm.llm'
ImportError: No module named 'openhands.sdk.marketplace.registration'
```
Cause: version skew between the installed `openhands` (uv tool 1.21.0) and its
`sdk` dependency. This is environmental, not a OpenHand bug — run the official
Docker image and mount persisted settings instead of hand-stubbing missing modules.
