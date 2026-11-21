# Wrapper Restructure & Upstream-Race Recovery (2026-07-28)

## Context
User: "ada upgrade dari repo github project wrapper, silahkan pull, anda sesuaikan semua config dengan pembaruan terakhir dari repo github"

## Upstream restructure that landed
Pulled via `git pull --ff-only github main` (HEAD was `4706765`, moved to `7a8dc64`):
- `d6a87fc` refactor: standardize all wrapper structures for consistency
- `7a8dc64` feat: achieve 100/100 production grade across all wrappers

Result: every wrapper moved from `<wrapper>/wrapper_<name>.py` → `<wrapper>/src/main.py`.
`wrappers.json` rewritten to:
```json
{ "wrappers": { "nous": { "port": 9102, "module": "nous.src.main", "entry_point": "nous.src.main:app", ... } } }
```
(was a flat array with `source: "nous/wrapper_nous.py"`).

## Bugs found AFTER pull (wrapper 500 on /health)
All 5 LLM wrappers run via `python3 -m uvicorn src.main:app` from `WorkingDirectory=/root/wrapper/<wrapper>`
(nvidia-python/opencode/blackbox already correct). `wrapper-nous` + `wrapper-vercel` systemd still pointed at
the OLD `wrapper_*.py` filenames → broken on restart.

### Bug 1 — nous/vercel systemd ExecStart stale
- Symptom: service `active` but `/health` 500 / file-not-found on restart.
- Fix: `wrapper-nous.service` + `wrapper-vercel.service` ExecStart →
  `/usr/bin/python3 -m uvicorn src.main:app --host 127.0.0.1 --port 9102` (nous) / `...9105` (vercel).

### Bug 2 — vercel relative imports broken post-restructure
- `vercel/src/main.py` does `from .key_pool import KeyPool` and `from .metrics import Metrics`.
- Upstream left `key_pool.py` / `metrics.py` at FLAT `vercel/` level (not `vercel/src/`).
- `from .key_pool` from inside `vercel/src/main.py` resolves to `vercel.src.key_pool` → `ModuleNotFoundError`.
- Fix: `git mv vercel/key_pool.py vercel/src/key_pool.py && git mv vercel/metrics.py vercel/src/metrics.py`.
- Verified: with siblings in `src/`, `from .key_pool` → `vercel.src.key_pool` ✅.
- Dashboard path stays `Path(__file__).parent.parent / "dashboard.html"` (= `vercel/dashboard.html`, which exists) — DO NOT change it.

### Bug 3 — `[wrapper]` NameError in latency middleware
- `add_latency_tracking` middleware logs `f"[{wrapper}] request_id=..."` but `wrapper` is never defined
  → `NameError` on every request (500).
- Affects nous, vercel, opencode (opencode happened to survive because its middleware wasn't triggered by the
  endpoints tested, but the bug is latent — fix it everywhere).
- Fix: replace `[wrapper]` → `[app.title]` (app.title = "wrapper-nous" / "wrapper-vercel" / "wrapper-opencode").
- Do NOT hunt for where `wrapper` was "supposed" to be defined — just use `app.title`.

### Bug 4 — upstream reversed two working local fixes (commit e908334)
After our first commit attempt, `git push` was REJECTED ("fetch first") — remote `github/main` had a NEW commit
`e908334` "fix: correct dashboard and database paths":
- Re-reverted `nous/_dynamic_alias_lock` back to `asyncio.Lock()` (Bos's fix was `threading.Lock()`).
- Re-reverted `opencode`/`vercel` health `metrics.summary()` back to `metrics.snapshot()` (Bos's fix was `await metrics.summary()`).
- Re-introduced `[wrapper]` NameError and moved vercel siblings BACK to flat (broken imports again).
- ALSO fixed legitimate path issues (model-state.db, env-watcher, dashboard paths for the flat layout).

**Recovery flow:**
```
git reset --hard 7a8dc64        # discard our unpushed commit, return to pre-race base
git pull --rebase github main   # fast-forward to e908334
# re-apply ONLY our verified-working fixes on top:
#   git mv vercel/{key_pool,metrics}.py -> vercel/src/
#   [wrapper] -> [app.title]  (nous, vercel, opencode)
#   nous: threading.Lock()
#   opencode/vercel: await metrics.summary()
systemctl --user daemon-reload && restart wrapper-nous wrapper-vercel
# test all 6 -> commit -> push
```
Final push: `e908334..7591c70 main -> main`.

## Verification recipe (run after ANY wrapper change)
```bash
for p in 9101 9102 9103 9104 9105; do
  code=$(curl -s --max-time 4 -o /dev/null -w "%{http_code}" http://127.0.0.1:$p/health)
  echo "port $p: HTTP $code"
done
systemctl --user is-active wrapper-nvidia-python wrapper-nous wrapper-opencode wrapper-blackbox wrapper-vercel
```
All 6 must be 200. ALSO hit `/v1/models` with an `x-request-id` header to exercise the latency middleware
(this is what catches the `[wrapper]` NameError — `/health` alone may not trigger it):
```bash
curl -s -H "x-request-id: ilma-test" -o /dev/null -w "%{http_code}\n" http://127.0.0.1:9102/v1/models
```

## Final state (commit 7591c70)
- HEAD == github/main (7591c70), working tree clean.
- All 6 wrappers HTTP 200.
- runtime/*.commit aligned to HEAD.
- systemd: nous + vercel now use `python3 -m uvicorn src.main:app` (matching nvidia/opencode/blackbox).
