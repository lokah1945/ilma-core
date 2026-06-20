#!/usr/bin/env python3
"""
ILMA Skill Health Check - Verifikasi skills ILMA
==================================================
Memeriksa semua skill ILMA dan memastikan mereka accessible dan functional.

Usage:
    python3 ilma_skill_health_check.py          # Check all skills
    python3 ilma_skill_health_check.py --fix   # Auto-fix issues
    python3 ilma_skill_health_check.py --report # Generate report
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

# ─── Paths ─────────────────────────────────────────────────────────────────
PROFILE_DIR = Path("/root/.hermes/profiles/ilma")
SKILLS_DIR = PROFILE_DIR / "skills"
STATE_FILE = PROFILE_DIR / "state" / "skill_health.json"

# ─── ANSI Colors ───────────────────────────────────────────────────────────
C_R = "\033[91m"; C_G = "\033[92m"; C_Y = "\033[93m"; C_B = "\033[94m"
C_C = "\033[96m"; C_BOLD = "\033[1m"; C_RESET = "\033[0m"
def c(t, col): return f"{col}{t}{C_RESET}"

# ─── Dataclasses ────────────────────────────────────────────────────────────
@dataclass
class SkillHealth:
    name: str
    path: str
    status: str  # OK, MISSING, NO_SKILL_MD, SYNTAX_ERROR, EMPTY, OK_BUT_OLD
    size_bytes: int = 0
    lines: int = 0
    issues: List[str] = field(default_factory=list)
    last_modified: Optional[str] = None

# ─── Utility Functions ────────────────────────────────────────────────────────
def log(msg, color=C_C):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{ts}] {msg}{C_RESET}")

def get_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()

def check_skill_dir(path: Path) -> SkillHealth:
    """Check health of a single skill."""
    name = path.name
    issues = []
    
    if not path.exists():
        return SkillHealth(name=name, path=str(path), status="MISSING", issues=["Directory missing"])
    
    # Check what type of skill it is
    if path.is_dir():
        # Directory skill - needs SKILL.md
        skill_md = path / "SKILL.md"
        if not skill_md.exists():
            issues.append("Missing SKILL.md")
            status = "NO_SKILL_MD"
        else:
            # Check content
            content = skill_md.read_text()
            if len(content) < 50:
                issues.append("SKILL.md too small")
                status = "EMPTY"
            else:
                status = "OK"
        
        # Check for scripts in skill dir
        scripts = list(path.glob("*.py"))
        if scripts:
            for script in scripts:
                exit_code, _, _ = subprocess.run(
                    ["python3", "-m", "py_compile", str(script)],
                    capture_output=True, timeout=10
                )
                if exit_code != 0:
                    issues.append(f"Syntax error in {script.name}")
                    status = "SYNTAX_ERROR"
        
        # Count total files
        total_files = len(list(path.rglob("*")))
        size = sum(f.stat().st_size for f in path.rglob("f") if f.is_file())
        
        return SkillHealth(
            name=name,
            path=str(path),
            status=status,
            size_bytes=size,
            issues=issues,
            last_modified=datetime.fromtimestamp(path.stat().st_mtime).isoformat()
        )
    
    elif path.suffix == ".py":
        # Python skill file
        try:
            content = path.read_text()
            exit_code, _, stderr = subprocess.run(
                ["python3", "-m", "py_compile", str(path)],
                capture_output=True, text=True, timeout=10
            )
            
            if exit_code != 0:
                issues.append(f"Syntax error: {stderr[:50]}")
                status = "SYNTAX_ERROR"
            elif len(content) < 100:
                issues.append("File suspiciously small")
                status = "EMPTY"
            else:
                status = "OK"
            
            return SkillHealth(
                name=name,
                path=str(path),
                status=status,
                size_bytes=len(content),
                lines=len(content.splitlines()),
                issues=issues,
                last_modified=datetime.fromtimestamp(path.stat().st_mtime).isoformat()
            )
        except Exception as e:
            return SkillHealth(
                name=name, path=str(path), status="SYNTAX_ERROR",
                issues=[str(e)]
            )
    
    return SkillHealth(name=name, path=str(path), status="OK")

def fix_skill(skill: SkillHealth, dry: bool = False) -> bool:
    """Attempt to fix a broken skill."""
    if not skill.issues:
        return True
    
    path = Path(skill.path)
    
    if skill.status == "NO_SKILL_MD" and path.is_dir():
        # Create minimal SKILL.md
        minimal = f"""# {skill.name.replace('-', ' ').title()}

## Purpose
Auto-generated skill placeholder.

## Triggers
- "{skill.name}"

## Status
Auto-generated by skill health check.

## Content
Files in this skill:
{chr(10).join('- ' + str(f.relative_to(path)) for f in path.rglob('*') if f.is_file())}
"""
        if not dry:
            (path / "SKILL.md").write_text(minimal)
        log(f"✅ Created SKILL.md for {skill.name}", C_G)
        return True
    
    elif skill.status == "SYNTAX_ERROR":
        log(f"⚠️ Cannot auto-fix syntax error in {skill.name}", C_Y)
        return False
    
    return False

def update_state(results: List[SkillHealth]):
    """Update skill health state file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    state = {
        "last_check": get_timestamp(),
        "total": len(results),
        "by_status": {},
        "skills": {}
    }
    
    for r in results:
        state["by_status"][r.status] = state["by_status"].get(r.status, 0) + 1
        state["skills"][r.name] = {
            "status": r.status,
            "path": r.path,
            "last_modified": r.last_modified,
            "issues": r.issues
        }
    
    STATE_FILE.write_text(json.dumps(state, indent=2))

def generate_report(results: List[SkillHealth]) -> str:
    """Generate a detailed report."""
    report = []
    report.append(c("=" * 60, C_BOLD))
    report.append(c("ILMA SKILL HEALTH REPORT", C_BOLD))
    report.append(c("=" * 60, C_BOLD))
    
    # Summary
    total = len(results)
    by_status: Dict[str, int] = {}
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    
    report.append(f"\nTotal Skills: {total}")
    for status, count in sorted(by_status.items()):
        color = C_G if status == "OK" else C_Y if status in ("EMPTY", "OK_BUT_OLD") else C_R
        report.append(f"  {c(status, color)}: {count}")
    
    # Issues list
    issues = [r for r in results if r.status != "OK"]
    if issues:
        report.append(f"\n{c('ISSUES:', C_Y)}")
        for r in issues[:20]:
            report.append(f"  [{r.name}] {', '.join(r.issues)}")
        if len(issues) > 20:
            report.append(f"  ... and {len(issues) - 20} more")
    
    # Recommendations
    report.append(f"\n{c('RECOMMENDATIONS:', C_C)}")
    if by_status.get("MISSING", 0) > 0:
        report.append(f"  • Remove references to {by_status['MISSING']} missing skills")
    if by_status.get("NO_SKILL_MD", 0) > 0:
        report.append(f"  • Run with --fix to create missing SKILL.md files")
    if by_status.get("SYNTAX_ERROR", 0) > 0:
        report.append(f"  • Fix syntax errors in {by_status['SYNTAX_ERROR']} skills")
    if by_status.get("EMPTY", 0) > 0:
        report.append(f"  • Expand {by_status['EMPTY']} empty skills")
    
    return "\n".join(report)

# ─── Main ───────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="ILMA Skill Health Check")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues")
    parser.add_argument("--report", action="store_true", help="Generate detailed report")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()
    
    log("Starting skill health check...")
    
    results: List[SkillHealth] = []
    
    if not SKILLS_DIR.exists():
        log(f"Skills directory not found: {SKILLS_DIR}", C_R)
        sys.exit(1)
    
    # Check all skills
    for item in sorted(SKILLS_DIR.iterdir()):
        # Skip non-skill items
        if item.name.startswith(".") or item.name.startswith("_"):
            continue
        
        health = check_skill_dir(item)
        results.append(health)
        
        if health.status != "OK":
            log(f"  {health.name}: {c(health.status, C_Y)}")
            if health.issues:
                for issue in health.issues[:2]:
                    log(f"    → {issue}", C_Y)
    
    # Fix if requested
    if args.fix:
        log("\n⚙️ Auto-fixing issues...")
        fixed = 0
        for r in results:
            if r.status != "OK":
                if fix_skill(r):
                    fixed += 1
        log(f"✅ Fixed {fixed} issues")
    
    # Update state
    update_state(results)
    
    # Output
    if args.json:
        print(json.dumps([
            {"name": r.name, "status": r.status, "issues": r.issues}
            for r in results
        ], indent=2))
    elif args.report:
        print(generate_report(results))
    else:
        # Simple summary
        total = len(results)
        ok = sum(1 for r in results if r.status == "OK")
        issues = total - ok
        log(f"\n📊 Skills: {ok}/{total} OK", C_G if issues == 0 else C_Y)
        if issues > 0:
            log(f"   Issues: {issues}", C_Y)

if __name__ == "__main__":
    main()
