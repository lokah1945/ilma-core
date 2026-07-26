---
name: ilma-parallel-coding-agent
description: ILMA ClaudeCode-style parallel coding agent — fan out to multiple free models, judge, pick winner.
category: ilma
version: 1.0.0
---

# ILMA Parallel Coding Agent

ClaudeCode-style parallel coding agent that fans out tasks to multiple free-tier models (NVIDIA NIM, OpenRouter, BlackBox, Qwen) in parallel, judges results, and picks the winner.

## Scripts

- `scripts/verify_claudecode.sh` — Verification script for ClaudeCode agent

## Usage

The canonical implementation is `ilma_claudecode_agent.py` (Phase 71). Use via:
```bash
python3 ilma_claudecode_agent.py parallel --task "build X" --count 3
python3 ilma_super_coding_command_center.py claudecode "build X" --parallel 3
```

Priority stack (FREE-ONLY): TIER 1 NVIDIA → TIER 2 OpenRouter → TIER 3 BlackBox → TIER 4 Qwen.
