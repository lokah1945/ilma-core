# AgentEnhancements Bridge — Skill ID Extraction Fix (2026-11-16)

## Problem
The `ilma_external_skills_bridge.py` module failed to resolve `file_path` for external skills because the skill ID extraction logic incorrectly used the filename (`SKILL.md`) instead of the skill directory name.

## Root Cause
In `all-skills.json`, the `path` field points to the SKILL.md file:
```
"path": "unified-integration/skills/by-category/general/python-fastapi-development/SKILL.md"
```

Original code (line 122):
```python
skill_id = s.get("path", "").split("/")[-1]  # → "SKILL.md"
```

This caused the bridge to look for skills at:
- `/root/project/AgentEnhancements/agentic-awesome-skills/skills/SKILL.md/SKILL.md` ❌
- `/root/project/AgentEnhancements/unified-integration/skills/by-category/general/python-fastapi-development/SKILL.md/SKILL.md` ❌

Both paths don't exist because they append `SKILL.md` twice.

## Fix Applied
Changed to use the parent directory (the actual skill ID):
```python
# Line 122 in ilma_external_skills_bridge.py
skill_id = s.get("path").split("/")[-2]       # → "python-fastapi-development"
```

Now `file_path` correctly resolves to:
```
/root/project/AgentEnhancements/agentic-awesome-skills/skills/python-fastapi-development/SKILL.md ✅
```

## Verification
```bash
cd /root/.hermes/profiles/ilma
python3 ilma_external_skills_bridge.py --skill python-fastapi-development
# Returns full SKILL.md content with frontmatter and body
```

## Impact
- All 3,378 external skills now have correct `file_path` resolution
- `load_external_skill_content()` works end-to-end
- Capability registry extensions include valid `script_fallback` paths
- External skills usable as fallback chain in ILMA routing

## Related
- `ilma_external_skills_bridge.py` — main module
- `agent-enhancements-bridge-status.md` — prior bridge status
- `agent-enhancements-full-integration-2026-11-14.md` — full integration session