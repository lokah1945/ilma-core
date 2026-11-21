# Wrapper Service — Restart-All & Repair Recipe (2026-07-23)

Operational walkthrough used when Bos says "restart all wrapper service" or a wrapper
port is dead after a `git pull` updated the code.

## 1. Enumerate reality (don't assume)

```bash
# What systemd --user actually knows about
systemctl --user list-unit-files | grep -i wrapper
systemctl --user list-units --all  | grep -i wrapper

# What's on disk (the repo may ship units that were never registered)
find /root/wrapper -name '*.service'

# For each candidate: active + enabled state
for s in wrapper-nvidia wrapper-nous wrapper-opencode; do
  printf "%s: active=%s enabled=%s\n" "$s" \
    "$(systemctl --user is-active $s 2>/dev/null || echo -)" \
    "$(systemctl --user is-enabled $s 2>/dev/null || echo -)"
done
```

A unit that is `not-found` via `is-enabled` but exists on disk = never registered.
A unit that is `active` but its port is NOT listening = process died / wrong path / missing dep.

## 2. Common unit-file defects found this session

| Defect | Symptom | Fix |
|--------|---------|-----|
| `WantedBy=multi-user.target` in a `--user` unit | `enable` succeeds but never auto-starts | change to `WantedBy=default.target` |
| `WorkingDirectory=/root/wrappers/` (typo) | unit starts, process can't find module | fix to `/root/wrapper/<provider>` |
| `ExecStart=/usr/local/bin/python` (absent) | unit fails immediately, port free | use `/usr/bin/python3` |
| `EnvironmentFile=` points to missing `.env` | unit fails at start | create `.env` from `.env.example` |

**Edit the unit where systemd reads it:** `/root/.config/systemd/user/<unit>.service`
(the repo copy under `/root/wrapper/<provider>/` is NOT what `--user` loads).

## 3. Repair + register + start

```bash
systemctl --user daemon-reload
systemctl --user enable  wrapper-nvidia.service wrapper-opencode.service
systemctl --user restart wrapper-nous.service      # already registered
systemctl --user start   wrapper-nvidia.service wrapper-opencode.service
```

## 4. Verify (ports + health, not just `is-active`)

```bash
ss -ltnp | grep -E '9100|9106|9107|9910'
curl -s --max-time 5 http://127.0.0.1:9106/health   # wrapper-nous
curl -s --max-time 5 http://127.0.0.1:9100/health   # wrapper-nvidia
curl -s --max-time 5 http://127.0.0.1:9107/health   # wrapper-opencode
```

`is-active=active` is NOT enough — a process can be "active" while its port isn't
bound (e.g. bound to wrong host, or crashed-and-restarted into a bad state). Always
confirm the port listens AND the `/health` endpoint returns 200-shaped JSON.

## 5. Git-update + restart coupling

After `git pull github main` updates wrapper code, restart the affected service so the
new code is live. Verify sync first:

```bash
git fetch github
git rev-list --left-right --count HEAD...github/main   # "0\t0" = fully synced
```

If `0 0` the local already equals GitHub; a restart still reloads the new code.
