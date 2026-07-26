---
name: ilma-browser-admin-profile
description: ILMA Browser Identity Isolation — per-profile browser system (admin-only lokah2150, others isolated). Safe slug validation, path traversal protection, admin guard, CDP per profile.
triggers:
  - browser profile isolation
  - chrome multi-user
  - per-profile browser
  - browser identity isolation
  - /root/user-data/lokah2150 admin
  - ilma-chrome template service
  - phase 69d
  - binary audit
  - cdp direct
---

# ILMA Browser Identity Isolation — Per-Profile System

## Overview

`/root/user-data/lokah2150` is **ADMIN-ONLY** — protected browser identity. Non-admin profiles get isolated user-data-dir under `/root/user-data/<profile_name>`.

## Architecture

```
Admin (lokah2150 / huda)
  -> Profile: /root/user-data/lokah2150
  -> CDP: http://127.0.0.1:9222
  -> Service: ilma-chrome@lokah2150.service
  -> Protected: YES

User (arahman)
  -> Profile: /root/user-data/user_arahman
  -> CDP: http://127.0.0.1:9231
  -> Service: ilma-chrome@user_arahman.service
  -> Protected: NO

User (sinta)
  -> Profile: /root/user-data/user_sinta
  -> CDP: http://127.0.0.1:9232
  -> Service: ilma-chrome@user_sinta.service
  -> Protected: NO
```

## Key Files

| File | Purpose |
|------|---------|
| `/root/.hermes/browser-registry/browser-registry.yaml` | Central profile registry |
| `/root/.config/systemd/user/ilma-chrome@.service` | Template systemd service |
| `/root/.config/hermes-browser/<profile>.env` | Per-profile env vars |
| `/root/.hermes/playwright-cdp/launcher.mjs` | Secure launcher (v2.0, safeSlug) |
| `/root/.hermes/profiles/ilma/scripts/ilma_browser_engine.py` | v2.6+ per-profile routing |
| `/root/.hermes/profiles/ilma/scripts/ilma_browser_keepalive.py` | v2.2 keepalive daemon |

## Security Guarantees

1. **safeSlug() validation** — profile names must match `/^[a-zA-Z0-9_-]+$/`, max 64 chars
2. **Path traversal protection** — user-data-dir MUST be under `/root/user-data/`
3. **Admin profile guard** — non-admin profiles CANNOT access `/root/user-data/lokah2150`
4. **0700 permissions** — all user-data-dir must have 0700
5. **CDP 127.0.0.1 only** — never 0.0.0.0
6. **No duplicate Chrome** — never run two Chrome with same user-data-dir

## Operations

### Status check
```bash
python3 /root/.hermes/profiles/ilma/scripts/ilma_browser_keepalive.py status
python3 /root/.hermes/profiles/ilma/scripts/ilma_browser_keepalive.py list
```

### Start/stop a profile
```bash
# Admin profile
systemctl --user enable --now ilma-chrome@lokah2150.service
systemctl --user stop ilma-chrome@lokah2150.service

# User profile
systemctl --user enable --now ilma-chrome@user_arahman.service
systemctl --user stop ilma-chrome@user_arahman.service
```

### Verify CDP
```bash
curl -s http://127.0.0.1:9222/json/version | python3 -m json.tool
curl -s http://127.0.0.1:9231/json/version | python3 -m json.tool
```

### Check no cross-use
```bash
ps aux | grep -Ei 'chrome|chromium|headless-shell' | grep -- '--user-data-dir'
```

## Adding a New Profile

1. Add to `/root/.hermes/browser-registry/browser-registry.yaml` under `users:`
2. Create env file: `/root/.config/hermes-browser/<profile>.env`
3. Create user-data-dir: `mkdir -p /root/user-data/<profile> && chmod 700 /root/user-data/<profile>`
4. Reload systemd: `systemctl --user daemon-reload`
5. Enable service: `systemctl --user enable --now ilma-chrome@<profile>.service`

## BrowserEngine Usage (v2.6+)

```python
from ilma_browser_engine import BrowserEngine, ADMIN_BROWSER_PROFILE, ACTIVE_PROFILE_NAME

# Default: uses active profile (from HERMES_BROWSER_PROFILE_NAME env or config)
engine = BrowserEngine(stealth=True, cdp=True)
await engine.initialize()

# Explicit profile (validated against registry)
engine = BrowserEngine(
    stealth=True,
    cdp=True,
    persistent_user_data_dir="/root/user-data/user_arahman"
)
await engine.initialize()

# Admin profile explicitly
engine = BrowserEngine(
    stealth=True,
    cdp=True,
    persistent_user_data_dir="/root/user-data/lokah2150"  # admin only!
)
await engine.initialize()

# One-time session (no persistence)
engine = BrowserEngine(stealth=True, cdp=True, one_time_session=True)
await engine.initialize()
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HERMES_BROWSER_PROFILE_NAME` | Profile slug | lokah2150 |
| `HERMES_BROWSER_HOST` | CDP host | 127.0.0.1 |
| `HERMES_BROWSER_PORT` | CDP port | 9222 (admin), 9231+ (users) |
| `HERMES_BROWSER_USER_DATA_DIR` | Explicit user-data-dir | auto |
| `HERMES_BROWSER_HEADLESS` | 0=headed, 1=headless | 1 |
| `HERMES_BROWSER_PROTECTED` | 1=admin protected | 0/1 |
| `HERMES_BROWSER_ROLE` | 'admin' or 'user' | user |