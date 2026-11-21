---
name: ilma-self-improvement
description: SSS Tier self-improvement cycle — verify-before-report, audit, evolution, learning loop
version: 2.0.0
tier: SSS
last_updated: 2026-11-01
---

# Ilma Self Improvement

## Purpose
ILMA continuous self-improvement system. Verifies state before reporting, runs audits, tracks evolution, and maintains learning loop.

## Triggers
- "ilma-self-improvement"
- post-task learning hook
- audit request
- capability status verification

## Content
Files in this skill:
- ilma-state-verify-before-report/SKILL.md
- ilma-state-verify-before-report/references/comprehensive-status-report-10-sections.md
- ilma-state-verify-before-report/references/gateway-dedup-patches-2026-06-25.md
- ilma-state-verify-before-report/references/sdk-compat-audit-matrix.md
- ilma-state-verify-before-report/references/cross-handler-param-scope-bug-class-2026-07-01.md
- ilma-state-verify-before-report/references/repr-sandbox-masking-2026-06-19.md
- ilma-state-verify-before-report/references/duplicate-delivery-audit-2026-06-20.md
- ilma-state-verify-before-report/references/verification-recipes.md
- ilma-state-verify-before-report/references/workspace-duality-daemon-audit-2026-07-01.md
- ilma-state-verify-before-report/references/audit-false-positive-pattern-2026-07-07.md

## References
- `references/reverse-engineering-capability.md` — REA (reverse-engineer-anything) capability status: NOT installed, only skill docs present; Ghidra 12.0.4 exists but headless fails without JDK+TTY; no primary_cap in 25 ILMA capabilities