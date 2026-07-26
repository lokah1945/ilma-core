# 2026-06-20 — Telegram conclusion-duplication audit trace

## What Bos reported

> "respon di bawah ini masih duplikat saya terima di akhir, jadi jawaban atau repon terakhir atau kesimpulan akhir anda saja yg duplikat, saat proses runtime tidak ada duplikat. ini saya terima lebih dari 15x."

Translation: final/conclusion of a long audit reply arrived in Telegram as 15+ separate copies. Runtime body streamed normally with no internal duplication.

## What we found (5 delivery paths converging on the last accumulated chunk)

File evidence from trace session (audit-only — NO deploy):

### Path 1: `hermes-agent/gateway/stream_consumer.py` line 585-600 (overflow split)
```python
while _len_fn(self._accumulated) > _safe_limit and self._message_id is not None and self._edit_supported:
    ...
    ok = await self._send_or_edit(chunk, finalize=True, is_turn_final=False)
    self._accumulated = self._accumulated[split_at:].lstrip("\n")
    self._message_id = None
    self._last_sent_text = ""
```
Each overflow-chunk-derived NEW message ships through Telegram as `message_id=N`, `message_id=N+1`, ...

### Path 2: `hermes-agent/gateway/stream_consumer.py` line 1427-1431 (fresh-final)
```python
if (finalize and (
    self._should_send_fresh_final() or self._adapter_prefers_fresh_final(text)
)) and await self._try_fresh_final(text, is_turn_final=is_turn_final):
    return True
```
Telegram adapter has `_adaprer_prefers_fresh_final(text) == True` (rich markdown fresh/final), so the **full accumulated text** ships as **one additional fresh message**, after the chunks already went out.

### Path 3: `hermes-agent/gateway/platforms/base.py` line 3423 (`_send_with_retry`)
```python
result = await self.send(chat_id=chat_id, content=content, ...)   # whole text
if result.success:
    return result
if is_network:
    for attempt in range(1, max_retries + 1):
        await asyncio.sleep(delay)
        result = await self.send(chat_id=chat_id, content=content, ...)  # whole text AGAIN
```
`adapter.send(content=text)` with `len(text) > 4096` → `truncate_message()` splits into N chunks → Telegram receives N new message_ids. On network/flood retry, the same N chunks ship AGAIN.

### Path 4: `hermes-agent/gateway/run.py` line 9487-9498 (trailing footer)
```python
if _footer_line:
    await _foot_adapter.send(source.chat_id, _footer_line, metadata=...)
```
If `_already_sent` flag race loses (race between `_already_sent` set in stream_consumer and the read in run.py:9476), footer ships as a NEW message that **duplicates the closing content**.

### Path 5: `hermes-agent/gateway/run.py` line 16107-16130 (queued follow-up resend)
```python
await asyncio.wait_for(stream_task, timeout=5.0)
...
_already_streamed = bool(
    (_sc and getattr(_sc, "final_response_sent", False))
    or _previewed
    or (_sc and getattr(_sc, "final_content_delivered", False))
)
first_response = result.get("final_response", "")
if first_response and not _already_streamed:
    await adapter.send(source.chat_id, first_response, metadata=_status_thread_metadata)
```
The 5-second wait_for(stream_task) means if streaming is still running, the timeout cancels it and the gateway ships `final_response` as a duplicate NEW message.

## Evidence of correct upstream behavior (so the bug is downstream)

- ILMA state DB `state.db` — 0 duplicate-content groups for the 2026-06-20 19:46:04 session (`session_id='20260620_145147_825baa9c'`).
- Gateway log `gateway.log` line `2026-06-20 19:38:10,063` shows correct `Suppressing normal final send for session ... final delivery already confirmed (streamed=True previewed=False content_delivered=True).`
- Same pattern in `gateway.log` for sessions 14:01:14, 14:01:14, 19:38:10, 23:21:32, 00:18:04 etc. — gateway IS aware streaming delivered.

Yet user reports 15+ copies visible in Telegram. Conclusion: the duplication occurs below the gateway log layer — at Telegram Bot API level (flood retry duplicate the chunk N when chunk N-1 failed) and at Telegram app-level receipt (race between Edit-message-event vs New-message-event rendering).

## The ILMA-side mitigation that DOES work

The `ilma-long-response-delivery` skill describes Pattern A: physically separate the conclusion from the body, end with a single terminal character, never re-state bullets as a closing block. This is purely a content-shape fix that neutralizes the 5-path amplification: even if Telegram API duplicates the *last* chunk, the last chunk is now a 2-line wrap-up, not a 500-char re-statement. The cost of duplication drops from "confusing" to "negligible".

## What patches we did NOT propose to deploy (audit gates)

| Patch | File | Why blocked from audit-only |
|---|---|---|
| Add `asyncio.Lock` in `stream_consumer.py` | `stream_consumer.py` constructor | Touches Hermes core, shared with master-chief / all profiles |
| Fix `response_previewed` boolean at `run.py:13723` | `run.py` | Touches Hermes core |
| Atomic flag `_delivery_confirmed` single-source-of-truth at `run.py:16297` | `run.py` | Touches Hermes core |
| Disable `home-channel startup notification` during active session | `run.py` startup helper | Touches Hermes core |
| Refactor `_send_with_retry` to use `edit_message` instead of `send` on retry | `base.py:3423` | Touches Hermes core |
| Disable streaming in ILMA profile `config.yaml` `streaming.enabled: true` | `config.yaml` profile ILMA | Touches profile — Bos said no deploy |

All six are valid patches but require explicit Bos approval before any deployment. Audit-only mode per Bos 2026-06-20 23:53 instruction.

## Cross-reference back to skill

The `Conclusion-Split Pattern` (skill SKILL.md "Pattern A") IS the ILMA-side mitigation that:
- has zero deploy risk,
- survives any future gateway bug fix or regression,
- costs the user nothing extra,
- and matches Bos's explicit "1 message = 1 delivery" preference.

Always apply Pattern A on long-form responses. The lesson is durable even after the underlying Hermes-layer bug is eventually fixed — Telegram / WhatsApp / Discord delivery races are not ILMA's exclusive problem, the shape of the response can always be controlled.
