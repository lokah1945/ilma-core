#!/usr/bin/env python3
"""
ILMA Fast Boot v1.0
===================
Fast boot system for quick ILMA startup.

Based on: ILMA fast_boot patterns
"""
import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

WORKSPACE = Path("/root/.hermes/profiles/ilma")
CACHE_DIR = WORKSPACE / ".cache"


class FastBoot:
    """
    Fast boot system for ILMA.
    Preloads components for quick startup.
    """
    
    def __init__(self):
        self.boot_config = {
            "preload_scripts": True,
            "preload_skills": True,
            "preload_cache": True,
            "warmup_mode": "fast"  # fast, complete, minimal
        }
        self.boot_history = []
    
    def check_prerequisites(self) -> Dict:
        """Check if prerequisites are met."""
        checks = {
            "workspace_exists": WORKSPACE.exists(),
            "scripts_dir_exists": (WORKSPACE / "scripts").exists(),
            "skills_dir_exists": (WORKSPACE / "skills").exists(),
            "cache_dir_exists": CACHE_DIR.exists(),
            "python_version": sys.version_info >= (3, 8),
        }
        
        all_passed = all(checks.values())
        
        return {
            "all_passed": all_passed,
            "checks": checks
        }
    
    def preload_scripts(self) -> Dict:
        """Preload scripts into cache."""
        scripts_dir = WORKSPACE / "scripts"
        
        if not scripts_dir.exists():
            return {"loaded": 0, "error": "Scripts directory not found"}
        
        scripts = list(scripts_dir.glob("*.py"))
        
        # Create script index
        script_index = {}
        for script in scripts:
            try:
                with open(script) as f:
                    content = f.read(1000)  # Read first 1KB for header
                
                script_index[script.name] = {
                    "path": str(script),
                    "size": script.stat().st_size,
                    "loaded_at": datetime.now().isoformat()
                }
            except Exception as e:
                pass
        
        # Save index
        cache_file = CACHE_DIR / "script_index.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w") as f:
            json.dump(script_index, f, indent=2)
        
        return {
            "loaded": len(script_index),
            "cache_file": str(cache_file)
        }
    
    def preload_skills(self) -> Dict:
        """Preload skills into cache."""
        skills_dir = WORKSPACE / "skills"
        
        if not skills_dir.exists():
            return {"loaded": 0, "error": "Skills directory not found"}
        
        skills = [d for d in skills_dir.iterdir() if d.is_dir()]
        
        # Create skills index
        skills_index = {}
        for skill in skills:
            skill_meta = skill / "SKILL.md"
            if skill_meta.exists():
                skills_index[skill.name] = {
                    "path": str(skill),
                    "has_meta": True,
                    "loaded_at": datetime.now().isoformat()
                }
        
        # Save index
        cache_file = CACHE_DIR / "skills_index.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w") as f:
            json.dump(skills_index, f, indent=2)
        
        return {
            "loaded": len(skills_index),
            "cache_file": str(cache_file)
        }
    
    def warmup_cache(self) -> Dict:
        """Warm up cache with frequently used data."""
        cache_files = {
            "script_index": CACHE_DIR / "script_index.json",
            "skills_index": CACHE_DIR / "skills_index.json",
        }
        
        loaded = {}
        for name, cache_file in cache_files.items():
            if cache_file.exists():
                try:
                    with open(cache_file) as f:
                        data = json.load(f)
                    loaded[name] = len(data)
                except Exception:
                    loaded[name] = 0
            else:
                loaded[name] = 0
        
        return {
            "cache_warmed": True,
            "loaded_items": loaded
        }
    
    def fast_startup(self) -> Dict:
        """Perform fast startup sequence."""
        start_time = time.time()
        
        results = {
            "start_time": datetime.now().isoformat(),
            "steps": []
        }
        
        # Step 1: Prerequisites check
        prereq = self.check_prerequisites()
        results["steps"].append({
            "name": "prerequisites",
            "passed": prereq["all_passed"],
            "time_ms": 0
        })
        
        if not prereq["all_passed"]:
            results["success"] = False
            results["error"] = "Prerequisites not met"
            return results
        
        # Step 2: Preload scripts
        step_start = time.time()
        scripts = self.preload_scripts()
        results["steps"].append({
            "name": "preload_scripts",
            "loaded": scripts.get("loaded", 0),
            "time_ms": int((time.time() - step_start) * 1000)
        })
        
        # Step 3: Preload skills
        step_start = time.time()
        skills = self.preload_skills()
        results["steps"].append({
            "name": "preload_skills",
            "loaded": skills.get("loaded", 0),
            "time_ms": int((time.time() - step_start) * 1000)
        })
        
        # Step 4: Warmup cache
        step_start = time.time()
        cache = self.warmup_cache()
        results["steps"].append({
            "name": "warmup_cache",
            "loaded": cache.get("loaded_items", {}),
            "time_ms": int((time.time() - step_start) * 1000)
        })
        
        # Calculate total time
        elapsed = time.time() - start_time
        results["total_time_ms"] = int(elapsed * 1000)
        results["total_time_seconds"] = round(elapsed, 3)
        results["success"] = True
        
        # Record boot
        self.boot_history.append({
            "timestamp": datetime.now().isoformat(),
            "total_time_ms": results["total_time_ms"],
            "success": True
        })
        
        return results
    
    def get_boot_stats(self) -> Dict:
        """Get boot statistics."""
        if not self.boot_history:
            return {"total_boots": 0}
        
        total_boots = len(self.boot_history)
        avg_time = sum(b["total_time_ms"] for b in self.boot_history) / total_boots
        fastest = min(b["total_time_ms"] for b in self.boot_history)
        slowest = max(b["total_time_ms"] for b in self.boot_history)
        
        return {
            "total_boots": total_boots,
            "avg_time_ms": int(avg_time),
            "fastest_ms": fastest,
            "slowest_ms": slowest,
            "recent_boots": self.boot_history[-5:]
        }


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="ILMA Fast Boot")
    parser.add_argument("command", nargs="?", default="start",
                        choices=["start", "stats", "prereq", "preload"])
    
    boot = FastBoot()
    args = parser.parse_args()
    
    if args.command == "start":
        print("Starting ILMA Fast Boot...")
        results = boot.fast_startup()
        
        if results["success"]:
            print(f"✓ Boot completed in {results['total_time_ms']}ms")
            for step in results["steps"]:
                status = "✓" if step.get("passed", True) else "✗"
                if "loaded" in step:
                    print(f"  {status} {step['name']}: {step.get('loaded', 0)} loaded ({step['time_ms']}ms)")
                else:
                    print(f"  {status} {step['name']} ({step['time_ms']}ms)")
        else:
            print(f"✗ Boot failed: {results.get('error')}")
    
    elif args.command == "stats":
        stats = boot.get_boot_stats()
        print(json.dumps(stats, indent=2))
    
    elif args.command == "prereq":
        prereq = boot.check_prerequisites()
        print("Prerequisites Check:")
        for check, passed in prereq["checks"].items():
            status = "✓" if passed else "✗"
            print(f"  {status} {check}: {passed}")
        print(f"\nAll passed: {prereq['all_passed']}")
    
    elif args.command == "preload":
        scripts = boot.preload_scripts()
        skills = boot.preload_skills()
        print(f"Scripts loaded: {scripts.get('loaded', 0)}")
        print(f"Skills loaded: {skills.get('loaded', 0)}")

if __name__ == "__main__":
    main()
