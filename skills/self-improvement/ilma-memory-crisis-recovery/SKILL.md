---
name: ilma-memory-crisis-recovery
description: "ILMA Memory Tool Crisis Recovery — recover when memory tool hits its 2,200 char hard limit. Multi-file rewrite + memory API operations batch pattern."
tags:
  - memory
  - crisis-recovery
  - system-maintenance
  - batch-operations
triggers:
  - "memory full"
  - "can't save memory"
  - "memory tool failed"
  - "is ILMA stuck"
  - "memory crisis"
  - "memory at 97%"
  - "char limit"
---

# ILMA Memory Crisis Recovery

## Problem

The `memory` tool has a **2,200 char hard limit** for injection. When it reaches ~97% (2,148+ chars):
- New `memory save` calls silently fail
- Memory injection becomes unreliable
- System appears "frozen" even though ILMA is operational

## Symptoms

1. `memory` tool saves seem to work but don't persist
2. Memory injection shows very high char count
3. User reports ILMA "stuck" or not responding correctly
4. Daily memory file missing for current date
5. Evidence/learning not being saved between sessions

---

## Solution Pattern

### Step 1: Diagnose — Measure Actual Memory State

```bash
# Test current memory injection size
cd /root/.hermes/profiles/ilma
echo "=== Memory Tool Test ==="
python3 -c "
import json
with open('memory/memory.md') as f:
    content = f.read()
print(f'Current memory.md: {len(content)} chars')
"

# List all memory files and sizes
find memory/ -name "*.md" -exec wc -c {} \; | sort -rn | head -20

# Check if daily memory exists
ls -la memory/$(date +%Y-%m-%d).md 2>/dev/null || echo "DAILY MEMORY MISSING"
```

### Step 2: Identify What's Bloating Memory

```bash
# Find largest memory files
find memory/ -name "*.md" -exec wc -l {} \; | sort -rn | head -10

# Check SOUL.md size (should NOT be in memory tool)
wc -c SOUL.md 2>/dev/null || echo "Not found"

# List memory directory
ls -la memory/
```

### Step 3: Backup Before Rewriting

```bash
cd /root/.hermes/profiles/ilma/memory

# Always backup before rewriting
for f in DNA_UPDATES.md ILMA_EXTREME_TARGETS.md UPGRADE_BACKLOG.md SYSTEM_STATE.md; do
    [ -f "$f" ] && cp -v "$f" "${f}.bak.$(date +%s)"
done

# Count backups
ls *.bak.* 2>/dev/null | wc -l
```

### Step 4: Rewrite Memory Files with Compact Formatting

The fix is **rewrite not delete** — preserve context while reducing character count.

**Key strategies:**
1. Remove verbose explanations, keep only facts
2. Use abbreviations where unambiguous
3. Remove redundant entries (entries that appear in multiple files)
4. Consolidate related information
5. Remove task-specific details (save those to daily memory files instead)
6. Keep injection-critical facts only

**Target: ~366 chars / 2,200** (leaving 83% headroom)

### Step 5: Create Separate LONGTERM_MEMORY.md

For curated facts that should persist across sessions but don't need to be in the memory tool injection:

```bash
cat > memory/LONGTERM_MEMORY.md << 'EOF'
# LONGTERM MEMORY — Curated facts, NOT injected via memory tool
# Read manually when needed in main sessions

## ILMA Identity & Setup
- ILMA = Hermes Agent, Memory Specialist, Smart Router
- Profile: /root/.hermes/profiles/ilma
- v3.0 (2026-05-08) — Post-Optimization, 12 canonical + 240 scripts

## Felo Integration (2026-05-08)
- Account: lokah2150@gmail.com
- API Key: in /root/credential/api_key.json:felo
- LiveDoc: YfxkwnggzHQJhtfuoZpEnH
- 11 skills in ~/.hermes/skills/felo/
- Routing: planning→superagent, news→search, twitter→writer
- Threads expire — renew with new conversation when "fetch failed"

## Phase 7 Results (2026-05-08)
- Phase 6J delivered — 12-phase extreme target system complete
- 4 targets: longform/1000p, codebase/1000f, research/paper, OS/deriv
- 52 sub-capabilities mapped, 27 benchmark rungs
- DNA-006 to DNA-010 ACTIVE

## System Health
- Gateway PID: 78963, Telegram connected
- Memory injection: ~366/2200 chars (healthy)
- Use daily memory: memory/YYYY-MM-DD.md for session data
- Evidence ledger: config/ilma_evidence_registry.json
- Capability registry: config/ilma_capability_registry.json
EOF
```

### Step 6: Create Daily Memory File

```bash
DATE=$(date +%Y-%m-%d)
cat > "memory/${DATE}.md" << 'EOF'
# Daily Memory — $(date)

## Session Summary
[TODO: Fill with session accomplishments]

## Issues Found
[TODO: Document any problems encountered]

## Next Actions
[TODO: Document pending tasks]
EOF
```

### Step 7: Rewrite Memory Tool Content (Target ~366 chars)

Use the `memory` tool to replace the entire memory content with a compact version.

### Step 8: Verify Fix

```bash
cd /root/.hermes/profiles/ilma
python3 -c "
content = open('memory/memory.md').read()
print(f'Memory injection: {len(content)} chars / 2200')
print(f'Headroom: {2200 - len(content)} chars ({(2200-len(content))/2200*100:.1f}%)')
"
```

---

## Memory API `operations[]` Batch Pattern (NEW 2026-06-20)

**Critical pitfall learned:** Single-step `memory` calls DO NOT batch well. When nearing the limit, you cannot incrementally add or replace — the final state is rejected as `would exceed limit`.

### Symptom

```
<error>Memory at 2,154/2,200 chars. Adding this entry (322 chars) would exceed the limit.
Consolidate now: use 'replace' to merge overlapping entries into shorter ones or 'remove' stale or
less important entries, then retry — all in this turn.</error>
```

Or worse, in mid-batch:
```
<error>After applying all 3 operations, memory would be at 2,262/2,200 chars -- over the limit.
Remove or shorten more entries in the same batch.</error>
```

### Why This Happens

- `replace` ops do not lock the char budget before computing
- Each operation computes its result character count separately
- The error message **only triggers when an individual operation** exceeds, NOT the batch sum

### Required Pattern

Use `operations` array (single-batch atomic apply) for any complex memory transaction. Pass ALL adds/removes/replaces in ONE call. The runtime computes the FINAL char budget; if it exceeds 2,200, the entire batch is rejected atomically with no partial write.

```python
# Python equivalent of memory tool call:
memory(
    action="operations",
    operations=[
        {"action": "remove", "old_text": "entry A to remove"},
        {"action": "remove", "old_text": "entry B to remove"},
        {"action": "add",    "content": "new concise entry C"},
        {"action": "replace", "old_text": "long entry D", "new_string": "shorter entry D"},
    ],
)
```

### Atomicity Invariant

> **All-or-nothing batch semantics**: if ANY operation causes the final state to exceed the budget, NONE of the operations are applied. Lifetime of partial intermediate states is zero.

This means you can safely reason about the budget by:
1. **Compute post-state size** = current_size - removed_size + added_size - diff_in_replace
2. **If post-state > 2,200**, shrink entries before submitting

### Compression Strategy When Budget Tight

Use `replace` with shorter `new_string` to free budget on a single batch operation:

```python
# 5 entries × average 400 chars = 2,000 chars (too tight)
# Strategy: compress 1 largest entry to free ~250 chars
memory(
    action="operations",
    operations=[
        {"action": "replace", "old_text": "[mem_X] long content...", "new_string": "[mem_X] short"},
        {"action": "add", "content": "[mem_Y] new content"},
    ],
    # Post-state target: under 2,200 (200 chars headroom minimum)
)
```

### Anti-Patterns

❌ **Add multiple entries one-at-a-time** — second call may reject (budget exceeded)
❌ **Try to remove one then add bigger** — failure leaves partial state
❌ **Skip computing post-state size** — produces error cycle
❌ **Use `action="add"` for the lone-op** — when multi-op needed, batch via `operations`
❌ **Compress prose in add** — better to use `replace` to shorten EXISTING entry first

### Practical Sequence

1. **First measure** — `memory(action=...)` returns usage in the response
2. **Plan the batch** — list all ops, compute post-state size in your head
3. **Submit as operations** in ONE call
4. **Verify the response** — check usage reflects the post-batch state

### Related Tip: `replace` Single-Ops Need `old_text`

Single-op `replace` requires both `old_text` AND `new_string`. Forgetting either produces an error. When patching multiple occurrences, use `replace_all=true`.

---

## Additional Fixes to Check

When memory crisis is part of a broader "freeze" diagnostic, also check:

### Codex SQLite WAL Bloat
```bash
ls -lh /root/.hermes/profiles/ilma/home/.codex/logs_2.sqlite
sqlite3 /root/.hermes/profiles/ilma/home/.codex/logs_2.sqlite "PRAGMA wal_checkpoint(TRUNCATE);"
```

### Cron Lock Check
```bash
ls -la /root/.hermes/profiles/ilma/.cron.lock 2>/dev/null
cat /root/.hermes/profiles/ilma/.cron.lock 2>/dev/null || echo "LOCK EMPTY"
```

### Gateway Health
```bash
ps aux | grep -E "(78963|ilma_hermes)" | grep -v grep
uptime
```

---

## Key Lessons Learned

1. **Memory tool has hard 2,200 char limit** — not documented, must be self-discovered
2. **Silent failure** — memory saves appear to work but don't persist when at limit
3. **Rewrite, don't delete** — backup first, then compact, never just wipe
4. **Separate concerns** — LONGTERM_MEMORY.md for curated facts, daily memory for session data, memory tool injection only for critical identity/preference facts
5. **Prevention** — run weekly memory compaction, use daily memory files, keep injection tight
6. **BATCH required near limit** — single-call `add`/`replace` will fail when within ~200 chars of limit. Use `operations[]` batch atomic apply
7. **`replace` shortens to free budget** — when compressing, use `replace` with shorter `new_string` rather than remove+add (atomic + smaller fail window)

## Anti-Patterns

❌ **Don't just delete memory files** — you'll lose context
❌ **Don't keep saving to memory tool when at limit** — it silently fails
❌ **Don't put everything in memory tool injection** — use daily files + LONGTERM_MEMORY.md
❌ **Don't assume memory save worked** — verify by reading back
❌ **Don't skip backups** — memory files contain critical identity data
❌ **Don't add atomically when near limit** — use `operations[]` batch

## Related Skills

- `ilma-memory` — Normal memory operations
- `ilma-evolution-routine` — Daily optimizer that should prevent this
- `ilma-system-optimizer-workflow` — Broader system cleanup
- `memory-audit-protocol` — F0 priority chain, MEMORY SOVEREIGNTY (v8/v9/v10)
- `ilma-false-positive-detection` — Avoid over-claim; prefer verification over blanket prohibition

## Files

| File | Purpose |
|------|---------|
| `memory/memory.md` | Memory tool injection (~366 chars target) |
| `memory/LONGTERM_MEMORY.md` | Curated long-term facts (2KB) |
| `memory/YYYY-MM-DD.md` | Daily session memory |
| `memory/*.md.bak.*` | Backups before rewrite |
