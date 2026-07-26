#!/usr/bin/env python3
"""
ILMA Skill Indexer
Lexically indexes 9000+ skills into a JSONL database for rapid O(1) resolution.
"""

import os
import json
from pathlib import Path
import hashlib

SKILLS_DIR = Path("/root/.hermes/profiles/ilma/skills")
INDEX_PATH = Path("/root/.hermes/profiles/ilma/skill_index_manifest.jsonl")

def extract_metadata(content: str) -> dict:
    meta = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            import yaml
            try:
                meta = yaml.safe_load(parts[1]) or {}
            except Exception:
                pass
    return meta

def index_skills():
    print(f"Indexing skills in {SKILLS_DIR}...")
    skills = []
    
    # We will walk and parse SKILL.md
    for skill_file in SKILLS_DIR.rglob("SKILL.md"):
        try:
            content = skill_file.read_text(errors="ignore")
            meta = extract_metadata(content)
            
            # Simple domain guessing if not explicit
            domain = meta.get("domain", "GENERAL")
            if "tags" in meta:
                tags = [str(t).lower() for t in meta["tags"]]
                if "writing" in tags: domain = "WRITING"
                elif "research" in tags: domain = "RESEARCH"
                elif "coding" in tags or "development" in tags: domain = "CODING"
                elif "security" in tags or "pentest" in tags: domain = "SECURITY"
                elif "ui" in tags or "ux" in tags: domain = "UIUX"
                elif "data" in tags: domain = "DATA"
            
            # Additional fallback based on path
            path_str = str(skill_file).lower()
            if "security" in path_str: domain = "SECURITY"
            elif "writing" in path_str: domain = "WRITING"
            elif "software" in path_str: domain = "CODING"
            
            record = {
                "skill_path": str(skill_file.relative_to(SKILLS_DIR)),
                "skill_name": meta.get("name", skill_file.parent.name),
                "description": meta.get("description", "")[:200],
                "domain_tags": domain,
                "risk_level": "high" if domain == "SECURITY" else "low",
                "checksum": hashlib.md5(content.encode()).hexdigest()[:8],
                "callable_status": "ready"
            }
            skills.append(record)
        except Exception as e:
            pass

    print(f"Indexed {len(skills)} skills.")
    with open(INDEX_PATH, "w") as f:
        for s in skills:
            f.write(json.dumps(s) + "\n")
    print(f"Index written to {INDEX_PATH}")

if __name__ == "__main__":
    index_skills()
