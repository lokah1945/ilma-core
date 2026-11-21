---
name: ilma-wrapper-sdk-audit
description: Recurring production-readiness SDK-compatibility audit + service-ops of the /root/wrapper LLM-proxy ecosystem (nvidia-python:9101 / nous:9102 / opencode:9103 / blackbox:9104 / model-registry:9200). Use when Bos asks to "audit wrapper", "production score 100/100", "OpenAI/Anthropic SDK compatible", "pull github", "restart all wrapper", "update config codex", or any Vn audit/planning cycle. Covers the read-only audit + separate-agent-fix loop, independent re-verification (never trust execution reports), versioned Vn report discipline in /root/audit_report/, systemd--user service install/restart, codex config port-sync, and a deep curl-based E2E SDK-compat matrix.
category: ilma
---

# ILMA Wrapper SDK-Compat Audit

Class-level skill for auditing the `/root/wrapper/` LLM proxy ecosystem for
**OpenAI / Anthropic SDK compatibility** and **production-readiness**, scored
0–100, iterated toward "mutlak 100/100" (spec-strict, zero potential bug).

## Ecosystem under audit
**CANONICAL PORTS (mem_014 override, 2026-07-24 — sequential, NO gaps):**
| Wrapper | Port | Notes |
|---------|:----:|-------|
| nvidia-python (`nvidia-python/`) | **9101** | Most modular (`src/` pkg); alias via `DYNAMIC_ALIAS_TARGET` |
| nous (`nous/`) | **9102** | Monolith `wrapper_nous.py`; `FREE_ONLY=yes` blocks non-free models |
| opencode (`opencode/`) | **9103** | `src/` pkg; alias `sonnet→big-pickle` |
| blackbox (`blackbox/`) | **9104** | `src/` pkg; BLACKBOX AI free proxy. **Often NOT installed by default — see Service Ops below.** |
| model-registry (`model-registry/`) | **9200** | Control plane (not a router); `GET /health` 200, writes fail-closed without `MODEL_REGISTRY_ADMIN_TOKEN`. |

⚠️ **PORT DRIFT IS A RECURRING BUG.** Old docs/configs say nous=9106, opencode=9107, nvidia=9100/9910. Those are STALE. Real live ports above. Codex configs (`~/.codex/config.toml` + `~/.codex-homes/*/config.toml`) and any `.service` files in the repo must be synced to these or clients silently fail to connect.

All speak OpenAI `/v1/chat/completions` + `/v1/responses` + Anthropic
`/v1/messages`, behind a `BEARER_TOKEN` (also accepts `x-api-key` for Anthropic).

## THE LOOP (Vn cycle) — DO NOT DEVIATE
Bos runs this as a recurring session. Two roles are SEPARATE:
1. **ILMA (audit session, HARD READ-ONLY on `/root/wrapper/*`)** writes:
   - `AUDIT_Vn.md` — findings from independent re-verification
   - `Vn_PLAN.md` — precise fix instructions for the patch agent
2. **A separate patch agent** reads `Vn_PLAN.md`, edits source, writes
   `Vn_EXECUTION_REPORT.md` (its claims MUST be re-verified, never trusted).
3. **Directory hygiene:** between versions, DELETE old `AUDIT_Vn.md` /
   `Vn_PLAN.md`; **KEEP** all `*_EXECUTION_REPORT.md` as the reference chain.
   Canonical dir is **`/root/audit_report/`** — NEVER `/root/wrapper/audit_report/`.

## GOLDEN RULES (learned the hard way)
- **Never trust an execution report's score.** Every Vn_EXECUTION_REPORT
  overclaimed: 93→89, then "100/100" while nvidia/nous were at ~70, then
  "mutlak 100/100" with 6 residual gaps. ALWAYS re-run the E2E matrix yourself.
- **Audit ALL 3 siblings before scoring.** Bos corrected a 1-of-3 audit.
- **After any service restart, WAIT ~8s + poll `/health`** before testing —
  early curl gives false-negative 000/404 (cold alias resolution).

## BOS STYLE DIRECTIVES (apply to EVERY ILMA session, not just audits)
- **Execute first, report short.** Bos: "Execute first + short report. No pre-flight. No runtime/IMOS until SOT stable." Do the work, then give a concise Indonesian summary. Don't narrate the plan before acting.
- **Verify via tool — NEVER assume.** Bos: "JANGAN asumsi model/config/state — verify with tool (grep config.yaml) before claiming anything." Every capability/port/state claim must come from a real command, not memory.
- **One response = one Telegram delivery.** Bos: "1 respon=1x Telegram, NO duplicate." End each turn with a single consolidated message marked `✅ terkirim 1x`. Never re-emit a final body; never loop "as a reminder" follow-ups. (Infra dedup P1–P4 exists, but behavior must be clean too.)
- **Concise Indonesian.** Bos writes concisely; match it. Tables/task-lists over dense prose when structured data is involved.
- **Read-only audit sessions:** ILMA does NOT patch. If you must "continue
  until 100", still emit `Vn_PLAN.md` for the patch agent; do not edit
  `/root/wrapper/*` in an audit session unless Bos explicitly lifts the ban.
- **Timeout traps:** model `sonnet`→nemotron is SLOW (reasoning). Use
  `--max-time 40`+ on chat/anth; never pipe SSE to `head -c` (SIGPIPE kills
  curl → false "000"). Save to a temp file, then `grep`.

## Service Ops (install / restart / codex sync) — NOT read-only
Bos frequently asks to "pull github", "restart all wrapper", "update config codex".
These MUTATE state. Pattern proven 2026-07-25:

### Install a wrapper service from repo (blackbox / model-registry were NOT installed by default)
```bash
SRC=/root/wrapper/<svc>/systemd/wrapper-<svc>.service   # or /root/wrapper/<svc>/wrapper-<svc>.service
DST=/root/.config/systemd/user/wrapper-<svc>.service
cp "$SRC" "$DST"
systemctl --user daemon-reload
systemctl --user enable --now wrapper-<svc>.service
sleep 3
systemctl --user is-active wrapper-<svc>.service   # expect: active
curl -s -m5 -o /dev/null -w "%{http_code}\n" http://127.0.0.1:<port>/health
```
Verify via BOTH `systemctl is-active` AND the port `/health` → 200.

### Codex config port sync (recurring drift source)
Codex reads `~/.codex/config.toml` (default) + `~/.codex-homes/<name>/config.toml`.
Each `[model_providers.<name>]` has `base_url = "http://127.0.0.1:<port>/v1"`.
**Audit all of them** for stale ports (9106/9107/9100) and fix to canonical:
```bash
grep -rniE 'base_url.*910[0-9]' /root/.codex/config.toml /root/.codex-homes/*/config.toml
# expect only: 9101 (nvidia/nvidia-py), 9102 (nous), 9103 (opencode), 9104 (blackbox)
```
Do NOT edit while a `.config.toml.swp` vim-swap is held — check `lsof` first.

### H-01 trap: audit report "service inactive / orphan runtime" is often a STALE false-positive
A separate audit agent reported `wrapper-nous inactive / orphan runtime` while endpoints
returned 200. Reality: services WERE active and systemd-managed. The report was
generated BEFORE the services were (re)started in the live session.
**Always re-verify live before acting on an audit report's service-state claims:**
```bash
# 1. systemd state
systemctl --user is-active wrapper-nous.service
# 2. port -> PID
pid=$(ss -ltnp 2>/dev/null | grep -E ":$port\b" | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2)
# 3. is PID actually systemd-managed? (orphan check)
tr '\n' ' ' < /proc/$pid/cgroup 2>/dev/null | grep -q 'user@' && echo "SYSTEMD-MANAGED" || echo "ORPHAN"
```
If `is-active=active` AND cgroup contains `user@` → NOT orphan, report was stale. Don't kill/restart.

## Production audit RUNNER (repo-internal, 2026-07-25)
Bos now uses the **repo-internal** runner, NOT the legacy `/root/audit_report/` discipline:
- Runner: `bash productions/run_production_audit.sh [flags]` (wrapper around `productions/production_audit.py`)
- Report output: `productions/reports/production-audit-YYYYMMDD-HHMMSS.md`
- Flags: `--run-tests` (isolated pytest + transparency), `--run-smoke` (exact-model call),
  `--wrapper-url http://127.0.0.1:9101/v1`, `--model '<exact-id>'`, `--api-key-env WRAPPER_API_KEY`,
  `--run-load`, `--required-wrapper <name>` (default: all 5), `--require-registry`.
- Smoke example that PASSED this session:
  `bash productions/run_production_audit.sh --run-tests --run-smoke --wrapper-url http://127.0.0.1:9101/v1 --model 'nvidia/llama-3.3-nemotron-super-49b-v1' --api-key-env WRAPPER_API_KEY`
  → exact-model smoke HTTP 200, returned_model == requested (no substitution).
- WRAPPER_API_KEY for open-auth wrappers = `wrapper-local-key` (BEARER_TOKEN unset in running services).
- The legacy `AUDIT_Vn.md` / `/root/audit_report/` loop still applies for the SEPARATE patch-agent discipline, but the *scoring* now comes from this runner.

## H-01 ROOT CAUSE (systemd --user false-positive) — PATCH THE RUNNER
The audit runner initially reported all wrappers "inactive / orphan runtime" while endpoints returned 200.
**Root cause:** `production_audit.py` called `systemctl is-active <unit>` **WITHOUT `--user`**,
so it queried the *system* scope (empty on this box) → false `inactive`. Wrappers run under `systemctl --user`.
**Fix applied 2026-07-25 (commit c0a6535):** change line ~214 to
`audit.command(["systemctl", "--user", "is-active", unit], timeout=15)`.
After fix: 30 PASS / 0 FAIL / 1 BLOCKED (working-tree-uncommitted) → 0 BLOCKED after commit = PRODUCTION READY.
**Lesson:** when auditing systemd-managed services, ALWAYS use `systemctl --user` on this VPS. A bare `systemctl is-active` that says "inactive" for a service whose `/health` returns 200 is almost certainly a scope mismatch, not a real orphan.
See `references/production-audit-runner-2026-07-25.md`.

## H-03 / H-04: source-level hardening (for fix sessions, not audit)
- **Test isolation:** wrap every top-level `load_dotenv()` in wrappers with
  `if os.environ.get("WRAPPER_SKIP_DOTENV","")).lower() != "true": load_dotenv()`.
  Audit runner sets `WRAPPER_SKIP_DOTENV=true` for test subprocesses so production `.env` keys don't leak into isolated tests.
- **Build identity (proves source==runtime):** add to `/health` AND `/version`:
  `git_commit` (from `git rev-parse HEAD` at `/root/wrapper` cwd), `source_root`, `pid`.
  Audit then compares `git HEAD` vs runtime `git_commit`. Reference `references/wrapper-service-operations.md`.

### H-04 PITFALL: runtime git_commit is FROZEN at restart → audit loop FALSE-FAILs
`git_commit` is resolved once at **module import / wrapper startup** (`_resolve_git_commit()` runs in the top-level scope, not per-request). So after you `git commit` new source, the **running process still reports the OLD commit** until you restart it.
**The trap (hit 2026-07-25):** every commit bumps `git HEAD`. The audit compares `git HEAD` (new) vs runtime `git_commit` (old, pre-restart) → 4 FAIL "runtime commit mismatch" on every post-commit audit. Restarting to fix it bumps HEAD again → endless loop.
**Correct sequence (breaks the loop):**
1. Make ALL source changes (H-03/H-04/M-05/etc).
2. `git add -A && git commit && git push` (HEAD = `NEW`).
3. `systemctl --user restart wrapper-nvidia-python wrapper-nous wrapper-opencode wrapper-blackbox wrapper-model-registry` (runtime now reads `NEW`).
4. `sleep 3`; verify `curl /health | git_commit == git rev-parse HEAD` on all 4 ports.
5. Run audit → **0 FAIL**. Then STOP — do NOT commit the report again (that would bump HEAD and re-open the mismatch).
   - If you DO commit the report (for GitHub history), you MUST restart once more before the next audit, OR accept 1 BLOCKED = "working tree: uncommitted changes" (a report artifact, NOT a service defect).
**Lesson:** runtime `git_commit` is a startup snapshot. Audit "runtime commit mismatch" is almost always "you committed but didn't restart", not a real source/runtime divergence. Restart AFTER the final commit, then audit without re-committing.

## Deep E2E SDK-compat matrix (reusable)
The canonical probe is `/tmp/vN_audit.sh` — a curl-based matrix covering:
health, chat/responses/anthropic alias `sonnet`, SSE format
(`data:`/`[DONE]` for chat; `event:` for anthropic; `response.*` for responses),
`tool_use` roundtrip, x-api-key auth, missing `anthropic-version`, bad model
(400 `invalid_request_error`, no cache pollution), `usage` field presence +
real counts, OOB `temperature`, `max_tokens` required, malformed JSON, unknown
path, CORS preflight, burst ×N concurrency. **Copy the latest from
`references/deep_audit_script.md` and bump the version.**

## D-gap taxonomy (residual bugs found across V4–V7)
Reference `references/d_gap_taxonomy.md`. Summary of what "mutlak 100/100"
actually required, iteratively:
- B1 alias resolver caches invalid model → reject, don't cache (nous/opencode)
- B2 chat response missing `usage` → add `prompt_tokens/completion_tokens/total_tokens`
- C3 Anthropic `max_tokens` missing → 400 (was 200)
- D3 invalid `messages[].role` → nvidia hung (000); guard → 400
- D6 Anthropic `system` as number → 400 (spec: string|array)
- D7 Anthropic tool missing `input_schema` → 400
- D8 CORS preflight needs `Access-Control-Allow-Credentials` (localhost-only safe)
- D10 malformed JSON → 400 (nous/opencode returned 500)
- D11 unknown path → 404 (nvidia returned 401)

## Scoring framework
Weighted across: A code correctness, B SDK-compat, C resilience, D observability,
E deployment, F security, G docs. "Mutlak 100" = B=100 AND no residual D-gap AND
all matrix cells green on all 3 wrappers.

## Companion skills
- `ilma-llm-wrapper-builder` — how the wrappers are built (not audited)
- `ilma-codebase-audit` — general ILMA codebase audit (different target)
