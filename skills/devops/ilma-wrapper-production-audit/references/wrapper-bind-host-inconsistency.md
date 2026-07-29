# Bind Host Inconsistency Across Wrappers — 2026-07-29

## Symptom
Wrappers bind to different interfaces:
- wrapper-nous: `0.0.0.0:9102` (all interfaces)
- wrapper-openrouter: `0.0.0.0:9106` (all interfaces)
- wrapper-opencode: `127.0.0.1:9103` (localhost only)
- wrapper-blackbox: `127.0.0.1:9104` (localhost only)
- wrapper-vercel: `127.0.0.1:9105` (localhost only)
- wrapper-nvidia-python: `0.0.0.0:9101` (all interfaces)

## Root Cause
No standard bind host in systemd units or code. Each wrapper's service file and main.py use different defaults.

## Impact
- LAN access works for some wrappers, not others
- Inconsistent security posture (0.0.0.0 exposes to LAN)
- Reverse proxy / mesh routing inconsistent
- "Site can't be reached" for LAN IP on some wrappers

## Fix Required
Standardize on `127.0.0.1` for all internal wrappers (secure by default):
- Edit all `~/.config/systemd/user/wrapper-*.service`: `ExecStart=... --host 127.0.0.1`
- Or set `BIND_HOST=127.0.0.1` in all `.env` files and read in code
- Use `0.0.0.0` ONLY for services explicitly meant for external access (via reverse proxy)

## Verification
After fix:
```bash
ss -tlnp | grep -E '910[1-6]'
# All should show 127.0.0.1:PORT
curl http://<LAN-IP>:9101/health  # Should fail (connection refused)
curl http://127.0.0.1:9101/health  # Should succeed
```

## Related
- `references/wrapper-free-only-inconsistency.md`
- `references/wrapper-python-venv-inconsistency.md`