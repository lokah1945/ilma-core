#!/usr/bin/env python3
"""
ILMA Reverse Engineering Helper Script
Provides unified interface for binary analysis using available tools:
- radare2 (primary, persistent DB)
- Ghidra (headless, if JDK configured)
- REA agents (if installed via npm)
"""

import subprocess
import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict


@dataclass
class AnalysisResult:
    tool: str
    target: str
    success: bool
    output: str
    error: Optional[str] = None
    artifacts: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.artifacts is None:
            self.artifacts = []


class ReverseEngineering:
    """Unified reverse engineering interface for ILMA."""
    
    def __init__(self):
        self.radare2_path = "/usr/local/bin/radare2"
        self.ghidra_path = "/usr/local/bin/ghidra"
        self.rea_agents_path = self._find_rea_agents()
        # Use JDK 21 for Ghidra (installed at /opt/jdk-21)
        self.java_home = os.environ.get("GHIDRA_JAVA_HOME", "/opt/jdk-21")
        
    def _find_rea_agents(self) -> Optional[str]:
        """Find rea-agents CLI if installed."""
        for path in ["/usr/local/bin/rea-agents", "/usr/bin/rea-agents", 
                     os.path.expanduser("~/.npm-global/bin/rea-agents")]:
            if os.path.exists(path):
                return path
        # Check npm global
        result = subprocess.run(["npm", "list", "-g", "rea-agents"], 
                               capture_output=True, text=True)
        if result.returncode == 0:
            return "rea-agents"
        return None
    
    def check_tools(self) -> Dict[str, Any]:
        """Check availability of all RE tools."""
        tools = {}
        
        # radare2
        try:
            result = subprocess.run([self.radare2_path, "-v"], 
                                  capture_output=True, text=True, timeout=10)
            tools["radare2"] = {
                "available": result.returncode == 0,
                "version": result.stdout.split("\n")[0] if result.stdout else "unknown",
                "path": self.radare2_path
            }
        except Exception as e:
            tools["radare2"] = {"available": False, "error": str(e)}
        
        # Ghidra
        try:
            # Check if the support script exists and is executable
            ghidra_support = "/opt/ayda/tools/ghidra_12.0.4_PUBLIC/support/analyzeHeadless"
            available = os.path.exists(ghidra_support) and os.access(ghidra_support, os.X_OK)
            tools["ghidra"] = {
                "available": available,
                "version": "12.0.4" if available else "unknown",
                "path": self.ghidra_path,
                "java_home": self.java_home
            }
        except Exception as e:
            tools["ghidra"] = {"available": False, "error": str(e)}
        
        # REA agents
        if self.rea_agents_path:
            try:
                result = subprocess.run([self.rea_agents_path, "--version"], 
                                      capture_output=True, text=True, timeout=10)
                tools["rea_agents"] = {
                    "available": result.returncode == 0,
                    "version": result.stdout.strip() if result.stdout else "unknown",
                    "path": self.rea_agents_path
                }
            except Exception as e:
                tools["rea_agents"] = {"available": False, "error": str(e)}
        else:
            tools["rea_agents"] = {"available": False, "error": "Not installed"}
        
        return tools
    
    def radare2_analyze(self, binary_path: str, db_path: Optional[str] = None, 
                       commands: Optional[List[str]] = None) -> AnalysisResult:
        """
        Analyze binary with radare2 using persistent database.
        
        Args:
            binary_path: Path to binary file
            db_path: Path for .r2db database (default: <binary>.r2db in /tmp)
            commands: List of radare2 commands to run (default: full analysis)
        """
        if not os.path.exists(binary_path):
            return AnalysisResult(
                tool="radare2", target=binary_path, success=False,
                output="", error=f"Binary not found: {binary_path}"
            )
        
        # Use /tmp for database to ensure write permissions
        if db_path is None:
            binary_name = Path(binary_path).stem
            db_path = f"/tmp/{binary_name}.r2db"
        else:
            # If relative path, use /tmp; if absolute, use as-is
            if not os.path.isabs(db_path):
                db_path = f"/tmp/{db_path}"
        
        # Default commands: analyze all, list functions, strings, imports
        if commands is None:
            commands = [
                f"Po {os.path.basename(db_path)}",  # open project (relative name)
                "aaa",            # analyze all
                "afl",            # list functions
                "iz",             # strings
                "ii",             # imports
                "ie",             # entry points
                "iS",             # sections
                "pdf @ main",     # disassemble main if exists
                f"Ps {os.path.basename(db_path)}",  # save project
                "q",              # quit
            ]
        else:
            # Prepend project open command
            commands = [f"Po {os.path.basename(db_path)}"] + commands + [
                f"Ps {os.path.basename(db_path)}", "q"]
        
        # Write commands to temp script file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.r2', delete=False) as f:
            script_path = f.name
            for c in commands:
                f.write(c + "\n")
        
        # Run from /tmp to ensure project is created there
        original_cwd = os.getcwd()
        os.chdir("/tmp")
        
        try:
            # Run radare2 with script file - this is the working pattern
            cmd = [self.radare2_path, binary_path, "-i", script_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            artifacts = [db_path] if os.path.exists(db_path) else []
            
            return AnalysisResult(
                tool="radare2",
                target=binary_path,
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None,
                artifacts=artifacts
            )
        except subprocess.TimeoutExpired:
            return AnalysisResult(
                tool="radare2", target=binary_path, success=False,
                output="", error="Timeout (120s)"
            )
        except Exception as e:
            return AnalysisResult(
                tool="radare2", target=binary_path, success=False,
                output="", error=str(e)
            )
        finally:
            # Clean up temp script
            try:
                os.unlink(script_path)
            except:
                pass
            os.chdir(original_cwd)
    
    def radare2_load_db(self, db_path: str, commands: List[str]) -> AnalysisResult:
        """Load existing radare2 database and run commands."""
        # Ensure absolute path
        if not os.path.isabs(db_path):
            db_path = f"/tmp/{db_path}"
        
        if not os.path.exists(db_path):
            return AnalysisResult(
                tool="radare2", target=db_path, success=False,
                output="", error=f"Database not found: {db_path}"
            )
        
        # Prepend project open command
        db_name = os.path.basename(db_path)
        full_commands = [f"Po {db_name}"] + commands + [f"Ps {db_name}", "q"]
        
        # Write commands to temp script file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.r2', delete=False) as f:
            script_path = f.name
            for c in full_commands:
                f.write(c + "\n")
        
        # Run from /tmp
        original_cwd = os.getcwd()
        os.chdir("/tmp")
        
        try:
            # Need a dummy binary to load the project
            cmd = [self.radare2_path, "/bin/true", "-i", script_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return AnalysisResult(
                tool="radare2",
                target=db_path,
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None
            )
        except Exception as e:
            return AnalysisResult(
                tool="radare2", target=db_path, success=False,
                output="", error=str(e)
            )
        finally:
            try:
                os.unlink(script_path)
            except:
                pass
            os.chdir(original_cwd)
    
    def ghidra_analyze_headless(self, binary_path: str, project_dir: str, 
                               project_name: str, script_path: Optional[str] = None,
                               script_args: Optional[str] = None) -> AnalysisResult:
        """
        Run Ghidra headless analysis.
        Requires: JDK installed, GHIDRA_JAVA_HOME set.
        Uses the direct support script to avoid wrapper background mode issues.
        """
        if not os.path.exists(binary_path):
            return AnalysisResult(
                tool="ghidra", target=binary_path, success=False,
                output="", error=f"Binary not found: {binary_path}"
            )
        
        # Use the direct support script (not the wrapper) for reliable headless execution
        # The script IS analyzeHeadless, so we call it directly
        ghidra_support = "/opt/ayda/tools/ghidra_12.0.4_PUBLIC/support/analyzeHeadless"
        
        # Ensure project directory exists (analyzeHeadless requires it to pre-exist)
        # Use the full path including project name
        full_project_path = os.path.join(project_dir, project_name)
        os.makedirs(project_dir, exist_ok=True)
        os.makedirs(full_project_path, exist_ok=True)
        
        cmd = [
            ghidra_support,
            project_dir, project_name,
            "-import", binary_path,
            "-deleteProject"
        ]
        
        if script_path and os.path.exists(script_path):
            cmd.extend(["-postScript", script_path])
            if script_args:
                cmd.append(script_args)
        
        env = os.environ.copy()
        env["GHIDRA_JAVA_HOME"] = self.java_home
        env["JAVA_HOME"] = self.java_home
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                  timeout=300, env=env)
            return AnalysisResult(
                tool="ghidra",
                target=binary_path,
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None
            )
        except subprocess.TimeoutExpired:
            return AnalysisResult(
                tool="ghidra", target=binary_path, success=False,
                output="", error="Timeout (300s)"
            )
        except Exception as e:
            return AnalysisResult(
                tool="ghidra", target=binary_path, success=False,
                output="", error=str(e)
            )
    
    def rea_analyze_js(self, app_path: str, client: str = "codex") -> AnalysisResult:
        """Analyze JavaScript/Electron app with REA agents CLI."""
        if not self.rea_agents_path:
            return AnalysisResult(
                tool="rea_agents", target=app_path, success=False,
                output="", error="rea-agents not installed. Run: npm install -g rea-agents"
            )
        
        if not os.path.exists(app_path):
            return AnalysisResult(
                tool="rea_agents", target=app_path, success=False,
                output="", error=f"Path not found: {app_path}"
            )
        
        cmd = [self.rea_agents_path, "analyze-javascript-application", 
               app_path, "--json"]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            return AnalysisResult(
                tool="rea_agents",
                target=app_path,
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None
            )
        except subprocess.TimeoutExpired:
            return AnalysisResult(
                tool="rea_agents", target=app_path, success=False,
                output="", error="Timeout (180s)"
            )
        except Exception as e:
            return AnalysisResult(
                tool="rea_agents", target=app_path, success=False,
                output="", error=str(e)
            )
    
    def rea_doctor(self, client: str = "codex") -> AnalysisResult:
        """Run REA doctor to check MCP registration."""
        if not self.rea_agents_path:
            return AnalysisResult(
                tool="rea_agents", target="doctor", success=False,
                output="", error="rea-agents not installed"
            )
        
        cmd = [self.rea_agents_path, "doctor", "--client", client, "--json"]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return AnalysisResult(
                tool="rea_agents",
                target=f"doctor:{client}",
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None
            )
        except Exception as e:
            return AnalysisResult(
                tool="rea_agents", target=f"doctor:{client}", success=False,
                output="", error=str(e)
            )
    
    def auto_analyze(self, binary_path: str) -> Dict[str, Any]:
        """
        Auto-detect best tool and run analysis.
        Priority: radare2 (always available) -> Ghidra (if JDK) -> REA (if JS)
        """
        results = {"target": binary_path, "tools_checked": {}, "results": {}}
        
        # Check tools
        tools = self.check_tools()
        results["tools_checked"] = tools
        
        # Determine file type
        is_js = binary_path.endswith((".js", ".asar", ".app", ".exe")) and \
                any(kw in binary_path.lower() for kw in ["electron", "asar", "node"])
        
        # 1. radare2 (primary - always available)
        if tools["radare2"]["available"]:
            results["results"]["radare2"] = asdict(
                self.radare2_analyze(binary_path)
            )
        
        # 2. Ghidra (if JDK available)
        if tools["ghidra"]["available"]:
            project_dir = f"/tmp/ghidra_proj_{Path(binary_path).stem}"
            results["results"]["ghidra"] = asdict(
                self.ghidra_analyze_headless(binary_path, project_dir, "ilma_analysis")
            )
        
        # 3. REA for JS apps
        if is_js and tools["rea_agents"]["available"]:
            results["results"]["rea_agents"] = asdict(
                self.rea_analyze_js(binary_path)
            )
        
        return results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="ILMA Reverse Engineering Tool")
    parser.add_argument("target", help="Binary/app path to analyze")
    parser.add_argument("--tool", choices=["auto", "radare2", "ghidra", "rea"], 
                       default="auto", help="Analysis tool to use")
    parser.add_argument("--db", help="radare2 database path")
    parser.add_argument("--commands", nargs="+", help="radare2 commands")
    parser.add_argument("--ghidra-project", help="Ghidra project directory")
    parser.add_argument("--ghidra-script", help="Ghidra post-script path")
    parser.add_argument("--rea-client", default="codex", help="REA client for doctor/analyze")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    
    args = parser.parse_args()
    
    re = ReverseEngineering()
    
    if args.tool == "auto":
        result = re.auto_analyze(args.target)
    elif args.tool == "radare2":
        result = asdict(re.radare2_analyze(args.target, args.db, args.commands))
    elif args.tool == "ghidra":
        project_dir = args.ghidra_project or f"/tmp/ghidra_proj_{Path(args.target).stem}"
        result = asdict(re.ghidra_analyze_headless(args.target, project_dir, "ilma", 
                                                    args.ghidra_script))
    elif args.tool == "rea":
        result = asdict(re.rea_analyze_js(args.target, args.rea_client))
    else:
        result = {"error": f"Unknown tool: {args.tool}"}
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        # Human-readable summary
        if "results" in result:
            for tool, r in result["results"].items():
                status = "✅" if r["success"] else "❌"
                print(f"{status} {tool}: {'OK' if r['success'] else r.get('error', 'Failed')}")
                if r["output"] and len(r["output"]) < 500:
                    print(f"  Output: {r['output'][:500]}")
        else:
            status = "✅" if result.get("success") else "❌"
            print(f"{status} {result.get('tool', args.tool)}: {'OK' if result.get('success') else result.get('error', 'Failed')}")
            if result.get("output"):
                print(result["output"][:1000])


if __name__ == "__main__":
    main()