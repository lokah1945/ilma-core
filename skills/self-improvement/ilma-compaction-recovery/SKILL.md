---
name: ilma-compaction-recovery
description: "ILMA Compaction Recovery — Step-by-step recovery when context gets truncated. Auto-trigger on summary tags, truncation indicators, or 'where were we' questions. Read working buffer, SESSION-STATE, daily notes, then unified search."
---

# ILMA Compaction Recovery

**Source:** Adapted from halthelobster/proactive-agent (Hal Labs, MIT License)
**Attribution:** https://github.com/halthelobster/proactive-agent
**ILMA Integration:** v3.4

## The Problem

Session starts with `<summary>` tag. Or human says "where were we?" Context was truncated. Without recovery, you start fresh and lose all progress.

## The Solution

Compaction Recovery is a step-by-step protocol that reconstructs context from multiple sources, starting with the most recent (working buffer) and cascading to older sources (daily notes, memory search).

## Auto-Trigger Conditions

**Compaction Recovery activates when ANY of:**
1. Session starts with `<summary>` tag
2. Message contains "truncated", "context limits", "context lost"
3. Human says "where were we?", "continue", "what were we doing?"
4. Human says "I was just saying...", "as I mentioned"
5. You should know something but don't (knowledge gap detected)

**Don't ask "what were we discussing?"** — The working buffer literally has the conversation.

## Recovery Steps

### Step 1: Read Working Buffer
```
Source: memory/working-buffer.md
Action: Parse buffer entries from most recent to oldest
Why: Buffer captures every exchange during danger zone
```

### Step 2: Read SESSION-STATE
```
Source: memory/SESSION-STATE.md
Action: Read active task state, decisions, preferences
Why: WAL entries capture corrections and decisions
```

### Step 3: Read Daily Notes
```
Source: memory/YYYY-MM-DD.md (today + yesterday)
Action: Scan for task context, decisions, file changes
Why: Daily notes capture full session activity
```

### Step 4: Unified Search (if needed)
```
Source: memory_search("query") — all available sources
Action: Search for specific topics, files, decisions
Why: Semantic search finds relevant context missed by file reading
```

### Step 5: Extract & Clear
```
Action: 
- Pull important context from buffer into SESSION-STATE.md
- Note unresolved tasks
- Note pending decisions
- Note file modifications
```

### Step 6: Present Recovery
```
Format: "Recovered from working buffer. [summary]. Continue from where we left off?"

Example:
"Recovered from working buffer. Last task was writing Phase 15 docs for ClawHub integration.
We had completed 8 of 12 subsections. File is at docs/ILMA_PHASE15_CLAWHUB_INTEGRATION.md.
Continue with subsection 9 (Specific Integrations)?"
```

## Recovery Message Template

```
📋 **Compaction Recovery Complete**

I found context from [N] sources:

**Status:** [Active task / Last action / Outstanding items]

**From Working Buffer:**
- [Key exchanges logged during danger zone]
- [Last decision or modification]

**From SESSION-STATE:**
- [Active task description]
- [User preferences captured via WAL]
- [Constraints or requirements]

**From Daily Notes:**
- [Recent session activity]
- [Files modified]
- [Decisions made]

**Outstanding:** [Any tasks that were in progress]
**Next Step:** [Suggested continuation point]

Continue from where we left off?
```

## Integration with Working Buffer

Working Buffer feeds Compaction Recovery:

```
Working Buffer (Phase 2: Danger Zone)
  ↓ [Session ends / compaction occurs]
Compaction Recovery (Phase 3: Recovery)
  ↓ [Extract important context]
SESSION-STATE.md (Updated with recovered details)
```

## Integration with WAL Protocol

WAL Protocol provides high-value context for recovery:

```
WAL captures: corrections, decisions, preferences, constraints
  ↓ [During recovery]
Extract: Important WAL entries from buffer
  ↓ [Promote to]
SESSION-STATE.md (Recovery summary)
```

## Common Scenarios

### Scenario 1: Long Session with Context Loss

```
Initial: Session starts with <summary> tag
→ Read working buffer (found 15 exchanges)
→ Read SESSION-STATE (found active task)
→ Read daily notes (found file path)
→ Extract: "Writing Phase 15 docs, subsection 9 of 12"
→ Present: Recovery summary + continuation point
```

### Scenario 2: "Where were we?"

```
Human: "Where were we?"
→ Check working buffer (found exchanges)
→ Check SESSION-STATE (found task + preferences)
→ Present: "We were writing the ClawHub integration docs..."
```

### Scenario 3: Truncated Mid-Task

```
System: "Context limits reached, truncating..."
→ Buffer has: current file being written, last section completed
→ SESSION-STATE has: task description, file path, line number
→ Recovery: "Last task: writing Phase 15 subsection 9. File at line 450. Continue?"
```

## Best Practices

1. **Never skip sources** — Always follow order: buffer → SESSION-STATE → daily → search
2. **Extract immediately** — Pull important context from buffer to SESSION-STATE
3. **Be specific in recovery** — Include file paths, line numbers, task details
4. **Suggest next step** — Don't just say "ready to continue" — say "Continue with X?"
5. **Ask for confirmation** — Let human verify recovery is accurate

## Anti-Patterns

❌ **Don't ask "what were we doing?"** — You have the buffer, use it
✅ **Read buffer first** — The answer is in the buffer

❌ **Don't start from scratch** — Recovery protocol exists for this
✅ **Follow recovery steps** — Structured approach ensures nothing missed

❌ **Don't give vague recovery** — "We were working on something" is useless
✅ **Be specific** — File, line, task, decisions, next step

## File Locations

```
memory/
├── working-buffer.md    # Danger zone log (recovery source 1)
├── SESSION-STATE.md     # Active task state (recovery source 2)
├── YYYY-MM-DD.md         # Daily notes (recovery source 3)
└── [other memory files]  # Unified search targets
```

## Verification

To verify Compaction Recovery works:
1. Simulate truncation (don't provide context)
2. Check if recovery steps execute in order
3. Verify recovery message is specific (not vague)
4. Confirm continuation point is accurate

---

*ILMA Compaction Recovery v1.0*
*Integrated from: halthelobster/proactive-agent (Hal Labs)*
*Attribution: https://github.com/halthelobster/proactive-agent*
*License: MIT*