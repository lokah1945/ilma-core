---
name: ilma-evolution-guide
description: Focus on functional capability parity over numbers when evolving against reference systems
version: 1.0
created: 2026-05-07
category: self-improvement
tags:
  - evolution
  - reference-system
  - functional-parity
  - capability-mapping
---

# Skill: ilma-evolution-guide

## When to Use
When instructed to evolve with reference system or compare against another system.

## Core Lesson

**FOCUS ON FUNCTIONS AND CAPABILITIES, NOT NUMBERS.**

### What Happened
1. Initial approach: Count skills/scripts -> Create more files to match numbers
2. User correction: "Ini bukan tentang angka. Ini tentang fungsi dan kemampuan."
3. Correct approach: Study actual FUNCTIONS -> Create functional equivalents -> Add unique capabilities

## The Wrong Way
- Count how many skills reference has
- Count how many scripts reference has
- Create more files to exceed count

## The Right Way
1. Study what reference scripts actually DO
2. Find functional equivalent implementations
3. Match FUNCTIONS first
4. Then add unique capabilities reference does not have

## Step-by-Step Process

### Phase 1: Deep Functional Analysis
```bash
# List reference scripts and read their contents
ls /path/to/reference/scripts/
cat /path/to/script.py
```

### Phase 2: Functional Capability Mapping
Create comparison table:

| Function | Reference | My System | Status |
|----------|-----------|-----------|--------|
| Indonesian NLP | Has 12KB | Have 10KB | PARITY |
| Semantic Memory | BM25+cosine | BM25+cosine | PARITY |

### Phase 3: Build Functional Equivalents
1. Read reference implementation
2. Understand what it DOES (not its size)
3. Implement same functionality
4. Add tests to verify

### Phase 4: Add Unique Capabilities
After parity, add capabilities reference system lacks.

## Critical Functions When Evolving Against ILMA

| Critical Function | ILMA File | ILMA Equivalent |
|-----------------|-----------|------------------|
| Indonesian NLP | ILMA_indonesian_nlp.py | ilma_indonesian_nlp.py |
| Semantic Memory | ILMA_memory_layer.py | ilma_memory_layer.py |
| Eval Harness | ILMA_eval_harness.py | ilma_eval_harness.py |
| Hook Engine | ILMA_hook_engine.py | ilma_hook_engine.py |
| Ethics Core | ILMA_ethics_core.py | ilma_ethics_core.py |
| Blue Team Rules | ILMA_blue_team_rules.py | ilma_blue_team_rules.py |

## Verification
```bash
python3 scripts/ilma_[function].py
# Should output operational confirmation
```

## Phase 0: Governance Before Everything (LESSON: Phase 4C-R3, 2026-06-04)

**Critical Rule:** Do NOT start capability evolution work without governance first.

Before touching any capability, create a governance document with:
1. Scope of development
2. Security boundaries
3. Prohibited activities (what ILMA must NEVER do)
4. Allowed activities
5. Definition of target tier (e.g., SSS+++ criteria)
6. Evidence requirements
7. Rollback policy
8. Human escalation policy
9. Data privacy policy
10. External auditor handoff format

**Do not proceed to Phase 1 before governance is complete.** The governance document is the contract that makes all evolution traceable, auditable, and rollback-able.

## Phase Gate Pattern (LESSON: Phase 4C-R3, 2026-06-04)

Every phase MUST have explicit acceptance criteria (gate) verified by tool before claiming completion.

Example gate structure — 12 criteria:
```
  1. Security incident contained (if any)
  2. No raw API keys/credentials in any output file
  3. Credential loader handles all providers
  4. Router uses authority file as single source of truth
  5. Router considers multiple free providers (not single-provider)
  6. Multi-provider fallback ranked by composite score (not hardcoded)
  7. OpenRouter free subset — data gap documented, not claimed as code bug
  8. Paid/unknown providers blocked at routing layer
  9. L1 production test passes (6/6 or stated benchmark)
 10. Selection trace explains why model was chosen
 11. No new source-of-truth duplicating existing authority files
 12. No tier claims (SSS+++, SSS, etc.) in any output
```

**Pattern:** All criteria must pass (12/12). Failed criteria → fix ONLY those. Gate verification must be automated where possible.

## Security-First Execution (LESSON: Phase 4C-R3, 2026-06-04)

**Absolute priority:** Security incident handling comes BEFORE all other work.

If a secret/API key leak is discovered:
1. STOP all other work immediately
2. Scan ALL output files with secret patterns (nvapi-, sk-or-, sk-cp-, etc.)
3. Redact all occurrences — replace with [REDACTED] or metadata-only identifiers
4. Report incident to Bos immediately (scope, files affected, rotation recommendation)
5. Only continue other work after incident is contained

**Credential slot naming rule:** Never use `provider-{identifier}` patterns in slot names.
- WRONG: `nvapi-smahud@gmail.com`, `oro-slot-1`
- RIGHT: `smahud@gmail.com` (pure email), `slot_1`
Reason: `nvapi-*` patterns trigger secret-leak scanners even in metadata.

## Architecture Bug vs Data Gap — Critical Distinction (LESSON: Phase 4C-R3, 2026-06-04)

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| Model ranked low | Missing benchmark enrichment | Enrich authority file, NOT rewrite router |
| "NVIDIA-centric" routing | NVIDIA is only provider with benchmark data | Add benchmark data for other providers |
| Capability marked UNVERIFIED | Registry wrong, runtime works | Fix registry, don't rewrite code |
| OpenRouter models not selected | quality_score=0 (no data), not code bug | Run DB enrichment pipeline, not router fix |

**The most expensive mistake:** Rewriting code that already works correctly because the data powering it was incomplete.

## Tier Claiming Rules

- Never claim SSS+++, SSS+, SSS until formal certification gate passes
- Never claim a capability is "VERIFIED" without test evidence
- Never claim a pattern is "correct" without running the tests
- Bos explicitly prohibits SSS+++ claims until all certification criteria pass

## Author
ILMA - Learned from evolution session 2026-05-07
Updated 2026-06-04: governance-first, gate pattern, security-first, architecture-vs-data distinction
