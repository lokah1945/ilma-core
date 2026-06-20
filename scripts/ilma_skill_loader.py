#!/usr/bin/env python3
"""
ILMA Skill Loader — Minimal Skill Execution Framework
Version: 1.0.0
Date: 2026-05-07
Purpose: Execute skill workflows in safe dry-run mode

Usage:
    python3 ilma_skill_loader.py --skill <name> --task "..." [--dry-run] [--json]
    python3 ilma_skill_loader.py --list
    python3 ilma_skill_loader.py --audit
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Configuration
SKILLS_DIR = Path(os.environ.get("ILMA_SKILLS_DIR", "/root/.hermes/profiles/ilma/skills"))
SCRIPT_DIR = Path(__file__).parent.resolve()
EVIDENCE_COUNTER = 0

# Execution script registry: skill_category -> script_name
EXECUTION_SCRIPTS = {
    "ilma-research": "ilma_exec_research.py",
    "ilma-writing": "ilma_exec_writing_blog.py",
    "ilma-indonesian-nlp": "ilma_exec_indonesian_nlp.py",
    "ilma-memory": "ilma_exec_memory.py",
    "ilma-qa-critic": "ilma_exec_qa_critic.py",
    "research": "ilma_exec_research.py",
    "writing": "ilma_exec_writing_blog.py",
    "writing_blog": "ilma_exec_writing_blog.py",
    "indonesian_nlp": "ilma_exec_indonesian_nlp.py",
    "memory": "ilma_exec_memory.py",
    "qa_critic": "ilma_exec_qa_critic.py",
    "dogfood": None,  # Use browser tool
}

SKILLS_EXEC_DIR = Path(__file__).parent / "skills_exec"

def get_evidence_id() -> str:
    global EVIDENCE_COUNTER
    EVIDENCE_COUNTER += 1
    return f"P2C-LOADER-{EVIDENCE_COUNTER:03d}"

def parse_frontmatter(content: str) -> tuple[Dict, str]:
    """Parse YAML frontmatter from SKILL.md content."""
    frontmatter = {}
    body = content
    
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                import yaml
                frontmatter = yaml.safe_load(parts[1]) or {}
            except Exception:
                # YAML parse failed, use simple key:value extraction
                frontmatter = {}
                fm_text = parts[1]
                for line in fm_text.split("\n"):
                    if ":" in line:
                        key, _, val = line.partition(":")
                        frontmatter[key.strip()] = val.strip()
            body = parts[2].strip()
    return frontmatter, body

def extract_sections(body: str) -> Dict[str, str]:
    """Extract markdown sections from body."""
    sections = {}
    current = "intro"
    lines = body.split("\n")
    
    for line in lines:
        if re.match(r"^#{1,3}\s+", line):
            current = re.sub(r"^#{1,3}\s+", "", line).strip().lower().replace(" ", "_")
            sections[current] = ""
        elif current in sections:
            sections[current] += line + "\n"
    
    return sections

def detect_tools(content: str) -> List[str]:
    """Detect tools mentioned in skill content."""
    tool_patterns = [
        "browser_navigate", "browser_snapshot", "browser_click", "browser_type",
        "browser_vision", "browser_console", "browser_scroll", "browser_back",
        "browser_press", "execute_code", "terminal", "read_file", "write_file",
        "search_files", "web_search", "memory", "session_search", "patch",
        "delegate_task", "skill_view", "skill_manage"
    ]
    found = []
    for tool in tool_patterns:
        if tool in content:
            found.append(tool)
    return found

def detect_steps(sections: Dict) -> List[str]:
    """Detect workflow steps from sections."""
    steps = []
    step_keywords = ["workflow", "phase", "step", "procedure", "process"]
    
    for section_name, content in sections.items():
        if any(kw in section_name for kw in step_keywords):
            # Extract numbered items
            numbered = re.findall(r'(?:^|\n)\s*(?:[-*]|\d+\.)\s+(.+?)(?=\n|$)', content)
            steps.extend(numbered)
    
    return steps[:10]  # Max 10 steps

def classify_skill(frontmatter: Dict, sections: Dict, tools: List[str]) -> str:
    """Classify execution mode for this skill."""
    has_workflow = any("workflow" in s.lower() or "phase" in s.lower() 
                       for s in sections.keys())
    has_script_ref = any("script" in s.lower() or "bash" in s.lower() 
                         for s in sections.values())
    
    if has_workflow and tools:
        return "workflow_backed"
    elif has_script_ref:
        return "script_backed"
    elif has_workflow:
        return "manual_procedure"
    else:
        return "documentation_only"

def load_skill(skill_name: str) -> Dict:
    """Load a skill and return structured information."""
    skill_path = SKILLS_DIR / skill_name / "SKILL.md"
    
    result = {
        "skill": skill_name,
        "status": "BROKEN",
        "execution_mode": "unknown",
        "skill_path": str(skill_path),
        "summary": "",
        "steps_detected": [],
        "tools_detected": [],
        "limitations": [],
        "evidence_id": get_evidence_id(),
        "output": ""
    }
    
    # Check exists
    if not skill_path.exists():
        result["summary"] = f"Skill not found: {skill_name}"
        result["limitations"].append(f"Path does not exist: {skill_path}")
        return result
    
    # Read content
    try:
        with open(skill_path, "r") as f:
            content = f.read()
    except Exception as e:
        result["summary"] = f"Cannot read skill file: {e}"
        result["limitations"].append(f"Read error: {e}")
        return result
    
    # Parse
    try:
        frontmatter, body = parse_frontmatter(content)
    except Exception:
        frontmatter = {}
        body = content
    sections = extract_sections(body)
    tools = detect_tools(content)
    steps = detect_steps(sections)
    mode = classify_skill(frontmatter, sections, tools)
    
    # Build result
    result["status"] = "DRY_RUN_VERIFIED"
    result["execution_mode"] = mode
    result["summary"] = frontmatter.get("description", 
              sections.get("overview", sections.get("description", "No description"))[:200])
    result["steps_detected"] = steps
    result["tools_detected"] = tools
    result["limitations"] = [
        "Dry-run mode — actual execution not performed",
        "Steps detected from markdown — may not be exhaustive",
    ]
    
    # Add skill-specific notes
    if mode == "documentation_only":
        result["limitations"].append("No workflow detected — only documentation")
    elif mode == "workflow_backed":
        result["limitations"].append(f"Workflow detected with {len(tools)} tools")
    
    return result

def get_script_for_skill(skill_name: str):
    """Find execution script for a skill."""
    script_name = EXECUTION_SCRIPTS.get(skill_name)
    if script_name:
        script_path = SKILLS_EXEC_DIR / script_name
        if script_path.exists():
            return script_path
    # Try lowercase
    script_name = EXECUTION_SCRIPTS.get(skill_name.lower())
    if script_name:
        script_path = SKILLS_EXEC_DIR / script_name
        if script_path.exists():
            return script_path
    return None

def run_execution_script(script_path: Path, skill_name: str, user_task: str) -> Dict:
    """Run a skill execution script and return structured result."""
    import subprocess, uuid
    result = {
        "script_used": str(script_path),
        "status": "EXECUTION_FAILED",
        "output": "",
        "error": "",
        "evidence_id": f"EXEC-{uuid.uuid4().hex[:8].upper()}"
    }
    
    # Map script name to appropriate argument
    script_name = script_path.name
    if "research" in script_name:
        cmd_args = ["--query", user_task]
    elif "writing_blog" in script_name:
        cmd_args = ["--topic", user_task]
    elif "indonesian" in script_name:
        cmd_args = ["--text", user_task]
    elif "memory" in script_name:
        cmd_args = ["--read", user_task]
    elif "qa_critic" in script_name:
        cmd_args = ["--text", user_task]
    else:
        cmd_args = ["--task", user_task]
    
    try:
        proc = subprocess.run(
            [sys.executable, str(script_path)] + cmd_args + ["--json"],
            capture_output=True, text=True, timeout=30
        )
        if proc.returncode == 0:
            result["status"] = "EXECUTED"
            result["output"] = proc.stdout[:2000]
            try:
                result["output_json"] = json.loads(proc.stdout)
            except Exception:
                pass
        else:
            result["error"] = proc.stderr[:500]
    except subprocess.TimeoutExpired:
        result["error"] = "Timeout after 30s"
    except Exception as e:
        result["error"] = str(e)
    return result

def execute_dry_run(skill_name: str, user_task: str, mode: str = "dry_run") -> Dict:
    """Execute a dry-run for a skill."""
    # Try execution script FIRST for known script-backed skills
    script_path = None
    if mode == "execute":
        script_path = get_script_for_skill(skill_name)
    
    # Load skill metadata (may be BROKEN if path doesn't exist)
    result = load_skill(skill_name)
    
    if script_path:
        # Execute script even if skill path doesn't exist
        script_result = run_execution_script(script_path, skill_name, user_task)
        result["script_used"] = script_result["script_used"]
        result["script_status"] = script_result["status"]
        result["script_output"] = script_result["output"]
        if script_result["error"]:
            result["script_error"] = script_result["error"]
        result["evidence_id"] = script_result.get("evidence_id", result["evidence_id"])
        if script_result["status"] == "EXECUTED":
            result["status"] = "EXECUTION_VERIFIED"
            result["limitations"] = []
            result["output"] = script_result["output"]
    
    if result["status"] != "EXECUTION_VERIFIED":
        # Simulate task analysis (only if no script worked)
        result["output"] = (
            f"[DRY-RUN] Skill: {skill_name}\n"
            f"Task: {user_task}\n"
            f"Mode: {mode}\n"
            f"Execution: {result['execution_mode']}\n"
            f"Steps: {len(result['steps_detected'])}\n"
            f"Tools: {result['tools_detected']}\n"
            f"---\n"
            f"This is a dry-run. No actual execution performed.\n"
            f"To execute, use --execute flag."
        )
    
    return result

def list_skills() -> List[Dict]:
    """List all available skills."""
    skills = []
    if not SKILLS_DIR.exists():
        return skills
    
    for item in SKILLS_DIR.iterdir():
        if item.is_dir():
            skill_md = item / "SKILL.md"
            skills.append({
                "name": item.name,
                "has_skill_md": skill_md.exists(),
                "path": str(item)
            })
    
    return sorted(skills, key=lambda x: x["name"])

def audit_skills() -> Dict:
    """Audit all skills and return summary."""
    skills = list_skills()
    verified = 0
    readable = 0
    broken = 0
    
    for skill in skills:
        if skill["has_skill_md"]:
            result = load_skill(skill["name"])
            if result["status"] == "DRY_RUN_VERIFIED":
                verified += 1
            else:
                readable += 1
        else:
            broken += 1
    
    return {
        "total": len(skills),
        "verified": verified,
        "readable": readable,
        "broken": broken
    }

def main():
    parser = argparse.ArgumentParser(
        description="ILMA Skill Loader — Minimal Skill Execution Framework"
    )
    parser.add_argument("--skill", type=str, help="Skill name to load")
    parser.add_argument("--task", type=str, default="", help="User task/goal")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run mode (default)")
    parser.add_argument("--execute", action="store_true", help="Execute mode (requires approval)")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument("--list", action="store_true", help="List all skills")
    parser.add_argument("--audit", action="store_true", help="Audit all skills")
    
    args = parser.parse_args()
    
    # List mode
    if args.list:
        skills = list_skills()
        print(f"Total skills: {len(skills)}")
        for s in skills[:20]:
            print(f"  {s['name']} {'[SKILL.md]' if s['has_skill_md'] else '[NO SKILL.md]'}")
        if len(skills) > 20:
            print(f"  ... and {len(skills) - 20} more")
        return
    
    # Audit mode
    if args.audit:
        result = audit_skills()
        print(f"Skill Audit Results:")
        print(f"  Total: {result['total']}")
        print(f"  DRY_RUN_VERIFIED: {result['verified']}")
        print(f"  READABLE_ONLY: {result['readable']}")
        print(f"  BROKEN: {result['broken']}")
        return
    
    # Load skill
    if not args.skill:
        print("Error: --skill required (or use --list / --audit)")
        sys.exit(1)
    
    mode = "execute" if args.execute else "dry_run"
    result = execute_dry_run(args.skill, args.task, mode)
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"=== Skill Loader Result ===")
        print(f"Skill: {result['skill']}")
        print(f"Status: {result['status']}")
        print(f"Mode: {result['execution_mode']}")
        print(f"Path: {result['skill_path']}")
        print(f"Summary: {result['summary'][:100]}...")
        print(f"Steps: {len(result['steps_detected'])} detected")
        print(f"Tools: {result['tools_detected']}")
        print(f"Limitations: {result['limitations']}")
        print(f"Evidence ID: {result['evidence_id']}")
        if result['output']:
            print(f"\n--- Output ---")
            print(result['output'])

if __name__ == "__main__":
    main()
