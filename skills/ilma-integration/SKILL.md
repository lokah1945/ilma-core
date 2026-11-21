---
name: ilma-integration
description: "Class-level skill for ILMA system integration patterns — wiring external skill sources, capability registry extensions, runtime wiring verification, and cross-project data bridges. Covers both internal ILMA modules and read-only bridges to external projects like agent-enhancements and agency-agents."
tags: [integration, external-skills, agent-enhancements, runtime-wiring, capability-registry]
related_skills: [ilma-capability-registry, ilma-runtime-wiring]
---

# Ilma Integration

## Purpose
Class-level skill for ILMA system integration patterns: wiring external skill sources, capability registry extensions, runtime wiring verification, and cross-project data bridges. Covers both internal ILMA modules and read-only bridges to external projects like agent-enhancements.

## Triggers
- "ilma-integration"
- "external skills bridge"
- "agent-enhancements"
- "skill index integration"
- "runtime wiring verification"

## Status
Active — maintained as class-level integration reference.

## Key Integration Points

### 1. External Skills Bridge (Phase 73+)
**Module:** `ilma_external_skills_bridge.py` (root profile)
**Index source:** `/root/project/AgentEnhancements/unified-integration/skills/all-skills.json`
**Skills source:** `/root/project/AgentEnhancements/agentic-awesome-skills/skills/`

**Purpose:** Read-only bridge to consume 2,884+ external skills from agent-enhancements project without modifying it. Provides:
- Skill discovery by keyword/task
- Skill content loading (reads SKILL.md from source)
- Capability registry extensions for fallback chain

**Current Status (2026-11-14, verified):** Bridge loads **3,116 skills** (all compatible with `codex` agent target) — index fields `id` and `plugin.targets` are now populated.
- Risk breakdown: 1,534 critical, 1,340 safe, 150 offensive, 73 none, 19 unknown
- Categories: general (2,771), devops (127), security (152), productivity (40), testing (16), ai-ml (5), architecture (5)

**Verified Fix (2026-11-14):** The `npm run build` in `/root/project/AgentEnhancements` successfully populates required fields. Bridge now fully functional.

**Verified Fix (2026-11-16):** Skill ID extraction bug in `ilma_external_skills_bridge.py` — `path.split('/')[-1]` returned `SKILL.md` instead of the skill directory name. Fixed to use `path.split('/')[-2]` (parent directory).

```python
# Before (line 122):
skill_id = s.get("path", "").split("/")[-1]  # → "SKILL.md"

# After:
skill_id = s.get("path").split("/")[-2]       # → "python-fastapi-development"
```

This enables correct `file_path` resolution to `/root/project/AgentEnhancements/agentic-awesome-skills/skills/<id>/SKILL.md`.

**Test Command:**
```bash
cd /root/.hermes/profiles/ilma && python3 ilma_external_skills_bridge.py --stats
# Output: Total skills: 3378
```

### 4. Full AgentEnhancements Integration & Multi-Agent Setup (2026-11-14)
**Session:** Moved repo from `/root/agent-enhancements` → `/root/project/AgentEnhancements`, ran unified setup, updated all ILMA references.

**Steps Executed:**
1. **Replace local repo** — deleted old `/root/project/AgentEnhancements` (scaffold), moved GitHub clone to that path
2. **Run unified setup** — `AGENT_ENHANCEMENTS_BASE_DIR=/root/project/AgentEnhancements ./unified-integration/setup.sh`
   - Detected: Claude Code, Codex, OpenCode, Gemini CLI
   - Configured system prompts for each agent
   - Aggregated skills (3,116 indexed)
   - Generated `config/detected-agents.sh` with 4 agents
3. **Update ILMA bridge path** — changed default from `/root/agent-enhancements` → `/root/project/AgentEnhancements` in:
   - `ilma_external_skills_bridge.py` (EXTERNAL_SKILLS_ROOT)
   - `ilma_integration_manifest.json` (EXTERNAL_SKILLS_INDEX)
   - SOUL.md, skills/ilma-integration/SKILL.md, all reference files
4. **Fix unified-integration scripts** — updated hardcoded paths in `load-skills.py`, `compress.py`
5. **Verify** — ILMA boot loads 3,116 skills, runtime wiring 38/38 OK

**Agent Integration Results:**
| Agent | Status | Config Location |
|-------|--------|-----------------|
| Claude Code | ✅ Hooks configured | `~/.claude/settings.json` (merged with wrapper) |
| Codex | ✅ Skills loadable | `load-skills.py codex "task"` works |
| OpenCode | ✅ System prompt | `unified-integration/prompts/opencode-system-prompt.txt` |
| Gemini CLI | ✅ System prompt | `unified-integration/prompts/gemini-cli-system-prompt.txt` |
| Universal | ✅ Fallback | `unified-integration/prompts/universal-system-prompt.txt` |

**Memory Hooks (Tested):**
- `claude-code-memory-hook.sh` → Python script → SQLite at `~/.agent-memory/memory.db`
- Works for: save/load/list/delete/cleanup per agent/project
- Tested: save + list returned stored value

**Headroom Compression:**
- Binary: `/root/project/AgentEnhancements/headroom/target/release/headroom-proxy`
- `compress.py` updated to use `headroom-proxy` binary

**Key Lesson:** When Bos says "update local to match GitHub and integrate", always:
1. Check if local path is actually a git clone or a different project
2. Replace rather than merge when architectures differ
3. Run the project's own setup script with correct BASE_DIR
4. Update ALL downstream consumers (ILMA bridge, configs, references) atomically
5. Verify end-to-end: bridge loads skills → ILMA boots → wiring passes

### 2. Runtime Wiring Verification
**Module:** `ilma_runtime_wiring.py`
**Command:** `python3 ilma_runtime_wiring.py --verify`
**Pipeline:** 9 layers, 36 wired modules (as of Phase 73)

### 3. Integration Manifest
**File:** `config/ilma_integration_manifest.json`
Documents data stores, pipeline steps, routing engine, runtime wiring, scheduled jobs, and git sync.

## References
- `references/agent-enhancements-bridge-status.md` — Detailed status of the external skills bridge, root cause analysis, fix options, and test commands
- `references/agency-agents-multi-cli-install.md` — Session detail (2026-11-02): exact convert+install commands for codex/hermes from /root/agency-agents, per-tool status table, pitfalls (path typo, codex exec has no --agent flag, hermes installs to active profile dir, convert.sh must run before install.sh)
- `references/agent-enhancements-full-integration-2026-11-14.md` — Full AgentEnhancements repo replacement + multi-agent integration with ILMA capability registry extensions
- `references/agent-enhancements-audit-2026-11-14.md` — **End-to-end audit**: identifies critical gaps — system prompts missing, OpenCode/Windsurf/Kiro have 0% skill coverage (only fallback `plan-writing`), setup script incomplete, Codex config stale, no live agent test
## External Agent Catalog → Multi-CLI Install (agency-agents pattern, learned 2026-11-02)

When Bos asks to wire an external agent catalog (repo with `scripts/convert.sh` + `scripts/install.sh` + `tools.json`, e.g. `/root/agency-agents`, 282 agents / 18 divisions) into local CLIs:

1. **Verify the exact path first** — `ls` what Bos names; repos are often plural (`agency-agents`, not `agency-agent`).
2. **Read `tools.json`** for the per-tool destination contract before running anything.
3. **Always convert before install**: `bash scripts/convert.sh --tool <tool>` then `bash scripts/install.sh --no-interactive --tool <tool>`. `integrations/<tool>/` ships README-only.
4. **Codex**: installs to `~/.codex/agents/*.toml`; TUI picks them up via `/agents`; `codex exec` has NO `--agent` flag — inject `developer_instructions` text manually for headless runs.
5. **Hermes**: plugin goes to the ACTIVE profile dir (`~/.hermes/profiles/<profile>/plugins/`) and is appended to that profile's `config.yaml` `plugins.enabled` — needs session/gateway restart to expose new tools.
6. **Verify after install**: file count in dest dir, the tool's own listing (`hermes plugins list`), and a functional smoke test (parse one generated TOML with `tomllib`; call the plugin's search tool).

## Files in this skill:
- ilma-openhand-config/SKILL.md
- ilma-openhand-config/templates/persisted-settings.json
- ilma-openhand-config/templates/openhand-launcher.sh
- ilma-openhand-config/templates/openhand-up.sh
- ilma-openhand-config/references/openhands-serve-agent-settings-fix.md
- ilma-openhand-config/references/wrapper-nous-facts.md
- references/agent-enhancements-bridge-status.md
- references/runtime-integration-gaps-2026-11-16.md