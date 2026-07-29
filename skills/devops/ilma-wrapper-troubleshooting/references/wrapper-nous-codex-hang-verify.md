# wrapper-nous Codex Hang Verification (BUG-CODEX1/2) — 2026-07-27

## User Report
"Codex stops mid-way when using wrapper-nous as backend" — streaming responses cut off, process appears to hang.

## Reproduction
Using Codex with Anthropic-compatible `/v1/messages` endpoint:
```bash
# Codex sends:
POST /v1/messages
{
  "model": "inclusionai/ling-3.0-flash:free",
  "max_tokens": 100,
  "messages": [{"role": "user", "content": "Write a function"}],
  "stream": true
}
# Response: stream starts, emits chunks, then STOPS (no [DONE], no message_stop)
```

## Initial Diagnosis (WRONG — see BUG-CODEX2)
First session assumed: "Codex expects specific event format" — tried adding `message_stop`, `content_block_stop` events. **This was incorrect.**

## Root Cause Found (BUG-CODEX2) — Brotli Decompression Failure
The actual cause: **aiohttp failing to decompress Brotli-encoded responses from Nous upstream**.

Nous returns `Content-Encoding: br`. aiohttp 3.13.5 with `auto_decompress=True` CAN handle Brotli — BUT only if `brotlipy` package is installed (not system `brotli`).

System `python3-brotli` (Debian) provides `brotli.Decompressor` with `.process()` only.
aiohttp's `BrotliDecompressor` tries `.decompress(data, max_length)` first, falls back to `.process(data, max_length)` — but system brotli's `.process()` takes only 1 arg.

Result: `ClientPayloadError: Can not decode content-encoding: br` → circuit breaker opens → all requests 503.

## Verification (Fixed)
```bash
pip install brotlipy --break-system-packages
systemctl --user restart wrapper-nous
```

All 3 streaming surfaces now complete:
- `/v1/chat/completions` (OpenAI streaming) ✅
- `/v1/messages` (Anthropic streaming) ✅ — Codex path
- `/v1/responses` (OpenAI Responses streaming) ✅

## Lessons
1. **Environment-dependent bugs look like code bugs.** The wrapper code was correct; the missing `brotlipy` was the issue.
2. **Don't assume Codex/Anthropic format issues first.** Check transport layer (compression, encoding) first.
3. **Add `brotlipy` to pre-deployment checklist** for any wrapper hitting Brotli-enabled upstreams.
4. **Log raw upstream headers on decompression error** — `Content-Encoding: br` would have been visible.

## Related
- `references/wrapper-nous-brotli-streaming-bug.md` — full technical details
- `references/cloudflare-1010-ua-block.md` — similar env-dependent upstream block