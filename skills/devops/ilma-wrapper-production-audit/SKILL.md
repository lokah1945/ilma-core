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
- **Verify topology with `ss`/`systemctl`, never from memory.** Ports drift between
  sessions (2026-07-27 confirmed nous=9102, opencode=9103, nvidia-python=9101; old
  memory said 9106/9107/9100). Run `ss -tlnp | grep 910` + `systemctl --user
  list-units --type=service | grep wrapper` at the START of every audit. Do not
  trust stored port numbers.
- **`git pull` does not restart services** (see Technique 8). After any pull, check
  runtime-commit-vs-HEAD ancestry; a stale runtime means pulled fixes are not yet
  live. Report staleness; do not silently assume the new code is running.

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
