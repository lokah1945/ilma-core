---
name: ilma-codex-stdio-agent
description: Spawn OpenAI Codex binary (gpt-5.5) as subprocess via STDIO JSON-RPC — verified working as of 2026-05-08
triggers:
  - gpt-5.5 sub-agent
  - codex subagent
  - openai codex via stdio
  - codex-cli subprocess
category: autonomous-ai-agents
tags: [codex, gpt-5.5, sub-agent, stdio, json-rpc, openai]
version: 1.0.0
verified: true
verified_date: 2026-05-08
---

# ILMA Codex STDIO Agent — gpt-5.5 Sub-Agent

## What it does
Spawns the Codex binary (codex-cli 0.125.0) as a subprocess, communicates via **STDIO JSON-RPC** protocol to run gpt-5.5 coding tasks. ILMA has achieved parity with AYDA's capability.

## Protocol Sequence
```
initialize → account/login/start → thread/start → turn/start → poll for thread/status:idle → extract from session JSONL
```

## Working Script
`/root/.hermes/profiles/ilma/scripts/ilma_codex_stdio.py`

### Binary Path
```
/root/.openclaw/plugin-runtime-deps/openclaw-2026.4.26-4eca5026e977/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/codex/codex
```

### Spawn Pattern
```python
proc = subprocess.Popen(
    [CODEX_BIN, "app-server", "--listen", "stdio://"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    env={**os.environ, "OPENAI_AUTH_TOKEN": TOKEN}
)
```

### Protocol Messages
```python
# 1. Initialize
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{
  "clientInfo":{"name":"ilma","title":"ILMA Hermes Agent","version":"1.0"},
  "capabilities":{"experimentalApi":True}
}}

# 2. Login (REQUIRED — without this → 401 Unauthorized)
{"jsonrpc":"2.0","id":2,"method":"account/login/start","params":{
  "type":"chatgptAuthTokens",
  "accessToken":"<oauth_jwt_token>",
  "chatgptAccountId":"lokah2150@gmail.com",
  "chatgptPlanType":"plus"
}}

# 3. Start thread
{"jsonrpc":"2.0","id":3,"method":"thread/start","params":{
  "model":"gpt-5.5",
  "modelProvider":"openai"
}}

# 4. Send turn
{"jsonrpc":"2.0","id":4,"method":"turn/start","params":{
  "threadId":"<thread_id>",
  "input":[{"type":"text","text":"Hello gpt-5.5","text_elements":[]}],
  "model":"gpt-5.5",
  "approvalPolicy":"never"
}}
```

### Response Extraction
Response text found in session JSONL file, NOT in JSON-RPC responses:
```json
{"type":"response_item","payload":{"type":"message","role":"assistant","content":[{"type":"output_text","text":"..."}],"phase":"final_answer"}}
```

**Pattern**: Poll `thread/status/changed` notification. When `status.type == "idle"`, read session JSONL file and extract assistant message.

## Critical Insights

| Aspect | Detail |
|--------|--------|
| Protocol | STDIO JSON-RPC via subprocess stdin/stdout (NOT HTTP/WebSocket) |
| Auth method | `account/login/start` with ED25519 JWT accessToken (NOT Bearer header) |
| Token source | `auth-profiles.json` key `openai-codex:lokah2150@gmail.com` |
| Response source | Session JSONL file in `~/.codex/sessions/` (notifications arrive async) |
| Completion signal | `thread/status.type == "idle"` arrives before `turn/completed` notification |
| Token usage | 23K-50K tokens/turn with 3-27K cached input tokens |
| Latency | 8-30 seconds per turn |
| Model | `gpt-5.5` with `modelProvider: "openai"` |

## OAuth Token Loading
```python
import json
with open("/root/.openclaw/agents/main/agent/auth-profiles.json") as f:
    profiles = json.load(f)
token = profiles["openai-codex:lokah2150@gmail.com"]["accessToken"]
```

## Verification
```bash
python3 /root/.hermes/profiles/ilma/scripts/ilma_codex_stdio.py
# Expected output:
# [TURN RESULT] "ILMA gpt-5.5 SUCCESS!"
```

## Pitfalls
- ❌ Missing `account/login/start` → `401 Unauthorized: Missing bearer or basic authentication`
- ❌ Using HTTP instead of STDIO → wrong protocol
- ❌ Closing process before idle signal → response not captured
- ❌ Using `getConversationSummary` RPC → wrong params format (params variant error)
- ❌ Session file path changes → use `codexHome` from initialize response

## Session File Format
Session files stored at:
```
/root/.hermes/profiles/ilma/home/.codex/sessions/YYYY/MM/DD/rollout-<timestamp>-<thread_id>.jsonl
```

Session JSONL entry types:
- `session_meta` — metadata (thread ID, model, etc.)
- `event_msg` — task_started, etc.
- `response_item` — **THE RESPONSE** (role: assistant, phase: final_answer)
- `token_usage` — token usage events

## Status
✅ **VERIFIED WORKING** — 2026-05-08, 23:58 WIB
- Token auth: ✅
- Thread start: ✅
- Turn execution: ✅
- Response extraction: ✅
- Token usage reporting: ✅
