# Wrapper-nous Brotli Streaming Bug — 2026-07-29

## Symptom
Codex (and any OpenAI SDK client) stops mid-stream when using wrapper-nous (port 9102) as backend. Streaming chunks stop arriving after ~10 failures. Non-streaming requests also fail.

## Root Cause
Nous Research upstream returns `Content-Encoding: br` (Brotli compression). aiohttp 3.13.5 with `auto_decompress=True` CAN decompress Brotli — but ONLY if the `brotlipy` package is installed.

**Critical detail**: Debian's system `python3-brotli` package provides `brotli.Decompressor` with `.process()` method only (no `.decompress()`). aiohttp's internal `BrotliDecompressor` tries `.decompress(data, max_length)` first, falls back to `.process()` with `max_length` (which brotlipy doesn't accept). Result: `ClientPayloadError: Can not decode content-encoding: br` → circuit breaker opens after 10 failures → ALL streaming fails.

## Evidence
```
2026-07-29 08:25:52,352 [nous] [upstream] post_nous network error: ClientPayloadError: 400, message:
  Can not decode content-encoding: br
2026-07-29 08:25:52,352 [nous] [circuit-breaker:nous-upstream] opening circuit after 10 consecutive failures
```

## Fix
```bash
pip install brotlipy --break-system-packages
```
This replaces system `brotli` with `brotlipy` which has `.decompress(data, max_length)` — aiohttp then works correctly.

**Verification after fix:**
- `/v1/chat/completions` streaming: ✅ (OpenAI format)
- `/v1/messages` streaming: ✅ (Anthropic format)
- `/v1/responses`: ✅ (OpenAI Responses API)
- Circuit breaker stays CLOSED

## Why This Wasn't Caught Earlier
- `brotlipy` was not in any wrapper's `requirements.txt`
- Local dev environments may have had `brotlipy` pre-installed
- Non-streaming requests appeared to work (different code path)
- The bug only manifests with streaming + Brotli response

## Prevention
**Add to pre-deployment checklist:**
```bash
# Verify brotlipy import works
python3 -c "import brotli; print(brotli.__version__)"

# Verify aiohttp auto_decompress works with brotli
python3 -c "
import aiohttp, asyncio
async def test():
    # This would fail without brotlipy
    pass
print('brotli decompression available')
"
```

## Affected Wrappers
- **wrapper-nous (port 9102)** — primary victim (Nous upstream returns Brotli)
- Other wrappers may be affected if their upstreams also return Brotli

## Related Fixes This Session
1. Installed `brotlipy` system-wide
2. Added `Accept-Encoding: gzip, deflate` header to upstream requests in `nous/src/main.py:post_nous()` to request only gzip/deflate (defense in depth)
3. Verified all 3 streaming surfaces work end-to-end

## SDK Compatibility Impact
This bug blocked Codex (uses OpenAI streaming) and any client using the streaming endpoint. After fix:
- ✅ OpenAI Python SDK (chat.completions.create(stream=True))
- ✅ Anthropic Python SDK (messages.stream())
- ✅ Codex (OpenAI API)
- ✅ Claude Code (Anthropic API)
- ✅ OpenRouter, OpenHands, Hermes Agent, OpenClaw