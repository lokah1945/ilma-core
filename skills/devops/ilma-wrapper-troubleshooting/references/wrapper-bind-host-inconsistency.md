# Wrapper Bind Host Inconsistency — 2026-07-29

## Current State
| Wrapper | Bind Host | Port | systemd ExecStart |
|---------|-----------|------|-------------------|
| wrapper-nous | 0.0.0.0 | 9102 | `--host 0.0.0.0 --port 9102` |
| wrapper-openrouter | 0.0.0.0 | 9106 | `--host 0.0.0.0 --port 9106` |
| wrapper-opencode | 127.0.0.1 | 9103 | `--host 127.0.0.1 --port 9103` |
| wrapper-blackbox | 127.0.0.1 | 9104 | `--host 127.0.0.1 --port 9104` |
| wrapper-vercel | 127.0.0.1 | 9105 | `--host 127.0.0.1 --port 9105` |

## Problem
- **Mixed exposure**: Some wrappers accessible on LAN IP, some only localhost
- **Debugging confusion**: `curl http://<LAN-IP>:9103` fails (connection refused) but `127.0.0.1:9103` works
- **Security inconsistency**: Some services unnecessarily exposed on LAN

## Standard
**All internal wrappers bind `127.0.0.1` only.** External access via reverse proxy (nginx/Caddy) if needed.

Systemd unit should use:
```ini
ExecStart=... --host 127.0.0.1 --port <PORT>
```

## Fix
Update each wrapper's systemd unit:
```bash
# For each wrapper
sed -i 's/--host 0\.0\.0\.0/--host 127.0.0.1/' ~/.config/systemd/user/wrapper-<svc>.service
systemctl --user daemon-reload
systemctl --user restart wrapper-<svc>
```

## Exception
If a wrapper MUST be directly accessible (e.g., for a specific client that can't use reverse proxy), document it in the unit file with a comment and in this reference.

## Related
- `ilma-web-observability-dashboard` skill pitfall #8 — same bind issue for dashboard
- `ilma-wrapper-production-audit` — checks bind host in audit