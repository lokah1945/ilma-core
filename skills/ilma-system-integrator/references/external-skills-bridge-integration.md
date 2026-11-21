# External Skills Bridge Integration — v3.31+

**Session:** 2026-11-01  
**Task:** Integrate `/root/project/AgentEnhancements` (3116 skills) into ILMA without modifying original project  
**Pattern:** Read-only bridge consuming external skill index as supplementary capability source

---

## Architecture

```
ILMA Core (154 skills + 86 Hermes)
    │
    ├── ilma_external_skills_bridge.py (LAYER_2_EXECUTION)
    │       │
    │       ├── find_external_skills_for_task(task, max_results) → SkillMatch[]
    │       ├── load_external_skill_content(skill_id) → {frontmatter, body, file_path}
    │       ├── extend_capability_registry_with_external() → CapabilityEntry[] (EXTERNAL status)
    │       └── get_external_skills_bridge() → singleton
    │
    └── /root/project/AgentEnhancements/unified-integration/skills/all-skills.json (READ-ONLY)
            │
            └── /root/project/AgentEnhancements/agentic-awesome-skills/skills/*/SKILL.md (source files)
```

---

## Integration Points

### 1. Runtime Wiring (`ilma_runtime_wiring.py`)
```python
LAYER_2_EXECUTION = [
    ...,
    "ilma_browser_engine",
    "ilma_external_skills_bridge",  # ← ADDED
]

PURPOSES["ilma_external_skills_bridge"] = (
    "Phase 73+ — Read-only bridge to /root/project/AgentEnhancements unified skills "
    "(3116 skills). Provides skill discovery, content loading, and capability "
    "registry extensions without modifying source project."
)
```

### 2. Integration Manifest (`ilma_integration_manifest.json`)
```json
{
  "data_stores": {
    "EXTERNAL_SKILLS_INDEX": {
      "file": "/root/project/AgentEnhancements/unified-integration/skills/all-skills.json",
      "description": "Agent-enhancements unified skills index (3116 skills) — READ ONLY",
      "readers": ["ilma_external_skills_bridge.py"],
      "writers": []
    }
  },
  "runtime_wiring": {
    "integrates": [
      ...,
      "ilma_external_skills_bridge.py"
    ]
  }
}
```

### 3. Capability Registry (`ilma_capability_registry.py`)
External skills registered as `CapabilityStatus.EXTERNAL` with:
- `primary_tool: "external_skill:{skill_id}"`
- `script_fallback: "{absolute_path_to_SKILL.md}"`
- `risk_level` from external skill (`safe`, `critical`, `none`, `offensive`, `unknown`)
- `metadata.source: "agent-enhancements"`

---

## Usage Patterns

### Task → Skill Discovery
```python
from ilma_external_skills_bridge import find_external_skills_for_task

matches = find_external_skills_for_task(
    "create a REST API with authentication", 
    max_results=5
)
# Returns SkillMatch[] with: skill, score, matched_keywords
```

### Skill Content Loading
```python
from ilma_external_skills_bridge import load_external_skill_content

content = load_external_skill_content("api-integration-architect")
# Returns: {skill_id, skill_name, category, source, file_path, frontmatter, body}
```

### Capability Extension (Auto-registration)
```python
from ilma_external_skills_bridge import extend_capability_registry_with_external
from ilma_capability_registry import get_registry, CapabilityEntry, CapabilityCategory, CapabilityStatus

reg = get_registry()
exts = extend_capability_registry_with_external()

for ext in exts:
    if ext['risk_level'] == 'safe':  # Only safe skills auto-registered
        entry = CapabilityEntry(
            name=ext['name'],
            category=CapabilityCategory(ext['category']),
            status=CapabilityStatus.EXTERNAL,
            # ... all fields from ext
        )
        reg.register(entry)
```

---

## Risk Classification Mapping

| External Risk | ILMA Treatment |
|--------------|----------------|
| `safe` | Auto-registered as EXTERNAL capability, available in fallback chain |
| `critical` | NOT auto-registered — requires explicit Bos approval |
| `none` | Available for discovery, not auto-registered |
| `offensive` | Blocked — excluded from compatible skills for agent |
| `unknown` | Available for discovery, manual review required |

---

## Key Design Decisions

### Read-Only Principle
- **Never writes** to `/root/project/AgentEnhancements`
- Original project git status unchanged (verified)
- Bridge only reads `all-skills.json` and `SKILL.md` files

### Path Resolution
```python
# Index path: skills/{skill_id}/SKILL.md
# Actual source: agentic-awesome-skills/skills/{skill_id}/SKILL.md

candidate = EXTERNAL_SKILLS_ROOT / skill.path / "SKILL.md"
if not candidate.exists():
    candidate = EXTERNAL_SKILLS_SOURCE / skill.id / "SKILL.md"
```

### Agent Compatibility Filter
```python
def is_compatible(self, agent: str = "codex") -> bool:
    # If plugin.targets exists, use it for filtering
    targets = self.plugin.get("targets") if self.plugin else None
    if targets:
        if isinstance(targets, dict):
            return targets.get(agent, "").lower() in ("supported", "yes", "true")
        if isinstance(targets, list):
            return agent in targets
    # If no targets specified, default permissive (skill works for all agents)
    return True
```

---

## Verification Commands

```bash
# Bridge stats
python3 -c "from ilma_external_skills_bridge import get_external_skills_bridge; b=get_external_skills_bridge(); print(b.get_stats())"

# Skill discovery test
python3 -c "from ilma_external_skills_bridge import find_external_skills_for_task; print(find_external_skills_for_task('write blog post', 3))"

# Runtime wiring check
python3 ilma_runtime_wiring.py --verify | grep external_skills_bridge

# Integration manifest check
python3 -c "import json; m=json.load(open('ilma_integration_manifest.json')); print('EXTERNAL_SKILLS_INDEX' in m['data_stores'])"
```

---

## Related Skills

- **ilma-capability-registry** — Capability registration pattern
- **ilma-hermes-skills-router** — Internal skill routing (complementary)
- **ilma-system-audit** — For auditing bridge integration

---

## Lessons Learned

1. **External index path vs actual source path differ** — `unified-integration/skills/by-category/*` contains symlinks/copies but actual SKILL.md lives in `agentic-awesome-skills/skills/`. Bridge resolves both.

2. **Risk filtering is critical** — 1473/2800 skills are `critical` risk. Auto-registering all would flood capability registry with unapproved skills.

3. **Agent compatibility matters** — Index includes `tools: ['codex', 'claude']` or `plugin.targets`. Bridge filters by target agent (default: `codex`).

4. **CapabilityStatus.EXTERNAL** — New status enum value allows distinction from native VERIFIED/PROVISIONAL skills in routing logic.

5. **Bridge is supplementary, not replacement** — ILMA's 154 native skills + 260 Hermes skills remain primary. External skills are fallback/extended options only.

---

## Update 2026-11-01: Full Integration Complete

**Changes made to complete the integration:**

| File | Change |
|------|--------|
| `ilma_external_skills_bridge.py` | Fixed `is_compatible()` to default permissive when `plugin.targets` missing; derive `id` from `path`/`name`; resolve `file_path` from `agentic-awesome-skills` source (~30 lines) |
| `ilma.py` | Added boot steps 13 & 14: load bridge + extend capability registry with 3,116 external skills (~60 lines) |

**Results verified:**
- External skills loaded: **3,116** (was 4 — broken filter)
- External capabilities in registry: **3,077** (was 0)
- `route_capability('ext_plan-writing')` → `external_skill:plan-writing` ✅
- `ilma.py --status` shows bridge + capabilities ✅
- Runtime wiring: 38/38 modules OK

**Risk:** External skills remain read-only; if `/root/project/AgentEnhancements` is removed/moved, bridge degrades gracefully (logs warning, returns empty). No ILMA core dependency.