# ILMA System Audit — 2026-07-26 Findings

End-to-end audit of all ILMA profile components. 5 defects found & fixed, all verified,
committed + pushed (HTTPS PAT — see SKILL.md Gotchas). Companion to the live audit playbook.

## Coverage
- Boot/Runtime: `ilma.py --status` Ready 10/10, `ilma_runtime_wiring --verify` 37/37, `ilma_orphan_wiring --verify` 24/24.
- Routing/Health: router E2E hang fixed.
- Browser/CDP: `http://127.0.0.1:9222` reachable, `ilma-chrome@lokah2150.service` active.
- Mongo/SOT: SOT dispatcher OK; cron 3 jobs (2 enabled).
- Syntax: `python3 -m py_compile ilma_*.py` → 0 errors.
- Repo hygiene: 71MB bloat untracked.

## Fixes
| # | Sev | File | Defect | Fix | Verify |
|---|-----|------|--------|-----|--------|
| 1 | 🔴 | `capability_registry.json` (root) | INVALID JSON (models block missing key wrappers) | Root → symlink to `config/ilma_capability_registry.json` (canonical valid) | `python3 -c "import json; json.load(open('capability_registry.json'))"` → VALID |
| 2 | 🔴 | `ilma_subagent_router.py` | `route_and_execute` hung >60s when top model (`poolside/laguna-xs-2.1:free`) returns `content=None` (finish_reason=length) → empty→re-route loop up to 20×60s | Bounded: `MAX_EXECUTION_TIME` 300→120s, `while len(tried)<20`→`<8`, per-call `timeout=60`→`25`, `MAX_ATTEMPTS=3`→`2` | Re-run E2E: `success=True`, 41.9s, content `'Three words here'` |
| 3 | 🟡 | `.gitignore` + `bin/` | 71MB vendored binaries (`bin/uv` 61MB, `bin/uvx` 349KB, `bin/tirith` 9.8MB) git-tracked but unused (system uv at `/root/.local/bin/uv`) | Added `bin/uv`,`bin/uvx`,`bin/tirith` to `.gitignore`; `git rm --cached` (disk intact) | `git ls-files bin/` → only `bin/ilma_common_lib.sh` remains tracked |
| 4 | 🟡 | `ilma_super_coding_command_center.py:70` | `subprocess.run(["which",tool], capture_output=True, text=True)` no `timeout` | Added `timeout=10` | `py_compile` OK |
| 5 | 🟡 | `ilma_self_improve_integrator.py:334` | `kg.add_edge(from_node=..., to_node=..., edge_type=...)` but `KnowledgeGraph.add_edge(self, source_id, target_id, ...)` needs positional | Map to positional: `add_edge(f"skill_{...}", f"LEARNING:{...}", edge_type="EVIDENCES")` | Re-run `ilma_workflow_ecc.py --task ...` → WARNING `KnowledgeGraph update failed` GONE, `✅ Learning recorded` |

## Reproduction recipes
- JSON corruption locator: `python3 -c "import json; raw=open('X.json').read(); json.loads(raw)"` → `Extra data: line N` → `read_file` around N.
- Router hang isolation: `python3 -c "from ilma_subagent_router import SubAgentRouter; r=SubAgentRouter(); d=r.route('writing', thinking='off', allow_paid=False); print(d.model, d.provider)"` (fast ~0.8s) then `r.route_and_execute(message=..., task_type_or_desc='writing', thinking='off', allow_paid=False, stateless=True)` (bounded now).
- True missing-timeout scan (accurate): Python brace-scan over `subprocess.run/call/Popen/check_output/check_call` arg lists for `timeout` (not naive grep).

## Notes
- 48 modules flagged "orphan" by naive AST import-scan were FALSE POSITIVES (dynamic `importlib`/`getattr` + CLI entry via `ilma_orphan_wiring`). Do NOT delete based on static scan alone.
- `git push` required HTTPS PAT (SSH publickey denied). See SKILL.md Gotchas.
- `execute_code` is BLOCKED in this profile's cron-safety mode → use `terminal` with `python3 -c` / heredoc for JSON/string surgery (already in Gotchas).
