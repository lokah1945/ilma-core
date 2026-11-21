# Wrapper Dashboard Auth Parity — Pitfall & Fix Recipe

## Symptom
User reports "dashboard tidak seperti sebelumnya" / blank / all cards show "–" /
charts empty, but the static `dashboard.html` is byte-identical to a known-good
version.

## Root cause class (Node→Python migration parity bug)
The dashboard SPA fetches `/metrics`, `/metrics/chart/hourly`,
`/metrics/activity`, `/metrics/models`, etc. These endpoints sit behind a
`BEARER_TOKEN` auth middleware. The browser gets the token from a server-injected
`<meta name="wrapper-bearer-token" content="...">` tag in the served HTML.

- **Node reference** (`index.js` dashboard handler) does:
  `html = html.replace('<head>', '<head>\n<meta name="wrapper-bearer-token" content="...">')`
  when `BEARER_TOKEN` is set → dashboard works.
- **Python/FastAPI** that does only `HTMLResponse(content=Path('dashboard.html').read_text())`
  serves the file WITHOUT the meta tag → JS `getAuthHeaders()` returns `{}` →
  every `/metrics*` call gets `401 Unauthorized` → all cards render "–".

Confirm in one command:
```bash
# endpoints the dashboard JS hits — expect 401 without token, 200 with
B=$(grep BEARER_TOKEN .env | cut -d= -f2)
for p in /metrics /metrics/chart/hourly /metrics/activity /metrics/models; do
  echo "$p noauth: $(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:PORT$p?window=24h")"
  echo "$p auth:   $(curl -s -o /dev/null -w '%{http_code}' --max-time 5 -H "Authorization: Bearer $B" "http://127.0.0.1:PORT$p?window=24h")"
done
```

## The fix (FastAPI)
Replace the bare `@app.get('/dashboard')` handler with a helper that injects the
meta tag — exact parity with Node:

```python
def _serve_dashboard_html() -> HTMLResponse:
    dashboard_path = Path(__file__).parent.parent / 'dashboard.html'
    if not dashboard_path.exists():
        return HTMLResponse(content='<html><body><h1>wrapper</h1></body></html>')
    html = dashboard_path.read_text()
    token = (BEARER_TOKEN or '').strip()
    if token:
        meta_tag = '<meta name="wrapper-bearer-token" content="' \
            + token.replace('"', '&quot;') + '">'
        html = html.replace('<head>', '<head>\n' + meta_tag, 1)  # first <head> only
    return HTMLResponse(content=html)

@app.get('/dashboard')
async def dashboard():
    return _serve_dashboard_html()

@app.get('/dashboard.html')
async def dashboard_html():
    return _serve_dashboard_html()
```

## Verify after fix
```bash
curl -s http://127.0.0.1:PORT/dashboard | grep -o '<meta name="wrapper-bearer-token"[^>]*>'
# → <meta name="wrapper-bearer-token" content="wrapper-local-key">
```
Then re-run the noauth/auth loop above: noauth still 401 (auth intact), auth 200.
Dashboard cards now populate.

## Gotcha: grep false-positive
`grep '<meta name="wrapper-bearer-token">'` can match a **JS comment** inside the
HTML (`// 1. <meta name="wrapper-bearer-token"> — injected server-side`). The
real injected tag has `content="..."`. Filter with `[^>]*>` or check for `content=`.

## Architecture note (this environment)
- `/root/wrapper/nvidia` — DEPRECATED Node.js (`package.json` engines node>=20,
  runtime `v24.16.0`). Treat as READ-ONLY reference. Do not edit.
- `/root/wrapper/nvidia-python` — PRODUCTION FastAPI (`LISTEN_PORT=9101`,
  systemd `wrapper-nvidia-python.service`). This is the drop-in successor.
  When user says "fix the production dashboard", patch here, not the Node tree.
- Migration parity bugs (constants, endpoints, injected assets) are the usual
  cause of "dashboard broke after migration" — diff behavior, not just files.
