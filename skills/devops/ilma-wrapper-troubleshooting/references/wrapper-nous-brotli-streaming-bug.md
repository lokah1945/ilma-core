# wrapper-nous Brotli Streaming Bug (CVE-class) — 2026-07-29

## Symptom
```
[upstream] post_nous network error: ClientPayloadError: 400, message:
  Can not decode content-encoding: br
[circuit-breaker:nous-upstream] opening circuit after 10 consecutive failures
```

ALL streaming requests fail → circuit breaker opens → all endpoints return 503.

## Root Cause
1. Nous upstream returns `Content-Encoding: br` (Brotli compressed)
2. aiohttp 3.13.5 has `auto_decompress=True` by default
3. aiohttp CAN decompress Brotli — but ONLY if `brotlipy` package is available
4. System has `python3-brotli` (Debian package) which provides `brotli.Decompressor` with `.process(data)` ONLY
5. aiohttp's `BrotliDecompressor` (in `compression_utils.py`) tries:
   ```python
   if hasattr(self._obj, "decompress"):
       return self._obj.decompress(data, max_length)
   return self._obj.process(data, max_length)
   ```
6. System `brotli` has NO `.decompress()` method, so it falls back to `.process(data, max_length)` — but system brotli's `.process()` takes ONLY 1 argument!

Result: `TypeError: process() takes exactly 1 argument (2 given)` → wrapped as `ClientPayloadError: Can not decode content-encoding: br`

## Fix
```bash
pip install brotlipy --break-system-packages
# Replaces system brotli with brotlipy which has:
# - Decompressor.decompress(data, max_length)
# - Decompressor.process(data) [no max_length]
```

## Verification
```bash
python3 -c "
import brotli
d = brotli.Decompressor()
print('Has decompress:', hasattr(d, 'decompress'))
# Test with a simple brotli stream
print('brotli module:', brotli.__file__)
"

# After fix, should show:
# Has decompress: True
# brotli module: /usr/local/lib/python3.11/dist-packages/brotli/__init__.py
```

## Prevention
Add to pre-deployment checklist:
- [ ] `python3 -c "import brotli; d=brotli.Decompressor(); assert hasattr(d, 'decompress')"`
- [ ] Test streaming request to any Brotli-enabled upstream (Nous, Vercel, etc.)

## Related
- `references/wrapper-nous-codex-hang-verify.md` — Codex hang was this bug
- `references/cloudflare-1010-ua-block.md` — similar env-dependent bug
- `ilma-wrapper-production-audit` — added to Pitfalls section