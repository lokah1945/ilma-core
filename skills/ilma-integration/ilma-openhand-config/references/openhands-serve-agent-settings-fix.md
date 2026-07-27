# Fix: `openhands serve` stuck at agent-settings + reach wrapper-nous

Verified recipe from session 2026-07-27 (user installed via
`install.openhands.dev/install.sh`, runs `openhands` / `openhands serve` → :3000).

## Symptom
Web UI at http://localhost:3000 always shows the "agent settings" onboarding
screen and won't proceed. Root causes found:
1. Local venv `openhands` (uv tool, 1.21.0) is version-skewed — `python -m
   openhands.agent_server` dies on missing `LLM_SECRET_FIELDS` /
   `marketplace.registration`. So the server only runs via the Docker image that
   `openhands serve` spawns.
2. The persisted-settings store is empty → UI prompts.
3. Container on default bridge net cannot reach wrapper-nous (127.0.0.1-only).

## Fix A — patch `gui_launcher.py` (makes `openhands serve` work directly)
File: `<venv>/lib/python3.12/site-packages/openhands_cli/gui_launcher.py`
function `launch_gui_server`.

Edit 1 — `-it` → `-d` (TTY error in non-interactive sessions):
```diff
 docker_cmd = [
     "docker",
     "run",
-    "-it",
+    "-d",
     "--rm",
     "--pull=always",
```

Edit 2 — inject persistence dir + host network (before the `-p 3000:3000` block):
```diff
 docker_cmd.extend([
     "-e",
     "OH_PERSISTENCE_DIR=/.openhands",
+    "--network=host",
 ])
```

Edit 3 — drop `-p 3000:3000` (host net already exposes it):
```diff
-docker_cmd.extend([ "-p", "3000:3000", "--add-host", "host.docker.internal:host-gateway", "--name", "openhands-app", app_image ])
+docker_cmd.extend([ "--add-host", "host.docker.internal:host-gateway", "--name", "openhands-app", app_image ])
```

The launcher already mounts `{config_dir}:/.openhands` where config_dir =
`~/.openhands` (via `get_persistence_dir()` → `OPENHANDS_PERSISTENCE_DIR` or
`~/.openhands`). `OH_PERSISTENCE_DIR=/.openhands` makes the in-container
agent-server read the mounted file.

## Fix B — write the correct persisted-settings JSON
`~/.openhands/settings.json` MUST be the **PersistedSettings** shape (NOT the
`version:2, llm:` SDK shape):
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
With `--network=host`, `127.0.0.1:9102` inside the container = host's wrapper-nous.
Do NOT use `host.docker.internal` (bridge gateway 172.17.0.1 isn't listened on →
HTTP 000).

## Verification (what proved it worked)
```bash
# container reaches wrapper-nous:
docker exec openhands-app curl -s -m5 http://127.0.0.1:9102/v1/models \
  -H "Authorization: Bearer wrapper-local-key" -o /dev/null -w "HTTP %{http_code}\n"
# -> HTTP 200

# UI up:
curl -s -m8 http://127.0.0.1:3000/ -o /dev/null -w "HTTP %{http_code}\n"
# -> HTTP 200

# persisted settings mounted inside container:
docker exec openhands-app cat /.openhands/settings.json | head -5
# -> shows hy3 / wrapper-nous
```
Container log should end with: `Uvicorn running on http://0.0.0.0:3000`.

## Notes
- `openhands serve` auto-pulls `docker.openhands.dev/openhands/openhands:latest`
  (`--pull=always`). First run downloads the image.
- If you'd rather not patch the venv, use `templates/openhand-up.sh` (Docker manual
  launcher with the same `--network=host` + mount).
- Validate the JSON shape locally (avoids the broken `agent_server` import chain):
  `.../openhands/bin/python -c "from openhands.sdk.settings.model import
  OpenHandsAgentSettings; import json;
  print(OpenHandsAgentSettings.model_validate(json.load(open('/root/.openhands/settings.json'))['agent_settings']).llm.model)"`
