# AgentEnhancements End-to-End Audit — 2026-11-14

## Audit Scope
Verify that AgentEnhancements (at `/root/project/AgentEnhancements`) is **fully implemented and actually usable** by all installed agents: Claude Code, OpenCode, Codex.

## Test Results Summary

| Component | Status | Notes |
|-----------|--------|-------|
| **Repo location** | ✅ `/root/project/AgentEnhancements` | GitHub clone, 3.9GB, valid git history |
| **Skills index** | ✅ `all-skills.json` | 3,116 skills, valid JSON |
| **ILMA Bridge** | ✅ Active | 3,116 skills loaded (1,340 safe) |
| **Runtime wiring** | ✅ 38/38 modules OK | `external_skills_bridge` in LAYER_2 |
| **Skill discovery** | ✅ Working | Bridge returns relevant matches |
| **Skill content loading** | ✅ Working | Reads SKILL.md from source |
| **Capability extensions** | ✅ 3,116 generated | Mapped to ILMA categories |
| **Memory hooks** | ✅ Tested | Python scripts work for all agents |
| **Compression** | ✅ Working | `headroom-proxy` binary ready |
| **Load-skills script** | ✅ Working | Returns skills for task |

---

## Gaps / NOT Fully Implemented

### 1. System Prompts Missing
**Agents affected:** Claude Code, Codex, Gemini CLI
**Issue:** Prompts not found in `system-prompts-and-models-of-ai-tools` — uses universal fallback only
```
[WARN] Claude Code prompt not found in /root/project/AgentEnhancements/system-prompts-and-models-of-ai-tools/Anthropic/
[WARN] Codex prompt not found in /root/project/AgentEnhancements/system-prompts-and-models-of-ai-tools/OpenAI/
[WARN] Gemini CLI prompt not found in /root/project/AgentEnhancements/system-prompts-and-models-of-ai-tools/Google/
```
**Impact:** Agents don't get optimized system prompts; only universal fallback works.

### 2. by-agent/ Directories Sparse (Critical Coverage Gap)
**Agents affected:** OpenCode, Windsurf, Kiro
**Root cause:** Only **112/3,116 skills** have `tools` frontmatter populated. The rest have empty `tools: []`.
**Result:**
| Agent | Skills in by-agent/ | Source |
|-------|---------------------|--------|
| OpenCode | 1 (plan-writing) | Fallback copy only |
| Windsurf | 1 (plan-writing) | Fallback copy only |
| Kiro | 1 (plan-writing) | Fallback copy only |
| Codex | 5 | Has some `tools: ['codex', 'codex-cli']` |
| Claude Code | 94 | Has `tools: ['claude-code']` |

**Source breakdown:**
| Source | Total | With tools | Without tools |
|--------|-------|------------|---------------|
| agentic-awesome-skills | 2,781 | 112 | 2,669 |
| ECC | 314 | 0 | 314 |
| Superpowers | 15 | 0 | 15 |
| Ponytail | 6 | 0 | 6 |

**Impact:** OpenCode/Windsurf/Kiro effectively have **0% skill coverage** — only fallback copy of `plan-writing` exists.

### 3. Setup Script Too Slow / Incomplete
**Issue:** Processing 2,781 skills takes >2 min, times out at 60s background clamp.
**Evidence:** `all-skills.json.tmp` stays at 15 bytes (initial `{"skills": []}`) — aggregation never completes.
**Impact:** `by-agent/` and `by-category/` directories not fully populated; `all-skills.json` not refreshed.

### 4. Codex config.yaml Path Stale
**File:** `/root/.codex/config.yaml`
**Current:** `system_prompt: '@/root/agent-enhancements/unified-integration/prompts/codex-system-prompt.txt'`
**Should be:** `system_prompt: '@/root/project/AgentEnhancements/unified-integration/prompts/codex-system-prompt.txt'`
**Also:** `skills.directory` points to old path.

### 5. No Live Agent Test
Didn't actually run `claude`, `codex`, or `opencode` with the config to verify end-to-end.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| OpenCode/Windsurf/Kiro have no usable skills | HIGH | HIGH | Populate `tools` frontmatter in ECC/Superpowers/Ponytail skills; add `opencode`, `windsurf`, `kiro` to agentic-awesome-skills |
| Setup script never completes aggregation | HIGH | MEDIUM | Optimize aggregation (parallel, batch); or pre-build index offline |
| Codex uses stale path | MEDIUM | MEDIUM | Update `/root/.codex/config.yaml` paths |
| System prompts missing | MEDIUM | LOW | Add prompts to `system-prompts-and-models-of-ai-tools` or document universal fallback is sufficient |

---

## Commands to Fix Gaps

```bash
# 1. Update Codex config
sed -i 's|/root/agent-enhancements|/root/project/AgentEnhancements|g' /root/.codex/config.yaml

# 2. Add tools frontmatter to ECC skills (example)
# Edit /root/project/AgentEnhancements/ECC/skills/*/SKILL.md
# Add: tools:\n  - opencode\n  - windsurf\n  - kiro\n  - codex\n  - claude-code

# 3. Run npm build to populate id/plugin.targets
cd /root/project/AgentEnhancements && npm run build

# 4. Re-run setup with longer timeout or in foreground
AGENT_ENHANCEMENTS_BASE_DIR=/root/project/AgentEnhancements /root/project/AgentEnhancements/unified-integration/setup.sh

# 5. Verify by-agent population
for agent in opencode windsurf kiro codex claude-code; do
  count=$(ls -1 /root/project/AgentEnhancements/unified-integration/skills/by-agent/$agent/ 2>/dev/null | wc -l)
  echo "$agent: $count skills"
done
```

---

## Key Lessons for Future Sessions

1. **Skill coverage ≠ index count** — 3,116 indexed ≠ 3,116 usable by each agent. Must verify `tools` frontmatter per agent.

2. **Fallback copy is a trap** — The setup script's fallback copies `plan-writing` to all agents when `tools` is empty, creating false appearance of coverage.

3. **Setup script must complete** — Background timeout at 60s means aggregation never finishes. Run in foreground or optimize.

4. **Config paths must be updated atomically** — Codex config.yaml, ILMA bridge, all references — miss one and agent breaks silently.

5. **End-to-end test = run the agent** — Only way to verify is actually invoke `claude`, `codex`, `opencode` with a task.