# wrapper-nous Brotli Streaming Bug — Root Cause & Fix

## Date: 2026-07-29
## Severity: CRITICAL (CVE-class — breaks ALL streaming)

## Symptom
- Codex stops mid-way during streaming
- Claude Code fails on `/v1/messages` streaming
- Circuit breaker opens after 10 consecutive failures
- All 3 streaming surfaces affected: `/v1/chat/completions`, `/v1/messages`, `/v1/responses`

## Root Cause
Nous Research upstream returns `Content-Encoding: br` (Brotli compression).

aiohttp 3.13.5 with `auto_decompress=True` CAN decompress Brotli — BUT ONLY if the `brotlipy` package is installed.

**System `brotli` (Debian `python3-brotli`)** provides `brotli.Decompressor` with `.process()` method ONLY (no `.decompress()`).

**aiohttp's `BrotliDecompressor`** tries `.decompress(data, max_length)` first, falls back to `.process(data, max_length)` — but `brotlipy`'s `.process()` doesn't accept `max_length` parameter.

Result: `ClientPayloadError: Can not decode content-encoding: br` → circuit breaker opens → ALL streaming fails.

## Fix
```bash
pip install brotlipy --break-system-packages
```

This replaces system `brotli` with `brotlipy` which provides `.decompress(data, max_length)`.

## Verification
After fix, all 3 streaming surfaces complete:
- `/v1/chat/completions` — OpenAI format ✅
- `/v1/messages` — Anthropic format ✅  
- `/v1/responses` — OpenAI Responses API ✅

## Prevention
Add to pre-deployment checklist:
```bash
python3 -c "import brotlipy; print('brotlipy OK')" || echo "MISSING: pip install brotlipy"
```

## Affected Files
- `/root/wrapper/nous/src/main.py` — Added `Accept-Encoding: gzip, deflate` header to force gzip/deflate from upstream (defense in depth)
- System package: `brotlipy` installed

## Related
- `references/catalog-route-ordering-fix.md` — same session, different bug
- `references/2026-07-29-full-audit-summary.md` — session summary