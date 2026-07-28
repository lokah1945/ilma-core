# Reachability / "site can't be reached" — 2026-07-28

## Symptom reported by Bos
"cek all wrapper, dashboard tidak muncul dan ada error 'This site can't be reached'"

Services showed `active (running)` via `systemctl --user`, but browser (via LAN IP) got connection-refused.

## Diagnosis transcript (condensed)

```bash
# ss -tlnp BEFORE fix — note 127.0.0.1 and [::1] binds:
LISTEN 127.0.0.1:9101   (wrapper-nvidia-python)
LISTEN 127.0.0.1:9102   (wrapper-nous)
LISTEN 127.0.0.1:9103   (wrapper-opencode)
LISTEN 127.0.0.1:9104   (wrapper-blackbox)
LISTEN 127.0.0.1:9105   (wrapper-vercel)
LISTEN [::1]:3001       (ilma-dashboard-frontend — Vite, IPv6 localhost only)
LISTEN 0.0.0.0:8000     (ilma-dashboard-backend — already correct)

# curl via LAN IP 172.16.102.11 BEFORE fix:
PORT 9100: REFUSED (not deployed)
PORT 9101: HTTP 200
PORT 9102: HTTP 404   (server alive, no / route)
PORT 9103-9105: HTTP 404
PORT 3001: HTTP 000   REFUSED  <-- dashboard frontend dead to 127.0.0.1 too

# Machine IPs: 172.16.102.11 (LAN), CloudflareWARP tunnel present. No nginx/caddy.
```

Key insight: `127.0.0.1:*` binds mean a browser hitting `http://172.16.102.11:9102` is refused. `[::1]:3001` means even `127.0.0.1:3001` is refused (Vite IPv6-only default).

## Fixes applied

### 1. All 5 wrapper units → `--host 0.0.0.0`
File: `~/.config/systemd/user/wrapper-<nous|nvidia-python|opencode|blackbox|vercel>.service`
```diff
- ExecStart=/usr/bin/python3 -m uvicorn src.main:app --host 127.0.0.1 --port 910X
+ ExecStart=/usr/bin/python3 -m uvicorn src.main:app --host 0.0.0.0 --port 910X
```

### 2. Vite frontend → bind 0.0.0.0, port 3000 (match config)
File: `/root/.hermes/profiles/ilma/dashboard/frontend/vite.config.ts`
```diff
   server: {
+    host: '0.0.0.0',
     port: 3000,
+    strictPort: true,
     proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } }
   }
```
File: `~/.config/systemd/user/ilma-dashboard-frontend.service`
```diff
- ExecStart=/usr/bin/node .../vite --port 3001
+ ExecStart=/usr/bin/node .../vite --port 3000 --host 0.0.0.0
```

### 3. Backend CORS → allow LAN origin
File: `/root/.hermes/profiles/ilma/dashboard/backend/app/main.py`
```diff
- allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
+ allow_origins=["*"],
```

### 4. Reload + restart
```bash
systemctl --user daemon-reload
systemctl --user restart wrapper-nous wrapper-nvidia-python wrapper-opencode wrapper-blackbox wrapper-vercel ilma-dashboard-frontend ilma-dashboard-backend
```

## Verification AFTER fix (via LAN IP 172.16.102.11)
```bash
ss -tlnp | grep -E ':(9101|9102|9103|9104|9105|8000|3000)'
# all now 0.0.0.0:<port>

curl -s -o /dev/null -w "%{http_code}\n" http://172.16.102.11:9102/  # 200 (server alive)
curl -s -o /dev/null -w "%{http_code}\n" http://172.16.102.11:3000/  # 200 (dashboard)
curl -s -o /dev/null -w "%{http_code}\n" http://172.16.102.11:8000/  # 200 (backend)

# CORS now echoes the LAN origin:
curl -s -i -H "Origin: http://172.16.102.11:3000" http://172.16.102.11:8000/ | grep -i access-control
# access-control-allow-origin: http://172.16.102.11:3000
```

## Why the services were down ~3h before the fix
Wrapper logs showed graceful shutdown at 08:27 (external `daemon-reload`/restart), then no traffic until the fix restarted them at 08:30. Not a crash — just not running while Bos tried to open them. After the bind fix they are `enabled` + `Restart=always`, so a future crash auto-recovers; the bind fix is what makes them *reachable* from the LAN.

## Reuse checklist for next "site can't be reached"
1. `ss -tlnp` → read the INTERFACE column (127.0.0.1 / [::1] / 0.0.0.0).
2. `curl` the LAN IP (not localhost). `000` = bind issue.
3. Patch `--host` in the systemd unit (or `host:` in vite.config.ts) → `0.0.0.0`.
4. Check CORS `allow_origins` in any FastAPI/Flask backend if a web UI talks to an API.
5. `daemon-reload` + restart + re-test via LAN IP.
