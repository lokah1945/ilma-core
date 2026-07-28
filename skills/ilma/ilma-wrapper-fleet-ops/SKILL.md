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
10. **Misleading "All API keys exhausted" = classification.get() object bug (nvidia-python, 2026-07-28, commit 461ad81)**: classify_upstream_error() returns an ErrorClassification OBJECT (has __getitem__, NOT .get()). nvidia-python/src/main.py (~line 2355/2357) uses classification.get('state','') / .get('retry_same_model') → AttributeError inside the per-key retry loop whenever upstream returns ANY error (404/400/etc). Exception swallowed → every key marked failed → wrapper reports MISLEADING "All API keys exhausted" (hides real 404/400). TELLTALE: wrapper .log shows `[proxy_openai] error: 'ErrorClassification' object has no attribute 'get'` repeated N times (N = key count). Fix: classification.get('state','') → classification['state'] and classification.get('retry_same_model') → classification['retry_same_model'] (bracket access, dict-compat via __getitem__). After fix, REAL upstream error surfaces (e.g. 404 Function '...' Not found for account '...' = model not deployed in that NVIDIA account). CRITICAL: if minimaxai/minimax-m3 returns 200 but another model returns "exhausted" on SAME key pool, keys are FINE — error-path crashed. Do NOT rotate keys before checking log for this telltale. Full repro + fix in ilma-wrapper-troubleshooting SKILL.md § "Misleading 'All API keys exhausted'".

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

## Reachability / "site can't be reached" (bind host + CORS) — 2026-07-28
Symptom: user reports ALL wrappers + dashboard show "This site can't be reached" in the browser, even though `systemctl --user` shows `active (running)`.
Root causes, in priority order:
1. **Wrappers bound to `127.0.0.1` only.** Every `wrapper-*.service` ExecStart used `--host 127.0.0.1`. Opening via the machine LAN IP (e.g. `172.16.102.11:9102`) or any non-localhost name → connection refused → browser "site can't be reached". Fix: `--host 127.0.0.1` → `--host 0.0.0.0` in each unit, `daemon-reload`, restart.
2. **Vite frontend bound to `[::1]` (IPv6 localhost) only.** `vite.config.ts` had no `host` set and `ilma-dashboard-frontend.service` hardcoded `--port 3001`. With no host, Vite defaults to `[::1]` → `127.0.0.1:3001` REFUSED. Fix: add `host: '0.0.0.0'` + `strictPort: true` to `vite.config.ts` `server:{}`, and change the unit ExecStart to `--port 3000 --host 0.0.0.0` (match config port). After fix `ss -tlnp` shows `0.0.0.0:3000`.
3. **Backend CORS blocks LAN-origin browser.** `dashboard/backend/app/main.py` CORSMiddleware `allow_origins=["http://localhost:3000","http://127.0.0.1:3000"]`. Browser hitting the dashboard from `http://172.16.102.11:3000` sends `Origin: http://172.16.102.11:3000` → CORS reject → dashboard loads but every `/api` call fails silently. Fix: `allow_origins=["*"]` (dev/LAN only — see security note).

Diagnosis recipe (run BEFORE assuming a crash):
```bash
# 1. What is actually listening, and on which interface?
ss -tlnp 2>/dev/null | grep -E ':(9101|9102|9103|9104|9105|8000|3000|3001)'
#   127.0.0.1:9102  = localhost-only, LAN IP fails
#   [::1]:3001       = IPv6 localhost-only, 127.0.0.1 fails
#   0.0.0.0:9102     = all interfaces, GOOD
# 2. Test from the machine LAN IP (what the user's browser does), not localhost
curl -s -o /dev/null -w "%{http_code}\n" --max-time 5 http://172.16.102.11:9102/
#   000 = connection refused (bind issue); 200/404 = reachable
# 3. Test CORS header from the LAN origin
curl -s -i -H "Origin: http://172.16.102.11:3000" http://172.16.102.11:8000/ | grep -i access-control
#   must echo back the Origin (or "*")
```
Port-mismatch gotcha: if the systemd unit hardcodes `--port 3001` but `vite.config.ts` says `port: 3000` with `strictPort: true`, Vite refuses 3000 and falls back to 3001 (or exits). Make unit + config port AGREE — prefer editing the unit to match config (config is the app's source of truth).

Security note: opening bind to `0.0.0.0` + CORS `*` exposes wrapper ports (9101–9105, 8000, 3000) to the whole network. If the machine is internet-reachable (CloudflareWARP / public IP), recommend a reverse proxy (nginx) + basic-auth/TLS, or firewall-limit to the Bos IP. Don't leave `0.0.0.0`+`*` open on a public host without auth. Full transcript in `references/reachability-bind-host-2026-07-28.md`.

## Pre-auth / open LAN access mode (user preference: "tanpa auth / pre-auth")
Bos wants ALL wrappers + dashboards reachable from the LAN IP **without** sending a bearer token (pre-auth / open mode). This is a recurring preference — apply it whenever Bos says "akses tanpa auth", "pre-auth saja", or "buka untuk user".

**CRITICAL GOTCHA — do NOT blank `BEARER_TOKEN`.** `nvidia-python/src/main.py::validate_config()` does `if not os.environ.get('BEARER_TOKEN'): sys.exit(1)` → blanking it makes the wrapper crash-loop (`activating (auto-restart)`, port 9101 curl `000`). Keep `BEARER_TOKEN=wrapper-local-key` and disable auth a different way.

**Correct procedure:**
1. Keep `BEARER_TOKEN=wrapper-local-key` in each `.env`. ADD a new line `DISABLE_AUTH=1`.
2. Patch each wrapper's auth gate to respect `DISABLE_AUTH`. Each wrapper has a DIFFERENT gate location/form (see `references/pre-auth-open-access.md` for exact diffs):
   - **nvidia-python**: `auth_middleware` → `if BEARER_TOKEN and not is_public:` → `if BEARER_TOKEN and not is_public and not os.environ.get('DISABLE_AUTH'):`
   - **nous**: `_auth_check` → after `if not BEARER_TOKEN: return` add `if os.environ.get('DISABLE_AUTH'): return`
   - **opencode / vercel / blackbox**: `_auth_check` → after `if request.method == 'OPTIONS': return` add `if os.environ.get('DISABLE_AUTH'): return  # pre-auth mode`
3. **model-registry (9200)** has its OWN `.env` at `/root/wrapper/model-registry/.env` with `MODEL_REGISTRY_HOST=127.0.0.1` that OVERRIDES the default in `service.py`. To open it: set `MODEL_REGISTRY_HOST=0.0.0.0` there (not just patching service.py — the .env wins).
4. `daemon-reload` is NOT needed for `.env` changes (services re-read via `EnvironmentFile` on restart) — just `systemctl --user restart <unit>`.
5. Verify: `curl -X POST http://<LAN-IP>:9102/v1/chat/completions -d '{"model":"tencent/hy3:free","messages":[{"role":"user","content":"hi"}]}'` → must return a chat completion (NOT 401). A `400`/`404` from upstream (e.g. NVIDIA "Function not found for account") is EXPECTED and means auth was bypassed successfully — only `401` means auth still on.

**Security note:** open + `0.0.0.0` exposes all LLM wrappers to the network. If internet-reachable (CloudflareWARP / public IP), recommend nginx + basic-auth/TLS or firewall-limit to Bos IP. Don't leave pre-auth open on a public host.

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
- **"Site can't be reached" with `active (running)` service = bind-host issue, NOT a crash.** Check the interface column in `ss -tlnp` FIRST: `127.0.0.1:*` = localhost-only (LAN IP fails), `[::1]:*` = IPv6-localhost-only (`127.0.0.1` fails). Fix the `--host`/Vite `host` flag, not the app code. A LAN-IP `curl` returning `000` while `localhost` returns `200` is the smoking gun.
- OpenCode model list is static — re-sync `opencode.jsonc` when models change in a wrapper.
- **Pre-auth open mode:** never blank `BEARER_TOKEN` (nvidia-python `validate_config()` will `sys.exit(1)` and crash-loop). Keep the token, add `DISABLE_AUTH=1` to each `.env`, and patch each wrapper's auth gate to honor it (gate locations differ per wrapper — see `references/pre-auth-open-access.md`). `model-registry` `.env` (`MODEL_REGISTRY_HOST`) overrides `service.py` defaults, so edit the `.env`, not just the code.
- **Upstream race on push**: if `git push` is rejected with "fetch first", someone pushed to `github/main` after your pull. NEVER force-push. `git fetch` → inspect the new commit (it may reverse your fixes or re-break imports) → `git reset --hard` to your pre-commit base → `git pull --rebase` → re-apply your verified fixes → retest all 6 → push.
- After ANY wrapper change, verify ALL 6 ports (9101–9105) return 200, not just the one you touched — a restructure commit can break siblings. Also hit `/v1/models` with an `x-request-id` header to exercise the latency middleware (catches the `[wrapper]` NameError that `/health` alone may miss).

## Support files
- `references/pre-auth-open-access.md` — exact `DISABLE_AUTH` diffs for all 5 wrappers + model-registry `.env`, and the "don't blank BEARER_TOKEN" crash gotcha.
- `references/recurring-bugs.md` — exact bug transcripts + diffs.
- `references/reachability-bind-host-2026-07-28.md` — "site can't be reached" root cause (127.0.0.1 / [::1] / CORS) + ss/curl diagnosis transcript + fix diffs for all 5 wrapper units + Vite + dashboard backend.
- `references/opencode-provider-setup.md` — jsonc template + install + verify.
- `references/restructure-2026-07-28.md` — restructure pull, 4 bugs found + fixes, upstream-race recovery, verification recipe.
- `references/nous-modular-split-broken-2026-07-28.md` — upstream `69af4aa` split nous into broken `key_pool.py`; symptom, fix (revert to inline), intentional divergence.
- `scripts/verify_wrappers.py` — probe all wrapper ports, print health table.
- `scripts/smoke_hallo_all.py` — **end-to-end chat smoke**: sends "hallo" to all 5 wrappers, picks first `:free` model, reports non-empty reply or error class (401/0-models/exhausted/No-capacity). Usage: `python3 scripts/smoke_hallo_all.py [--token wrapper-local-key] [--prompt "hallo"] [--ports 9101,9102]`. Runs in ONE command — use this (not manual curl loops) to verify chat works after a pull/config change.
- `scripts/test_all_llm_models.py` — **per-wrapper model sweep**: fetches `/v1/models`, filters to text-to-text LLMs (drops embed/vision/image/audio/safety), sends "hallo" to EACH, writes JSON report {total_tested, ok, failed, results}. Usage: `python3 scripts/test_all_llm_models.py --base http://127.0.0.1:9101 [--token wrapper-local-key] [--out report.json]`. Use this when Bos asks "test all models / list which ones reply" — proves wrapper works even if most models 404 (account not deployed). From 2026-07-28: 65 tested → 18 OK, 47 failed (34 not-deployed, 9 timeout, 3 not-found).
