# Reverse Engineering Capability Status (Session 2026-11-01)

## Summary
REA (reverse-engineer-anything) tooling is **NOT installed** on this machine. Only the skill documentation exists in `/root/agent-enhancements/agentic-awesome-skills/skills/reverse-engineer-anything/`.

## What's Present

| Component | Status | Path / Notes |
|-----------|--------|--------------|
|| Ghidra 12.0.4 | ✅ Installed | `/opt/ghidra_12.0.4/` → `/usr/local/bin/ghidra` (symlink) |
| rea-agents CLI | ❌ Not installed | `which rea-agents` → nothing |
| REA MCP server | ❌ Not registered | Skill explicitly states it does not register MCP or install engines |
| IDA Pro / radare2 / angr / pwntools | ❌ Not installed | |
| Skill docs only | ✅ Present | Documentation/guidance only |

## Ghidra Limitation
Ghidra exists but **cannot run headless** without JDK + X11/TTY:
```
ERROR: Unable to prompt user for JDK path, no TTY detected.
```

## Skill Guidance (from REA skill)
> *"REA setup never installs or upgrades Node.js, npm, Homebrew, Java, Ghidra, IDA, JADX, Binwalk, or Unblob. Use existing prerequisites; do not install unrelated software to repair MCP registration."*

## To Enable REA
1. Install rea-agents: `npm install -g rea-agents` (or version-pinned)
2. Configure MCP registration: `rea-agents setup --client <client> --dry-run --json` then `--yes`
3. Restart/reconnect agent, verify tools appear
4. For CLI fallback (no MCP): `rea-agents analyze-javascript-application /absolute/path/to/app --json`

## Capability Mapping
No `primary_cap` for "reverse_engineering" exists in the 25 ILMA capabilities. This would need:
- New capability entry in `credentials._meta.capability_registry`
- Models with `capabilities_v2` including `reverse_engineering`
- Models with `hermes_caps` for any REA-specific Hermes handles

## Risk
Any `rea-agents` command will fail with "command not found". Ghidra exists but cannot run headless without JDK + X11/TTY setup.

## Related References
- ilma-capability-registry/references/reverse-engineering-capability.md — Same content in capability registry
- agentic-awesome-skills/skills/reverse-engineer-anything/SKILL.md — Source skill documentation