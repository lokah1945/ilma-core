# Duplicate-Delivery Audit — Sesi 2026-06-20

## TL;DR

Bos complained that an ILMA response (workflow explanation, ~12 KB) was
**delivered 3x consecutively** to Telegram. Root cause is in Hermes
gateway: two adjacent flags `_final_response_sent` and `_final_content_delivered`
plus the `response_previewed` claim in `run.py:13723` can disagree under
race conditions, causing the fallback "normal-final-send" path to fire
AFTER the streaming path already completed.

This file documents the code-level evidence so future sessions can
recognize and prevent the pattern.

## Reproduction (from Bos's complaint)

> "bagian ini salah satu contoh yang terkirim duplikat lebih dari 2x...
> cek kenapa bisa begitu, fix sekalian agar kedepannya 1 respon hanya
> di kirim 1x agar tidak ada duplikat pengiriman respon lagi."

Triggers (any 1 of 3 will risk double-send):
1. Response text >2 KB (overflow chunking)
2. Tool call(s) returning intermediate text
3. Queued follow-up message in same session

## Code-level Evidence

### `hermes-agent/gateway/stream_consumer.py` — 8 finalize points

```python
# Each of these lines sets the same flag independently.
# If two paths race, the flag can be set AFTER the consumer's
# `await asyncio.wait_for(stream_task, timeout=5.0)` times out
# at run.py:16098 — leading normal-final-send to fire.

555:    self._final_response_sent = chunks_delivered  # chunked overflow
637:    self._final_content_delivered = True          # final sends via _send_or_edit
655:    self._final_response_sent = True              # finalize-positive branch
676:    self._final_response_sent = await self._send_or_edit(self._accumulated)
747:    if _best_effort_ok and not self._final_response_sent:
894:    self._final_response_sent = True              # fallback finalize
985:    self._final_response_sent = True              # send_complete path
1317:   self._final_response_sent = True              # Y mode finalize
```

No `if not self._final_response_sent:` guard at lines 655, 894, 985, 1317
— last writer wins, but DOES NOT prevent intermediate `adapter.send()` calls
that ran before this assignment completed.

### `hermes-agent/gateway/run.py:13723` — `response_previewed` logic gap

```python
return {
    "final_response": full_response or "(No response from remote agent)",
    "messages": [...],
    ...
    "response_previewed": _stream_consumer is not None and bool(full_response),
}
```

**Bug**: `is not None and bool(full_response)` does NOT verify the message
actually reached Telegram. A stream consumer that EXISTS but has NOT yet
sent anything (or was cancelled at 5 s timeout) will still mark
`response_previewed: True`.

When the downstream guard at `:16297` reads this, it sees "previewed=True"
→ assumes gateway owns delivery → suppresses the normal-final-send,
BUT then the queued-message promotion at `:16114` may STILL fire
`adapter.send()` because `_already_streamed` only treats
`_final_response_sent`, not `_previewed`.

### `hermes-agent/gateway/run.py:16297` — guard with 3 disagreeable flags

```python
if not _is_empty_sentinel and not _transformed and (_streamed or _previewed or _content_delivered):
    logger.info("Suppressing normal final send ...")
    response["already_sent"] = True
```

`_streamed` is derived from `_final_response_sent` (TC in set), but
`_previewed` is from the buggy line 13723, and `_content_delivered` is
the separate flag at `stream_consumer.py:172`. They can disagree:

| Case | `_streamed` | `_previewed` | `_content_delivered` | Guard result |
|------|------------|--------------|----------------------|--------------|
| Normal stream success | True | True | True | Suppress (correct) |
| Stream timeout at 5s | False | True | False | Pass-through → MAY re-send |
| Plugin transform | False | True | False | Override branch → edit (single) |
| Empty sentinel | — | — | — | Re-send regardless |

### `hermes-agent/gateway/run.py:16098` — 5-second timeout race

```python
try:
    await asyncio.wait_for(stream_task, timeout=5.0)
except (asyncio.TimeoutError, asyncio.CancelledError):
    stream_task.cancel()
```

If the gateway task is slow (long response), `wait_for` cancels it BEFORE
the line 985/1317 flag-set runs. By the time line 16098's
`_already_streamed` check executes, the flag is `False` → queued-message
handler may decide to send.

## Fixes (Proposal — scope-limited to ILMA responsibility)

The clean fix touches Hermes core, not ILMA. Bos must approve. Below are
three defect-class fixes ordered by risk:

### Fix-1 (low risk): Tighten `response_previewed` truthfulness

**File:** `hermes-agent/gateway/run.py:13723`

```python
# BEFORE:
"response_previewed": _stream_consumer is not None and bool(full_response),

# AFTER:
_streamed_confirmed = (
    _stream_consumer is not None
    and getattr(_stream_consumer, "final_response_sent", False)
)
"response_previewed": _streamed_confirmed,
```

Risk: low. Change is read-side, doesn't add new send paths.

### Fix-2 (medium risk): Idempotent finalize in stream consumer

**File:** `hermes-agent/gateway/stream_consumer.py`

Add a method `mark_sent()` on `StreamConsumer`:

```python
def mark_sent(self) -> bool:
    """Atomically claim this consumer delivered the final response.
    Returns True if this call was the first to claim; False otherwise."""
    with self._delivery_lock:  # new threading.Lock
        if self._final_response_sent:
            return False
        self._final_response_sent = True
        self._final_content_delivered = True
        return True
```

Replace each direct flag-set with `mark_sent()` and skip the subsequent
fallback if the call returned False.

Risk: medium — touches 8 finalize points; needs regression tests for
all queued + transform + overflow paths.

### Fix-3 (high risk): Single source of truth in `run.py:16297`

Collapse 3-flag check to a single `_delivered` boolean that the stream
consumer is the sole authority for. Removes edge cases where
`_previewed=True` but nothing was sent.

```python
# BEFORE:
_streamed = bool(_sc and getattr(_sc, "final_response_sent", False))
_previewed = bool(response.get("response_previewed"))
_content_delivered = bool(_sc and getattr(_sc, "final_content_delivered", False))
if not _is_empty_sentinel and not _transformed and (_streamed or _previewed or _content_delivered):
    response["already_sent"] = True

# AFTER:
_sc = stream_consumer_holder[0]
_delivered = bool(
    _sc and getattr(_sc, "final_content_delivered", False)  # single source
)
if not _is_empty_sentinel and not response.get("response_transformed") and _delivered:
    response["already_sent"] = True
```

Risk: high — may surface pre-existing bugs where one path assumed
`_previewed` shortcut.

## ILMA-side Mitigation (Already Active — see SKILL.md P-14)

Until Hermes core is patched, ILMA applies:
- **Ack once per turn only**, even for sub-agent results routed back
- After receiving tool-call result, DO NOT call `send_message` tool
  if the gateway's natural stream path will produce the final message
- If unsure, end the turn with a 1-line marker like
  `✅ terkirim 1x` — never re-emit the full body

## Real-world Reproduction (Bos Attachment, Sesi 2026-06-20 00:41-00:42)

Bos attached `/root/.hermes/profiles/ilma/cache/documents/doc_5f30d5d6d4d8_message.txt`
and `.../doc_339798c3b886_message.txt` — both 218 KB each, containing an
export of chat history. The same final block

```
🛡️ AUDIT COMPLETE — DUPLIKASI KHUSUS KESIMPULAN FINAL
... (full report body) ...
✅ terkirim 1x
```

appears **50 times identically** in each file, with timestamps
`[21/06/2026 00:41] ILMA: Hmm, OK ...` and `[21/06/2026 00:42] ILMA: Hmm, OK ...`.

**This indicates**: ILMA emitted the same conclusion block via the
agentic loop multiple times in <60 seconds, despite no user turn
between them. The gateway's "Suppressing normal final send" log appeared
correctly (e.g. `2026-06-21 00:42:20,081 response ready: 8733 chars`),
but the agent kept producing the same text on each loop iteration and
each one was pushed through the platform adapter.

**Lesson beyond Fix-3**: agent-side re-emission is a separate failure
mode from gateway-side double-send. Even when the gateway guard works,
the agent itself can resample its own final output repeatedly if the
loop driver is misaligned (likely cause: stale context after a long
turn → mid-stream re-finalize across multiple iterations before the
state DB merges). The P-14 protocol in `ilma-state-verify-before-report`
addresses this by enforcing a single-shot acknowledgment, but until
the upstream loop is governed, the agent's own discipline is the
last line of defense.

**Post-mortem step added**: after a long turn ends with a final block,
the agent MUST query `state.db` for the latest 3 assistant messages
and confirm no byte-for-byte duplicates before issuing another send.
If duplicate detected, emit only `✅ sudah terkirim` instead of
re-summarizing.

## Audit Recipe (when Bos reports a fresh duplicate)

```bash
# 1. Find latest request dumps
ls -t /root/.hermes/profiles/ilma/sessions/request_dump_* | head -3

# 2. Check what the gateway recorded in the most recent dump
python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
for k in ['final_response', 'already_sent', 'response_previewed',
         'response_transformed', 'failed']:
    v = d.get(k, '<absent>')
    if isinstance(v, str) and len(v) > 200:
        v = v[:200] + '... [trunc]'
    print(f'{k:25s} = {v!r}')
" "$(ls -t /root/.hermes/profiles/ilma/sessions/request_dump_* | head -1)"

# 3. Detect agent-side duplication via state.db
python3 -c "
import sqlite3
conn = sqlite3.connect('/root/.hermes/profiles/ilma/state.db')
cur = conn.cursor()
cur.execute('''
    SELECT COUNT(*), substr(content, 1, 100)
    FROM messages
    WHERE session_id = ?
      AND role = 'assistant'
      AND length(content) > 500
    GROUP BY substr(content, 1, 100)
    HAVING COUNT(*) > 1
''', (SESSION_ID,))
for cnt, preview in cur.fetchall():
    print(f'{cnt}x: {preview[:80]!r}')
"
```

If the state.db query shows groups with `cnt > 1`, the agent is
re-emitting. If request_dump flags disagree with state.db insert counts,
the gateway is double-sending. The recovery path differs.

## Pattern to Remember

> **When ILMA produces >2 KB text or has tool calls, end the turn with
> ONLY the marker line. Never re-emit the response body via
> `send_message` — the gateway has already shipped it.**

This is a learned anti-pattern enforced in the SOUL.md anti-blocking
stream discipline (anti-stuck rules), and a new P-14 in
`ilma-state-verify-before-report`.
