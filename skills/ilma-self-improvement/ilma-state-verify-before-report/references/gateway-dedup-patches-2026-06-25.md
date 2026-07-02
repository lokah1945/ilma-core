# Gateway-Level Duplicate Delivery Patches — 2026-06-25

## Bug Report

Bos reported: "Respon ini di telegram sebelum nya anda kirim sebanyak lebih dari 2x."
The final response content itself was correct (format, structure good) — the problem was
the *process* of assembling it being visible to the user, i.e. intermediate delivery
attempts leaking through alongside the final message.

## Root Cause Analysis (5 Causes)

### RC-1: `_send_with_retry` whole-message retry
**File:** `gateway/platforms/base.py`, `_send_with_retry` method
When a send fails (network/transient), Hermes retries the FULL message. If the first
attempt partially delivered (e.g. Telegram got chunks 1-2 before timeout), the retry
sends ALL chunks again — chunks 1-2 are now duplicates on screen.

**Fix (Patch 1):** SHA-256 content-fingerprint dedup guard. Before each `_send_with_retry`
call, check if this exact (chat_id, content) pair was delivered within the last 30s.
If so, skip and return synthetic success.

Keycode added to `base.py`:
- `_content_fingerprint(chat_id, content)` → SHA-256 hex[:16]
- `_is_duplicate_delivery(chat_id, content)` → checks TTL 30s against `_recent_sends`
- `_record_delivery_fingerprint(chat_id, content)` → stores in `_recent_sends` (max 256)
- Guard at top of `_send_with_retry`: skip if duplicate
- Recording after `result.success` and on timeout (defensive fingerprint)

### RC-2: `response_previewed` false positive in run.py
**File:** `gateway/run.py`, line 13723
`response_previewed = _stream_consumer is not None and bool(full_response)`
This evaluated True whenever the stream consumer existed AND had accumulated content —
even if nothing was actually delivered to Telegram yet. The gateway then assumed
"already delivered" and could suppress its own final send, or the flag's truthiness
could cause already_sent gate miscalculation.

**Fix (Patch 2):** Changed to also require `getattr(_stream_consumer, "final_content_delivered", False)`
— proving the stream consumer actually completed delivery, not just accumulated text.

### RC-3: Already_sent gate race condition in run.py
**File:** `gateway/run.py`, line ~16297
The already_sent gate checked `_streamed`, `_previewed`, `_content_delivered` flags
but NOT `_sc.already_sent` (the stream consumer's own atomic flag). This meant the
gateway could proceed to send even when the stream consumer had already delivered.

**Fix (Patch 2):** Added `_sc.already_sent` as additional OR signal in the gate condition.
Also added debug logging when gate is NOT satisfied — visibility for future tracing.

### RC-4: CancelledError + gateway final-send race in stream_consumer.py
**File:** `gateway/stream_consumer.py`, lines 750-800
When the stream consumer is cancelled (asyncio.CancelledError), the best-effort
final edit could race with the gateway's own fallback final send. Without a lock,
both paths could read `_already_sent=False` and both proceed to deliver.

**Fix (Patch 3):** Added `self._final_delivery_lock = asyncio.Lock()` in `__init__`.
CancelledError handler now wraps flag mutations in `async with self._final_delivery_lock`.
Only sets `_already_sent=True` + `_final_response_sent=True` + `_final_content_delivered=True`
if the best-effort send actually succeeded. If not, leaves `already_sent=False` so
gateway's fallback path works correctly.

### RC-5: `_send_fallback_final` unguarded entry
**File:** `gateway/stream_consumer.py`, `_send_fallback_final` method
Multiple callers (CancelledError handler, edit failures, gateway fallback) could all
enter `_send_fallback_final` concurrently. No lock, no early-return guard.

**Fix (Patch 3):** Split into locked wrapper `_send_fallback_final` (checks `_already_sent`
under lock, delegates to `_send_fallback_final_impl`) and implementation method.
This prevents concurrent entry entirely.

### RC-6: Overflow split chunk retry without per-chunk tracking
**File:** `gateway/platforms/telegram.py`, overflow_split continuation loop
When `_send_with_retry` retries a message that was split into chunks, all N chunks
are re-sent even if chunks 1-(N-1) were already delivered. The per-chunk fingerprint
in base.py's dedup only catches whole-message fingerprint matches, not partials.

**Fix (Patch 4):** Added `_record_delivery_fingerprint(chat_id, f"overflow:{idx}:{chunk[:200]}")`
after each successful continuation chunk send. Also imported `_dedup_enabled` and
`_record_delivery_fingerprint` from base.py into telegram.py.

## Files Modified

| File | Patch | Lines touched (approx) |
|------|-------|----------------------|
| `gateway/platforms/base.py` | P1: dedup guard | +30 lines (functions + guard + recording) |
| `gateway/run.py` | P2: response_previewed + gate | ~4 lines changed |
| `gateway/stream_consumer.py` | P3: asyncio.Lock + CancelledError + fallback guard | ~25 lines added |
| `gateway/platforms/telegram.py` | P4: per-chunk fingerprint | +12 lines (import + recording) |

## Verification Checklist

After patching, verify:
1. `python3 -c "import gateway.platforms.base; import gateway.run; import gateway.stream_consumer; import gateway.platforms.telegram"` — no import errors
2. `grep -c "ILMA.Anti.Duplicate\|ILMA-DEDUP" gateway/platforms/base.py gateway/run.py gateway/stream_consumer.py gateway/platforms/telegram.py` — count patch markers
3. Send a >4KB test message and verify exactly 1 delivery in Telegram
4. Test CancelledError path: kill stream consumer mid-delivery → verify no double send
5. Test overflow_split: send >4096 char message → verify chunks arrive once

## Relationship to P-14/P-15

These patches address P-15 case **A** (gateway-side double-send). The fixes are:
- Fix-1 (base.py dedup) — generic safety net for any send path
- Fix-2 (run.py flags) — correct already_sent evaluation
- Fix-3 (stream_consumer lock) — atomic flag mutation
- Fix-4 (telegram.py per-chunk) — overflow_split partial retry protection

P-15 case **B** (agent-side re-emission) is NOT addressed by these patches — that
remains an agent discipline issue covered by P-14 single-ack rule.
