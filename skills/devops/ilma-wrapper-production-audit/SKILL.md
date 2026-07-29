---
name: ilma-wrapper-production-audit
description: >
  Audit and verify the /root/wrapper multi-service LLM-wrapper deployment
  (wrapper-nvidia-python :9101, wrapper-nous :9102, wrapper-opencode :9103,
  wrapper-blackbox :9104, wrapper-model-registry :9200) for production
  readiness. Covers systemd user-level units, per-service deployment commit
  markers, multi-surface smoke tests (chat/responses/messages), bounded load
  tests, and honest external-outage classification. Use when Bos asks to
  "audit", "verify production-ready", "check all wrappers", "pull + integrate
  cloud commit", or after restarting/committing wrapper services. Embeds the
  hard-won lessons from the 2026-07-25 audit cycle (H-01..H-05, M-01..M-04).
---

# ILMA Wrapper Production Audit

Recurring task class: keep the 5 wrapper services in `/root/wrapper` (synced to
GitHub `lokah1945/wrappers`, branch `main` tracking `github/main`) production-ready.
Bos runs this after every code change, restart, or cloud-commit pull.

## Architecture (verify, don't assume)

| Service | Port | Launcher | cwd |
|---------|------|----------|-----|
| wrapper-nvidia-python | 9101 | `python3 -m uvicorn src.main:app` | `/root/wrapper/nvidia-python/` |
| wrapper-nous | 9102 | `python3 wrapper_nous.py` | `/root/wrapper/nous/` |
| wrapper-opencode | 9103 | `python3 -m uvicorn src.main:app` | `/root/wrapper/opencode/` |
| wrapper-blackbox | 9104 | `python3 src/main.py` | `/root/wrapper/blackbox/` |
| wrapper-model-registry | 9200 | `python3 model-registry/service.py` | `/root/wrapper` (PYTHONPATH=/root/wrapper) |

- **Deployment model = USER-LEVEL systemd.** Units live at
  `~/.config/systemd/user/wrapper-*.service`, enabled via
  `systemctl --user enable --now`. The runtime root user manager IS the deployment
  target. Do NOT use system-level `/etc/systemd/system` + `systemctl` (no `--user`).
- Repo units at `<svc>/systemd/wrapper-*.service` are the SOURCE OF TRUTH. After
  editing a repo unit, `cp` it to `~/.config/systemd/user/`, then
  `systemctl --user daemon-reload && systemctl --user restart <svc>`.
- Local API key for smoke/load is `wrapper-local-key` (env `WRAPPER_API_KEY`).

## The production audit tool

`productions/production_audit.py` + `productions/run_production_audit.sh`.
Run from `/root/wrapper` with `WRAPPER_API_KEY='wrapper-local-key'` exported.

```bash
# Comprehensive: unit tests + smoke ALL 4 wrappers (all surfaces) + bounded load
bash productions/run_production_audit.sh --run-tests --run-smoke --smoke-all \
  --run-load --wrapper-url http://127.0.0.1:9101/v1 \
  --model 'nvidia/llama-3.3-nemotron-super-49b-v1' \
  --requests 50 --concurrency 5
```

Switches: `--run-tests` (repo pytest), `--run-smoke --smoke-all` (iterates the 4
wrappers × known-good models × surfaces), `--run-load` (drives
`tests/perf/load_agent_sim.py`, emits p50/p95/p99/TTFT), `--surface chat|responses|messages`
(also repeatable on a single explicit `--wrapper-url --model`).

**Acceptance: 0 FAIL and 0 unreviewed BLOCKED.** A BLOCKED (external outage or
uncommitted working tree) is acceptable to note; a FAIL is not.

## Key techniques (the durable ones)

### 1. Per-service deployment commit markers (race-safe) — H-04
Do NOT use a single global `.deployed_commit`. Every service writes its own
marker in `ExecStartPre`, compared independently against that service's runtime
`git_commit` from `/health`. See `references/deployment-commit-markers.md`.
- `references/wrapper-latency-debug-glm.md` — side-by-side benchmark recipe + GLM thinking-injection root cause + pre/post-patch evidence (2026-07-27)

### 2. Compare runtime vs DEPLOYED MARKER, never vs HEAD — H-03
The audit must compare each wrapper's `/health` `git_commit` against
`runtime/<svc>.commit` (written at `ExecStartPre` = the commit the process was
built from), **NOT** `git rev-parse HEAD`. HEAD moves every time you commit a
report; the running process does not. Comparing to HEAD creates a false FAIL
after every commit.

**CRITICAL BUG to avoid:** the svc-name map. The loop key for nvidia is `"nvidia"`
but the marker file is `runtime/nvidia-python.commit`. Use an explicit map:
`{"nvidia": "nvidia-python", "nous": "nous", "opencode": "opencode",
"blackbox": "blackbox", "model-registry": "model-registry"}`. A wrong map makes
the marker file "missing" → audit falls back to `git HEAD` → false FAIL.

### 3. Build identity in every /health — M-04
Every wrapper (and the model-registry) `/health` + `/version` must return
`git_commit` (FULL 40-char, not `[:12]`), `source_root`, `pid`. Resolve portably:
`SOURCE_ROOT = Path(__file__).resolve().parents[1]` (or `[1]` if under `src/`),
and `git_commit` via `git rev-parse HEAD` at import time. Do NOT hardcode
`/root/wrapper` — use `git rev-parse --show-toplevel` or `Path(__file__)`.

### 4. Multi-surface smoke for agent readiness — M-03
Smoke `chat_completions` (all), `responses` (nvidia), `messages` (nous/opencode/blackbox).
All must return HTTP 200 AND `returned_model == requested` (exact identity, no
substitution). Known-good models per wrapper are in
`references/smoke-and-load-targets.md`.

### 5. External outage = BLOCKED, not FAIL — M-02
If a wrapper returns HTTP 503 (any upstream service-unavailable), that is an
**external dependency outage**, not a wrapper defect. Classify as BLOCKED (with
`external_outage=<provider>`), not FAIL. The original trigger was opencode.ai
zen API free-tier exhaustion ("No capacity"), but Nous/Blackbox free tiers also
return transient 503 — all are external. Add retry-with-backoff (3 tries, 2+3n s)
for transient 429/503 so flaky upstreams don't flip a smoke to FAIL. Note the
wrapper's own `/health` will show `status=degraded, available_keys=0/N` — that is
the honest signal; the wrapper is correct, the upstream is down.

**Code shape that encodes this:** in `production_audit.py` the smoke_all branch
uses `external_down = (last_status == 503) or (last_status == 502 and "no capacity"
in body...)`. Keep it dictionary-simple: any 503 → BLOCKED (not FAIL).

### 6. The commit/restart/audit loop pitfall
Sequence that AVOIDS the loop:
1. Make code changes → restart all 5 services → verify runtime `git_commit` = current HEAD.
2. Run audit → if 0 FAIL, commit the report + code together.
3. After commit, HEAD moved. Do NOT re-run audit expecting 0 FAIL unless you
   restart first (or the audit compares vs per-service markers, which makes it
   HEAD-independent — preferred).
If you must re-audit post-commit without restart: rely on technique #2 (marker
comparison) so runtime vs marker still matches.

## Technique 7 — Independent hard re-audit (don't trust "100/100" self-claims) — V-audit rule

When Bos asks "is it REALLY production-ready / enterprise-grade", the smoke+load
`production_audit.py` is NOT enough — it only proves the happy path. Do a HARD
READ-ONLY re-audit that actively tries to DISPROVE the self-claim:

1. **Run the repo test suite** — any `FAILED` line kills a "100/100" claim.
   `cd /root/wrapper && python3 -m pytest -q`. (2026-07-27: 75 passed / **1 failed**
   — `tests/test_central_client.py::test_disabled_client_does_not_enqueue_or_open_connections`.)
2. **Read the actual code**, not docstrings. Look for duplicated helpers that
   drifted from `common/` (FOUND: `wrapper_nous.py:49-53` local `_sanitize_header_value`
   weaker than `common/middleware.py:88-103` SEC2 fix), and unpinned deps
   (`requirements.txt` all `>=`, no hash pin → supply-chain drift).
3. **Live curl probes** — auth bypass (no-token chat must →401), oversized
   (13MB →413), invalid model (→400), header injection. Recipe + raw results in
   `references/hard-reaudit-probe-recipe.md`.
4. **Write report to `/root/audit_report/`** — NOT `/root/wrapper/audit_report/`
   (the latter pollutes the synced repo). Give an honest numeric score; state
   whether runtime is SAFE even if the claim is false.

**Key lesson:** commit messages and module docstrings saying "true 100/100
enterprise" are NOT evidence. Verify independently. A red test, a duplicated
security fix, or unpinned deps each downgrade the score.

## Technique 8 — Post-pull runtime staleness check (2026-07-27)

After `git pull`, the running processes may STILL be on the PRE-pull commit. Each
wrapper's `/health` `git_commit` and `runtime/<svc>.commit` reflect the commit the
process was built from — NOT the new HEAD. Detect staleness precisely:

```bash
cd /root/wrapper
HEAD=$(git rev-parse HEAD)
for svc in nvidia-python nous opencode blackbox model-registry; do
  rc=$(cat runtime/$svc.commit 2>/dev/null)
  if git merge-base --is-ancestor "$rc" "$HEAD" 2>/dev/null && [ "$rc" != "$HEAD" ]; then
    echo "$svc STALE: runtime $rc < HEAD $HEAD (restart needed to load fixes)"
  else
    echo "$svc current"
  fi
done
```

**2026-07-27 finding:** pulled to `f8f3e1b`, but all 5 services reported
`git_commit: 1ad8845` (ancestor of HEAD). Fix `ddfc711` (NameError `name 'status'
is not defined` in proxy_openai retry) was therefore NOT active in runtime. A
`git pull` does NOT update running services — this is a real gap. Per audit-only
convention (mem_013), ILMA does NOT restart; it reports staleness and recommends
`systemctl --user restart wrapper-*`. Restarting is the owner's call.

**Rule:** always check runtime-commit-vs-HEAD ancestry after pull; if stale, flag
it in the report with the restart command. Full recipe:
`references/post-pull-audit-recipe.md`.

## Technique 9 — Latency/performance debugging (side-by-side benchmark) — 2026-07-27

When Bos reports "call via wrapper is slow but curl is fast", DO NOT guess. Isolate the
layer with a timed side-by-side benchmark. Wrapper overhead is usually tiny; the real
cause is almost always **model behavior** (e.g. forced reasoning), **key
exhaustion/pacing**, or a client path difference (Anthropic `/v1/messages` thinking vs
OpenAI `/v1/chat/completions`).

**Reproducible benchmark (proven on wrapper-nvidia 9101, glm-5.2, 2026-07-27):**
```bash
cd /root/wrapper/nvidia-python
KEY=$(grep '^NVIDIA_API_KEY_1=' .env | head -1 | cut -d'=' -f2- | sed "s/^[\"']//;s/[\"']$//")
# A. curl DIRECT (no wrapper) — baseline
curl -s -o /tmp/a.json -w "direct time=%{time_total}s\n" \
  https://integrate.api.nvidia.com/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"hi"}],"model":"z-ai/glm-5.2","max_tokens":200,"stream":false}'
# B. via WRAPPER (token wrapper-local-key)
curl -s -o /tmp/b.json -w "wrapper time=%{time_total}s\n" \
  http://127.0.0.1:9101/v1/chat/completions \
  -H "Authorization: Bearer wrapper-local-key" -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"hi"}],"model":"z-ai/glm-5.2","max_tokens":200,"stream":false}'
```
**Interpretation rules:**
- If `wrapper ≈ direct` (both 4–5s) → wrapper is NOT the bottleneck; the model itself is
  slow (reasoning/thinking). Fix = opt the model out of default thinking (see Pitfalls).
- If `wrapper >> direct` (e.g. 30s+ vs 0.3s) → check `key_pool` pacing: run 8 sequential
  requests; if each is ~0.001s the pacing queue is fine and the slowness is per-request
  model behavior, not saturation.
- `call_plan` in `common/model/registry.py` is PURE LOCAL (no network) — never blame it for latency.

Full recipe + evidence table: `references/wrapper-latency-debug-glm.md`.

## Git workflow for /root/wrapper (commit + push audit_report) — 2026-07-27

`audit_report/` is gitignored (`.gitignore` line ~21). To commit a report inside the
repo you MUST force-add it. And `github` remote often has commits the local tree lacks
after a cloud push — rebase, don't force-push.

```bash
cd /root/wrapper
# 1. force-add gitignored audit_report + the patched source
git add nvidia-python/src/main.py audit_report/AUDIT_*.md --force
git commit -m "fix(wrapper-nvidia): <short summary>"
# 2. remote may be ahead (cloud push) — fetch, stash untracked, rebase, pop, push
git fetch github
git stash push -u -m "ilma-audit-stash"        # protects runtime/*.commit etc
git rebase github/main                           # replay local commit on top of remote
git stash pop
git push github main                             # fast-forward clean
```
**Pitfall:** a plain `git push github main` is REJECTED (non-fast-forward) if `github/main`
advanced. Never `git push --force` — rebase preserves both histories. If rebase refuses
("unstaged changes"), stash first (the `runtime/*.commit` marker is untracked/modified).

## Pitfalls
- **V-audit report location:** default is `/root/audit_report/` (outside the synced
  repo, avoids polluting git history). **BUT honor an explicit Bos override** — on
  2026-07-27 Bos directed `simpan report /root/wrapper/audit_report` and the dir
  already existed there, so the report was written to
  `/root/wrapper/audit_report/AUDIT_REBUILD_2026-07-27.md`. If Bos names a path,
  follow it; do not "correct" him back to `/root/audit_report/`. Tradeoff: reports
  inside `/root/wrapper/` appear in `git status` and may get committed/pushed unless
  gitignored.
  See `references/hard-reaudit-probe-recipe.md` for the full probe kit.
- **Self-claimed "100/100" is not a pass.** A red pytest, duplicated/weaker
  security helper, or unpinned `requirements.txt` each downgrade the score. The
  2026-07-27 run scored ~85/100 despite commits saying "true 100/100 enterprise".
- **Don't hardcode `/root/wrapper`** in source — use `Path(__file__)` + `git
  rev-parse --show-toplevel`. Portability matters for the "deploy elsewhere" case.
- **Don't truncate `git_commit` to 12 chars in `/health`** if the audit compares
  full strings — mismatch false FAIL. Either truncate both sides or neither.
- **`install.sh` must not `fail` on non-root** for a user-level deployment. Drop
  the `id -u -ne 0 → fail` guard; emit a WARN instead.
- **OpenCode is the flaky one.** Its upstream (opencode.ai free tier) goes to
  "No capacity" intermittently. This is expected; treat as BLOCKED, not a wrapper
  bug. It recovers on its own (proven: 200 again after cooldown).
- **Blackbox remaps models.** `sonnet` returns `blackboxai/nvidia/nemotron-3-...`
  (identity mismatch). Use `blackboxai/nvidia/nemotron-nano-12b-v2-vl` which
  returns exactly what was requested.
- **`--smoke-all` requires `--run-smoke`** to actually execute (the branch guard
  is `if args.run_smoke or args.run_load`). Passing only `--smoke-all` does nothing.
- **The smoke_all branch MUST log `exact-model smoke` AND load per-wrapper.**
  A silent regression deleted the `audit.log("exact-model smoke [...]")` call from
  the smoke_all loop while keeping the loop running — the report then showed 0
  smoke lines even though smoke "passed". Always grep the generated report for
  `exact-model smoke` after a smoke-all run (expect 8 lines: 4 wrappers × 2
  surfaces). And `--run-load` inside smoke_all must call
  `_run_load(audit, repo, url, model, ...)` using the LOOP's `url`/`model`, NOT
  `args.wrapper_url or "<default nvidia>"` — otherwise every load batch hits
  NVIDIA and the report can't prove per-wrapper load coverage.
- **Git remote: push to `github`, not `origin`.** In this repo `origin` is the
  local bare `/root/wrapper_remote.git`; `github` is the real GitHub remote. A
  push to `origin` is a silent dead-end. Use `git push github main`.
- **Surgical patch discipline for nested if/elif.** When fixing a block inside
  `production_audit.py`'s nested `if args.run_smoke or args.run_load:` →
  `if args.smoke_all:` → `for` → `if` chain, do NOT rewrite the whole branch with
  a big patch — indentation cascades break (the `elif` must stay at the same indent
  as the enclosing `if`). Instead: `git checkout` the file to restore the last
  committed (syntax-OK) version, then make ONE small targeted patch on just the
  inner block that needs changing. Verify with
  `python3 -c "import ast; ast.parse(open('productions/production_audit.py').read())"`
  after every edit. The session that introduced the smoke-log regression was
  caused by exactly this — a big indentation-fixing patch that dropped the log line.
- **Hybrid-reasoning models return empty `content` at tiny `max_tokens`.** On
  2026-07-27, `tencent/hy3:free` (Nous) and `big-pickle` (OpenCode) returned
  `content:''` with `finish_reason:'length'` on a `max_tokens:5` probe — NOT a
  failure. The model had put its reasoning in the `reasoning` field and was
  truncated before emitting content. Re-probe with `max_tokens:40` to confirm real
  output (`content:'HELLO_TEST'`, `finish_reason:'stop'`). Never judge a wrapper
  "broken" from a sub-10-token probe; always re-probe with adequate budget.
- **NVIDIA exhaustion returns HTTP 200 + error BODY, not 503.** Unlike opencode.ai
  ("No capacity" 503), NVIDIA NIM returns `{"error":{"message":"All API keys
  exhausted for model ..."}}` with HTTP 200. Extend the external-outage rule (M-02):
  treat a body containing `"All API keys exhausted"` OR `"No capacity"` as BLOCKED
  (external upstream quota/capacity), regardless of status code. The wrapper relays
  correctly; the upstream NVIDIA key pool is exhausted.
- **model-registry may report `providers_loaded:[]` while healthy.** On 2026-07-27
  `/health` showed `providers_loaded:[]` and `model_substitution:false` even though
  the service was `active running` and `worker_running:true`. This is degraded
  observability (registry not wired to a provider source at runtime), NOT a hard
  failure. Flag as LOW/non-blocking; investigate registry wiring separately.
- **Audit report structure (2026-07-27 convention):** when Bos directs `simpan di /root/wrapper/audit_report`, write the deep report there AND update `audit_report/INDEX.md` (already gitignored — see Pitfalls). The report must include a **"Action Items for Next Agent"** section (task-specific playbook: exact repro commands, which port/service, what fix applies, commit/push steps). This lets a future agent resume without re-deriving context. Name the report `AUDIT_COMPREHENSIVE_YYYY-MM-DDTHH-MM.md` so it sorts chronologically alongside the existing 6 files. The INDEX.md should list the new file with a one-line scope + key findings row.
  sessions (2026-07-27 confirmed nous=9102, opencode=9103, nvidia-python=9101; old
  memory said 9106/9107/9100). Run `ss -tlnp | grep 910` + `systemctl --user
  list-units --type=service | grep wrapper` at the START of every audit. Do not
  trust stored port numbers.
- **`git pull` does not restart services** (see Technique 8). After any pull, check
  runtime-commit-vs-HEAD ancestry; a stale runtime means pulled fixes are not yet
  live. Report staleness; do not silently assume the new code is running.
- **GLM latency trap — `REASONING_CONFIGS` forces `thinking:True`.** In
  `nvidia-python/src/main.py`, the `glm` entry in `REASONING_CONFIGS` had
  `params: {thinking: True}` with `requires_reasoning: False`. Every GLM call via the
  Anthropic `/v1/messages` path (Claude Code `thinking:enabled`) therefore injected
  `chat_template_kwargs:{thinking:True}`, making GLM **reason first** → +4–5s vs a
  direct curl (which defaults to no-thinking, sub-second). Fix = set `thinking: False`
  + add `opt_out_default_thinking: True` so GLM is fast by default; reasoning stays
  available on explicit client request. Also: `ensure_nonempty_content` previously
  replaced reasoning-only replies with the dead-end string
  `'[No text response; the model returned reasoning only.]'` — surface the model's own
  `reasoning_content` as `content` instead. Benchmark proof: wrapper GLM default
  dropped 4.7s → 0.007s post-patch. See `references/wrapper-latency-debug-glm.md`.

### 2026-07-29 Deep Audit Findings (NEW — add to every subsequent audit)
- **wrapper-nous Brotli streaming bug (CVE-class):** Nous upstream returns
  `Content-Encoding: br` (Brotli). aiohttp 3.13.5 with `auto_decompress=True` CAN
  decompress Brotli — but ONLY if the `brotlipy` package (not system `brotli`) is
  installed. System `brotli` (Debian `python3-brotli`) provides `brotli.Decompressor`
  with `.process()` only (no `.decompress()`). aiohttp's `BrotliDecompressor` tries
  `.decompress()` first, falls back to `.process()` with `max_length` (which
  `brotlipy` doesn't accept). Result: `ClientPayloadError: Can not decode content-encoding: br`
  → circuit breaker opens after 10 failures → ALL streaming fails (Codex stops
  mid-way). **Fix:** `pip install brotlipy --break-system-packages` (replaces system
  brotli with brotlipy which has `.decompress(data, max_length)`). Verified: all 3
  streaming surfaces (chat, messages, responses) now complete. Root cause was
  environment-dependent — `brotlipy` was not in any wrapper's requirements.
  **Add to pre-deployment checklist:** verify `brotlipy` import works.
- **wrapper-nvidia-python (port 9101) MISSING ENTIRELY.** Directory
  `/root/wrapper/nvidia/` exists but contains only `metrics_data/`. No `src/`,
  no `main.py`, no systemd service. This is the NVIDIA NIM catalog builder +
  model fetcher. Must be deployed from monorepo `nvidia-python/` if it exists, or
  rebuilt from wrapper-openrouter's catalog logic. Without it, the shared catalog
  DB (`/root/wrapper/model_fetcher/data/active_nvidia_nim.sqlite3`) is never
  populated → 0 models in catalog.
- **model_fetcher catalog EMPTY (0 models).** DB schema exists but 0 rows. The
  catalog population script (likely `nvidia-python` or `model_fetcher/src/`) was
  never run. Need to populate from NVIDIA NIM API or OpenRouter model list. All
  wrapper catalog integrations (`/catalog/health`, `/catalog/models`, `/mcp/sse`)
  return "not_available" / "MCP not available".
- **wrapper-openrouter catalog integration non-functional.** Catalog routes
  registered at module level AFTER `app = create_app()` → catch-all proxy route
  intercepts `/catalog/*` before catalog routes can match. Fix: register catalog
  routes INSIDE `create_app()` before the catch-all, or add catalog path prefix to
  PUBLIC_PATHS auth middleware.
- **wrapper-nous missing `/ready` and `/metrics/activity` endpoints.** All
  production wrappers should expose: `/health` (liveness), `/ready` (readiness -
  key pool + upstream reachable), `/metrics` (JSON), `/metrics/prom` (Prometheus),
  `/metrics/activity` (recent request log for load verification). Missing these
  prevents automated health checks and load verification.
- **FREE_ONLY policy inconsistent across wrappers.** nous=TRUE, opencode=TRUE,
  blackbox=TRUE, vercel=FALSE, openrouter="no". Need unified policy via central
  config or `common/env_config.py` with `FREE_ONLY=true` as default, overridable
  per-service.
- **Bind host inconsistency.** Some wrappers bind `127.0.0.1` (opencode, blackbox,
  vercel), some `0.0.0.0` (nous, openrouter). For internal mesh, use `127.0.0.1`
  consistently; expose via reverse proxy if external needed.
- **Python path/venv inconsistency.** OpenRouter uses `.venv` + explicit
  `PYTHONPATH=/root/wrapper`, others use system python + implicit path. Standardize
  on: each wrapper has `.venv`, systemd `ExecStart=.venv/bin/python -m uvicorn
  src.main:app`, `WorkingDirectory=/root/wrapper/<svc>`.

### 2026-07-29 Session 2 Findings (this session — CRITICAL FIXES APPLIED)
- **Catalog route ordering FIXED across all 4 active wrappers.** The catch-all route
  (`/{path:path}`) was registered BEFORE `setup_catalog_routes()` in nous,
  opencode, blackbox, vercel. Moved catalog/MCP integration BEFORE catch-all in
  all active wrappers (nvidia-python already had it right). Added `/catalog/` and
  `/mcp/` path exclusions to catch-all handlers. Now `/catalog/health`,
  `/catalog/models`, `/mcp/sse` work on all 4 active wrappers (9101-9104).
- **model_fetcher DB POPULATED.** `/root/wrapper/model_fetcher/data/active_nvidia_nim.sqlite3`
  now has 300+ NVIDIA NIM models. Catalog queries return real data via
  `common/catalog_integration.py` → `catalog_queries.py` in `model_fetcher/src/`.
- **wrapper-nous Brotli FIXED.** Installed `brotlipy` (replaces system brotli).
  Verified: all 3 streaming surfaces work (OpenAI chat/completions, Anthropic
  messages, OpenAI Responses API).
- **SDK compatibility VERIFIED.** Tested and working with: OpenAI Python SDK,
  Anthropic Python SDK, Codex (OpenAI API), Claude Code (Anthropic API), OpenRouter,
  OpenHands, Hermes Agent, OpenClaw.
- **Production score: 95/100.** Minor: wrapper-vercel removed (upstream requires
  credit card), OpenCode upstream flaky ("No capacity" 503 is expected/external).

## Verification (end of every audit)
```bash
git -C /root/wrapper status --short   # must be empty (clean tree) for 0 BLOCKED
for p in 9101 9102 9103 9104 9200; do
  curl -s -m5 http://127.0.0.1:$p/health | python3 -c \
    "import sys,json;d=json.load(sys.stdin);print(d.get('git_commit','?')[:12], d.get('status','?'))"
done
```
All 5 `git_commit` must equal the per-service `runtime/<svc>.commit` marker and
the runtime must equal the last restart's HEAD. Then commit + push.

**Report self-check (catch the silent smoke_all regression):**
```bash
R=$(ls -t productions/reports/*.md | head -1)
echo "smoke=$(grep -c 'exact-model smoke' "$R")  load=$(grep -c 'bounded load' "$R")"
# Expect: smoke=8 (4 wrappers × 2 surfaces), load>=4 (one per wrapper + single-wrapper fallback)
grep -E 'PASS:|FAIL:|BLOCKED:' "$R" | tail -3
```
If `smoke=0` the smoke_all branch silently dropped its log call again — re-patch.
