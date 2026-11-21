---
name: ilma-openhand-provider-wiring
description: Configure OpenHand SDK coding agent (v1.21.0+) to use a custom OpenAI-compatible LLM backend (e.g. wrapper-nous) with live/dynamic model discovery, mirroring the Codex CLI pattern. Covers LiteLLM backend, ACP env injection, settings.json, and the no-TUI gotcha.
---

# OpenHand Provider Wiring (custom backend + dynamic model)

## When to use
- User installed `openhands` and wants it pointed at a local/custom LLM proxy (wrapper-nous, LiteLLM, etc.)
- User wants "dynamic model like Codex CLI" → live fetch from `GET /v1/models`, no static catalog, `-m <slug>` override at runtime
- Migrating a Codex-CLI workflow to OpenHand

## Key architecture facts (OpenHand SDK v1.21.0)
- Installed via uv at `/root/.local/share/uv/tools/openhands/`; binary symlink `/root/.local/bin/openhands` → venv bin.
- **NO TUI mode** in this package. Subcommands: `acp`, `serve`, `web`, `mcp`, `cloud`, `login`, `logout`, `view`. Codex has an interactive TUI; OpenHand does NOT — it is a server/agent (IDE via ACP, browser via `web`).
- Backend = **LiteLLM**. Custom OpenAI-compatible endpoint uses `LLM(model="openai/<slug>", base_url="http://host/v1", api_key="...")`. LiteLLM forwards to `base_url` and treats `openai/` prefix as "custom OpenAI passthrough".
- `openhands acp --override-with-envs` reads env `LLM_MODEL` / `LLM_BASE_URL` / `LLM_API_KEY`. This is the PROVEN env-injection path.
- `openhands web` (browser UI) reads `~/.openhands/settings.json` → `llm` section.
- `LLM` is a pydantic model; it does NOT auto-read env vars (only `acp --override-with-envs` injects them).
- `acp` subcommand does NOT accept `-t <task>` (unlike Codex CLI). Do not forward `-t` to `acp`.
- Response object is OpenHands `LLMResponse`, NOT OpenAI-style. Access: `resp.message.content[0].text` (TextContent list), never `resp.choices[0].message.content`.

## Steps
1. Create `~/.openhands/settings.json` with an `llm` block (see templates/settings.json).
2. Create a launcher `openhand` (see references/openhand-launcher.py) that:
   - fetches the live model list from backend `GET /v1/models` (dynamic, NO static catalog — this is the Codex-like behavior)
   - `-m <slug>` overrides the model; default = a known-good slug present in the live list
   - writes the chosen model into settings.json (so `web` mode picks it up)
   - invokes `openhands acp --override-with-envs` with `LLM_*` env exported
3. Symlink `openhand-acp` / `openhand-web` → `openhand` for convenience.
4. Verify by instantiating `LLM(...)` in the uv venv python and calling `.completion()` — confirm a real response string returns.

## Pitfalls
- **argparse REMAINDER breaks flag forwarding.** If you parse `-m` with argparse and forward the rest via `nargs=REMAINDER`, downstream flags like `-t "task"` get rejected as "unrecognized arguments". Use manual `sys.argv` slicing instead (consume only `-m/--model/--list-models/--tui`, forward everything else raw). See references/openhand-launcher.py.
- **Don't assume TUI.** `openhands -t task` does not exist; use `acp` (IDE) or `web` (browser). The launcher defaults to `acp`.
- **Response shape.** Use `resp.message.content[0].text`, never `.choices`.
- **execute_code is blocked** by cron-safety in this environment — use `terminal` for curl / python-subprocess probes.
- **Port drift.** wrapper-nous currently runs on **9102** (old 9106 is VOID per SOUL.md). Always verify with `curl http://127.0.0.1:9102/v1/models` before assuming the endpoint.
- **Benign cost warning.** LiteLLM prints `Cost calculation failed: This model isn't mapped yet` for free slugs — this is NOT a connection failure; the call still succeeds.
- **TWO different settings files — do not confuse them:**
  - `~/.openhands/settings.json` = **PersistedSettings** shape (`{schema_version, agent_settings:{agent_kind,agent,llm}}`). Read by `web` / `serve` (Docker, via `OH_PERSISTENCE_DIR`).
  - `~/.openhands/agent_settings.json` = **`Agent` object** shape (`{llm:{model,api_key,base_url,...}, tools, condenser,...}`). Read by the **bare `openhands` CLI/TUI** (`AgentStore.load_or_create` → `load_from_disk` → `Agent.model_validate_json`). If this file is missing/valid, the TUI force-shows the "agent settings" onboarding screen (`is_initial_setup_required=True`).
- **🔴 CRITICAL — SecretStr masks api_key to `"**********"`.** Generating `agent_settings.json` via `Agent.model_dump_json()` serializes the `LLM.api_key` (a pydantic `SecretStr`) as the literal masked string `"**********"`. On reload, OpenHand parses that as invalid → `llm.api_key = None`. LiteLLM then rejects `openai/<slug>` with `LLMServiceUnavailableError: OpenAIException - Missing credentials. Please pass an api_key... or set OPENAI_API_KEY`. Symptom: even a trivial prompt like "hallo" fails with a conversation error. **Fix:** after writing the file, replace `"**********"` with the real key (`wrapper-local-key`) — either `patch` the JSON directly or set env `OPENAI_API_KEY=wrapper-local-key` when launching `openhands`. Verify with: `Agent.model_validate_json(open(...).read()).llm.api_key is not None`.
- **Verify the EXACT failure path before claiming fixed.** Reproduce with `LLM(model=..., base_url=..., api_key=None)` → must raise the same `Missing credentials` error; then `api_key='wrapper-local-key'` → must return a real response. Only then is the TUI fix confirmed.

## Verification recipe
```bash
OH_PY=/root/.local/share/uv/tools/openhands/bin/python
$OH_PY -c "
import os; os.environ['OPENHANDS_SUPPRESS_BANNER']='1'
from openhands.sdk.llm.llm import LLM
from openhands.sdk.llm.message import Message
llm = LLM(model='openai/tencent/hy3:free', base_url='http://127.0.0.1:9102/v1', api_key='wrapper-local-key')
resp = llm.completion(messages=[Message(role='user', content='hi')])
print(resp.message.content[0].text)
"
```

## References
- references/openhand-launcher.py — full working launcher deployed at /root/.local/bin/openhand
- references/openhand-architecture.md — deeper LiteLLM prefix rewrite + ACP env injection notes
- templates/settings.json — known-good settings.json for wrapper-nous

## Sibling skills
- `ilma-codex-provider-wiring` — same goal but for the Codex CLI (which DOES have a TUI and fetches /v1/models natively).
- `ilma-wrapper-nous-integration` — broader wrapper-nous wiring; this skill is the OpenHand-specific slice.
