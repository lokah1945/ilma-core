---
name: ilma-wrapper-fleet-ops
description: Manage the /root/wrapper LLM proxy fleet — git pull from github, restart systemd user units, register all wrappers as OpenCode custom providers, and fix recurring upstream bugs by adapting the healthy sibling wrappers (nvidia-python/blackbox) as reference. Use when user says "pull wrapper", "update local", "restart service", "sync wrappers", or when a wrapper 500s after a pull.
---

# ILMA Wrapper Fleet Ops

## When to use
- User says "pull wrapper repo", "update local file", "restart service", "sync wrappers".
- User wants all `/root/wrapper` proxies visible in OpenCode as provider choices.
- A wrapper returns HTTP 500 or fails to bind its port after a `git pull`.
- User says "abaikan local" (discard local fixes, reset to pure remote).

## Repo conventions (FACT — verified 2026-07-28)
- Repo: `/root/wrapper`, branch `main`.
- `git remote -v`: `github` = https://github.com/lokah1945/wrappers.git (**PULL FROM THIS**); `origin` = /root/wrapper_remote.git (LOCAL bare — **NEVER pull from origin**).
- Each wrapper is a Python FastAPI/uvicorn service on `127.0.0.1:910X`, managed as a **systemd user unit** in `~/.config/systemd/user/` (NOT a system unit).
- Unit `ExecStartPre` writes `runtime/<name>.commit` (git HEAD) — auto-generated, safe to stash/ignore.

## Standardized wrapper structure (post-2026-07-28 restructure)
- Every wrapper now lives at `<wrapper>/src/main.py` (was `<wrapper>/wrapper_<name>.py`).
- ALL 5 LLM wrappers run via `python3 -m uvicorn src.main:app` from `WorkingDirectory=/root/wrapper/<wrapper>` (nous + vercel were updated to this — they previously used `wrapper_*.py`).
- `wrappers.json` is now `{ "wrappers": { "nous": { "port": 9102, "module": "nous.src.main", "entry_point": "nous.src.main:app", ... } } }` (was a flat array).
- When aligning after a pull, also refresh `runtime/*.commit` files to the new HEAD (they pin the deployed commit per wrapper).

## Wrapper inventory (commit 4706765)
| Wrapper | Port | systemd unit | LLM? |
|---------|------|--------------|------|
| nvidia  | 9101 | wrapper-nvidia-python | yes |
| nous    | 9102 | wrapper-nous           | yes |
| opencode| 9103 | wrapper-opencode       | yes |
| blackbox| 9104 | wrapper-blackbox       | yes |
| vercel  | 9105 | wrapper-vercel         | yes |
| model-registry | 9200 | wrapper-model-registry | control plane (not an LLM provider) |

Client auth for all LLM wrappers: `Authorization: Bearer wrapper-local-key` (BEARER_TOKEN in each `.env`).

## Standard pull → update → restart workflow
1. `cd /root/wrapper && git status --short` — check uncommitted local fixes BEFORE pulling.
2. If local fixes exist and must be kept: `git stash push -u -m "ilma-fix-$(date +%s)"`, pull, then `git checkout stash@{0} -- <specific-file>` to restore only the needed fix (discard `runtime/*.commit` from stash).
3. If user says **"abaikan local"**: `git reset --hard github/main` (destroys ALL local commits/edits), then `git pull github main` (no-op if already at remote). Do NOT re-apply local patches unless user later asks.
4. `git fetch github main` + `git rev-list --left-right --count HEAD...github/main` → left=local-only, right=remote-only commits.
5. Restart: `systemctl --user restart wrapper-<name>.service` for each changed wrapper.
6. Verify with `scripts/verify_wrappers.py` (probes `/health` on every port).

## User preferences (embedded — do not re-ask)
- **"abaikan local"** = reset hard to `github/main`, discard local fixes. Wait for user to push real fixes to github.
- **"fix error 500, acuan pakai code dari repo github, sesuaikan saja"** = when fixing wrapper bugs, **ADAPT the pattern from the healthy sibling wrappers in the same repo** (nvidia-python & blackbox are the reference-stable ones). Do NOT invent a new method. Concretely: if `/health` calls `metrics.snapshot()` but the class lacks it, do what nvidia/blackbox do — call `await metrics.summary()` instead of adding a new `snapshot()` method.

## Recurring upstream bugs (knowledge bank → references/recurring-bugs.md)
Check these FIRST when a wrapper 500s after pull:
1. `Metrics.snapshot()` called in `/health` but class has no `snapshot()` → `AttributeError`. Fix: change to `await metrics.summary()` (matches nvidia/blackbox) OR add a `snapshot()` method.
2. `_dynamic_alias_lock = asyncio.Lock()` used with `with` (sync) → `TypeError: 'Lock' object does not support the context manager protocol`. Fix: `threading.Lock()`.
3. **VERCEL post-restructure broken imports** (2026-07-28): upstream moved `vercel/wrapper_vercel.py` → `vercel/src/main.py` but left `key_pool.py`/`metrics.py` at FLAT `vercel/` level. `vercel/src/main.py` does `from .key_pool import KeyPool` → resolves to `vercel.src.key_pool` → `ModuleNotFoundError`. Fix: `git mv vercel/key_pool.py vercel/src/key_pool.py` (and metrics.py). With siblings in `src/`, the relative import resolves ✅. Dashboard path stays `Path(__file__).parent.parent / "dashboard.html"` (= `vercel/dashboard.html`, which exists).
4. New wrapper in `wrappers.json` but no systemd unit → create `~/.config/systemd/user/wrapper-<name>.service` from the wrapper-nous template, adjust WorkingDirectory/port/ExecStart, then `daemon-reload && enable && start`.
5. **`[wrapper]` NameError in latency middleware** (`add_latency_tracking`): logs `f"[{wrapper}]..."` but `wrapper` is never defined → `NameError` 500 on every request. Affects nous/vercel/opencode. Fix: `[wrapper]` → `[app.title]` (app.title = "wrapper-nous" etc.). Don't hunt for a missing `wrapper` var — just use `app.title`.
6. **Upstream push race** (2026-07-28): between your `pull` and `push`, remote `github/main` may gain a commit that REVERSES your fixes or breaks imports (seen: `e908334` re-broke vercel + reverted `threading.Lock`/`await metrics.summary`). Symptom: `git push` rejected "fetch first". Fix flow: `git fetch github` → inspect new commit diff → `git reset --hard <pre-your-commit>` → `git pull --rebase github main` → re-apply ONLY your verified-working fixes on top → test all 6 → commit → push. See references/restructure-2026-07-28.md.

## OpenCode custom provider registration (references/opencode-provider-setup.md)
- Binary `/root/.opencode/bin/opencode`, config `~/.config/opencode/opencode.jsonc`.
- Custom OpenAI-compatible providers REQUIRE `"npm": "@ai-sdk/openai-compatible"` (install: `cd ~/.config/opencode && npm install @ai-sdk/openai-compatible`).
- Models MUST be registered manually under `"models"` (OpenCode does NOT auto-fetch `/v1/models` for custom providers).
- Verify: `opencode models` lists `wrapper-<name>/<model>` lines; smoke test `opencode run "reply exactly: PONG" -m wrapper-nous/tencent/hy3:free`.

## Pitfalls
- Never pull from `origin` (local bare repo) — only `github`.
- `git reset --hard` destroys uncommitted work — only on explicit "abaikan local".
- After `reset --hard`, recurring bug fixes are GONE → wrappers 500 until re-fixed or user pushes to github.
- `/health` returning 500 ≠ port not listening. Check both: `ss -ltnp` for bind, `/health` for app errors.
- OpenCode model list is static — re-sync `opencode.jsonc` when models change in a wrapper.
- **Upstream race on push**: if `git push` is rejected with "fetch first", someone pushed to `github/main` after your pull. NEVER force-push. `git fetch` → inspect the new commit (it may reverse your fixes or re-break imports) → `git reset --hard` to your pre-commit base → `git pull --rebase` → re-apply your verified fixes → retest all 6 → push.
- After ANY wrapper change, verify ALL 6 ports (9101–9105) return 200, not just the one you touched — a restructure commit can break siblings. Also hit `/v1/models` with an `x-request-id` header to exercise the latency middleware (catches the `[wrapper]` NameError that `/health` alone may miss).

## Support files
- `references/recurring-bugs.md` — exact bug transcripts + diffs.
- `references/opencode-provider-setup.md` — jsonc template + install + verify.
- `references/restructure-2026-07-28.md` — restructure pull, 4 bugs found + fixes, upstream-race recovery, verification recipe.
- `scripts/verify_wrappers.py` — probe all wrapper ports, print health table.
