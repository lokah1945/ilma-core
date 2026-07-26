#!/usr/bin/env python3
"""
ILMA Skill Resolver
Domain-aware resolution of skills from the lexical index.
"""

import json
from pathlib import Path
from typing import Dict, Any, List

INDEX_PATH = Path("/root/.hermes/profiles/ilma/skill_index_manifest.jsonl")

class SkillResolver:
    def __init__(self):
        self.skills = []
        if INDEX_PATH.exists():
            with open(INDEX_PATH, "r") as f:
                for line in f:
                    if line.strip():
                        self.skills.append(json.loads(line))

    def resolve(self, intent: str, domain: str) -> Dict[str, Any]:
        """Find the best skill for a given task profile."""
        
        candidates = [s for s in self.skills if s.get("domain_tags") == domain]
        
        if not candidates:
            # Fallback to lexical match on description/name
            intent_lower = intent.lower()
            for s in self.skills:
                if any(w in s.get("skill_name", "").lower() for w in intent_lower.split()):
                    candidates.append(s)
        
        if not candidates:
            return {"status": "fallback", "reason": "No exact match", "skill": None}

        # Just pick the first matched candidate for simplicity
        chosen = candidates[0]
        return {
            "status": "success",
            "reason": f"Matched domain {domain} or keywords",
            "skill": chosen
        }

def get_skill_resolver() -> SkillResolver:
    return SkillResolver()
