---
name: ilma-wal-protocol
description: "ILMA WAL Protocol — Write-Ahead Logging for corrections, decisions, and critical details. Captures important information BEFORE responding so nothing is lost to context loss. Trigger: every human message."
---

# ILMA WAL Protocol — Write-Ahead Logging

**Source:** Adapted from halthelobster/proactive-agent (Hal Labs, MIT License)
**Attribution:** https://github.com/halthelobster/proactive-agent
**ILMA Integration:** v3.4

## The Law

> You are a stateful operator. Chat history is a BUFFER, not storage. `SESSION-STATE.md` is your "RAM" — the ONLY place specific details are safe.

## The Problem

The urge to respond is the enemy. A correction feels so obvious ("use blue, not red") that writing it down seems unnecessary. But context vanishes. Details get forgotten. Future sessions lose critical information.

## The Protocol

### Trigger — SCAN EVERY MESSAGE FOR:

| Signal | What to Capture |
|--------|-----------------|
| ✏️ **Corrections** | "It's X, not Y" / "Actually..." / "No, I meant..." |
| 📍 **Proper nouns** | Names, places, companies, products, URLs |
| 🎨 **Preferences** | Colors, styles, approaches, "I like/don't like" |
| 📋 **Decisions** | "Let's do X" / "Go with Y" / "Use Z" |
| 📝 **Draft changes** | Edits to something we're working on |
| 🔢 **Specific values** | Numbers, dates, IDs, quantities |
| ⚠️ **Constraints** | "Don't...", "Never...", "Must be...", "Avoid..." |
| 🔄 **Context switches** | "Actually, let's try..." / "Wait, can we..." |

### The Action

**If ANY of these appear:**
1. **STOP** — Do not start composing your response
2. **WRITE** — Update `memory/SESSION-STATE.md` with the detail
3. **THEN** — Respond to the human

```python
# Example workflow:
if human_input_contains(WAL_TRIGGERS):
    write_to_session_state(detail)
    respond_to_human()
else:
    respond_to_human()  # Normal flow
```

### Why This Works

The trigger is the human's INPUT, not your memory. You don't have to remember to check — the rule fires on what they say. Every correction, every name, every decision gets captured automatically.

## WAL Entry Format

When capturing a WAL entry, write to `memory/SESSION-STATE.md`:

```markdown
## WAL Entry — [timestamp]

### Type: correction | preference | decision | constraint | proper_noun | specific_value
### Source: human_input

**Detail:** [what was captured]
**Context:** [why it matters for this task]
**Action:** [if any follow-up needed]

---
```

## Example Triggers

```
Human: "Use the blue theme, not red"
→ Write: "Theme: blue (not red)" → Then respond

Human: "The project is for Acme Corp, not Beta Inc"
→ Write: "Client: Acme Corp (not Beta Inc)" → Then respond

Human: "I prefer longer explanations, not short ones"
→ Write: "User preference: detailed responses > concise" → Then respond

Human: "Let's use PostgreSQL for the database"
→ Write: "Database: PostgreSQL (decision made)" → Then respond

Human: "Never use the delete command without confirmation"
→ Write: "Constraint: confirm before delete" → Then respond
```

## Integration with ILMA Memory System

ILMA already has:
- `memory/YYYY-MM-DD.md` (daily notes)
- `memory/DNA_UPDATES.md` (evolution rules)
- `memory/ILMA_EXTREME_TARGETS.md` (long-term goals)
- `memory/session_state.md` (if exists)

WAL Protocol adds:
- `memory/SESSION-STATE.md` — active task state (WAL target)
- `memory/working-buffer.md` — danger zone log

**ILMA WAL Integration:**
1. Read `memory/SESSION-STATE.md` at session start
2. Scan every human message for WAL triggers
3. Write to `SESSION-STATE.md` BEFORE responding
4. Sync important WAL entries to daily notes at end of session

## WAL vs Normal Memory

| Aspect | WAL Protocol | Normal Memory |
|--------|--------------|---------------|
| Timing | BEFORE responding | After responding |
| Trigger | Human input signals | Explicit instruction |
| Purpose | Capture before loss | Process and store |
| Target | SESSION-STATE.md | Daily notes, DNA |
| Frequency | Every message | End of session |

## Best Practices

1. **Stop composing before writing** — The urge to respond is the enemy.
2. **Be specific** — "blue" not "the color we discussed"
3. **Include context** — Why this detail matters
4. **Check for conflicts** — If detail contradicts previous, note both
5. **No secrets** — Don't write tokens, passwords, or sensitive data to WAL

## Anti-Patterns

❌ **Don't skip the write** — "This is obvious, why write it down?"
✅ **Write it down anyway** — Context will vanish

❌ **Don't write to chat** — WAL entries go to SESSION-STATE.md, not in the response
✅ **Write silently** — Human doesn't see the WAL write

❌ **Don't overwrite** — If entry exists, append rather than replace
✅ **Append with timestamp** — Preserve history

## Verification

To verify WAL protocol is working:
1. Check `memory/SESSION-STATE.md` after complex conversations
2. If entries are missing, WAL protocol needs enforcement
3. Review WAL entries at session end → promote important ones to DNA or daily notes

---

*ILMA WAL Protocol v1.0*
*Integrated from: halthelobster/proactive-agent (Hal Labs)*
*Attribution: https://github.com/halthelobster/proactive-agent*
*License: MIT*