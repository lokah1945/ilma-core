#!/usr/bin/env python3
"""
ILMA GitHub Issue Manager
========================
GitHub issue automation.
"""

import subprocess
import json

def run_gh(cmd):
    """Run gh CLI. SECURITY: Converted from shell=True to list args (Phase 15B)"""
    import shlex
    parts = shlex.split(f"gh {cmd}")
    return subprocess.run(parts, shell=False, capture_output=True, text=True)

def create_issue(title, body, labels=None):
    labels_arg = f"--label {labels}" if labels else ""
    result = run_gh(f"issue create --title '{title}' --body '{body}' {labels_arg}")
    print(result.stdout)

def list_issues(state="open"):
    result = run_gh(f"issue list --state {state} --json number,title,labels")
    print(result.stdout)

def close_issue(number):
    result = run_gh(f"issue close {number}")
    print(result.stdout)

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--create")
    p.add_argument("--body")
    p.add_argument("--labels")
    p.add_argument("--list")
    p.add_argument("--close")
    args = p.parse_args()
    if args.create:
        create_issue(args.create, args.body or "", args.labels)
    elif args.list:
        list_issues(args.list)
    elif args.close:
        close_issue(args.close)

if __name__ == "__main__": main()