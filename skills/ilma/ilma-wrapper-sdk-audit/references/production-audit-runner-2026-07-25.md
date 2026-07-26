# Production Audit Runner — Lessons 2026-07-25

Canonical runner for the `/root/wrapper` LLM-proxy ecosystem. Replaces the
legacy `/root/audit_report/` AUDIT_Vn.md loop for *scoring*; the separate
patch-agent discipline (Vn_PLAN / Vn_EXECUTION_REPORT) still applies for fixes.

## Location
- Script: `bash productions/run_production_audit.sh` (wrapper around `productions/production_audit.py`)
- Reports: `productions/reports/production-audit-YYYYMMDD-HHMMSS.md`

## Invocation (verified working)
```bash
cd /root/wrapper
export WRAPPER_API_KEY='wrapper-local-key'
bash productions/run_production_audit.sh \
  --run-tests \
  --run-smoke \
  --wrapper-url http://127.0.0.1:9101/v1 \
  --model 'nvidia/llama-3.3-nemotron-super-49b-v1' \
  --api-key-env WRAPPER_API_KEY
```
Note: the script is a **bash** script — do NOT run it with `python3` (SyntaxError on `set -euo pipefail`).

## Flags
| Flag | Effect |
|------|--------|
| `--run-tests` | isolated pytest + transparency checks (sets `WRAPPER_SKIP_DOTENV=true`) |
| `--run-smoke` | exact-model inference call to `--wrapper-url` with `--model` |
| `--wrapper-url` | e.g. `http://127.0.0.1:9101/v1` |
| `--model` | exact model id (must be one returned by `/v1/models`) |
| `--api-key-env` | env var name holding the bearer token (open-auth wrappers accept `wrapper-local-key`) |
| `--run-load` | bounded concurrency load test |
| `--required-wrapper <name>` | repeatable; default = all 5 (model-registry, nvidia, nous, opencode, blackbox) |
| `--require-registry` | mark model-registry required |

## Verified result (2026-07-25, commit c0a6535)
```
PASS=30  FAIL=0  BLOCKED=1   (BLOCKED = working tree had uncommitted changes)
→ after git commit + push: BLOCKED=0  ⇒ PRODUCTION READY
```
Smoke: `nvidia/llama-3.3-nemotron-super-49b-v1` → HTTP 200, `returned_model` == requested (no substitution). 72 unit tests passed.

## Critical pitfall: systemd `--user` scope (H-01 root cause)
The runner originally called `systemctl is-active <unit>` **without `--user`**.
On this VPS the wrappers run under `systemctl --user` (per-user scope), so a bare
`systemctl is-active` queries the *system* scope (empty) → false `inactive` +
false "orphan runtime" for every wrapper whose `/health` returns 200.

**Fix (commit c0a6535, production_audit.py ~line 214):**
```python
rc, out = audit.command(["systemctl", "--user", "is-active", unit], timeout=15)
```

**Generic lesson:** when auditing systemd-managed services, ALWAYS use `systemctl --user`
on this VPS. A bare `systemctl is-active` reporting "inactive" for a service whose
`/health` returns 200 is almost certainly a scope mismatch, not a real orphan.
Before killing/restarting, verify:
```bash
systemctl --user is-active wrapper-nous.service
pid=$(ss -ltnp | grep ':9102\b' | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2)
tr '\n' ' ' < /proc/$pid/cgroup | grep -q 'user@' && echo SYSTEMD-MANAGED || echo ORPHAN
```

## H-03 / H-04 source hardening (for fix sessions)
- **Test isolation:** wrap every top-level `load_dotenv()` in all 4 wrappers with
  `if os.environ.get("WRAPPER_SKIP_DOTENV","").lower() != "true": load_dotenv()`.
  The audit runner sets `WRAPPER_SKIP_DOTENV=true` for isolated test subprocesses
  so production `.env` keys cannot re-enter the test process.
- **Build identity:** `/health` AND `/version` now return `git_commit`
  (from `git rev-parse HEAD` at `/root/wrapper`), `source_root`, `pid`.
  Audit compares `git HEAD` vs runtime `git_commit` to prove source==runtime.
  Example live response:
  `{"version":"8.6.5-py","git_commit":"6b5a1d9...","source_root":"/root/wrapper/nvidia-python","pid":2271877}`

## Service install pattern (blackbox / model-registry were NOT installed by default)
```bash
SRC=/root/wrapper/blackbox/systemd/wrapper-blackbox.service
DST=/root/.config/systemd/user/wrapper-blackbox.service
cp "$SRC" "$DST"
systemctl --user daemon-reload
systemctl --user enable --now wrapper-blackbox.service
sleep 3
systemctl --user is-active wrapper-blackbox.service   # expect: active
curl -s -m5 -o /dev/null -w "%{http_code}\n" http://127.0.0.1:9104/health  # expect 200
```

## Codex config port sync (recurring drift)
Codex reads `~/.codex/config.toml` (default) + `~/.codex-homes/<name>/config.toml`.
Each `[model_providers.<name>]` has `base_url = "http://127.0.0.1:<port>/v1"`.
Audit ALL of them for stale ports (9106/9107/9100) → fix to canonical
(9101 nvidia / 9102 nous / 9103 opencode / 9104 blackbox). Do NOT edit while a
`.config.toml.swp` vim-swap is held (check `lsof` first).
