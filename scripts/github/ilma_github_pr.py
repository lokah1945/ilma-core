#!/usr/bin/env python3
"""
ILMA GitHub PR Workflow
======================
Automated PR management.
"""

import sys
import subprocess
from pathlib import Path

def run(cmd):
    """Run git/gh command. SECURITY: Converted from shell=True to list args (Phase 15B)"""
    import shlex
    parts = shlex.split(cmd)
    return subprocess.run(parts, shell=False, capture_output=True, text=True)

def create_branch(name):
    """Create new branch."""
    print(f"Creating branch: {name}")
    run(f"git checkout -b {name}")
    print("✅ Branch created")

def commit(message):
    """Commit changes."""
    run("git add -A")
    run(f"git commit -m '{message}'")
    print(f"✅ Committed: {message}")

def push():
    """Push to remote."""
    branch = run("git branch --show-current").strip()
    run(f"git push -u origin {branch}")
    print(f"✅ Pushed to {branch}")

def create_pr(title, body):
    """Create PR via gh CLI."""
    run(f'gh pr create --title "{title}" --body "{body}"')
    print("✅ PR created")

def main():
    if len(sys.argv) < 2:
        print("Usage: ilma_github_pr.py <action> [args]")
        print("  create-branch <name>")
        print("  commit <message>")
        print("  push")
        print("  create-pr <title> <body>")
        return
    
    action = sys.argv[1]
    
    if action == "create-branch":
        create_branch(sys.argv[2])
    elif action == "commit":
        commit(sys.argv[2])
    elif action == "push":
        push()
    elif action == "create-pr":
        create_pr(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")

if __name__ == "__main__":
    main()