---
name: ilma-working-buffer
description: "ILMA Working Buffer Protocol — Survive the danger zone between memory flush and compaction. Log every exchange after 60% context usage. Recovery tool after context truncation."
---

# ILMA Working Buffer Protocol

**Source:** Adapted from halthelobster/proactive-agent (Hal Labs, MIT License)
**Attribution:** https://github.com/halthelobster/proactive-agent
**ILMA Integration:** v3.4

## The Problem

Context hits 60% and you enter the "danger zone." The system will eventually compact (truncate older messages). Without a working buffer, everything said in this zone is lost after compaction.

## The Solution

Log EVERY exchange in the danger zone to a persistent file (`memory/working-buffer.md`). This file survives compaction. After waking up, read it first to recover context.

## The Protocol

### Phase 1: Normal Operation (0-59% context)

- Monitor context percentage
- No buffering needed
- Normal response flow

### Phase 2: Danger Zone (60%+ context)

1. **At 60% threshold:** CLEAR the old buffer, start fresh
2. **Every message after 60%:** Append both human's message AND your response summary
3. **Leave buffer as-is** until next 60% threshold or session end

### Phase 3: Recovery (after compaction)

1. **FIRST:** Read `memory/working-buffer.md` — raw danger-zone exchanges
2. **SECOND:** Read `memory/SESSION-STATE.md` — active task state
3. Read today's + yesterday's daily notes
4. If still missing context, search all sources
5. **Extract & Clear:** Pull important context from buffer into SESSION-STATE.md
6. Present: "Recovered from working buffer. Last task was X. Continue?"

## Buffer Format

```markdown
# Working Buffer (Danger Zone Log)
**Status:** ACTIVE | ARCHIVED
**Started:** [timestamp]
**Context at start:** [percentage]%

---

## [timestamp] Human
[their message — full text]

## [timestamp] Agent (summary)
[1-2 sentence summary of your response + key details]

---

## [timestamp] Human
[their message — full text]

## [timestamp] Agent (summary)
[1-2 sentence summary of your response + key details]

---
```

## Detection Triggers

**Enter Danger Zone when:**
- Context usage exceeds 60%
- System indicates "<summary>" tag at session start
- Human says "where were we?", "continue", "what were we doing?"
- Human says "truncated", "context limits", "reset"
- You should know something but don't

**Automatic triggers:**
```python
DANGER_ZONE_THRESHOLD = 0.60  # 60% context

if context_usage > DANGER_ZONE_THRESHOLD:
    enter_danger_zone()
    start_buffering()
```

## Buffer Management

### At 60% Threshold

```bash
# Clear old buffer and start fresh
# Status becomes ACTIVE
# Timestamp updated
# Context recorded
```

### During Danger Zone

```bash
# Every exchange appended:
# - Human message (full text)
# - Agent summary (1-2 sentences)
# - Timestamp
# - Separator
```

### At Session End

```bash
# Archive buffer:
# - Change Status to ARCHIVED
# - Extract important context to SESSION-STATE.md
# - Optionally promote to daily notes
# - Keep buffer for potential recovery
```

## Recovery Workflow

### Step-by-Step

1. **Read buffer** → `memory/working-buffer.md`
2. **Read SESSION-STATE** → `memory/SESSION-STATE.md`
3. **Read daily notes** → `memory/YYYY-MM-DD.md`
4. **Unified search** → memory_search for missing context
5. **Extract & clear** → Pull important details from buffer
6. **Present recovery** → "Recovered from working buffer. Last task was X. Continue?"

### Recovery Message Format

```
📋 **Recovered from Working Buffer**

I found [N] exchanges logged during the danger zone:

**Last active task:** [task description]
**Last decision:** [decision if any]
**Key details:** [extracted from buffer]

[Buffer excerpt if relevant]

Continue from where we left off?
```

## Integration with WAL Protocol

WAL Protocol captures **corrections and decisions** BEFORE responding.
Working Buffer captures **EVERY exchange** during danger zone.

Together they ensure:
1. Important details are captured before context loss (WAL)
2. Full conversation is preserved during danger zone (Buffer)
3. Recovery is possible after compaction (Buffer recovery)

## Integration with ILMA Memory

ILMA already has:
- `memory/YYYY-MM-DD.md` (daily notes)
- `memory/DNA_UPDATES.md` (evolution rules)
- `memory/ILMA_EXTREME_TARGETS.md` (long-term goals)

Working Buffer adds:
- `memory/working-buffer.md` — danger zone log
- `memory/SESSION-STATE.md` — active task state (linked to WAL)

## Best Practices

1. **Log every exchange** — No exceptions in danger zone
2. **Summarize your responses** — 1-2 sentences, not full transcript
3. **Include timestamps** — For ordering and recovery
4. **Clear at threshold** — Don't let old buffer pollute new context
5. **Extract at end** — Pull important details before archiving

## Anti-Patterns

❌ **Don't buffer before 60%** — Wasteful, normal operation is fine
✅ **Only buffer in danger zone** — When context is at risk

❌ **Don't write full transcripts** — Summarize agent responses
✅ **1-2 sentence summaries** — Enough context, not overwhelming

❌ **Don't forget to recover** — Always read buffer at session start with `<summary>`
✅ **Recovery is automatic** — Triggered by summary tag or truncation indicator

## Verification

To verify Working Buffer is working:
1. Check `memory/working-buffer.md` after long sessions
2. If file is empty after danger zone, protocol needs enforcement
3. Test recovery: simulate truncation, check if buffer enables recovery

---

*ILMA Working Buffer Protocol v1.0*
*Integrated from: halthelobster/proactive-agent (Hal Labs)*
*Attribution: https://github.com/halthelobster/proactive-agent*
*License: MIT*