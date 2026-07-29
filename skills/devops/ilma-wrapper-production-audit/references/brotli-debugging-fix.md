# Brotli Decoding Fix — wrapper-nous (Port 9102)

## The Bug
**Symptom:** Codex / Anthropic clients stop mid-stream when using wrapper-nous
**Error in logs:** `ClientPayloadError: 400, message: Can not decode content-encoding: br`
**Circuit breaker:** Opens after 10 consecutive failures → all 5 keys cooled down → wrapper returns 503/502

## Root Cause
Nous Research upstream API returns `Content-Encoding: br` (Brotli compression).
- `aiohttp` has `auto_decompress=True` by default
- **System package `python3-brotli` (brotlipy)** only implements `process()` — NO `decompress()` method
- `brotlipy` (PyPI) implements `brotli.decompress(data)` which aiohttp calls
- System package shadows PyPI package → aiohttp tries to call missing method → exception

## The Fix
```bash
# System package is WRONG for aiohttp
pip install brotlipy --break-system-packages
# This replaces /usr/lib/python3/dist-packages/brotli/ with one that has decompress()
```

## Verification
```bash
python3 -c "import brotli; print(hasattr(brotli, 'decompress'))"  # Must print True
```

## Preventive Header (belt-and-suspenders)
In `nous/src/main.py` `post_nous()` function, added:
```python
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "Accept-Encoding": "gzip, deflate"   # ← Force upstream to NOT send br
}
```

## Streaming Verification (All 3 Surfaces)
```bash
# OpenAI format
curl -s -N -H "Authorization: Bearer test" -H "Content-Type: application/json" \
  -d '{"model":"poolside/laguna-s-2.1:free","max_tokens":20,"messages":[{"role":"user","content":"Hi"}],"stream":true}' \
  http://localhost:9102/v1/chat/completions

# Anthropic format  
curl -s -N -H "Authorization: Bearer test" -H "Content-Type: application/json" \
  -d '{"model":"inclusionai/ling-3.0-flash:free","max_tokens":20,"messages":[{"role":"user","content":"Hi"}],"stream":true}' \
  http://localhost:9102/v1/messages

# Responses API
curl -s -N -H "Authorization: Bearer test" -H "Content-Type: application/json" \
  -d '{"model":"poolside/laguna-s-2.1:free","input":"Hi","max_output_tokens":20}' \
  http://localhost:9102/v1/responses
```
All must complete without `ClientPayloadError` or circuit breaker opening.

## Regression Guard
Add to pre-deployment checklist:
```bash
# In wrapper audit script or CI
python3 -c "import brotli; assert hasattr(brotli, 'decompress'), 'brotli.decompress missing - install brotlipy'"
```

## Files Modified
- `nous/src/main.py` — added `Accept-Encoding: gzip, deflate` header in `post_nous()`
- System Python packages — `pip install brotlipy --break-system-packages`

## Why This Happened
- Brotli support added to aiohttp in 2020
- System package managers (apt) ship `python3-brotli` which is `brotlipy` (the OLD fork without decompress)
- PyPI `brotlipy` is the ACTIVE fork with `decompress()`
- `pip install --break-system-packages` correctly overrides the system package

## Related
- Skill: `ilma-wrapper-production-audit` / `references/2026-07-29-full-audit-summary.md` (full audit context)
- Skill: `cf-bypass-browser-ua-pattern` (similar upstream header manipulation technique)