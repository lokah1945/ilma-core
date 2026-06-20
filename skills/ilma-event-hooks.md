---
name: ilma-event-hooks
description: Hermes three-tier event hooks system — Gateway hooks (HOOK.yaml + handler.py), Plugin hooks (ctx.register_hook), Shell hooks (config.yaml). React to agent lifecycle events. SSS Tier.
version: 1.0.0
category: workflow
platforms:
  - linux
  - macos
metadata:
  hermes:
    tags: [hooks, events, lifecycle, gateway, plugin, shell]
    category: workflow
---

# ILMA Event Hooks System — Three-Tier Architecture

## Overview

Hermes has THREE hook systems that run custom code at key lifecycle points:

| System | Registered via | Runs in | Primary Use Case |
|---------|---------------|---------|-----------------|
| **Gateway hooks** | `HOOK.yaml` + `handler.py` in `~/.hermes/hooks/` | Gateway only | Logging, alerts, webhooks |
| **Plugin hooks** | `ctx.register_hook()` in a plugin | CLI + Gateway | Tool interception, metrics, guardrails |
| **Shell hooks** | `hooks:` block in `~/.hermes/config.yaml` | CLI + Gateway | Drop-in scripts for blocking, auto-formatting, context injection |

**All three are non-blocking** — errors in any hook are caught and logged, never crashing the agent.

---

## Tier 1: Gateway Event Hooks

Gateway hooks fire during gateway operation (Telegram, Discord, Slack, etc.) without blocking the main agent pipeline.

### Creating a Gateway Hook

Each hook is a directory under `~/.hermes/hooks/` containing two files:

```
~/.hermes/hooks/
└── my-hook/
    ├── HOOK.yaml      # Declares which events to listen for
    └── handler.py     # Python handler function
```

### HOOK.yaml Format

```yaml
name: my-hook
description: Log all agent activity to a file
events:
  - agent:start
  - agent:end
  - agent:step
```

Events list determines which events trigger the handler. Wildcards supported: `command:*` for all slash commands.

### handler.py Format

```python
import json
from datetime import datetime
from pathlib import Path

LOG_FILE = Path.home() / ".hermes" / "hooks" / "my-hook" / "activity.log"

async def handle(event_type: str, context: dict):
    """Called for each subscribed event. Must be named 'handle'."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        **context,
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
```

**Rules:**
- Handler must be named `handle`
- Receives `event_type` (string) and `context` (dict)
- Can be `async def` or regular `def` — both work
- Errors caught and logged, never crash agent

### Available Events

| Event | When it fires | Context keys |
|-------|---------------|--------------|
| `gateway:startup` | Gateway process starts | `platforms` (list of active platform names) |
| `session:start` | New messaging session created | `platform`, `user_id`, `session_id`, `session_key` |
| `session:end` | Session ended (before reset) | `platform`, `user_id`, `session_key` |
| `session:reset` | User ran `/new` or `/reset` | `platform`, `user_id`, `session_key` |
| `agent:start` | Agent begins processing a message | `platform`, `user_id`, `session_id`, `message` |
| `agent:step` | Each iteration of the tool-calling loop | `platform`, `user_id`, `session_id`, `iteration`, `tool_names` |
| `agent:end` | Agent finishes processing | `platform`, `user_id`, `session_id`, `message`, `response` |
| `command:*` | Any slash command executed | `platform`, `user_id`, `command`, `args` |

### Wildcard Matching

Handlers registered for `command:*` fire for any `command:` event. Monitor all slash commands with single subscription.

---

## Example Hooks

### Telegram Alert on Long Tasks

```yaml
# ~/.hermes/hooks/long-task-alert/HOOK.yaml
name: long-task-alert
description: Alert when agent is taking many steps
events:
  - agent:step
```

```python
# ~/.hermes/hooks/long-task-alert/handler.py
import os
import httpx

THRESHOLD = 10
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_HOME_CHANNEL")

async def handle(event_type: str, context: dict):
    iteration = context.get("iteration", 0)
    if iteration == THRESHOLD and BOT_TOKEN and CHAT_ID:
        tools = ", ".join(context.get("tool_names", []))
        text = f"⚠️ Agent has been running for {iteration} steps. Last tools: {tools}"
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": CHAT_ID, "text": text},
            )
```

### Command Usage Logger

```yaml
# ~/.hermes/hooks/command-logger/HOOK.yaml
name: command-logger
description: Log slash command usage
events:
  - command:*
```

```python
# ~/.hermes/hooks/command-logger/handler.py
import json
from datetime import datetime
from pathlib import Path

LOG = Path.home() / ".hermes" / "logs" / "command_usage.jsonl"

def handle(event_type: str, context: dict):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now().isoformat(),
        "command": context.get("command"),
        "args": context.get("args"),
        "platform": context.get("platform"),
        "user": context.get("user_id"),
    }
    with open(LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
```

### Session Start Webhook

```yaml
# ~/.hermes/hooks/session-webhook/HOOK.yaml
name: session-webhook
description: Notify external service on new sessions
events:
  - session:start
  - session:reset
```

```python
# ~/.hermes/hooks/session-webhook/handler.py
import httpx

WEBHOOK_URL = "https://your-service.example.com/hermes-events"

async def handle(event_type: str, context: dict):
    async with httpx.AsyncClient() as client:
        await client.post(WEBHOOK_URL, json={
            "event": event_type,
            **context,
        }, timeout=5)
```

---

## Tier 2: Plugin Hooks

Plugin hooks are registered via `ctx.register_hook()` in a plugin. Run in both CLI and Gateway.

```python
# In a plugin file
def register_hook(self, hook_type: str, callback: Callable, priority: int = 50):
    """Register a hook callback."""
    ...

# Example: tool interception hook
ctx.register_hook("tool:before_call", my_tool_guard, priority=100)
ctx.register_hook("tool:after_call", my_tool_logger, priority=50)
ctx.register_hook("agent:before_response", my_response_guard, priority=75)
```

**Plugin hook types:**
- `tool:before_call` — before tool execution
- `tool:after_call` — after tool execution (success or failure)
- `agent:before_response` — before agent sends response
- `agent:after_response` — after agent sends response

---

## Tier 3: Shell Hooks

Shell hooks are drop-in scripts in `~/.hermes/config.yaml`:

```yaml
hooks:
  pre_tool:
    - path: /path/to/pre_tool_script.sh
      enabled: true
  post_tool:
    - path: /path/to/post_tool_script.sh
      enabled: true
  context_injection:
    - path: /path/to/inject_context.sh
      enabled: true
```

**Types:**
- `pre_tool` — runs before each tool call (can block/modify)
- `post_tool` — runs after each tool call
- `context_injection` — injects additional context before agent processes

---

## BOOT.md Pattern (Gateway Startup Checklist)

Popular community pattern: drop `~/.hermes/BOOT.md` with natural-language startup instructions.

```
~/.hermes/BOOT.md
    ↓ gateway:startup hook
Spawn one-shot agent with gateway's model/credentials
    ↓
Run BOOT.md instructions
    ↓
[SILENT] convention — opt out of sending message if nothing to report
```

### Step 1: Write your checklist

```markdown
# ~/.hermes/BOOT.md
Check overnight cron failures from /var/log/cron.log.
If any failures found, ping #ops on Discord with summary.
Summarize last 24h of deploy.log and post to Slack #engineering.
Run health check on all monitored services.
```

### Step 2: Create gateway hook

```yaml
# ~/.hermes/hooks/boot-check/HOOK.yaml
name: boot-check
description: Run BOOT.md on gateway startup
events:
  - gateway:startup
```

### Step 3: Implement handler

```python
# ~/.hermes/hooks/boot-check/handler.py
import subprocess, json
from pathlib import Path

async def handle(event_type: str, context: dict):
    boot_md = Path.home() / ".hermes" / "BOOT.md"
    if not boot_md.exists():
        return
    
    # Read BOOT.md and spawn one-shot agent to run it
    content = boot_md.read_text()
    # Spawn agent with content as system prompt
    ...
```

---

## ILMA Hook Implementation Pattern

For ILMA to implement hooks:

```python
# ilma_hooks_manager.py
from pathlib import Path
import asyncio

class HooksManager:
    def __init__(self, hooks_dir: str = "~/.hermes/hooks"):
        self.hooks_dir = Path(hooks_dir).expanduser()
        self.hooks = self._discover_hooks()
    
    def _discover_hooks(self):
        """Scan hooks/ directory for HOOK.yaml + handler.py pairs."""
        hooks = {}
        for hook_dir in self.hooks_dir.iterdir():
            if not hook_dir.is_dir():
                continue
            hook_yaml = hook_dir / "HOOK.yaml"
            handler_py = hook_dir / "handler.py"
            if hook_yaml.exists() and handler_py.exists():
                hooks[hook_dir.name] = {
                    "events": self._parse_yaml(hook_yaml),
                    "handler": self._load_handler(handler_py)
                }
        return hooks
    
    async def emit(self, event_type: str, context: dict):
        """Emit event to all matching hooks."""
        for name, hook in self.hooks.items():
            if self._matches(event_type, hook["events"]):
                try:
                    await hook["handler"](event_type, context)
                except Exception as e:
                    # Non-blocking — log and continue
                    print(f"Hook {name} error: {e}")
    
    def _matches(self, event_type: str, events: list) -> bool:
        for event in events:
            if event == event_type:
                return True
            if event.endswith("*"):
                prefix = event[:-1]
                if event_type.startswith(prefix):
                    return True
        return False
```

---

## Auto-Trigger

Load this skill when:
- User asks to "log agent activity", "alert on X", "send webhook on Y"
- User wants to "run something on startup", "check before each tool"
- User mentions "HOOK.yaml", "handler.py", "gateway hooks"

---

*Hermes v0.13.0 — Event Hooks feature*
*Integrated into ILMA v3.3*