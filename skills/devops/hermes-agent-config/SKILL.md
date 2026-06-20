---
name: hermes-agent-config
description: Edit Hermes agent configurations (SOUL.md, config.yaml, memories) and restart agents. For managing multi-agent setups like ILMA, DEPRECATED, DEPRECATED, DEPRECATED, etc.
triggers:
  - "fix agent behavior"
  - "edit SOUL.md"
  - "restart agent"
  - "reasoning still showing"
  - "change reasoning_effort"
  - "manage other agent"
---

# Managing Hermes Agent Configurations

## Agent Profile Locations

Each agent profile lives at: `/root/.hermes/profiles/<agent_name>/`

Example: ILMA → `/root/.hermes/profiles/ilma/`, DEPRECATED → `/root/.hermes/profiles/naila/`

## Key Files Per Profile

| File | Purpose |
|------|---------|
| `config.yaml` | Main config — model, provider, reasoning_effort, etc. |
| `SOUL.md` | System prompt / persona definition |
| `memories/MEMORY.md` | Agent's long-term memory |
| `memories/USER.md` | User profile and access rules |

## Config.yaml Key Settings

### reasoning_effort (line ~488)
Controls thinking/thinking output for OpenRouter/Nous Portal providers.
```
Options: "xhigh" (max), "high", "medium", "low", "minimal", "none" (disable)
```
**Note:** This setting primarily affects OpenRouter/Nous Portal. For NVIDIA NIM or other providers, the model itself may still output thinking — in that case, stronger rules in SOUL.md are needed.

### show_reasoning (line ~811)
```
show_reasoning: false  # Default — don't show reasoning to user
```

## SOUL.md Rules to Prevent Thinking/Reasoning Output

Sample rules that should be in SOUL.md:
```
### CARA RESPON YANG BENAR:
1. Langsung kasih jawaban final
2. TIDAK ada langkah-langkah berpikir yang ditunjukkan
3. TIDAK ada internal monologue
4. JAWABAN SAJA yang dikirim

### CONTOH SALAH:
Let me check... I should respond...

Selamat datang! 🎉

### CONTOH BENAR:
Selamat datang! 🎉

**TIADA PENGUNGKAPAN PROSES BERPIKIR. JAWABAN FINAL SAJA.**
```

## Restarting an Agent

1. Find the PID:
```bash
ps aux | grep -i "hermes.*<agent_name>" | grep -v grep
```

2. Kill and restart:
```bash
kill <PID>
cd /root/.hermes && nohup /root/.hermes/hermes-agent/venv/bin/python3 /root/.local/bin/hermes -p <agent_name> gateway run > /dev/null 2>&1 &
```

3. Verify it's running:
```bash
sleep 3 && ps aux | grep -i "hermes.*<agent_name>" | grep -v grep
```

## Known Agent Profiles

| Agent | Profile Path |
|-------|-------------|
| ILMA | `/root/.hermes/profiles/ilma/` |
| DEPRECATED | `/root/.hermes/profiles/nara/` |
| DEPRECATED | `/root/.hermes/profiles/naila/` |
| DEPRECATED | `/root/.hermes/profiles/zara/` |
| ELIA | `/root/.hermes/profiles/elia/` |
| VERA | `/root/.hermes/profiles/vera/` |
| MYRA | `/root/.hermes/profiles/myra/` |

## Troubleshooting Reasoning Output on NVIDIA NIM

If `reasoning_effort: "none"` doesn't stop thinking output on NVIDIA NIM:
- The model (e.g., llama-3.1-nemotron-ultra-253b-v1) may have built-in thinking
- Add stronger negative rules in SOUL.md:
  - ❌ Don't output `<thinking>`, `</thinking>`, `<reasoning>`, `</reasoning>`
  - ❌ Don't show steps, reasoning process, or internal monologue
  - ✅ Only final response

**AGENTS.md** also exists at `/root/.hermes/hermes-agent/AGENTS.md` — this is the canonical project README for the NousResearch/hermes-agent repo (52K+ chars), auto-discovered as a subdirectory context. It describes the full project structure, development environment, file dependency chain, AIAgent class, CLI architecture, slash commands, and skill system. This file should be consulted for any agent development work.
