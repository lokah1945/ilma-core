#!/usr/bin/env python3
"""
ILMA Master Shell - Unified CLI for all ILMA capabilities
Integrates: Scripts, Skills, Fabric, Capabilities, Browser, Memory
"""
import os
import sys
import json
import subprocess
from pathlib import Path

# ILMA Root
ILMA_ROOT = Path("/root/.hermes/profiles/ilma")
SCRIPTS_DIR = ILMA_ROOT / "scripts"
SKILLS_DIR = ILMA_ROOT / "skills"
FABRIC_DIR = ILMA_ROOT / "fabric"
CAPS_DIR = ILMA_ROOT / "capabilities"

class ILMAMasterShell:
    def __init__(self):
        self.name = "ILMA Master Shell"
        self.version = "2.0"
        self.cache_dir = ILMA_ROOT / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        
    def log(self, msg, level="INFO"):
        print(f"[{level}] {msg}")
        
    def run_script(self, script_name, *args):
        """Run an ILMA script"""
        script_path = SCRIPTS_DIR / script_name
        if not script_path.exists():
            script_path = SCRIPTS_DIR / f"{script_name}.py"
        if not script_path.exists():
            return {"error": f"Script not found: {script_name}"}
        
        cmd = [sys.executable, str(script_path)] + list(args)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"error": "Script timed out"}
        except Exception as e:
            return {"error": str(e)}
    
    def list_scripts(self, pattern="*"):
        """List all scripts matching pattern"""
        scripts = {}
        for p in SCRIPTS_DIR.glob(f"{pattern}*.py"):
            size = p.stat().st_size
            scripts[p.name] = {
                "size": size,
                "path": str(p),
                "lines": len(p.read_text().splitlines())
            }
        return scripts
    
    def list_skills(self, category=None):
        """List skills, optionally filtered by category"""
        skills = {}
        search_dir = SKILLS_DIR if not category else SKILLS_DIR / category
        if not search_dir.exists():
            return {"error": f"Category not found: {category}"}
        
        for p in search_dir.glob("**/*.md"):
            rel = p.relative_to(SKILLS_DIR)
            skills[str(rel)] = p.stat().st_size
        return skills
    
    def get_system_status(self):
        """Get ILMA system status"""
        # Count components
        scripts = len(list(SCRIPTS_DIR.glob("*.py")))
        skills = len(list(SKILLS_DIR.glob("**/*.md")))
        fabric = len(list(FABRIC_DIR.glob("**/*.py")))
        caps = len(list(CAPS_DIR.glob("**/*.py")))
        
        # Memory usage
        try:
            result = subprocess.run(["du", "-sh", str(ILMA_ROOT)], capture_output=True, text=True)
            size = result.stdout.split()[0] if result.returncode == 0 else "unknown"
        except Exception:
            size = "unknown"
        
        return {
            "scripts": scripts,
            "skills": skills,
            "fabric_modules": fabric,
            "capabilities": caps,
            "total_size": size,
            "ilma_root": str(ILMA_ROOT)
        }
    
    def run_health_check(self):
        """Run comprehensive health check"""
        self.log("Running ILMA Health Check...", "INFO")
        results = {
            "scripts": {},
            "fabric": {},
            "capabilities": {},
            "skills": {},
            "overall": "unknown"
        }
        
        # Check scripts
        critical_scripts = [
            "ilma_orchestrator.py",
            "ilma_self_improve.py", 
            "ilma_browser_plane.py",
            "ilma_passive_benchmark.py",
            "ilma_system_integration.py"
        ]
        for name in critical_scripts:
            path = SCRIPTS_DIR / name
            results["scripts"][name] = "✅ OK" if path.exists() else "❌ MISSING"
        
        # Check fabric
        critical_fabric = [
            "orchestration/adaptive_parallelism.py",
            "workers/browser_worker.py",
            "resilience/auto_recovery.py",
            "state_sync/checkpoint_engine.py"
        ]
        for name in critical_fabric:
            path = FABRIC_DIR / name
            results["fabric"][name] = "✅ OK" if path.exists() else "❌ MISSING"
        
        # Check capabilities
        for cap in ["streaming", "memory", "web_search", "learning"]:
            path = CAPS_DIR / cap
            if path.is_file():
                path = path.parent
            results["capabilities"][cap] = "✅ OK" if path.exists() else "❌ MISSING"
        
        # Calculate overall
        all_checks = []
        for section in results.values():
            if isinstance(section, dict):
                all_checks.extend(section.values())
        
        if all_checks:
            passed = sum(1 for c in all_checks if "✅" in c)
            total = len(all_checks)
            results["overall"] = f"{passed}/{total} passed ({100*passed//total}%)"
        
        return results
    
    def optimize_cache(self):
        """Clean and optimize ILMA cache"""
        self.log("Optimizing cache...", "INFO")
        cleaned = 0
        
        # Clean Python cache
        for pattern in ["__pycache__", "*.pyc", "*.pyo"]:
            for p in ILMA_ROOT.rglob(pattern):
                try:
                    if p.is_file():
                        p.unlink()
                        cleaned += 1
                    elif p.is_dir():
                        import shutil
                        shutil.rmtree(p)
                        cleaned += 1
                except Exception:
                    pass
        
        # Clean old benchmarks
        benchmark_dir = ILMA_ROOT / ".benchmark"
        if benchmark_dir.exists():
            import time
            cutoff = time.time() - 7 * 24 * 3600  # 7 days
            for p in benchmark_dir.glob("*.json"):
                if p.stat().st_mtime < cutoff:
                    p.unlink()
                    cleaned += 1
        
        return {"cleaned_items": cleaned}
    
    def benchmark_vs_ILMA(self):
        """Run ILMA vs ILMA benchmark"""
        return self.run_script("ilma_passive_benchmark.py", "--full")
    
    def show_menu(self):
        """Display menu"""
        print("""
╔══════════════════════════════════════════════════════════════╗
║          ILMA MASTER SHELL v2.0 - System Control             ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  📊 SYSTEM STATUS                                            ║
║     1. Show system status                                    ║
║     2. Run health check                                     ║
║     3. View benchmark vs ILMA                               ║
║                                                              ║
║  🔧 OPTIMIZATION                                             ║
║     4. Clean cache                                          ║
║     5. Optimize all components                              ║
║                                                              ║
║  📜 SCRIPTS                                                  ║
║     6. List all scripts                                     ║
║     7. Run specific script                                  ║
║                                                              ║
║  🎯 SKILLS                                                   ║
║     8. List all skills                                      ║
║     9. List skills by category                              ║
║                                                              ║
║  🌐 BROWSER                                                  ║
║    10. Launch browser (ILMA cookies)                        ║
║    11. Fresh anonymous browser                               ║
║                                                              ║
║  💾 MEMORY                                                   ║
║    12. View memory status                                    ║
║    13. Run memory optimization                               ║
║                                                              ║
║  🚀 EXECUTE                                                  ║
║    14. Run self-improvement cycle                           ║
║    15. Run evolution routine                                ║
║                                                              ║
║     0. Exit                                                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
        """)

def main():
    shell = ILMAMasterShell()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "--status":
            print(json.dumps(shell.get_system_status(), indent=2))
        elif cmd == "--health":
            print(json.dumps(shell.run_health_check(), indent=2))
        elif cmd == "--benchmark":
            result = shell.benchmark_vs_ILMA()
            print(json.dumps(result, indent=2))
        elif cmd == "--optimize":
            print(json.dumps(shell.optimize_cache(), indent=2))
        elif cmd == "--scripts":
            print(json.dumps(shell.list_scripts(), indent=2))
        elif cmd == "--skills":
            print(json.dumps(shell.list_skills(), indent=2))
        elif cmd == "--menu":
            shell.show_menu()
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: ilma_master_shell.py [--status|--health|--benchmark|--optimize|--scripts|--skills|--menu]")
    else:
        shell.show_menu()

if __name__ == "__main__":
    main()
