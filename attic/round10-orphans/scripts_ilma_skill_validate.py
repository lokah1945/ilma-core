#!/usr/bin/env python3
"""
ilma_skill_validate.py — skill catalog validation gate (P3, 2026-06-20)
======================================================================
Validates every SKILL.md under skills/: frontmatter present (name + description),
description is not auto-gen boilerplate, and any referenced asset paths exist.
Prevents the ~180 "SSS Tier / Military Grade Quality" stub regression.

Exit: 0 if all valid, 1 if any invalid.
Usage: python3 ilma_skill_validate.py [--skills-dir DIR] [--quiet]
"""
import os, re, sys, argparse

BOILERPLATE = re.compile(r"Military Grade Quality|SSS Tier skill for", re.I)


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm = {}
    for line in text[3:end].splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm


def validate_skill(skill_md: str) -> list:
    """Return list of problems (empty = valid)."""
    problems = []
    d = os.path.dirname(skill_md)
    try:
        text = open(skill_md, encoding="utf-8", errors="replace").read()
    except Exception as e:
        return [f"unreadable: {e}"]
    fm = parse_frontmatter(text)
    if not fm.get("name"):
        problems.append("missing frontmatter 'name'")
    if not fm.get("description"):
        problems.append("missing frontmatter 'description'")
    if BOILERPLATE.search(fm.get("description", "")):
        problems.append("boilerplate description (auto-gen stub)")
    # body substance: content after frontmatter should be non-trivial
    body = text.split("\n---", 2)[-1] if text.startswith("---") else text
    if len(body.strip()) < 80:
        problems.append(f"thin body ({len(body.strip())} chars)")
    # referenced local asset paths (markdown links / references/) must exist
    for m in re.finditer(r"\]\((?!https?://)([^)]+\.(?:md|py|sh|json|yaml|yml|tex))\)", text):
        rel = m.group(1).lstrip("./")
        if not os.path.exists(os.path.join(d, rel)) and not os.path.exists(os.path.join(d, os.path.basename(rel))):
            problems.append(f"missing referenced asset: {rel}")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills-dir", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    skill_mds = []
    for root, _, files in os.walk(args.skills_dir):
        if "SKILL.md" in files:
            skill_mds.append(os.path.join(root, "SKILL.md"))

    invalid = 0
    for sk in sorted(skill_mds):
        probs = validate_skill(sk)
        if probs:
            invalid += 1
            rel = os.path.relpath(sk, args.skills_dir)
            if not args.quiet:
                print(f"  ❌ {rel}: {'; '.join(probs)}")
    total = len(skill_mds)
    print(f"\nSkill validation: {total - invalid}/{total} valid, {invalid} invalid")
    sys.exit(1 if invalid else 0)


if __name__ == "__main__":
    main()
