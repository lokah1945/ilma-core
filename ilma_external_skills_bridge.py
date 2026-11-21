#!/usr/bin/env python3
"""
ILMA External Skills Bridge — Phase 73+ Integration
====================================================
Consumes skills from /root/agent-enhancements/unified-integration/skills/
WITHOUT modifying the original project.

Design: Read-only bridge. ILMA's native skills (154) + Hermes skills (260) 
remain primary. External skills (2884) are supplementary — available via 
capability registry and skill router as fallback/extended options.
"""

import json
import os
import re
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from functools import lru_cache

# Configure module logger
_logger = logging.getLogger(__name__)

# ─── Configuration ──────────────────────────────────────────────────────────
EXTERNAL_SKILLS_ROOT = Path(os.environ.get(
    "AGENT_ENHANCEMENTS_BASE_DIR", 
    "/root/project/AgentEnhancements"
))

EXTERNAL_SKILLS_INDEX = EXTERNAL_SKILLS_ROOT / "unified-integration" / "skills" / "all-skills.json"
EXTERNAL_SKILLS_BY_CATEGORY = EXTERNAL_SKILLS_ROOT / "unified-integration" / "skills" / "by-category"
# Actual skills source (agentic-awesome-skills)
EXTERNAL_SKILLS_SOURCE = EXTERNAL_SKILLS_ROOT / "agentic-awesome-skills" / "skills"

# ─── Data Classes ───────────────────────────────────────────────────────────

@dataclass
class ExternalSkill:
    """External skill from agent-enhancements project."""
    id: str
    name: str
    path: str
    category: str
    description: str
    risk: str
    source: str
    date_added: str
    plugin: Dict[str, Any] = field(default_factory=dict)
    tools: List[str] = field(default_factory=list)
    when_to_use: str = ""
    tags: List[str] = field(default_factory=list)
    file_path: Optional[str] = None  # Resolved absolute path to SKILL.md
    
    def is_compatible(self, agent: str = "codex") -> bool:
        """Check if skill is compatible with target agent."""
        # If plugin.targets exists, use it for filtering
        targets = self.plugin.get("targets") if self.plugin else None
        if targets:
            if isinstance(targets, dict):
                return targets.get(agent, "").lower() in ("supported", "yes", "true")
            if isinstance(targets, list):
                return agent in targets
        # If no targets specified, default permissive (skill works for all agents)
        return True

    def get_trigger_keywords(self) -> List[str]:
        """Extract trigger keywords from when_to_use and tags."""
        keywords = []
        if self.when_to_use:
            keywords.extend(re.findall(r'\b\w+\b', self.when_to_use.lower()))
        keywords.extend([t.lower() for t in self.tags])
        return list(set(keywords))


@dataclass
class SkillMatch:
    """Result of skill matching."""
    skill: ExternalSkill
    score: float
    matched_keywords: List[str]


# ─── Bridge Class ───────────────────────────────────────────────────────────

class ExternalSkillsBridge:
    """
    Read-only bridge to /root/agent-enhancements unified skills index.
    
    Does NOT modify the source project. Provides:
    - Skill discovery by keyword/task
    - Skill content loading (reads SKILL.md from source)
    - Integration hooks for ILMA capability registry
    - Fallback chain extension for capabilities
    """
    
    def __init__(self, target_agent: str = "codex"):
        self.target_agent = target_agent
        self._skills: List[ExternalSkill] = []
        self._index: Dict[str, ExternalSkill] = {}
        self._by_category: Dict[str, List[ExternalSkill]] = {}
        self._loaded = False
        
    def load(self) -> bool:
        """Load the external skills index. Returns True if successful."""
        if self._loaded:
            return True
            
        if not EXTERNAL_SKILLS_INDEX.exists():
            _logger.warning(f"External skills index not found: {EXTERNAL_SKILLS_INDEX}")
            return False
            
        try:
            with open(EXTERNAL_SKILLS_INDEX, 'r') as f:
                data = json.load(f)
            
            skills_data = data.get("skills", [])
            _logger.info(f"Loading {len(skills_data)} external skills from {EXTERNAL_SKILLS_INDEX}")
            
            for s in skills_data:
                # Use directory name from path as ID (path points to SKILL.md, so parent dir is the skill id)
                if s.get("id"):
                    skill_id = s.get("id")
                elif s.get("path"):
                    # Path is like "unified-integration/skills/by-category/general/python-fastapi-development/SKILL.md"
                    # Skill ID is the parent directory name
                    skill_id = s.get("path").split("/")[-2]
                else:
                    skill_id = s.get("name", "").lower().replace(" ", "-")
                
                skill = ExternalSkill(
                    id=skill_id,
                    name=s.get("name", ""),
                    path=s.get("path", ""),
                    category=s.get("category", ""),
                    description=s.get("description", ""),
                    risk=s.get("risk", "unknown"),
                    source=s.get("source", "external"),
                    date_added=s.get("date_added", ""),
                    plugin=s.get("plugin", {}),
                    tools=s.get("tools", []),
                    when_to_use=s.get("when_to_use", ""),
                    tags=s.get("tags", []),
                )
                
                # Resolve absolute file path to SKILL.md using the skill ID (directory name)
                if skill.id:
                    # Primary: agentic-awesome-skills/skills/<id>/SKILL.md
                    candidate = EXTERNAL_SKILLS_SOURCE / skill.id / "SKILL.md"
                    if candidate.exists():
                        skill.file_path = str(candidate)
                    else:
                        # Fallback: try the path from index
                        if skill.path:
                            candidate2 = EXTERNAL_SKILLS_ROOT / skill.path / "SKILL.md"
                            if candidate2.exists():
                                skill.file_path = str(candidate2)

                # Only index skills compatible with target agent
                if skill.is_compatible(self.target_agent):
                    self._skills.append(skill)
                    self._index[skill.id] = skill
                    self._index[skill.name] = skill
                    
                    cat = skill.category or "uncategorized"
                    if cat not in self._by_category:
                        self._by_category[cat] = []
                    self._by_category[cat].append(skill)
            
            self._loaded = True
            _logger.info(f"Loaded {len(self._skills)} compatible external skills for agent '{self.target_agent}'")
            return True
            
        except Exception as e:
            _logger.error(f"Failed to load external skills: {e}")
            return False
    
    def get_skill(self, skill_id: str) -> Optional[ExternalSkill]:
        """Get a skill by ID or name."""
        if not self._loaded:
            self.load()
        return self._index.get(skill_id)
    
    def get_skills_by_category(self, category: str) -> List[ExternalSkill]:
        """Get all skills in a category."""
        if not self._loaded:
            self.load()
        return self._by_category.get(category, [])
    
    def get_all_skills(self) -> List[ExternalSkill]:
        """Get all loaded skills."""
        if not self._loaded:
            self.load()
        return self._skills
    
    def find_skills_for_task(self, task_description: str, max_results: int = 10) -> List[SkillMatch]:
        """
        Find relevant skills for a task description.
        Uses keyword matching on when_to_use, tags, description.
        """
        if not self._loaded:
            self.load()
        
        task_lower = task_description.lower()
        task_keywords = set(re.findall(r'\b\w+\b', task_lower))
        
        matches = []
        for skill in self._skills:
            matched = []
            score = 0.0
            
            # Match when_to_use (highest weight)
            when_keywords = set(skill.get_trigger_keywords())
            overlap = task_keywords & when_keywords
            if overlap:
                score += len(overlap) * 3.0
                matched.extend(overlap)
            
            # Match description
            desc_words = set(re.findall(r'\b\w+\b', skill.description.lower()))
            overlap = task_keywords & desc_words
            if overlap:
                score += len(overlap) * 1.5
                matched.extend(overlap)
            
            # Match category
            if skill.category.lower() in task_lower:
                score += 2.0
                matched.append(skill.category)
            
            # Boost for low-risk skills (prefer safe skills)
            if skill.risk == "safe":
                score += 1.0
            elif skill.risk == "critical":
                score -= 2.0
            
            if score > 0:
                matches.append(SkillMatch(
                    skill=skill,
                    score=score,
                    matched_keywords=list(set(matched))
                ))
        
        # Sort by score descending
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:max_results]
    
    def load_skill_content(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """
        Load and parse the SKILL.md content for a skill.
        Returns dict with frontmatter and body, or None if not found.
        """
        skill = self.get_skill(skill_id)
        if not skill or not skill.file_path:
            return None
        
        try:
            content = Path(skill.file_path).read_text(encoding='utf-8')
            
            # Parse YAML frontmatter
            frontmatter = {}
            body = content
            
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    import yaml
                    try:
                        frontmatter = yaml.safe_load(parts[1]) or {}
                    except Exception:
                        pass
                    body = parts[2].strip()
            
            return {
                "skill_id": skill.id,
                "skill_name": skill.name,
                "category": skill.category,
                "source": "external",
                "file_path": skill.file_path,
                "frontmatter": frontmatter,
                "body": body,
            }
        except Exception as e:
            _logger.error(f"Failed to load skill content for {skill_id}: {e}")
            return None
    
    def get_capability_extensions(self) -> List[Dict[str, Any]]:
        """
        Generate capability registry extensions from external skills.
        Maps external skills to ILMA capability categories for fallback chain.
        """
        if not self._loaded:
            self.load()
        
        extensions = []
        
        # Map external categories to ILMA capability categories
        category_map = {
            "ai-ml": "analytical",
            "architecture": "cognitive",
            "code-review": "analytical",
            "devops": "operational",
            "documentation": "creative",
            "general": "cognitive",
            "productivity": "executive",
            "refactoring": "operational",
            "security": "security",
            "testing": "analytical",
        }
        
        for skill in self._skills:
            ilma_category = category_map.get(skill.category, "cognitive")
            
            # Create a capability entry that can be registered
            ext = {
                "external_id": skill.id,
                "name": f"ext_{skill.id}",
                "category": ilma_category,
                "status": "external",
                "description": skill.description,
                "primary_tool": f"external_skill:{skill.id}",
                "fallback_tools": [],
                "script_fallback": skill.file_path,
                "evidence_id": f"external_{skill.id}_{skill.date_added.replace('-', '')}",
                "risk_level": skill.risk,
                "tags": skill.tags + ["external", "agent-enhancements"],
                "metadata": {
                    "source": "agent-enhancements",
                    "original_category": skill.category,
                    "tools": skill.tools,
                    "when_to_use": skill.when_to_use,
                }
            }
            extensions.append(ext)
        
        return extensions
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        if not self._loaded:
            self.load()
        
        by_risk = {}
        by_category = {}
        
        for skill in self._skills:
            by_risk[skill.risk] = by_risk.get(skill.risk, 0) + 1
            cat = skill.category or "uncategorized"
            by_category[cat] = by_category.get(cat, 0) + 1
        
        return {
            "total_skills": len(self._skills),
            "by_risk": by_risk,
            "by_category": by_category,
            "index_path": str(EXTERNAL_SKILLS_INDEX),
            "target_agent": self.target_agent,
        }


# ─── Global Instance & Helpers ──────────────────────────────────────────────

_bridge: Optional[ExternalSkillsBridge] = None
_bridge_lock = __import__("threading").Lock()

def get_external_skills_bridge(target_agent: str = "codex") -> ExternalSkillsBridge:
    """Get the global external skills bridge singleton."""
    global _bridge
    if _bridge is None:
        with _bridge_lock:
            if _bridge is None:
                _bridge = ExternalSkillsBridge(target_agent)
                _bridge.load()
    return _bridge


def find_external_skills_for_task(task: str, max_results: int = 10) -> List[SkillMatch]:
    """Convenience function: find external skills relevant to a task."""
    bridge = get_external_skills_bridge()
    return bridge.find_skills_for_task(task, max_results)


def load_external_skill_content(skill_id: str) -> Optional[Dict[str, Any]]:
    """Convenience function: load SKILL.md content for an external skill."""
    bridge = get_external_skills_bridge()
    return bridge.load_skill_content(skill_id)


def extend_capability_registry_with_external() -> List[Dict[str, Any]]:
    """Get capability registry extensions from external skills."""
    bridge = get_external_skills_bridge()
    return bridge.get_capability_extensions()


# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    """CLI for testing the bridge."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ILMA External Skills Bridge")
    parser.add_argument("--agent", default="codex", help="Target agent (codex, claude, etc.)")
    parser.add_argument("--task", help="Task description to find skills for")
    parser.add_argument("--skill", help="Load specific skill content by ID")
    parser.add_argument("--stats", action="store_true", help="Show bridge statistics")
    parser.add_argument("--list-categories", action="store_true", help="List all categories")
    parser.add_argument("--max-results", type=int, default=10, help="Max results for task search")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    bridge = get_external_skills_bridge(args.agent)
    
    if args.stats:
        stats = bridge.get_stats()
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print(f"Total skills: {stats['total_skills']}")
            print(f"By risk: {stats['by_risk']}")
            print(f"By category: {stats['by_category']}")
        return
    
    if args.list_categories:
        cats = sorted(bridge._by_category.keys())
        if args.json:
            print(json.dumps(cats, indent=2))
        else:
            for c in cats:
                print(f"  {c}: {len(bridge._by_category[c])} skills")
        return
    
    if args.skill:
        content = bridge.load_skill_content(args.skill)
        if args.json:
            print(json.dumps(content, indent=2, default=str))
        else:
            if content:
                print(f"Skill: {content['skill_name']}")
                print(f"Category: {content['category']}")
                print(f"File: {content['file_path']}")
                print(f"Frontmatter: {content['frontmatter']}")
                print(f"Body (first 500 chars): {content['body'][:500]}...")
            else:
                print(f"Skill not found: {args.skill}")
        return
    
    if args.task:
        matches = bridge.find_skills_for_task(args.task, args.max_results)
        if args.json:
            print(json.dumps([
                {
                    "skill_id": m.skill.id,
                    "skill_name": m.skill.name,
                    "category": m.skill.category,
                    "risk": m.skill.risk,
                    "score": m.score,
                    "matched_keywords": m.matched_keywords,
                    "description": m.skill.description[:200],
                }
                for m in matches
            ], indent=2))
        else:
            print(f"Found {len(matches)} matching skills for: {args.task}")
            for i, m in enumerate(matches, 1):
                print(f"\n{i}. {m.skill.name} ({m.skill.category}) - Score: {m.score:.1f}")
                print(f"   Risk: {m.skill.risk} | Keywords: {', '.join(m.matched_keywords[:5])}")
                print(f"   {m.skill.description[:150]}...")
        return
    
    parser.print_help()


if __name__ == "__main__":
    main()