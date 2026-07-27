---
name: ilma-openhand-config
description: Configure OpenHand (openhands SDK agent CLI) to use a local LLM wrapper backend (wrapper-nous) with live/dynamic model discovery, and fix the "stuck at agent settings" onboarding screen. Covers backend wiring, dynamic-model launcher, persisted-settings JSON, and the reliable Docker run path. Trigger when user installs/uses OpenHand, wants it pointed at a custom OpenAI-compatible endpoint, complains about agent-settings prompt, or wants Codex-like dynamic model selection.
category: ilma-integration
---

# ILMA OpenHand ↔ Wrapper Backend Config

Wire **OpenHand** (`openhands` SDK CLI) to a local OpenAI-compatible LLM wrapper
(typically **wrapper-nous**) so it behaves like Codex CLI: live model discovery,
no static catalog, and a stable default model. Also eliminates the "stuck at agent
settings" onboarding screen.

## When to use
- User just installed `openhands` and wants it to use `wrapper-nous` (or any local
  OpenAI-compatible proxy) as the backend.
- User wants "dynamic model like Codex CLI" — i.e. pick model at runtime, fetch the
  live model list instead of a frozen catalog.
- User is stuck on the OpenHand web UI "agent settings" screen and can't proceed.
- User asks to set a specific default model (e.g. `tencent/hy3:free`) via the wrapper.

## Architecture facts (verified)
- OpenHand SDK uses **LiteLLM** under the hood. An `LLM` is built from
  `model`, `base_url`, `api_key`.
- For a **custom OpenAI-compatible endpoint**, prefix the model with `openai/`:
  `model = "openai/<slug>"` + `base_url = "http://host:port/v1"`. LiteLLM forwards
  to that base_url.
- `openhands acp --override-with-envs` reads `LLM_MODEL`, `LLM_BASE_URL`,
  `LLM_API_KEY` from the environment (proven injection path).
- OpenHand has **NO TUI console**. Subcommands are: `acp`, `serve`, `web`, `mcp`,
  `cloud`, `login`, `logout`, `view`. There is no `openhands -t "<task>"` one-shot
  TUI like Codex — `acp` does NOT accept `-t`.
- "Stuck at agent settings" = the persisted-settings store is empty, so the web UI
  always prompts. Fix = pre-populate the persisted settings JSON (see below).

## Backend endpoint (verify, don't assume)
wrapper-nous is an OpenAI-compatible proxy. **Verify the live port before wiring**
(memory of old ports goes stale — e.g. it moved 9106 → 9102):
```bash
curl -s -m 5 http://127.0.0.1:9102/v1/models -H "Authorization: Bearer wrapper-local-key" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print([m['slug'] for m in d['data']])"
```
- Base URL: `http://127.0.0.1:9102/v1` (verify — port may differ).
- Auth: wrapper runs in "open" mode → any bearer token accepted; `wrapper-local-key`
  is the documented default.
- `GET /v1/models` returns `{ "data": [ { "slug": "tencent/hy3:free", ... }, ... ] }`.
  The `slug` is what you pass as the model name.

## Step 1 — SDK / ACP LLM config (NOT the web/serve persisted store)
> ⚠️ **Format warning.** The block below is for the **SDK `LLM` constructor** and
> `openhands acp --override-with-envs`. It is **NOT** what the `serve`/`web` UI
> persisted store reads. For `openhands serve` / `openhands web` the file at
> `~/.openhands/settings.json` MUST be the **`PersistedSettings`** format from
> Step 3 (schema_version + agent_settings.llm), or the UI stays stuck on the
> agent-settings onboarding screen. Do not write the `version:2, llm:` shape to
> `~/.openhands/settings.json` if you launch via `serve`/`web`.

```json
{
  "version": 2,
  "llm": {
    "model": "openai/tencent/hy3:free",
    "base_url": "http://127.0.0.1:9102/v1",
    "api_key": "wrapper-local-key",
    "reasoning_effort": "xhigh",
    "num_retries": 3
  },
  "agent": "CodeActAgent",
  "max_iterations": 100,
  "security_analyzer": "none"
}
```

## Step 2 — Dynamic-model launcher (`openhand`)
A launcher that mirrors Codex's dynamic discovery: fetch `/v1/models` live (no static
catalog), default to a priority model, allow `-m <slug>` override, and forward to
`openhands acp --override-with-envs`. See `templates/openhand-launcher.sh`.

Usage:
```bash
openhand --list-models                 # enumerate live models from wrapper-nous
openhand -m poolside/laguna-s-2.1:free -t "task"   # pick model at runtime
openhand -t "task"                     # default model (tencent/hy3:free)
openhand --tui                         # force env injection (non-ACP)
```

## Step 3 — Fix "stuck at agent settings" (persisted settings)
The web UI reads a `PersistedSettings` JSON from the settings store. Write it BEFORE
launching the server so onboarding is skipped. Path resolution:
- Env `OH_PERSISTENCE_DIR` if set, else default `workspace/.openhands` (relative to
  cwd when the server starts).
- File name: `settings.json`.

Validated format (verified against OpenHand's Pydantic `OpenHandsAgentSettings`):
```json
{
  "schema_version": 2,
  "agent_settings": {
    "agent_kind": "openhands",
    "agent": "CodeActAgent",
    "llm": {
      "model": "openai/tencent/hy3:free",
      "base_url": "http://127.0.0.1:9102/v1",
      "api_key": "wrapper-local-key",
      "reasoning_effort": "xhigh",
      "num_retries": 3
    },
    "max_iterations": 100,
    "security_analyzer": "none"
  },
  "conversation_settings": { "max_iterations": 100, "confirmation_mode": "none" },
  "active_profile": "wrapper-nous-hy3",
  "misc_settings": {}
}
```
Validate locally (without the broken `agent_server` import chain) via:
```bash
/root/.local/share/uv/tools/openhands/bin/python -c "
from openhands.sdk.settings.model import OpenHandsAgentSettings
import json
cfg=json.load(open('/root/.openhands/server/settings.json'))['agent_settings']
print(OpenHandsAgentSettings.model_validate(cfg).llm.model)
"
```

## Step 4 — Reliable run path (Docker)
The locally-installed `openhands` venv is prone to **version skew** (e.g.
`agent_server` importing `LLM_SECRET_FIELDS` / `marketplace.registration` that are
absent from the installed `sdk`). When the server won't boot locally, run the
official Docker image and mount the persisted settings + set `OH_PERSISTENCE_DIR`.

**CRITICAL — container → wrapper-nous reachability:**
- wrapper-nous listens ONLY on `127.0.0.1:9102` (not `0.0.0.0`). A container on the
  default bridge network CANNOT reach it via `host.docker.internal` (that resolves to
  the bridge gateway `172.17.0.1`, which wrapper-nous does not listen on → `HTTP 000`).
- **Fix:** launch the OpenHand container with `--network=host`. Then `127.0.0.1:9102`
  inside the container IS the host's wrapper-nous. Set the persisted-settings
  `base_url` to `http://127.0.0.1:9102/v1` (NOT `host.docker.internal`).
- With `--network=host`, drop `-p 3000:3000` (host mode already exposes 3000).

See `templates/openhand-up.sh` (already uses `--network=host`).
```bash
openhand-up   # -> http://localhost:3000, already configured, no agent-settings prompt
```

## Step 5 — Patch `gui_launcher.py` so `openhands serve` works directly
If the user runs **`openhands serve`** (the command they actually use for :3000),
patch the venv's `gui_launcher.py` (`<venv>/site-packages/openhands_cli/gui_launcher.py`,
`launch_gui_server`) so the spawned container is pre-wired — no manual `openhand-up`
needed. Three edits:

1. **`-it` → `-d`** (detached). The script's `-it` fails with
   *"the input device is not a TTY"* when launched from a non-interactive/background
   session (e.g. via Hermes). `-d` lets it run headless.
2. **Inject `OH_PERSISTENCE_DIR=/.openhands`** into the docker run. The launcher
   already mounts `{config_dir}:/.openhands` (config_dir defaults to `~/.openhands`
   via `get_persistence_dir()` → `OPENHANDS_PERSISTENCE_DIR` or `~/.openhands`).
   Setting `OH_PERSISTENCE_DIR=/.openhands` makes the in-container agent-server read
   the mounted `/.openhands/settings.json` → **skips the agent-settings prompt**.
3. **Add `--network=host`** (and remove `-p 3000:3000`) so the container reaches
   wrapper-nous on `127.0.0.1:9102`.

Diff shape (apply via `patch` tool, fuzz-tolerant):
```diff
 docker_cmd = [
     "docker",
     "run",
-    "-it",
+    "-d",
     "--rm",
     "--pull=always",
```
```diff
 docker_cmd.extend([
     "-e",
     "OH_PERSISTENCE_DIR=/.openhands",
+    "--network=host",
 ])
-docker_cmd.extend([ "-p", "3000:3000", "--add-host", "host.docker.internal:host-gateway", "--name", "openhands-app", app_image ])
+docker_cmd.extend([ "--add-host", "host.docker.internal:host-gateway", "--name", "openhands-app", app_image ])
```
After patching, `~/.openhands/settings.json` MUST hold the **PersistedSettings**
format (Step 3) with `base_url: http://127.0.0.1:9102/v1`. Then:
```bash
openhands serve   # -> http://localhost:3000, hy3 preloaded, no onboarding screen
```

## Pitfalls
- **Don't assume the wrapper port.** Always `curl /v1/models` first. Old memory
  (9106) is VOID; current is 9102 (verify).
- **Don't use `openhands acp -t`** — `acp` has no `-t`. For one-shot tasks use the
  launcher's env injection or the web UI.
- **TUI mode doesn't auto-read `LLM_MODEL` env.** Either write `settings.json` (web/
  serve) or use `acp --override-with-envs` (proven). The launcher handles both.
- **Local venv corruption is environmental, not a OpenHand bug.** If
  `python -m openhands.agent_server` dies on a missing symbol, switch to the Docker
  image — do not hand-stub every missing module (fragile).
- **`model` must be `openai/<slug>`**, not bare `<slug>`, or LiteLLM routes to a
  hosted provider instead of your wrapper.
- **Two different `settings.json` shapes — don't mix them up.** The `version:2,
  llm:` shape is for the SDK `LLM` constructor / `acp --override-with-envs` ONLY.
  The `serve`/`web` UI reads the **`PersistedSettings`** shape (`schema_version` +
  `agent_settings.llm`) from `~/.openhands/settings.json`. Writing the SDK shape to
  the UI path leaves the agent-settings screen stuck.
- **`host.docker.internal` does NOT reach a `127.0.0.1`-only wrapper.** wrapper-nous
  binds `127.0.0.1:9102` only; the bridge gateway `172.17.0.1` is not listened on →
  `HTTP 000` from the container. Use `--network=host` and `base_url:
  http://127.0.0.1:9102/v1` instead.
- **`openhands serve` uses `-it` which fails without a TTY.** From a non-interactive
  session (Hermes/background) it errors *"the input device is not a TTY"*. Patch the
  launcher to `-d` (Step 5) or use `openhand-up`.

## References
- `references/wrapper-nous-facts.md` — verified endpoint facts, sample model list,
  and the local-venv corruption symptom/signature.
- `references/openhands-serve-agent-settings-fix.md` — exact `gui_launcher.py` patch
  (3 edits) + verified Docker reachability recipe so `openhands serve` skips the
  agent-settings prompt and reaches wrapper-nous.
- `templates/openhand-launcher.sh` — drop-in `openhand` launcher (dynamic model).
- `templates/persisted-settings.json` — known-good persisted settings (skip onboarding).
- `templates/openhand-up.sh` — Docker launcher with mounted settings.
