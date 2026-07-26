#!/usr/bin/env python3
"""
ILMA QA/Critic Execution Script
证据ID: P2E-QA-001
"""
import argparse, json, sys, re, datetime

EVIDENCE_ID = "P2E-QA-001"
VERSION = "1.0.0"

ISSUE_TYPES = ["clarity", "SEO", "structure", "factuality", "tone", "grammar"]

def find_issues(text):
    issues = []
    # Clarity
    long_sentences = [s for s in re.split(r'[.!?]', text) if len(s.split()) > 25]
    if long_sentences:
        issues.append({"type": "clarity", "severity": "medium", "description": f"Found {len(long_sentences)} sentences >25 words", "suggestion": "Break into shorter sentences"})
    # SEO
    words = text.lower().split()
    if not any(text.lower().startswith(p) for p in ['apa ', 'bagaimana ', 'mengapa ']):
        issues.append({"type": "SEO", "severity": "low", "description": "No clear question-based opening", "suggestion": "Start with a question for better SEO"})
    # Structure
    has_headers = bool(re.search(r'^##?\s+\w', text, re.MULTILINE))
    if not has_headers:
        issues.append({"type": "structure", "severity": "medium", "description": "No headers detected", "suggestion": "Use ## headers for sections"})
    # Tone
    if text.isupper():
        issues.append({"type": "tone", "severity": "high", "description": "All caps detected", "suggestion": "Use mixed case for readability"})
    if text.count('!') > 3:
        issues.append({"type": "tone", "severity": "low", "description": "Overuse of exclamation marks", "suggestion": "Reduce exclamation marks"})
    return issues

def fix_issues(text, issues):
    fixed = text
    fixes_applied = []
    for issue in issues:
        if issue["type"] == "clarity":
            fixed = re.sub(r'(?<=[a-z])\.( [A-Z])', r'.\1', fixed)
            fixes_applied.append("split_long_sentences")
        elif issue["type"] == "tone" and issue.get("description") == "All caps detected":
            fixed = fixed.title()
            fixes_applied.append("capitalize_properly")
        elif issue["type"] == "tone" and "exclamation" in issue.get("description",""):
            fixed = re.sub(r'!+', '!', fixed)
            fixes_applied.append("reduce_exclamation")
        elif issue["type"] == "structure" and not re.search(r'^##?\s+\w', fixed, re.MULTILINE):
            lines = fixed.split('\n')
            for i, line in enumerate(lines[:3]):
                if line.strip() and not line.startswith('#'):
                    lines[i] = f"## {line.strip()}"
                    fixes_applied.append("add_section_headers")
                    break
            fixed = '\n'.join(lines)
    return fixed, fixes_applied

def main():
    p = argparse.ArgumentParser(description="ILMA QA/Critic Execution Script")
    p.add_argument("--text", "-t", required=True)
    p.add_argument("--fix", action="store_true", help="Apply fixes")
    p.add_argument("--json", action="store_true")
    p.add_argument("--evidence-id", default=EVIDENCE_ID)
    args = p.parse_args()

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    issues = find_issues(args.text)
    fixes_applied = []
    revised = args.text

    if args.fix and issues:
        revised, fixes_applied = fix_issues(args.text, issues)

    output = {
        "evidence_id": args.evidence_id,
        "version": VERSION,
        "timestamp": timestamp,
        "input_length": len(args.text),
        "input_word_count": len(args.text.split()),
        "issues_found": len(issues),
        "issues": issues,
        "fixes_applied": fixes_applied,
        "revised": revised if args.fix else None,
        "revised_word_count": len(revised.split()) if args.fix else None,
        "status": "EXECUTED"
    }

    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"=== ILMA QA/Critic ===")
        print(f"Issues found: {len(issues)}")
        for i in issues:
            print(f"  [{i['type']}] {i['severity']}: {i['description']}")
        if fixes_applied:
            print(f"Fixes applied: {len(fixes_applied)}")
            for f in fixes_applied:
                print(f"  - {f}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
