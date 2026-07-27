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
7. **NOUS modular split broken (upstream `69af4aa`, 2026-07-28)**: upstream extracted `KeyPool`/`KeyEntry`/`Metrics` from `nous/src/main.py` into `nous/src/key_pool.py` + `metrics.py`, but `key_pool.py` is missing the imports it needs (`Path`, `ModelStateStore`, `asyncio`, `json`, `aiohttp`, `CircuitBreakerError`, `_UPSTREAM_BREAKER`, etc.) → `NameError`/`ImportError` on startup. Symptom: `systemctl --user is-active wrapper-nous` shows `activating` (never `active`), port 9102 curl = `000` (connection refused), log file empty or truncated. Fix: **revert nous to the last working inline commit** — `git checkout <pre-split-sha> -- nous/src/main.py && rm -f nous/src/key_pool.py nous/src/metrics.py` (pre-split = `7591c70` for this incident). Do NOT try to patch the extracted `key_pool.py` (it references ~30 undefined symbols — a Frankenstein file). Re-test import + restart + all-6 health. This is an INTENTIONAL local divergence (see Intentional divergence below).

8. **VERCEL shows 0 models (`/v1/models` empty) when `FREE_ONLY=yes`** (2026-07-28): vercel's curated fallback list (`gpt-5.4-mini`, `claude-*`, `google/gemini-*`, etc.) contains NO id with `free` in the name. `model_allowed()` returns `is_free_model(raw)` → False for all → `free_only` filter strips the entire list → `data: []`. Symptom: `curl /v1/models` → `{"data":[],"free_only":true}`. Fix: set `FREE_ONLY=no` in `vercel/.env` (Vercel AI Gateway has no free-tier curated models; the wrapper still enforces per-key entitlement upstream). After restart, `/v1/models` returns 13 models. NOTE: with `FREE_ONLY=no`, chat may still fail with upstream `"No capacity"` if `VERCEL_API_KEY` lacks entitlement — that is an upstream key issue, not a wrapper bug.
9. **BEARER_TOKEN placeholder → 401 on every client request** (2026-07-28): all 5 `.env` files shipped with `BEARER_TOKEN=your-secure-random-token-here` (upstream template default). Any client sending the real local key (`wrapper-local-key`) gets `401 Unauthorized`. This was the root cause of OpenHand/Codex/ILMA failing to auth after the restructure. Fix: `sed -i 's/^BEARER_TOKEN=your-secure-random-token-here/BEARER_TOKEN=wrapper-local-key/' <wrapper>/.env` for all 5 wrappers, restart. Verify: `curl -H "Authorization: Bearer wrapper-local-key" http://127.0.0.1:9102/v1/models` → 200.

## OpenCode custom provider registration (references/opencode-provider-setup.md)
- Binary `/root/.opencode/bin/opencode`, config `~/.config/opencode/opencode.jsonc`.
- Custom OpenAI-compatible providers REQUIRE `"npm": "@ai-sdk/openai-compatible"` (install: `cd ~/.config/opencode && npm install @ai-sdk/openai-compatible`).
- Models MUST be registered manually under `"models"` (OpenCode does NOT auto-fetch `/v1/models` for custom providers).
- Verify: `opencode models` lists `wrapper-<name>/<model>` lines; smoke test `opencode run "reply exactly: PONG" -m wrapper-nous/tencent/hy3:free`.

## Pre-restart import-test recipe (catches broken imports BEFORE the service dies)
After ANY code change to a wrapper (pull, revert, patch), do NOT just restart + curl. Test the import directly first — a broken import leaves the service `activating`/`failed` and wastes a restart cycle:
```bash
cd /root/wrapper/<wrapper>
python3 -c "
import sys; sys.path.insert(0,'.')
import importlib.util
spec = importlib.util.spec_from_file_location('src.main','src/main.py', submodule_search_locations=['src'])
m = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(m)
    print('IMPORT OK, title=', m.app.title)
except Exception as e:
    import traceback; traceback.print_exc()
"
```
If this raises (NameError/ImportError/ModuleNotFoundError), FIX before restarting. Note: relative imports (`from .key_pool`) require the `submodule_search_locations=['src']` arg above — loading `src/main.py` as a bare file fails with "attempted relative import with no known parent package".

## Intentional divergence (do NOT "fix" these back)
- **nous stays INLINE** (`nous/src/main.py` contains `KeyPool`/`KeyEntry`/`Metrics` inline). Upstream's modular split (`key_pool.py`/`metrics.py`) is broken (bug #7). Never re-apply the modular split or delete the inline classes. This divergence is documented in commit messages + runtime/*.commit pins so it is traceable.
- When pushing a fix that reverts an upstream change, the commit message MUST state WHY (e.g. "revert broken nous modular split — upstream key_pool.py missing imports → ImportError"). Future sessions reading `git log` will then know the divergence is deliberate.

## Distrust upstream "audit passed" claims
- Upstream audit docs (e.g. `AUDIT_ZERO_BUG_2026-07-28.md`) claim "syntax validation passed" / "100/100 production grade" — but **syntax check ≠ import/run check**. In this incident the audited `nous/src/key_pool.py` crashed on import. ALWAYS verify by actually importing + curling `/health`, never by trusting the audit doc.
- `journalctl --user -u wrapper-<name>` returns "No journal files were found" on this host (user journald not persistent). **Log files are the source of truth**: `tail /root/wrapper/<wrapper>/<wrapper>.log` (or `wrapper_<name>.log`).

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
- `references/nous-modular-split-broken-2026-07-28.md` — upstream `69af4aa` split nous into broken `key_pool.py`; symptom, fix (revert to inline), intentional divergence.
- `scripts/verify_wrappers.py` — probe all wrapper ports, print health table.
- `scripts/smoke_hallo_all.py` — **end-to-end chat smoke**: sends "hallo" to all 5 wrappers, picks first `:free` model, reports non-empty reply or error class (401/0-models/exhausted/No-capacity). Usage: `python3 scripts/smoke_hallo_all.py [--token wrapper-local-key] [--prompt "hallo"] [--ports 9101,9102]`. Runs in ONE command — use this (not manual curl loops) to verify chat works after a pull/config change.
