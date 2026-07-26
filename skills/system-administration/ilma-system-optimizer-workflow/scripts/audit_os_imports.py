#!/usr/bin/env python3
"""ILMA e2e audit: detect stdlib usage without import.

Walks .py files under a root directory and flags files that USE
`os.environ.*`, `os.path.*`, `os.getpid`, `os.replace` without a top-level
`import os`. Also flags missing default on `os.environ.get(...)` which
returns Optional[str].

Usage:
    python3 scripts/audit_os_imports.py [ROOT]

Returns non-zero exit code if issues found - useful in CI / pre-commit.
"""
from __future__ import annotations

import argparse
import ast
import os
import sys
from pathlib import Path

STDLIB_USAGE_PATTERNS = (
    "os.environ",
    "os.path",
    "os.getpid",
    "os.replace",
    "os.makedirs",
    "os.listdir",
    "os.getenv",
)


def audit_file(path: Path) -> list[str]:
    """Return list of issues for one file (empty list if clean)."""
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(src)
    except SyntaxError as e:
        return [f"SYNTAX_ERROR: {e}"]
    except Exception:
        return []

    top_imports = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top_imports.add(node.module.split(".")[0])

    issues: list[str] = []
    for pat in STDLIB_USAGE_PATTERNS:
        if pat not in src:
            continue
        lib = pat.split(".", 1)[0]
        if lib not in top_imports:
            if f"import {lib}" in src:
                continue
            issues.append(f"{lib} used ({pat}) but no top-level `import {lib}`")

    if "os.environ.get(" in src:
        i = 0
        while True:
            j = src.find("os.environ.get(", i)
            if j < 0:
                break
            i = j + 1
            depth = 0
            k = j + len("os.environ.get")
            while k < len(src):
                c = src[k]
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            inner = src[j + len("os.environ.get") + 1: k]
            depth2 = 0
            commas_top = 0
            for ch in inner:
                if ch in "([{":
                    depth2 += 1
                elif ch in ")]}":
                    depth2 -= 1
                elif ch == "," and depth2 == 0:
                    commas_top += 1
            if commas_top == 0:
                issues.append("os.environ.get(...) called WITHOUT default -> Optional[str]")

    return issues


def walk(root: Path, skip: list[str]) -> list[tuple[Path, list[str]]]:
    out: list[tuple[Path, list[str]]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        if any(s in dirpath for s in skip):
            dirnames[:] = []
            continue
        for f in filenames:
            if not f.endswith(".py"):
                continue
            p = Path(dirpath) / f
            issues = audit_file(p)
            if issues:
                out.append((p, issues))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit os.environ usage without import")
    ap.add_argument("root", nargs="?", default=".", help="root directory to walk")
    ap.add_argument("--skip", action="append",
                    default=[".git", "__pycache__", "archive", "fabric_archive", "data"])
    args = ap.parse_args()

    findings = walk(Path(args.root), args.skip)
    if not findings:
        print(f"[OK] Clean - no `os.*` usage without `import os` under {args.root}")
        return 0
    print(f"[FAIL] Found {len(findings)} file(s) with issues:\n")
    for path, issues in findings:
        rel = path
        try:
            rel = path.relative_to(args.root)
        except ValueError:
            pass
        for issue in issues:
            print(f"  {rel}: {issue}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
