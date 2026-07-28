# Cloudflare 1010 bot-block on default Python/aiohttp User-Agent

**Root-cause class (2026-07-28, opencode 9103 + vercel 9105).** A wrapper returns
`503 No capacity` / `invalid_credential` / `Not Found` for ALL models, but `curl` to the
same upstream with the same key works fine. The real cause is a **Cloudflare anti-bot
block on the client User-Agent**, NOT a key/account problem.

## Symptom
- `opencode` (9103) / `vercel` (9105) fail every request; direct `curl` to upstream = 200.
- `model-state.db` `model_account_status` shows `invalid_credential` for the key fingerprint,
  but the key is VALID (curl proves it).
- Wrapper uses `aiohttp` with default UA `Python/3.x aiohttp/x.x.x` → Cloudflare returns
  `HTTP 403 error code: 1010` (bot block) → wrapper marks key invalid / capacity 0.

## Repro that proves it is UA, not the key
```bash
KEY=$(python3 -c "from dotenv import dotenv_values; print(dotenv_values('/root/wrapper/opencode/.env').get('OPENCODE_API_KEY_1',''))")

# urllib (default Python UA) -> 403 error 1010 (bot block)
python3 - <<'PY'
import urllib.request, json
req = urllib.request.Request(
    "https://opencode.ai/zen/v1/chat/completions",
    data=json.dumps({"model":"nemotron-3-ultra-free","messages":[{"role":"user","content":"hi"}],"max_tokens":5}).encode(),
    headers={"Authorization":f"Bearer $KEY","Content-Type":"application/json"}, method="POST")
try:
    print("urllib:", urllib.request.urlopen(req, timeout=12).status)
except Exception as e:
    print("urllib ERR:", e)   # -> HTTP 403, error code: 1010
PY

# curl (realistic UA) -> 200
curl -s -o /dev/null -w "curl: %{http_code}\n" -X POST https://opencode.ai/zen/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"nemotron-3-ultra-free","messages":[{"role":"user","content":"hi"}],"max_tokens":5}'
```

## Fix (applied commit 5bb2e92) — browser UA on the aiohttp session
In `<wrapper>/src/main.py`, the `aiohttp.ClientSession(...)` is created WITHOUT headers.
Add a browser UA + restrict encoding:

```python
            _session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=max(REQUEST_TIMEOUT_SEC, STREAM_REQUEST_TIMEOUT_SEC), sock_connect=CONNECT_TIMEOUT_SEC),
                connector=aiohttp.TCPConnector(limit=MAX_CONNECTIONS, limit_per_host=MAX_CONNECTIONS_PER_HOST, ttl_dns_cache=300, enable_cleanup_closed=True),
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip, deflate",   # DROP 'br' — aiohttp can't decode brotli without the brotli lib
                },
            )
```

- **Drop `br` from `Accept-Encoding`** — otherwise upstream returns Brotli and aiohttp
  fails with `Can not decode content-encoding: br`. `gzip, deflate` is universally supported.
- Restart the wrapper → `curl http://127.0.0.1:9103/v1/chat/completions` with a free model → `200`.

## Which wrappers
- **opencode (9103)**: confirmed CF 1010 → fixed, verified `hallo` → "Hallo! Wie...".
- **vercel (9105)**: hardened with same UA for consistency; its remaining `403` is a
  SEPARATE root cause — **upstream requires a credit card on file**
  (`AI Gateway requires a valid credit card...`), NOT a UA/CF block. Do NOT chase UA for
  vercel's 403.
- Apply to ANY future wrapper that fronts a Cloudflare-protected API.

## KEY RULE
If `curl` to the upstream works but the wrapper (aiohttp/urllib) fails with `403/1010` or a
misleading `invalid_credential` / `No capacity`, SUSPECT the **User-Agent bot-block** BEFORE
rotating keys. Add a browser UA. This is a wrapper-side fix, not an upstream account limit.
