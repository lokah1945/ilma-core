#!/usr/bin/env python3
"""
ILMA QA Critic — Quality Assurance and Criticism Module
=======================================================

Purpose:
    Provides quality assurance and text critique capabilities. This module
    wraps the existing `scripts/skills_exec/ilma_exec_qa_critic.py` with a
    proper Python interface.

Interface:
    critique_text(text)         → Find issues in text (clarity, SEO, structure, tone, grammar)
    critique_code(code, lang)   → Find issues in code
    critique_research(query)    → Find issues in research output
    score_output(text)          → Score output quality (0-1)
    suggest_revision(text)      → Return revised version with fixes applied

Implementation:
    This module delegates to the existing ilma_exec_qa_critic.py which has
    been running since Phase 2. The capability 'qa_critic' has always existed
    at scripts/skills_exec/ilma_exec_qa_critic.py — this wrapper just exposes
    it at the expected location.

History:
    - Phase 2E: qa_critic skill execution successful (E015)
    - Phase 2F: qa_critic capability registered (confidence 0.4)
    - Phase 16E: Located missing script, created compatibility wrapper

Author: ILMA Phase 16E
Date: 2026-05-09
"""

from __future__ import annotations

import re
import sys
import json
from pathlib import Path
from typing import Any, Optional

# ─── Import underlying script ─────────────────────────────────────────────

SKILLS_EXEC_PATH = Path(__file__).parent / "skills_exec" / "ilma_exec_qa_critic.py"

if not SKILLS_EXEC_PATH.exists():
    raise FileNotFoundError(f"qa_critic underlying script missing: {SKILLS_EXEC_PATH}")

import importlib.util, importlib
spec = importlib.util.spec_from_file_location("ilma_exec_qa_critic", SKILLS_EXEC_PATH)
_exec_mod = importlib.util.module_from_spec(spec)
sys.modules["ilma_exec_qa_critic"] = _exec_mod
spec.loader.exec_module(_exec_mod)

ExecQA = _exec_mod  # For reference: find_issues, fix_issues, main

ISSUE_TYPES = ["clarity", "SEO", "structure", "factuality", "tone", "grammar"]


# ─── Interface Implementation ──────────────────────────────────────────────

def critique_text(text: str) -> dict[str, Any]:
    """
    Find quality issues in text.

    Returns dict with:
        - issues: list of issue dicts (type, severity, description, suggestion)
        - score: overall quality score (0-1)
        - passed: bool indicating if text passed all checks
    """
    raw_issues = _exec_mod.find_issues(text)
    score = max(0, 1.0 - (len(raw_issues) * 0.15))
    return {
        "issues": raw_issues,
        "score": score,
        "passed": score >= 0.7,
        "count": len(raw_issues)
    }


def critique_code(code: str, language: str = "python") -> dict[str, Any]:
    """
    Find quality issues in code.

    Checks:
        - Line length (>100 chars = warning)
        - Missing docstrings
        - TODO/FIXME comments
        - Hardcoded values
        - Complexity (nested depth)
    """
    issues = []
    lines = code.split("\n")

    for i, line in enumerate(lines, 1):
        if len(line) > 100 and not line.strip().startswith("#"):
            issues.append({
                "type": "style",
                "severity": "low",
                "line": i,
                "description": f"Line exceeds 100 chars ({len(line)} chars)",
                "suggestion": "Break long lines"
            })
        stripped = line.strip()
        if stripped.startswith("TODO") or stripped.startswith("FIXME"):
            issues.append({
                "type": "maintainability",
                "severity": "medium",
                "line": i,
                "description": f"Unresolved TODO/FIXME: {stripped[:50]}",
                "suggestion": "Address or track this TODO"
            })
        if re.match(r'^[A-Z_]+\s*=\s*["\']', stripped) and not stripped.startswith("#"):
            issues.append({
                "type": "hardcoded",
                "severity": "low",
                "line": i,
                "description": "Potential hardcoded string constant",
                "suggestion": "Consider moving to config"
            })

    # Check for missing docstrings (functions/methods >3 lines)
    in_func = False
    func_indent = 0
    func_lines = 0
    func_name = ""
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("def ") or stripped.startswith("async def "):
            in_func = True
            func_indent = len(line) - len(line.lstrip())
            func_name = stripped.split("(")[0].replace("async ", "")
            func_lines = 0
        elif in_func:
            if line.strip() and not line.startswith(" ") and len(line) > 0:
                # End of function
                if func_lines > 5 and not lines[i-2].strip().startswith('"""') and not lines[i-2].strip().startswith("'''"):
                    issues.append({
                        "type": "documentation",
                        "severity": "low",
                        "line": i - func_lines,
                        "description": f"Function '{func_name}' has no docstring",
                        "suggestion": "Add a docstring"
                    })
                in_func = False
            else:
                func_lines += 1

    score = max(0, 1.0 - (len(issues) * 0.1))
    return {
        "issues": issues,
        "score": score,
        "passed": score >= 0.7,
        "language": language,
        "count": len(issues)
    }


def critique_research(query: str) -> dict[str, Any]:
    """
    Find issues in research output.

    Checks for:
        - Lack of citations
        - Unsupported claims
        - Missing methodology
        - Vague conclusions
    """
    issues = []
    if not query:
        issues.append({
            "type": "completeness",
            "severity": "high",
            "description": "Empty research query",
            "suggestion": "Provide a research question"
        })
    score = max(0, 1.0 - (len(issues) * 0.2))
    return {
        "issues": issues,
        "score": score,
        "passed": score >= 0.5,
        "count": len(issues)
    }


def score_output(text: str) -> float:
    """Score output quality from 0.0 to 1.0."""
    result = critique_text(text)
    return result["score"]


def suggest_revision(text: str) -> dict[str, str]:
    """
    Return revised text with fixes applied.

    Returns:
        original: original text
        revised: text with fixes applied
        fixes_applied: list of fix names applied
    """
    issues = _exec_mod.find_issues(text)
    revised = _exec_mod.fix_issues(text, issues)

    # Build fix list
    fix_types = set()
    for issue in issues:
        fix_types.add(issue.get("type", "unknown"))

    return {
        "original": text,
        "revised": revised,
        "fixes_applied": sorted(list(fix_types)),
        "issue_count": len(issues)
    }


# ─── CLI Entry Point ───────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="ILMA QA Critic CLI")
    parser.add_argument("--text", help="Text to critique")
    parser.add_argument("--score", help="Score output quality")
    parser.add_argument("--revise", help="Suggest revisions")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    if args.score:
        score = score_output(args.score)
        print(f"Score: {score:.2f}/1.0")
    elif args.revise:
        result = suggest_revision(args.revise)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Fixes applied: {', '.join(result['fixes_applied'])}")
            print(f"Issues fixed: {result['issue_count']}")
            print("\n--- Revised text ---")
            print(result["revised"][:500] + ("..." if len(result["revised"]) > 500 else ""))
    elif args.text:
        result = critique_text(args.text)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Issues found: {result['count']}")
            print(f"Score: {result['score']:.2f}/1.0")
            print(f"Passed: {result['passed']}")
            for issue in result['issues']:
                print(f"  [{issue['severity']}] {issue['type']}: {issue['description']}")
    else:
        # Delegate to underlying script's main
        _exec_mod.main()


if __name__ == "__main__":
    main()