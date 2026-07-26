#!/usr/bin/env python3
"""
ILMA Meta Skill Orchestrator v1.0
=================================
Orchestrates skill selection, chaining, and optimization.

Based on: ILMA meta_skill_orchestrator.py patterns
"""
import os
import sys
import json
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime

WORKSPACE = Path("/root/.hermes/profiles/ilma")
SKILLS_DIR = WORKSPACE / "skills"
CACHE_DIR = WORKSPACE / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# In-memory skill index
_skill_index = None
_skill_index_mtime = 0
_INDEX_CACHE_TTL = 300

# ============================================================================
# SKILL INDEX
# ============================================================================

class SkillIndex:
    """
    Index of all available skills with metadata.
    """
    
    def __init__(self):
        self.skills = {}
        self.keywords_index = {}  # keyword -> [skill_names]
        self.category_index = {}   # category -> [skill_names]
        self.load()
    
    def load(self):
        """Load skill index from disk."""
        if not SKILLS_DIR.exists():
            return
        
        for skill_path in SKILLS_DIR.iterdir():
            if not skill_path.is_dir():
                continue
            
            skill_name = skill_path.name
            skill_meta = skill_path / "SKILL.md"
            
            if not skill_meta.exists():
                continue
            
            try:
                with open(skill_meta) as f:
                    content = f.read()
                
                # Parse frontmatter
                metadata = self._parse_frontmatter(content)
                
                # Index skill
                self.skills[skill_name] = {
                    "name": skill_name,
                    "path": str(skill_path),
                    "description": metadata.get("description", ""),
                    "category": metadata.get("category", "general"),
                    "trigger": metadata.get("trigger", ""),
                    "commands": metadata.get("commands", []),
                    "keywords": metadata.get("keywords", []),
                    "loaded_at": metadata.get("loaded_at", "")
                }
                
                # Build keyword index
                for keyword in metadata.get("keywords", []):
                    if keyword not in self.keywords_index:
                        self.keywords_index[keyword] = []
                    self.keywords_index[keyword].append(skill_name)
                
                # Build category index
                category = metadata.get("category", "general")
                if category not in self.category_index:
                    self.category_index[category] = []
                self.category_index[category].append(skill_name)
            
            except Exception as e:
                print(f"Warning: Failed to load skill {skill_name}: {e}")
    
    def _parse_frontmatter(self, content: str) -> Dict:
        """Parse YAML frontmatter from SKILL.md."""
        if not content.startswith("---"):
            return {}
        
        try:
            lines = content.split("\n")
            end_idx = 0
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    end_idx = i
                    break
            
            if end_idx == 0:
                return {}
            
            frontmatter = "\n".join(lines[1:end_idx])
            metadata = {}
            
            for line in frontmatter.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip()] = value.strip()
            
            return metadata
        except Exception:
            return {}
    
    def search(self, query: str, limit: int = 5) -> List[Tuple[str, float]]:
        """
        Search skills by query using keyword matching.
        Returns: [(skill_name, score), ...]
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        scores = {}
        
        for skill_name, skill_data in self.skills.items():
            score = 0.0
            
            # Check description
            desc = skill_data.get("description", "").lower()
            if query_lower in desc:
                score += 3.0
            
            # Check keywords
            for kw in skill_data.get("keywords", []):
                if kw.lower() in query_lower:
                    score += 2.0
                elif query_lower in kw.lower():
                    score += 1.5
            
            # Check trigger
            trigger = skill_data.get("trigger", "").lower()
            if trigger and trigger in query_lower:
                score += 4.0
            
            # Check name
            if skill_name.replace("ilma-", "").replace("-", " ") in query_lower:
                score += 2.5
            
            if score > 0:
                scores[skill_name] = score
        
        # Sort by score
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:limit]
    
    def get_skill(self, name: str) -> Optional[Dict]:
        """Get skill data by name."""
        return self.skills.get(name)
    
    def list_by_category(self, category: str) -> List[str]:
        """List all skills in a category."""
        return self.category_index.get(category, [])
    
    def get_stats(self) -> Dict:
        """Get index statistics."""
        return {
            "total_skills": len(self.skills),
            "categories": len(self.category_index),
            "keywords": len(self.keywords_index),
            "skills_by_category": {
                cat: len(skills) for cat, skills in self.category_index.items()
            }
        }


# ============================================================================
# SKILL CHAINER
# ============================================================================

class SkillChainer:
    """
    Chains multiple skills together for complex workflows.
    """
    
    def __init__(self):
        self.chains = {}
        self.history = []
    
    def create_chain(self, name: str, skill_sequence: List[str], 
                     description: str = "") -> Dict:
        """Create a skill chain."""
        chain_id = f"chain_{int(time.time())}"
        
        chain = {
            "id": chain_id,
            "name": name,
            "description": description,
            "skills": skill_sequence,
            "created_at": datetime.now().isoformat(),
            "usage_count": 0
        }
        
        self.chains[chain_id] = chain
        return {"ok": True, "chain_id": chain_id, "chain": chain}
    
    def execute_chain(self, chain_id: str, context: Dict = None) -> Dict:
        """Execute a skill chain."""
        if chain_id not in self.chains:
            return {"ok": False, "error": "Chain not found"}
        
        chain = self.chains[chain_id]
        chain["usage_count"] += 1
        
        results = []
        for skill_name in chain["skills"]:
            # Simulate skill execution
            results.append({
                "skill": skill_name,
                "executed_at": datetime.now().isoformat(),
                "status": "simulated"
            })
        
        return {
            "ok": True,
            "chain_id": chain_id,
            "results": results
        }
    
    def get_chain(self, chain_id: str) -> Optional[Dict]:
        """Get chain by ID."""
        return self.chains.get(chain_id)


# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

class MetaSkillOrchestrator:
    """
    Main orchestrator for skill operations.
    """
    
    def __init__(self):
        self.index = SkillIndex()
        self.chainer = SkillChainer()
    
    def find_skill(self, query: str, limit: int = 5) -> List[Dict]:
        """Find skills matching query."""
        results = self.index.search(query, limit)
        return [
            {
                "name": name,
                "score": score,
                "data": self.index.get_skill(name)
            }
            for name, score in results
        ]
    
    def get_recommended_skills(self, task: str, limit: int = 5) -> List[Dict]:
        """Get recommended skills for a task."""
        return self.find_skill(task, limit)
    
    def create_workflow(self, name: str, skills: List[str], 
                        description: str = "") -> Dict:
        """Create a skill workflow."""
        return self.chainer.create_chain(name, skills, description)
    
    def execute_workflow(self, workflow_id: str, context: Dict = None) -> Dict:
        """Execute a skill workflow."""
        return self.chainer.execute_chain(workflow_id, context)
    
    def get_stats(self) -> Dict:
        """Get orchestrator statistics."""
        return {
            "skill_index": self.index.get_stats(),
            "chains": len(self.chainer.chains),
            "chain_usage": sum(c["usage_count"] for c in self.chainer.chains.values())
        }


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="ILMA Meta Skill Orchestrator")
    parser.add_argument("command", nargs="?", default="stats",
                        choices=["find", "recommend", "chain", "execute", "stats", "list"])
    parser.add_argument("--query", type=str, help="Search query")
    parser.add_argument("--name", type=str, help="Workflow name")
    parser.add_argument("--skills", type=str, help="Comma-separated skill list")
    parser.add_argument("--workflow", type=str, help="Workflow ID")
    parser.add_argument("--limit", type=int, default=5, help="Result limit")
    
    orch = MetaSkillOrchestrator()
    args = parser.parse_args()
    
    if args.command == "find" or args.command == "recommend":
        if not args.query:
            print("Error: --query required")
            sys.exit(1)
        
        results = orch.find_skill(args.query, args.limit)
        print(json.dumps(results, indent=2))
    
    elif args.command == "chain":
        if not args.name or not args.skills:
            print("Error: --name and --skills required")
            sys.exit(1)
        
        skills = [s.strip() for s in args.skills.split(",")]
        result = orch.create_workflow(args.name, skills)
        print(json.dumps(result, indent=2))
    
    elif args.command == "execute":
        if not args.workflow:
            print("Error: --workflow required")
            sys.exit(1)
        
        result = orch.execute_workflow(args.workflow)
        print(json.dumps(result, indent=2))
    
    elif args.command == "stats":
        stats = orch.get_stats()
        print(json.dumps(stats, indent=2))
    
    elif args.command == "list":
        stats = orch.index.get_stats()
        print(f"Total Skills: {stats['total_skills']}")
        print(f"Categories: {stats['categories']}")
        print()
        print("Skills by Category:")
        for cat, count in stats["skills_by_category"].items():
            print(f"  {cat}: {count}")

if __name__ == "__main__":
    main()
