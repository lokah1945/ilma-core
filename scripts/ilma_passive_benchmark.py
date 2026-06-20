#!/usr/bin/env python3
"""
ILMA Passive Benchmark Research v1.0
====================================
Continuous benchmark intelligence gathering and competitive analysis.

Based on: ILMA passive_benchmark_research.py patterns (150KB)
"""
import os
import sys
import json
import time
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field

WORKSPACE = Path("/root/.hermes/profiles/ilma")
BENCHMARK_DIR = WORKSPACE / ".benchmark"
BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# BENCHMARK DATA
# ============================================================================

@dataclass
class ComponentBenchmark:
    name: str
    component_type: str  # script, skill, fabric
    size_bytes: int = 0
    lines_of_code: int = 0
    complexity: float = 0.0
    features: List[str] = field(default_factory=list)
    quality_score: float = 0.0
    last_updated: str = ""

class PassiveBenchmarkResearch:
    """
    Passive benchmark research system.
    Continuously collects and analyzes competitive intelligence.
    """
    
    def __init__(self):
        self.ilma_base = WORKSPACE
        self.ILMA_base = Path("/root/.hermes/profiles/ilma")
        self.cache = {}
        self.cache_ttl = 300
    
    def count_components(self, base_path: Path, pattern: str = "*.py") -> Dict:
        """Count components in a directory."""
        if not base_path.exists():
            return {"count": 0, "total_size": 0, "total_lines": 0}
        
        files = list(base_path.rglob(pattern))
        
        total_size = 0
        total_lines = 0
        
        for f in files:
            if f.is_file():
                try:
                    total_size += f.stat().st_size
                    with open(f) as fp:
                        total_lines += len(fp.readlines())
                except IOError:
                    pass
        
        return {
            "count": len(files),
            "total_size": total_size,
            "total_lines": total_lines
        }
    
    def analyze_script(self, script_path: Path) -> Dict:
        """Analyze a single script."""
        if not script_path.exists():
            return {}
        
        try:
            with open(script_path) as f:
                content = f.read()
            
            lines = content.split("\n")
            
            # Count functions, classes, etc.
            functions = len(re.findall(r"^def\s+\w+", content, re.MULTILINE))
            classes = len(re.findall(r"^class\s+\w+", content, re.MULTILINE))
            imports = len(re.findall(r"^import\s+|^from\s+\w+\s+import", content, re.MULTILINE))
            
            # Calculate complexity
            complexity = (functions * 0.3 + classes * 0.5 + imports * 0.2) / 10
            
            return {
                "name": script_path.name,
                "size": script_path.stat().st_size,
                "lines": len(lines),
                "functions": functions,
                "classes": classes,
                "imports": imports,
                "complexity": min(complexity, 10.0)
            }
        except Exception:
            return {}
    
    def analyze_skill(self, skill_path: Path) -> Dict:
        """Analyze a skill directory."""
        skill_meta = skill_path / "SKILL.md"
        if not skill_meta.exists():
            return {}
        
        try:
            with open(skill_meta) as f:
                content = f.read()
            
            # Parse frontmatter
            metadata = {}
            if content.startswith("---"):
                lines = content.split("\n")
                end_idx = 0
                for i, line in enumerate(lines[1:], 1):
                    if line.strip() == "---":
                        end_idx = i
                        break
                if end_idx > 0:
                    for line in lines[1:end_idx]:
                        if ":" in line:
                            k, v = line.split(":", 1)
                            metadata[k.strip()] = v.strip()
            
            # Count linked files
            linked_files = list(skill_path.rglob("*"))
            linked_files = [f for f in linked_files if f.is_file() and f.name != "SKILL.md"]
            
            return {
                "name": skill_path.name,
                "has_description": bool(metadata.get("description")),
                "has_trigger": bool(metadata.get("trigger")),
                "category": metadata.get("category", "unknown"),
                "linked_files": len(linked_files),
                "size": sum(f.stat().st_size for f in linked_files if f.is_file())
            }
        except Exception:
            return {}
    
    def analyze_fabric_module(self, module_path: Path) -> Dict:
        """Analyze a fabric module."""
        if not module_path.is_dir():
            return {}
        
        py_files = list(module_path.rglob("*.py"))
        total_lines = 0
        total_size = 0
        
        for f in py_files:
            try:
                with open(f) as fp:
                    total_lines += len(fp.readlines())
                total_size += f.stat().st_size
            except Exception:
                pass
        
        return {
            "name": module_path.name,
            "files": len(py_files),
            "lines": total_lines,
            "size": total_size
        }
    
    def benchmark_ilma(self) -> Dict:
        """Full ILMA benchmark."""
        results = {
            "timestamp": datetime.now().isoformat(),
            "source": "ilma"
        }
        
        # Scripts
        scripts_dir = self.ilma_base / "scripts"
        if scripts_dir.exists():
            script_stats = self.count_components(scripts_dir)
            
            # Analyze individual scripts
            script_details = []
            for script in scripts_dir.glob("*.py"):
                detail = self.analyze_script(script)
                if detail:
                    script_details.append(detail)
            
            results["scripts"] = {
                "count": script_stats["count"],
                "total_size": script_stats["total_size"],
                "total_lines": script_stats["total_lines"],
                "details": script_details[:20]  # Top 20
            }
        
        # Skills
        skills_dir = self.ilma_base / "skills"
        if skills_dir.exists():
            skill_stats = self.count_components(skills_dir, "*")
            
            skill_details = []
            for skill in skills_dir.iterdir():
                if skill.is_dir():
                    detail = self.analyze_skill(skill)
                    if detail:
                        skill_details.append(detail)
            
            # Count by category
            categories = {}
            for s in skill_details:
                cat = s.get("category", "unknown")
                categories[cat] = categories.get(cat, 0) + 1
            
            results["skills"] = {
                "count": len(skill_details),
                "categories": categories,
                "details": skill_details[:30]
            }
        
        # Fabric
        fabric_dir = self.ilma_base / "fabric"
        if fabric_dir.exists():
            fabric_details = []
            for module in fabric_dir.iterdir():
                if module.is_dir():
                    detail = self.analyze_fabric_module(module)
                    if detail:
                        fabric_details.append(detail)
            
            results["fabric"] = {
                "modules": len(fabric_details),
                "details": fabric_details
            }
        
        return results
    
    def benchmark_ILMA(self) -> Dict:
        """Full ILMA benchmark (reference)."""
        results = {
            "timestamp": datetime.now().isoformat(),
            "source": "ILMA"
        }
        
        # Scripts
        scripts_dir = self.ILMA_base / "scripts"
        if scripts_dir.exists():
            script_stats = self.count_components(scripts_dir)
            
            # Analyze top scripts by size
            all_scripts = list(scripts_dir.glob("*.py"))
            all_scripts.sort(key=lambda x: x.stat().st_size, reverse=True)
            
            script_details = []
            for script in all_scripts[:20]:
                detail = self.analyze_script(script)
                if detail:
                    script_details.append(detail)
            
            results["scripts"] = {
                "count": script_stats["count"],
                "total_size": script_stats["total_size"],
                "total_lines": script_stats["total_lines"],
                "details": script_details
            }
        
        # Skills
        skills_dir = self.ILMA_base / "skills"
        if skills_dir.exists():
            skill_details = []
            for skill in skills_dir.iterdir():
                if skill.is_dir():
                    detail = self.analyze_skill(skill)
                    if detail:
                        skill_details.append(detail)
            
            categories = {}
            for s in skill_details:
                cat = s.get("category", "unknown")
                categories[cat] = categories.get(cat, 0) + 1
            
            results["skills"] = {
                "count": len(skill_details),
                "categories": categories,
                "details": skill_details[:30]
            }
        
        # Fabric
        fabric_dir = self.ILMA_base / "fabric"
        if fabric_dir.exists():
            fabric_details = []
            for module in fabric_dir.iterdir():
                if module.is_dir():
                    detail = self.analyze_fabric_module(module)
                    if detail:
                        fabric_details.append(detail)
            
            results["fabric"] = {
                "modules": len(fabric_details),
                "details": fabric_details
            }
        
        return results
    
    def compare(self, ilma: Dict, ILMA: Dict) -> Dict:
        """Compare ILMA vs ILMA."""
        comparison = {
            "timestamp": datetime.now().isoformat(),
            "ilma": {},
            "ILMA": {},
            "winner": {}
        }
        
        # Scripts
        ilma_scripts = ilma.get("scripts", {})
        ILMA_scripts = ILMA.get("scripts", {})
        
        comparison["ilma"]["scripts"] = ilma_scripts.get("count", 0)
        comparison["ILMA"]["scripts"] = ILMA_scripts.get("count", 0)
        comparison["winner"]["scripts"] = "ilma" if ilma_scripts.get("count", 0) >= ILMA_scripts.get("count", 0) else "ILMA"
        comparison["ilma"]["script_lines"] = ilma_scripts.get("total_lines", 0)
        comparison["ILMA"]["script_lines"] = ILMA_scripts.get("total_lines", 0)
        
        # Skills
        ilma_skills = ilma.get("skills", {})
        ILMA_skills = ILMA.get("skills", {})
        
        comparison["ilma"]["skills"] = ilma_skills.get("count", 0)
        comparison["ILMA"]["skills"] = ILMA_skills.get("count", 0)
        comparison["winner"]["skills"] = "ilma" if ilma_skills.get("count", 0) >= ILMA_skills.get("count", 0) else "ILMA"
        
        # Fabric
        ilma_fabric = ilma.get("fabric", {})
        ILMA_fabric = ILMA.get("fabric", {})
        
        comparison["ilma"]["fabric"] = ilma_fabric.get("modules", 0)
        comparison["ILMA"]["fabric"] = ILMA_fabric.get("modules", 0)
        comparison["winner"]["fabric"] = "ilma" if ilma_fabric.get("modules", 0) >= ILMA_fabric.get("modules", 0) else "ILMA"
        
        # Total
        ilma_total = ilma_scripts.get("count", 0) + ilma_skills.get("count", 0) + ilma_fabric.get("modules", 0)
        ILMA_total = ILMA_scripts.get("count", 0) + ILMA_skills.get("count", 0) + ILMA_fabric.get("modules", 0)
        
        comparison["ilma"]["total"] = ilma_total
        comparison["ILMA"]["total"] = ILMA_total
        comparison["winner"]["total"] = "ilma" if ilma_total >= ILMA_total else "ILMA"
        comparison["ilma_lead"] = ilma_total - ILMA_total
        
        return comparison
    
    def run_full_benchmark(self) -> Dict:
        """Run full benchmark comparison."""
        print("Running ILMA benchmark...")
        ilma = self.benchmark_ilma()
        
        print("Running ILMA benchmark...")
        ILMA = self.benchmark_ILMA()
        
        print("Comparing...")
        comparison = self.compare(ilma, ILMA)
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        ilma_file = BENCHMARK_DIR / f"ilma_{timestamp}.json"
        ILMA_file = BENCHMARK_DIR / f"ILMA_{timestamp}.json"
        comparison_file = BENCHMARK_DIR / f"comparison_{timestamp}.json"
        
        with open(ilma_file, "w") as f:
            json.dump(ilma, f, indent=2)
        with open(ILMA_file, "w") as f:
            json.dump(ILMA, f, indent=2)
        with open(comparison_file, "w") as f:
            json.dump(comparison, f, indent=2)
        
        comparison["ilma_benchmark_file"] = str(ilma_file)
        comparison["ILMA_benchmark_file"] = str(ILMA_file)
        
        return comparison


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="ILMA Passive Benchmark Research")
    parser.add_argument("command", nargs="?", default="compare",
                        choices=["ilma", "ILMA", "compare", "history"])
    parser.add_argument("--full", action="store_true", help="Run full benchmark")
    
    pbr = PassiveBenchmarkResearch()
    args = parser.parse_args()
    
    if args.command == "ilma":
        result = pbr.benchmark_ilma()
        print(json.dumps(result, indent=2))
    
    elif args.command == "ILMA":
        result = pbr.benchmark_ILMA()
        print(json.dumps(result, indent=2))
    
    elif args.command == "compare" or args.full:
        result = pbr.run_full_benchmark()
        print(json.dumps(result, indent=2))
    
    elif args.command == "history":
        # Show recent comparisons
        comparisons = sorted(BENCHMARK_DIR.glob("comparison_*.json"), 
                          key=lambda x: x.stat().st_mtime, reverse=True)[:5]
        for c in comparisons:
            print(f"  {c.name}")

if __name__ == "__main__":
    main()
