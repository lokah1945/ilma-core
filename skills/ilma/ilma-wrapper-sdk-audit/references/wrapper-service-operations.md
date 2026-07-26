# Wrapper Service Operations (proven 2026-07-25)

Concrete commands + fixes for the `/root/wrapper` LLM-proxy ecosystem.
Companion to SKILL.md "Service Ops" + "H-03/H-04" sections.

## Canonical ports (mem_014 override, 2026-07-24 — sequential, no gaps)
| Wrapper | Port | systemd unit |
|---------|:----:|---------------|
| nvidia-python | 9101 | wrapper-nvidia-python.service |
| nous | 9102 | wrapper-nous.service |
| opencode | 9103 | wrapper-opencode.service |
| blackbox | 9104 | wrapper-blackbox.service (often NOT installed by default) |
| model-registry | 9200 | wrapper-model-registry.service |

STALE ports to reject on sight: nous=9106, opencode=9107, nvidia=9100/9910.

## A. Install a wrapper from repo (blackbox / model-registry pattern)
```bash
SRC=/root/wrapper/blackbox/systemd/wrapper-blackbox.service
DST=/root/.config/systemd/user/wrapper-blackbox.service
cp "$SRC" "$DST"
systemctl --user daemon-reload
systemctl --user enable --now wrapper-blackbox.service
sleep 3
systemctl --user is-active wrapper-blackbox.service   # -> active
curl -s -m5 -o /dev/null -w "%{http_code}\n" http://127.0.0.1:9104/health   # -> 200
```
Note: some repos ship BOTH `systemd/wrapper-X.service` and `wrapper-X.service` at the
subdir root — pick the one that exists; both are identical.

## B. Verify systemd-managed vs orphan runtime (H-01 trap)
Never trust an audit report's "service inactive / orphan runtime" claim blindly —
it is often generated before the live session restarted services.
```bash
for s in wrapper-nvidia-python wrapper-nous wrapper-opencode wrapper-blackbox wrapper-model-registry; do
  printf "%-26s active=%s\n" "$s" "$(systemctl --user is-active $s 2>/dev/null)"
done
# port -> PID -> cgroup
for p in 9101 9102 9103 9104 9200; do
  pid=$(ss -ltnp 2>/dev/null | grep -E ":$p\b" | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2)
  [ -n "$pid" ] && cg=$(tr '\n' ' ' < /proc/$pid/cgroup 2>/dev/null | grep -o 'user@[^ ]*')
  printf "port %s pid=%s %s\n" "$p" "${pid:-none}" "${cg:+SYSTEMD-MANAGED}${cg:-ORPHAN-OR-DOWN}"
done
```
`active` + `SYSTEMD-MANAGED` ⇒ real service, report was stale. Do NOT kill.

## C. Codex config port sync (recurring drift)
Codex reads `~/.codex/config.toml` (default) + `~/.codex-homes/<name>/config.toml`.
Each `[model_providers.<name>]` has `base_url = "http://127.0.0.1:<port>/v1"`.
```bash
grep -rniE 'base_url.*910[0-9]' /root/.codex/config.toml /root/.codex-homes/*/config.toml
# Expect only: 9101 (nvidia/nvidia-py), 9102 (nous), 9103 (opencode), 9104 (blackbox)
```
Fix: replace stale 9106/9107/9100 with canonical. Do NOT edit while a
`/root/.codex/.config.toml.swp` vim-swap is held (check `lsof` first).

## D. H-03: WRAPPER_SKIP_DOTENV (test isolation)
Every wrapper loads `.env` at import. Tests that cleared `os.environ` still get
production keys back via `load_dotenv()`. Guard all top-level loads:
```python
if os.environ.get("WRAPPER_SKIP_DOTENV", "").lower() != "true":
    load_dotenv()
```
Per-wrapper specifics:
- nvidia-python/src/main.py: line ~462 `load_dotenv()` (KEEP hot-reload at ~251)
- nous/wrapper_nous.py: def `load_dotenv()` then top-level call ~215 (KEEP watcher ~232)
- opencode/src/main.py: lines 50 + 53 (both guarded; keep `OPENCODE_BASE_URL` fallback gating)
- blackbox/src/main.py: lines 48 + 49

## E. H-04: git_commit / source_root / pid in /health + /version
Audit must prove source-commit == runtime-commit. Add to every wrapper:
```python
def _resolve_git_commit():
    try:
        import subprocess
        return subprocess.check_output(['git','rev-parse','HEAD'],
            cwd='/root/wrapper', stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return 'unknown'

GIT_COMMIT = _resolve_git_commit()
SOURCE_ROOT = '/root/wrapper/<svc>'   # nvidia-python|nous|opencode|blackbox
```
Then add `"git_commit": GIT_COMMIT, "source_root": SOURCE_ROOT, "pid": os.getpid()`
to the `/health` return dict AND the `/version` return dict (nvidia also `/api/version`).
Restart service, then confirm:
```bash
curl -s -m5 http://127.0.0.1:9101/health | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('git_commit'),d.get('source_root'),d.get('pid'))"
```

## F. Restart-guard note
`systemctl --user restart` on all 5 wrappers was BLOCKED by a safety guard once
(the runtime read it as "destructive"). If blocked, STOP and ask Bos — do not
rephrase/retry the same restart. Bos has explicitly authorized "restart all wrapper"
in prior sessions, so a block is a guard false-positive, not a refusal.
