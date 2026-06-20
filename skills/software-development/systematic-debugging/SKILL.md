---
name: systematic-debugging
description: "4-phase root cause debugging: understand bugs before fixing."
version: 1.2.0
author: Hermes Agent (adapted from obra/superpowers)
license: MIT
metadata:
  hermes:
    tags: [debugging, troubleshooting, problem-solving, root-cause, investigation]
    related_skills: [test-driven-development, writing-plans, subagent-driven-development]
---

# Systematic Debugging

## Overview

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**Violating the letter of this process is violating the spirit of debugging.**

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## When to Use

Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues

**Use this ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work
- You don't fully understand the issue

**Don't skip when:**
- Issue seems simple (simple bugs have root causes too)
- You're in a hurry (rushing guarantees rework)
- Someone wants it fixed NOW (systematic is faster than thrashing)

## The Four Phases

You MUST complete each phase before proceeding to the next.

---

## Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

### 1. Read Error Messages Carefully

- Don't skip past errors or warnings
- They often contain the exact solution
- Read stack traces completely
- Note line numbers, file paths, error codes

**Action:** Use `read_file` on the relevant source files. Use `search_files` to find the error string in the codebase.

### 2. Reproduce Consistently

- Can you trigger it reliably?
- What are the exact steps?
- Does it happen every time?
- If not reproducible → gather more data, don't guess

**Action:** Use the `terminal` tool to run the failing test or trigger the bug:

```bash
# Run specific failing test
pytest tests/test_module.py::test_name -v

# Run with verbose output
pytest tests/test_module.py -v --tb=long
```

### 3. Check Recent Changes

- What changed that could cause this?
- Git diff, recent commits
- New dependencies, config changes

**Action:**

```bash
# Recent commits
git log --oneline -10

# Uncommitted changes
git diff

# Changes in specific file
git log -p --follow src/problematic_file.py | head -100
```

### 4. Gather Evidence in Multi-Component Systems

**WHEN system has multiple components (API → service → database, CI → build → deploy):**

**BEFORE proposing fixes, add diagnostic instrumentation:**

For EACH component boundary:
- Log what data enters the component
- Log what data exits the component
- Verify environment/config propagation
- Check state at each layer

Run once to gather evidence showing WHERE it breaks.
THEN analyze evidence to identify the failing component.
THEN investigate that specific component.

### 5. Trace Data Flow

**WHEN error is deep in the call stack:**

- Where does the bad value originate?
- What called this function with the bad value?
- Keep tracing upstream until you find the source
- Fix at the source, not at the symptom

**Action:** Use `search_files` to trace references:

```python
# Find where the function is called
search_files("function_name(", path="src/", file_glob="*.py")

# Find where the variable is set
search_files("variable_name\\s*=", path="src/", file_glob="*.py")
```

### Phase 1 Completion Checklist

- [ ] Error messages fully read and understood
- [ ] Issue reproduced consistently
- [ ] Recent changes identified and reviewed
- [ ] Evidence gathered (logs, state, data flow)
- [ ] Problem isolated to specific component/code
- [ ] Root cause hypothesis formed

**STOP:** Do not proceed to Phase 2 until you understand WHY it's happening.

---

## Phase 2: Pattern Analysis

**Find the pattern before fixing:**

### 1. Find Working Examples

- Locate similar working code in the same codebase
- What works that's similar to what's broken?

**Action:** Use `search_files` to find comparable patterns:

```python
search_files("similar_pattern", path="src/", file_glob="*.py")
```

### 2. Compare Against References

- If implementing a pattern, read the reference implementation COMPLETELY
- Don't skim — read every line
- Understand the pattern fully before applying

### 3. Identify Differences

- What's different between working and broken?
- List every difference, however small
- Don't assume "that can't matter"

### 4. Understand Dependencies

- What other components does this need?
- What settings, config, environment?
- What assumptions does it make?

---

## Phase 3: Hypothesis and Testing

**Scientific method:**

### 1. Form a Single Hypothesis

- State clearly: "I think X is the root cause because Y"
- Write it down
- Be specific, not vague

### 2. Test Minimally

- Make the SMALLEST possible change to test the hypothesis
- One variable at a time
- Don't fix multiple things at once

### 3. Verify Before Continuing

- Did it work? → Phase 4
- Didn't work? → Form NEW hypothesis
- DON'T add more fixes on top

### 4. When You Don't Know

- Say "I don't understand X"
- Don't pretend to know
- Ask the user for help
- Research more

---

## Phase 4: Implementation

**Fix the root cause, not the symptom:**

### 1. Create Failing Test Case

- Simplest possible reproduction
- Automated test if possible
- MUST have before fixing
- Use the `test-driven-development` skill

### 2. Implement Single Fix

- Address the root cause identified
- ONE change at a time
- No "while I'm here" improvements
- No bundled refactoring

### 3. Verify Fix

```bash
# Run the specific regression test
pytest tests/test_module.py::test_regression -v

# Run full suite — no regressions
pytest tests/ -q
```

### 4. If Fix Doesn't Work — The Rule of Three

- **STOP.**
- Count: How many fixes have you tried?
- If < 3: Return to Phase 1, re-analyze with new information
- **If ≥ 3: STOP and question the architecture (step 5 below)**
- DON'T attempt Fix #4 without architectural discussion

### 4b. Post-Fix Verification with Judge System

After Phase 4 fix verification (pytest passes), **run Judge System** to confirm the solution actually solves the problem:

```bash
# Quick targeted check
python3 scripts/ilma_judge_system.py <fixed_file.py> \
    --task "Debug session: verify fix for [issue]" \
    --checkpoints L1_syntax L1_import L2_unit_tests

# Full verification
python3 scripts/ilma_judge_system.py <fixed_file.py> \
    --task "Debug session: post-fix verification" --json
```

**Why:** Tests prove code runs. Judge proves solution works. Debugging that doesn't use Judge may have fixed symptoms, not root cause.

### 5. If 3+ Fixes Failed: Question Architecture

**Pattern indicating an architectural problem:**
- Each fix reveals new shared state/coupling in a different place
- Fixes require "massive refactoring" to implement
- Each fix creates new symptoms elsewhere

**STOP and question fundamentals:**
- Is this pattern fundamentally sound?
- Are we "sticking with it through sheer inertia"?
- Should we refactor the architecture vs. continue fixing symptoms?

**Discuss with the user before attempting more fixes.**

This is NOT a failed hypothesis — this is a wrong architecture.

---

## Red Flags — STOP and Follow Process

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- "Skip the test, I'll manually verify"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- "Pattern says X but I'll adapt it differently"
- "Here are the main problems: [lists fixes without investigation]"
- Proposing solutions before tracing data flow
- **"One more fix attempt" (when already tried 2+)**
- **Each fix reveals a new problem in a different place**

**ALL of these mean: STOP. Return to Phase 1.**

**If 3+ fixes failed:** Question the architecture (Phase 4 step 5).

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too. Process is fast for simple bugs. |
| "Emergency, no time for process" | Systematic debugging is FASTER than guess-and-check thrashing. |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right from the start. |
| "I'll write test after confirming fix works" | Untested fixes don't stick. Test first proves it. |
| "Multiple fixes at once saves time" | Can't isolate what worked. Causes new bugs. |
| "Reference too long, I'll adapt the pattern" | Partial understanding guarantees bugs. Read it completely. |
| "I see the problem, let me fix it" | Seeing symptoms ≠ understanding root cause. |
| "One more fix attempt" (after 2+ failures) | 3+ failures = architectural problem. Question the pattern, don't fix again. |

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Root Cause** | Read errors, reproduce, check changes, gather evidence, trace data flow | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare, identify differences | Know what's different |
| **3. Hypothesis** | Form theory, test minimally, one variable at a time | Confirmed or new hypothesis |
| **4. Implementation** | Create regression test, fix root cause, verify | Bug resolved, all tests pass |

## Hermes Agent Integration

### Investigation Tools

Use these Hermes tools during Phase 1:

- **`search_files`** — Find error strings, trace function calls, locate patterns
- **`read_file`** — Read source code with line numbers for precise analysis
- **`terminal`** — Run tests, check git history, reproduce bugs
- **`web_search`/`web_extract`** — Research error messages, library docs

### With delegate_task

For complex multi-component debugging, dispatch investigation subagents:

```python
delegate_task(
    goal="Investigate why [specific test/behavior] fails",
    context="""
    Follow systematic-debugging skill:
    1. Read the error message carefully
    2. Reproduce the issue
    3. Trace the data flow to find root cause
    4. Report findings — do NOT fix yet

    Error: [paste full error]
    File: [path to failing code]
    Test command: [exact command]
    """,
    toolsets=['terminal', 'file']
)
```

### With test-driven-development

When fixing bugs:
1. Write a test that reproduces the bug (RED)
2. Debug systematically to find root cause
3. Fix the root cause (GREEN)
4. The test proves the fix and prevents regression

## Pitfalls

### Parallel Executor sys.path Shadowing

**Symptom:** A job handler works in isolation but fails in the parallel executor (1 per-cycle failure, every cycle).

**Root cause:** Process startup sets `sys.path.insert(0, "subdir")`, shadowing the root directory. Handlers that import root-level modules via `from module_name import ...` (without absolute path) fail silently because the root is no longer in the search path.

**Rule:** Inside job handler functions in `scripts/`, always explicitly set the root path before importing modules that live at project root:

```python
def job_handler() -> dict:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent))  # ILMA root
    from ilma_capability_registry import CapabilityRegistry
    ...
```

**See also:** `references/parallel-executor-path-resolution.md`

---

### Deep System Cleanup Pattern

**Symptom:** Need to remove deprecated component (legacy proxy project, old feature, deprecated subsystem) completely from codebase. Bos-style directive: "hapus sampai ke akar-akarnya", "no backward compatibility", "zero reference including memory".

**Root cause:** Components spread across active code, backups, archives, skills, sessions, config files, schema enums, JSON data, and documentation. Naive deletion misses hidden references. Semantic usages of the substring (song names, idioms, city names, design patterns) further complicate detection.

**Systematic cleanup pattern:**

**Phase 1: Comprehensive Discovery (5+ search patterns)** — see `references/deep-cleanup-pattern-20260619.md` for the full validated pattern.

**Phase 2: Categorize References** — split into ACTIVE / HISTORICAL / SEMANTIC using the Semantic Disambiguation Table in the reference doc.

**Phase 3: Deletion Strategy (ORDER MATTERS)**

1. **Backups first** — `rm -rf old_dated_folders` prevents old backups re-introducing removed code
2. **Duplicate folders** — `hermes_profile_<name>/` is often a full tree duplicate
3. **Schema/manifest before code** — JSON Schema enums must be updated before data validation runs
4. **Active code** — patch with clean replacements (no `if removed: legacy` stubs!)
5. **Data files (JSON/YAML)** — use Python script to filter nested dicts/lists
6. **Skills/Docs** — delete if target-specific, generic-ify if used target as example
7. **Memory** — mark entries `[HISTORICAL NOTE]` (don't delete, preserves audit trail)

**CRITICAL: No backward-compat stubs**

```python
# ❌ WRONG — leaves false sense of feature availability
@property
def is_target_source(self) -> bool:
    """Legacy compat — removed."""
    return False

# ✅ RIGHT — delete the symbol entirely
# (function deleted entirely, no replacement)
```

**Verification (4 mandatory checks — also see `scripts/verify_cleanup.sh`)**

```bash
# Run all 4 checks in one command
bash scripts/verify_cleanup.sh <target-string>

# Or manually:
# 1. Active code search — should be ZERO except for semantic usages
grep -rln "target-x\|target_proxy\|target_sync" --include="*.py" --include="*.json" --include="*.yaml" . 2>/dev/null \
  | grep -v ".git" | grep -v ".git-rewrite" | grep -v "sessions/" | grep -v "node_modules"

# 2. Module compile check
python3 -c "import sys; sys.path.insert(0, '.')
for m in ['ilma_subagent_router', 'ilma_model_registry']: __import__(m)"

# 3. Status check
python3 ilma.py --status

# 4. Wiring check
python3 ilma_runtime_wiring.py --verify
```

**Top 3 Pitfalls (see reference doc for 5):**

1. **`.git-rewrite/t/` is NOT a backup folder** — it's BFG Repo-Cleaner staging. Files there may be the only tracked copy. Always verify with `git ls-files` before deleting "archive" folders.
2. **Semantic strings look like project names** — "bridge" appears 1752 times in `LEARNINGS.md` but only a fraction is the bridge project. Apply the Semantic Disambiguation Table.
3. **Schema enum removal can break validation** — JSON Schema enums validate at load time. Patch data files BEFORE schemas.

**Memory marking pattern (preserves audit trail):**

```diff
-SOT LIVE-ONLY (...): ... **TARGET PROJECT FULLY REMOVED YYYY-MM-DD**: Zero target-x reference...
+SOT LIVE-ONLY (..., updated YYYY-MM-DD): ... **TARGET PROJECT FULLY REMOVED YYYY-MM-DD [HISTORICAL NOTE]**: All target-x sub-components deleted...
```

**Time Estimate** (validated 2026-06-19)

- Naive deletion (rm -f *target*): 2 minutes → 90% incomplete
- Systematic cleanup: 20-25 minutes → 100% verified removal

**See also:**
- `references/deep-cleanup-pattern-20260619.md` — full validated pattern with 5 search patterns, semantic disambiguation table, 5 pitfalls, ordering rationale
- `scripts/verify_cleanup.sh` — 4-check verification script (re-runnable)

---

### Random Fixes Waste Time

Random fixes waste time and create new bugs. Quick patches mask underlying issues.
- Systematic approach: 15-30 minutes to fix
- Random fixes approach: 2-3 hours of thrashing
- First-time fix rate: 95% vs 40%
- New bugs introduced: Near zero vs common

**No shortcuts. No guessing. Systematic always wins.**
