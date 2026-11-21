"""agentic-awesome-skills plugin for Hermes Agent.

This plugin registers 2,884+ reusable AI agent skills for use with Hermes.
Skills are loaded on-demand via skill_view() with the 'aas:' namespace.
"""

import os
from pathlib import Path

def _skills_dir() -> str:
    """Locate the skills directory."""
    here = os.path.dirname(os.path.realpath(__file__))
    candidates = (
        os.path.realpath(os.path.join(here, "skills")),
        os.path.realpath(os.path.join(here, "..", "skills")),
    )
    for cand in candidates:
        if os.path.isdir(cand) and os.listdir(cand):
            return cand
    raise RuntimeError(
        "agentic-awesome-skills plugin: cannot find the skills/ tree "
        f"(looked at {candidates})."
    )

def register(ctx):
    skills_dir = _skills_dir()
    
    # Register every stock skill with Hermes' native loader
    for name in sorted(os.listdir(skills_dir)):
        skill_md = os.path.join(skills_dir, name, "SKILL.md")
        if os.path.isfile(skill_md):
            try:
                with open(skill_md, encoding="utf-8") as f:
                    content = f.read()
                # Extract description from frontmatter
                description = ""
                if content.startswith("---"):
                    end = content.find("---", 3)
                    if end != -1:
                        frontmatter = content[3:end]
                        for line in frontmatter.splitlines():
                            if line.startswith("description:"):
                                description = line.split(":", 1)[1].strip().strip('"\'')
                                break
                ctx.register_skill(f"aas:{name}", Path(skill_md), description=description)
            except Exception:
                pass  # Skip invalid skills silently