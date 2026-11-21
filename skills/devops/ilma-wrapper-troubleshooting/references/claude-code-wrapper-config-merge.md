# Claude Code Wrapper Config Merge — 2026-11-01

## Context
User reported: "Claude code di mesin anda. Setelah patch skill baru, dia menghapus config nya. Gunakan file settings.json.wrapper sebagai basis, kombinasikan dengan dengan config saat ini. Jadi backend nya adalah wrapper tapi config untuk skill Agent Enhancements nya tetap aktif"

## Files Involved
- `/root/.claude/settings.json.wrapper` — wrapper env config (ANTHROPIC_BASE_URL=9100, model discovery, etc.)
- `/root/.claude/settings.json` (pre-merge) — only hooks for agent-enhancements memory
- `/root/.claude/settings.json` (post-merge) — combined

## Merge Result (applied)

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:9100",
    "ANTHROPIC_AUTH_TOKEN": "bearer-token-clone",
    "ANTHROPIC_API_KEY": "bearer-token-clone",
    "ANTHROPIC_MODEL": "meta/llama-3.1-8b-instruct",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "meta/llama-3.1-8b-instruct",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "meta/llama-3.1-70b-instruct",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "meta/llama-3.1-8b-instruct",
    "ENABLE_TOOL_SEARCH": "true",
    "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1",
    "CLAUDE_CODE_GATEWAY_MODEL_DISCOVERY_URL": "http://localhost:9100/v1/models"
  },
  "theme": "auto",
  "skipWorkflowUsageWarning": true,
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "/root/project/AgentEnhancements/unified-integration/memory/hooks/claude-code-memory-hook.sh save pre_tool_use \"${TOOL_NAME}\" \"${TOOL_INPUT}\""
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "/root/project/AgentEnhancements/unified-integration/memory/hooks/claude-code-memory-hook.sh save post_tool_use \"${TOOL_NAME}\" \"${TOOL_RESULT}\""
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/root/project/AgentEnhancements/unified-integration/memory/hooks/claude-code-memory-hook.sh save session_end \"summary\" \"${SESSION_SUMMARY}\""
          }
        ]
      }
    ]
  }
}
```

## Key Observations

1. **Wrapper endpoint mismatch**: `ANTHROPIC_BASE_URL` points to port 9100 (legacy wrapper-nvidia), but active NVIDIA wrapper is `wrapper-nvidia-python` on **port 9101** (see `opencode-config-fix-2026-11-01.md` port mapping). User may need to update to 9101.

2. **Hook path verified**: `/root/project/AgentEnhancements/unified-integration/memory/hooks/claude-code-memory-hook.sh` exists and executable.

3. **Agent-enhancements skills active**: `/root/project/AgentEnhancements/unified-integration/skills/` contains 5MB+ of skills (agentic-awesome-skills-index.json, all-skills.json, by-agent/, by-category/).

4. **OpenHands uses different wrapper**: `/root/.openhands/settings.json` points to `wrapper-nous` on **port 9102** with model `openai/tencent/hy3:free` — separate from Claude Code config.

## 2026-11-01 Update (This Session)

### Config Updated to Port 9101 (NVIDIA wrapper)
```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:9101",
    "ANTHROPIC_AUTH_TOKEN": "bearer-token-clone",
    "ANTHROPIC_API_KEY": "bearer-token-clone",
    "ANTHROPIC_MODEL": "nvidia/nemotron-3-ultra-550b-a55b",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "nvidia/nemotron-3-ultra-550b-a55b",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "nvidia/nemotron-3-ultra-550b-a55b",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "nvidia/nemotron-3.5-bolt-e4b",
    "ENABLE_TOOL_SEARCH": "true",
    "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1",
    "CLAUDE_CODE_GATEWAY_MODEL_DISCOVERY_URL": "http://localhost:9101/v1/models"
  },
  "theme": "auto",
  "skipWorkflowUsageWarning": true,
  "hooks": { ... }  // unchanged from agent-enhancements
}
```

### Verification Results (This Session)
- **GET /v1/models** at 9101 → 134 models (111 catalog_usable), `nvidia/nemotron-3-ultra-550b-a55b` present ✅
- **POST /v1/chat/completions** with `Authorization: Bearer wrapper-local-key` → 200 OK ✅
- **POST /v1/messages** (Anthropic endpoint) → 200 OK ✅ (wrapper translates Anthropic→OpenAI)
- **Direct NIM test** (port 9101 bypass) → NO native `/v1/messages` endpoint on NVIDIA NIM; only `/v1/chat/completions` exists. Wrapper translation layer **required** (see `nvidia-nim-native-protocol-test.md`).
- **Auth**: `BEARER_TOKEN=wrapper-local-key` in `/root/wrapper/nvidia-python/.env` matches client config.

### **2026-11-01 Auth Token Fix (Later in Same Session)**
**Problem**: Merged config used stale `bearer-token-clone` → wrapper returned `401 Unauthorized`.
**Evidence**: wrapper log showed `INFO: 127.0.0.1:36516 - "POST /v1/messages?beta=true HTTP/1.1" 401 Unauthorized` before fix, `200 OK` after.
**Fix**: Updated `ANTHROPIC_AUTH_TOKEN` and `ANTHROPIC_API_KEY` to `wrapper-local-key` in `/root/.claude/settings.json`.
**Root cause**: Legacy `settings.json.wrapper` had placeholder token, not the actual wrapper `BEARER_TOKEN`.
**Full details**: `references/claude-code-auth-token-fix-2026-11-01.md`.

### Verification Checklist (Post-Merge)
- [x] `curl http://127.0.0.1:9101/v1/models` returns models
- [x] `curl -H "Authorization: Bearer ***" -d '{"model":"nvidia/nemotron-3-ultra-550b-a55b",...}' http://127.0.0.1:9101/v1/chat/completions` → 200
- [x] `curl -H "Authorization: Bearer ***" -d '{"model":"nvidia/nemotron-3-ultra-550b-a55b",...}' http://127.0.0.1:9101/v1/messages` → 200 (Anthropic surface)
- [ ] Test `claude` CLI end-to-end (requires interactive session)
- [ ] Confirm hooks fire (check `~/.agent-memory/memory.db`)

## Verification Needed
- [ ] Test `claude` CLI connects to wrapper at port 9101
- [ ] Verify `GET /v1/models` returns models at configured base URL
- [ ] Confirm hooks fire (check memory DB at `~/.agent-memory/`)
- [ ] If wrapper at 9100 is removed, update to 9101 (nvidia-python) or 9102 (nous)

## Related
- `references/opencode-config-fix-2026-11-01.md` — port mapping: nvidia-python=9101, nous=9102, opencode=9103, blackbox=9104
- `references/wrapper-pull-restart-bugfix-2026-07-28.md` — wrapper restart & verification protocol