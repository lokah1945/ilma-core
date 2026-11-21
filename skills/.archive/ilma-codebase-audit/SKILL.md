---
name: ilma-codebase-audit
description: End-to-end audit of the ILMA agent codebase — boot verification, per-layer bug hunt, E2E execution, findings table. Use when Bos asks for comprehensive audit, "first bit to last bit" review, production-readiness check, or bug discovery across modules. Covers routing/health, orchestration/boot, capability/judge, browser/runtime, db/mongo/sot, reasoning/learning layers.
category: ilma
---

# ILMA Codebase Audit — Class-Level Skill

Recurring Bos request: "audit komprehensif end-to-end, first bit to last bit, masuk fase produksi."
This skill encodes the verified audit workflow + the bug-class checklist that catches real defects
in the ILMA runtime. It is the standing operationalization of Bos's AUDIT-FIRST discipline (mem_012).

## WHEN TO USE
- Bos: "audit sistem", "audit komprehensif", "first bit to last bit", "production-ready check"
- Before a major release / phase-promotion gate
- After a large refactor (many modules touched)
- Suspicion of silent failures, wiring desync, or capability-claim mismatch

## CRITICAL PITFALL — Single-Subproject Fixation (Bos caught this 2026-07-24)
When a project is a COLLECTION of sibling components (e.g. `/root/wrapper/` holds `nvidia-python/`,
`nous/`, `opencode/`), **enumerate ALL siblings FIRST** — do NOT fixate on the one you know.
In the 2026-07-24 session the auditor deep-audited only `nvidia-python`, reported it as "the project",
and Bos had to interrupt: *"Apakah anda sadar bahwa project wrapper ada 3?"* The later full audit
found nvidia was the LAGARD (Responses 500) while both siblings returned 200 — a finding invisible
to the single-subproject pass.

Rule — before any audit, run a discovery sweep:
```bash
# List ALL sibling components, not just the one you came for
find /root/wrapper -maxdepth 2 -name '*.service' -o -maxdepth 2 -name 'main.py' -o -maxdepth 2 -name 'wrapper_*.py'
systemctl --user list-units --type=service --no-legend | grep -iE '<prefix>'
# Then health-check EVERY running sibling on its port
for p in 9101 9106 9107; do curl -s http://127.0.0.1:$p/health | head -c 100; echo; done
```

## MULTI-COMPONENT / ECOSYSTEM AUDIT (scale-safe)
When the target is a family of components that will KEEP GROWING (wrapper #4, #5, …):

1. **Parity matrix** — test the SAME capability surface on EVERY sibling:
   `/health`, Chat, `/v1/responses`, `/v1/messages` (Anthropic), `/v1/capabilities`, error path, auth.
   Mark ✅/❌ per component. Inconsistencies (e.g. only nvidia has `/v1/capabilities`) are findings.
2. **Per-component score** — score each sibling independently on the 7 weighted categories
   (A code-correctness, B SDK-compat, C resilience, D observability, E deploy, F security, G docs).
   See `references/ecosystem-audit-pattern.md` for weights + a worked example.
3. **Ecosystem score** = weighted average of per-component scores. Report BOTH.
4. **Scalability lens** — flag duplication (same `KeyPool`/`alias`/translator copied N times),
   structural divergence (monolith vs `src/` package), and ops inconsistency (systemd-active vs
   manually-run, log-to-file vs journal-only, bind `0.0.0.0` vs `127.0.0.1`). Recommend a shared
   core lib + a contract/manifest (`wrappers.json` + a linter) BEFORE adding the next component.
5. **Output artifact** — write the report to a dedicated dir (e.g. `/root/audit_report/*.md`) with:
   `AUDIT_ECOSYSTEM.md` (state + parity matrix), per-component deep-dives, and a `ROADMAP` file
   (P0 blocker fixes → P1 standardization → P2 scale-safe extraction). Let agents patch from it.

## READ-ONLY SCORING / REPORTING MODE
Bos frequently asks: *"jangan ubah/edit file project, hanya scoring & reporting."* In this mode:
- ALL findings come from `read_file` + `terminal` (read-only curl/grep) + `search_files`. NEVER `write_file`/`patch` inside the project.
- You MAY write report `.md` files to a separate output dir (`/root/audit_report/`) — that is reporting, not editing the project.
- Clean up any scratch files you create inside the project (e.g. a `_repro_*.py`) before finishing.
- Never re-run a service, edit `.env`, or restart systemd as part of the audit.

## CRITICAL PITFALL — Delegation vs Direct Audit
**DO NOT spawn parallel subagents to audit the ILMA codebase on free models.**
In the 2026-07-09 session, 3 parallel `delegate_task` audit subagents all failed with
`HTTP 429: Rate limit exceeded: free-models-per-min` and returned ZERO findings. The main
context audit (terminal + read_file, zero LLM sub-calls) covered all 6 layers and found 9 real bugs.

Rule: For ILMA self-audit, audit DIRECTLY in the main context using `terminal` + `read_file` +
`execute_code`. Reserve `delegate_task` for tasks that need reasoning on external/large content,
never for grepping your own 110-module profile (it burns quota and rate-limits).

## AUDIT WORKFLOW (8 steps, all tool-based)

### Step 0 — Boot Verification (no assumptions, verify state)
```
python3 ilma.py --status
python3 ilma_runtime_wiring.py --verify      # expect: ok=N, missing=0, import_error=0
python3 ilma_orphan_wiring.py --verify        # expect: 24/24 imported OK (22 CLI + 3 library modules wired 2026-07-19)
git status --short                             # expect: clean or known-dirty
```

### Step 1 — Syntax Sweep (catch first-bit errors)
```
python3 -c "import py_compile,glob; errs=[(f,str(e)[:80]) for f in glob.glob('ilma_*.py') if (_ for _ in [0]).__len__()==1 and __import__('contextlib')]; ..."
# simpler:
python3 -m py_compile ilma_*.py && echo "SYNTAX OK"
```
(110 root modules + 302 scripts; a clean sweep = 0 compile errors.)

### Step 2 — Per-Layer Audit (6 domains, grep for bug classes)
For each layer, grep these ANTI-PATTERNS, then read the flagged lines:

| Bug class | Grep pattern | Why it's dangerous |
|-----------|--------------|--------------------|
| Duplicate dict key | `"same_key":` twice in one dict literal | Python last-wins silently → wrong value used |
| Missing module import | `from X import Y` where `X` doesn't exist | `except ImportError: pass` → feature silently dead |
| JSON trailing comma | `},\n  }` in `*.json` | Python `json.load` rejects; JS tolerates → cross-tool desync |
| Bare except | `except Exception:\n.*pass` / `except:\n.*pass` | Swallows real errors, masks root cause |
| Config↔runtime contradiction | `engine: ''` but code calls engine | Documented-off but actually-on → confusing state |
| Docs drift | SOUL.md lists X, registry lacks X | Capability/claim mismatch (not a crash) |
| Scoring/logic inversion | `if not x` where `if x` intended | Wrong branch taken silently |
| Circuit breaker desync | thresholds vs actual increments | Model blocked/unblocked incorrectly |
| **`cli: None` breaks sorted() in orphan_wiring** | `sorted(self.capabilities.items())` crashes with `'<' not supported between 'NoneType' and 'str'` when library modules have `cli: None` | Fix: `sorted(..., key=lambda x: (x[0] or ""))` — use module_name as fallback sort key |
| **`cli: None` dict key collision in orphan_wiring** | All library modules with `cli: None` use `None` as dict key → overwrite each other, only last one survives | Fix: `key = spec["cli"] or spec["module"]` — use module_name as fallback dict key |

Layers to cover (file roots):
- **Routing/Health:** `ilma_model_router.py`, `ilma_subagent_router.py`, `ilma_health_manager.py`, `ilma_fallback_cascade.py`, `ilma_confidence_router.py`, `ilma_provider_kernel.py`
- **Orchestration/Boot:** `ilma.py`, `ilma_orchestrator.py`, `ilma_workflow_ecc.py`, `ilma_runtime_wiring.py`, `ilma_orphan_wiring.py`, `ilma_dag_pipeline.py`, `ilma_quality_gate.py`
- **Capability/Judge:** `ilma_capability_registry.py`, `ilma_judge_system.py`, `ilma_actor_critic_core.py`, `ilma_grounding_loop.py`
- **Browser/Runtime:** `scripts/ilma_browser_engine.py`, `ilma_browser_runtime.py`, `ilma_human_interaction.py`
- **DB/Mongo/SOT:** `scripts/ilma_two_way_sync.py`, `sot/ilma_mongo_config.py`, `ilma_sot_dispatcher.py`, `ilma_model_db_manager.py`, `cron/jobs.json`
- **Reasoning/Learning:** `ilma_cognition_kernel.py`, `ilma_reasoning_runtime.py`, `ilma_learning_engine.py`, `ilma_autonomous_loop_engine.py`, `ilma_self_improve_integrator.py`

### Step 3 — E2E Execution Proof (don't trust imports — run it)
```
# Router + execution
python3 -c "from ilma_subagent_router import SubAgentRouter; r=SubAgentRouter(); d=r.route_and_execute('Write 5 words','writing',thinking='off',allow_paid=False,stateless=True); print(d.get('success'), repr(d.get('content'))[:60])"
# Workflow pipeline
python3 ilma_workflow_ecc.py --task "audit probe"
# Autonomous loop
python3 -c "import ilma_autonomous_loop_engine as A; print(A.AutonomousLoopEngine().run_cycle(task='x').get('state'))"
# Mongo/SOT live
python3 scripts/ilma_two_way_sync.py --status
curl -s http://127.0.0.1:9222/json/version | head   # browser CDP
systemctl --user is-active ilma-chrome@lokah2150.service
```

### Step 4 — Findings Table (deliverable format)
Use a Markdown table: `| # | Sev | file:line | Bug | Impact | Fix |`
Severity: **CRITICAL / HIGH / MEDIUM / LOW**.
Always include a **VERDICT** line: 🟢 PRODUCTION-READY / 🟡 NEAR-PRODUCTION (list blockers) / 🔴 NOT-READY.

## VERIFICATION COMMANDS (reusable, copy-paste)
See `references/ilma-audit-commands.md` for the full command bank.
See `references/ilma-audit-bug-patterns.md` for the 2026-07-09 findings as a reusable defect bank.

## OUTPUT DISCIPLINE
- One Telegram message = one report (Bos pref: no duplicate delivery). End with `✅ terkirim 1x`.
- Lead with the VERDICT, then the findings table, then "next step" offer (patch now? or see repro?).
- Never claim a layer is clean without running its verification command.

## POLICY COMPLIANCE AUDIT MODE
When auditing kebijakan (policy compliance) seperti FREE_ONLY, rate limiting, atau auth:
- Gunakan skill `ilma-policy-compliance-audit` untuk verifikasi
- **Jangan** berikan rekomendasi perbaikan kecuali diminta secara eksplisit
- Fokus pada laporan kepatuhanan, bukan perbaikan

See `references/free-only-implementation-patterns.md` for FREE_ONLY implementation verification steps.
See `references/policy-enforcement-points.md` for enforcement point locations across wrappers.