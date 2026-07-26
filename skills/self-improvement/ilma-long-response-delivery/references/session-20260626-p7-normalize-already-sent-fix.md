# P7 Fix: `_normalize_empty_agent_response` Must Respect `already_sent`

**Date:** 2026-06-26
**File:** `gateway/run.py`
**Lines:** ~9127 (normalize call), ~9476 (already_sent gate)

## The Bug

When streaming delivers content incrementally (via `stream_consumer.py`), the agent
often returns an **empty string** as its final response — the text was already sent
via streaming chunks, so there's nothing left to return.

The problem: `_normalize_empty_agent_response()` at line ~9127 was called
**BEFORE** the `already_sent` gate at line ~9476. The normalize function saw:

1. `response = ""` (empty — content already delivered via stream)
2. `api_calls > 0` (agent did work via tools)
3. Not failed, not partial, not interrupted

→ **Injected spurious message:** "⚠️ Processing completed but no response was generated. This may be a transient error — try sending your message again."

This message was user-visible and appeared as a **duplicate** alongside the already-delivered streaming content.

## Why P1-P6 Could Not Catch This

All P1-P6 patches operate in `stream_consumer.py` or `telegram.py` — they prevent
duplicate delivery at the transport/emission layer. But P7's spurious message
originates from `gateway/run.py`'s **response processing pipeline**, which is
upstream of all transport-level dedup:

```
Agent returns "" → _normalize_empty_agent_response() → "⚠️ no response"
                                                            ↓
                                                    already_sent gate (too late — message already generated)
                                                            ↓
                                                    Gateway sends it → DUPLICATE
```

The dedup infrastructure correctly prevents re-sending the **same content**, but
the normalize function generates **new different content** that dedup cannot catch
(it's not a fingerprint match — it's a novel string).

## The Fix

```python
# BEFORE (bug):
if not _intentional_silence:
    response = _normalize_empty_agent_response(
        agent_result, response, history_len=len(history),
    )

# AFTER (P7 fix):
# ILMA-DEDUP P7: When streaming already delivered content
# (already_sent=True), an empty response is expected — the
# text was sent incrementally via the stream consumer, not
# returned as a full response string.
if not _intentional_silence and not agent_result.get("already_sent"):
    response = _normalize_empty_agent_response(
        agent_result, response, history_len=len(history),
    )
```

## Key Insight

**Any function that can emit user-visible text must be gated by `already_sent`
BEFORE execution, not after.** The normalize-gate ordering bug was latent because:

- P1 (fingerprint dedup) only catches identical content — normalize produces NEW content
- P2 (`already_sent` gate) blocks the *original* response but normalize already replaced it
- P3 (`final_response_sent` flag) is set in stream_consumer, not visible to run.py's normalize
- P4 (chunk fingerprint) same as P1 — different content evades dedup
- P5/P6 operate in stream_consumer.py — the normalize runs in run.py, a different file

## Debugging Methodology

1. Traced the "↻ Empty response after tool calls" message
2. Grepped for `_normalize_empty_agent_response` — found single call site at line 9127
3. Read lines 9124-9130 (normalize call) and 9461-9500 (already_sent gate)
4. Identified the ordering: normalize at 9127 → gate at 9476 — **normalize runs first**
5. Realized normalize generates new content that dedup cannot fingerprint-match
6. Added `and not agent_result.get("already_sent")` to the normalize guard

## Complete Patch Map (P1-P7)

| Patch | File | Layer | Mechanism |
|-------|------|-------|-----------|
| P1 | `base.py` | Infrastructure | Content-fingerprint LRU dedup (2min, 64 entries) |
| P2 | `run.py` | Infrastructure | `already_sent` gate + `response_previewed` via `final_content_delivered` |
| P3 | `stream_consumer.py` | Infrastructure | `final_response_sent` atomic + CancelledError fix |
| P4 | `telegram.py` | Infrastructure | Per-chunk delivery fingerprint in overflow_split |
| P5 | `stream_consumer.py` | Behavior | Stale preview cleanup (4 finalize paths in `got_done`) |
| P6 | `stream_consumer.py` | Behavior | Sealed split tracking + orphaned continuation cleanup |
| **P7** | **`run.py`** | **Behavior** | **Skip normalize when `already_sent=True`** |

## Verification

- Syntax check: `python3 -c "import py_compile; py_compile.compile('gateway/run.py', doraise=True)"` → OK
- Hermes restart confirmed: API responds on port 8642
- The fix is self-verifying: if `already_sent=True` and response is empty, the user already has the content via streaming — no message should be generated
