# 2026-06-26 — Stream Consumer Sealed-Split Fix (P5+P6 Behavior Patches)

## Problem

Bug duplikat respon Telegram yang sama sejak 2026-06-20 masih terjadi.
Karakteristik: sebelum respon final dikirim, multiple duplikat (bagian 1/N, 2/N, 3/N)
terkirim ke user. Respon akhir sudah bagus, tapi part-part intermediate tetap visible.

## Root Cause (refined from 2026-06-20 session)

Proactive split di `stream_consumer.py` (~line 585-600):
1. Saat konten > safe_limit, overflow split terjadi → chunks dikirim
2. `_message_id` di-reset ke None setelah setiap chunk
3. Chunks yang sudah dikirim ("sealed") masuk ke `_preview_message_ids`
4. `got_done` tidak detect bahwa konten sudah terkirim via sealed chunks
5. Gateway mengirim ulang seluruh respon → DUPLIKAT
6. Continuation fragments (1/3, 2/3) tidak di-cleanup → tetap visible sebagai partial messages

**Key insight**: `_preview_message_ids` mencampur sealed chunks (konten final yang harus dipertahankan)
dengan continuation fragments (sisa partial yang harus dihapus). Cleanup path menghapus keduanya
atau tidak menghapus keduanya → bug di kedua arah.

## Solution: `_sealed_split_ids` + 8 Behavior Patches

### New Data Structure
```python
self._sealed_split_ids: Set[int] = set()  # In __init__
```
Tracks proactive-split chunks that carry final content. Separated from `_preview_message_ids`
which now ONLY tracks continuation/preview fragments that should be deleted.

### Patch Map

| Patch | Location | Line(s) | What it does |
|-------|----------|---------|--------------|
| P5 (x4) | `got_done` | 693, 707, 718, 746 | Cleanup stale previews in all finalize paths |
| P6 #1 | `got_done` | 719-750 | Skip dup send when `_message_id is None` + sealed chunks exist; also cleanup orphaned continuations |
| P6 #2 | `_send_or_edit` edit success | ~1631+ | Delete stale continuations BEFORE tracking new ones |
| Sealed init | `__init__` | 153-157 | `self._sealed_split_ids: Set[int] = set()` |
| Sealed tracking | Proactive split loop | ~618-625 | Promote IDs from `_preview_ids` to `_sealed_split_ids`, reset `_preview_message_ids` |
| Sealed reset | `_reset_segment_state` | 314-318 | `self._sealed_split_ids = set()` on segment break |
| Sealed protect | `_cleanup_stale_previews` | 1372-1374 | Subtract `_sealed_split_ids` from delete set — never delete sealed |
| Sealed cleanup | `got_done` P6 #1 path | 740+ | Cleanup orphaned `_preview_message_ids` when sealed detected |

### Infrastructure Patches (P1-P4, already deployed before this session)

| Patch | File | Mechanism |
|-------|------|-----------|
| P1 | `base.py` `_send_with_retry` | Content-fingerprint LRU dedup guard (2min TTL, 64 max entries) |
| P2 | `run.py` ~L16310 | `already_sent` gate strengthened (cek `_streamed + _previewed + _content_delivered + _sc_already_sent`) |
| P3 | `stream_consumer.py` | `final_response_sent` atomic flag + `CancelledError` race fix + `_fallback_lock` |
| P4 | `telegram.py` `overflow_split` | Per-chunk delivery fingerprint dedup |

### Architecture After Fix

```
STREAMING START
  ├── Edit message A (accumulating)
  │     └── Overflow → continuations B, C → _preview_message_ids = {A, B, C}
  │           └── P6 #2: cleanup stale continuations → track B, C
  ├── Proactive split
  │     ├── Sealed chunk A → _sealed_split_ids = {A}, _preview_message_ids = {}
  │     ├── _message_id = None
  │     └── send-new sisa konten → _message_id = B, _preview_message_ids tracked
  └── got_done (finalize)
        ├── _message_id exists → _send_or_edit(finalize=True) → P5 cleanup
        ├── _message_id is None + sealed chunks → P6 #1: SKIP + mark delivered
        │     └── Also cleanup orphaned _preview_message_ids (P6 sealed cleanup)
        └── else → _send_or_edit → P5 cleanup
```

### Rules enforced

1. **Sealed chunks NEVER deleted** — they carry final content the user should see
2. **Continuation fragments ALWAYS deleted** — they are stale partial messages
3. **`_reset_segment_state` clears sealed set** — new segment starts fresh
4. **Fresh-final path may delete sealed chunks** — only when `_adapter_prefers_fresh_final=True` (NOT Telegram, which returns False)
5. **P6 #1 cleanup is conditional** — only runs when `_preview_message_ids` is non-empty

### Dangerous patches that were REVERTED

| Patch | Why reverted |
|-------|-------------|
| P6 #3 (`_send_new_chunk` proactive check) | Would block legitimate proactive split chunk sends |
| P6 #4 (~line 864) | Interfered with `_clean_for_display` — no longer present in file |

## Files Modified

- `/root/.hermes/hermes-agent/gateway/stream_consumer.py` — 8 patch points (P5 + P6)
- `/root/.hermes/hermes-agent/gateway/platforms/base.py` — P1 (pre-existing)
- `/root/.hermes/hermes-agent/gateway/run.py` — P2 (pre-existing)
- `/root/.hermes/hermes-agent/gateway/platforms/telegram.py` — P4 (pre-existing)

## Verification

- Syntax check: PASSED (`py_compile.compile` doraise=True)
- Hermes restart: successful (API responds on port 8642)
- Total protection layers: 12 (4 infra + 8 behavior)

## Key Debugging Lessons

1. **`_preview_message_ids` mixing concerns** — it contained both sealed chunks (keep) and continuation fragments (delete). Splitting into `_sealed_split_ids` + `_preview_message_ids` resolved the conflict.
2. **`_reset_segment_state` MUST clear sealed set** — otherwise stale IDs from a prior segment trigger false-positive detection in `got_done`.
3. **P6 #2 must cleanup BEFORE tracking new** — if you track first then cleanup, the cleanup deletes the JUST-tracked IDs.
4. **Don't trust `_message_id is None` alone** — proactive split resets it, but content may have been delivered. Always check sealed set.
5. **`_adapter_prefers_fresh_final` returns False for Telegram** — means `_try_fresh_final` path never executes for Telegram, so sealed chunks there are safe from that path's stale-ID cleanup.
