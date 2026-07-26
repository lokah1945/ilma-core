# Deep Conceptual Audit — 2026-07-26 (Gelombang 1 + 2)

Bos directive: "audit komprehensif end-to-end, sekecil apapun, lalu optimisasi menyeluruh"
→ followed by: "ulangi audit lebih dalam, sampai detail paling dalam, secara logika & konsep tidak ada kesalahan"

## Scope covered
6 domains: Routing/Health, Orchestration/Workflow/Boot, Capability/Verification/Judge,
Browser/Runtime, System/DB/Mongo/SOT, Reasoning/Learning/Knowledge.

## Gelombang 1 (syntax + coverage) findings
| # | Sev | Finding | Fix |
|---|-----|----------|-----|
| 1 | 🔴 | `capability_registry.json` (root) INVALID JSON — models block missing key wrappers | Root → symlink to `config/ilma_capability_registry.json` (valid canonical) |
| 2 | 🔴 | `route_and_execute` could hang up to 20×60s when top model returns null content (poolside/laguna-xs-2.1:free) | Cap 8 attempts / 120s wall-clock, per-call 25s, MAX_ATTEMPTS 2 |
| 3 | 🟡 | 71MB vendored binaries tracked in git (bin/uv 61MB, bin/tirith 9.8MB) — system uv at /root/.local/bin/uv | `.gitignore` + `git rm --cached` (disk intact) |
| 4 | 🟡 | 1 `subprocess.run` without timeout (`is_tool_available`) | +`timeout=10` |
| 5 | 🟡 | `KnowledgeGraph.add_edge` called with kwargs but signature needs positional | Map to positional args |

## Gelombang 2 (deep conceptual / semantic) findings
| # | Sev | Bug (conceptual) | Impact | Fix |
|---|-----|------------------|---------|-----|
| A | 🔴 | **Circuit-breaker non-durable**: `mark_failure` persists `status="disabled"` to disk, but `_is_healthy()` only reads in-memory `_failure_count` (reset to 0 on boot) and never inspects persisted `status=="disabled"` | Disabled model reused after restart | Restore `_failure_count`/`_cooldown_until` from health file at `__init__`; `_is_healthy()` returns False on `status=="disabled"` |
| B | 🟡 | **Dead branch** in `mark_failure`: `else: status="degraded"` makes `elif count>=DEGRADE_THRESHOLD` unreachable | Tiered status has no nuance (soft vs degraded identical) | `else: status="soft_degraded"` (1-2 fails) |
| C | 🟡 | `KnowledgeGraph._coerce_type` → `NameError` on undefined `_e` in nested except | Crash if node_type can't be coerced | Generic warning, no `_e` ref |
| D | 🟡 | `ILMA_CAPABILITY_REGISTRY_PATH` pointed at `.py` (self), not the JSON | Misleading constant | Renamed to `ILMA_CAPABILITY_REGISTRY_JSON` → `config/ilma_capability_registry.json` |
| E | 🟡 | SOUL.md claimed "37 registered capabilities" conflating two sources (37 runtime registry + 108 evidence-ledger JSON) | Misleading doc | Clarified: 37 runtime + 108 ledger |

## Verified fixes (evidence)
- `py_compile` all 110 modules → OK
- Circuit-breaker persistence simulated: 5 fails → `disabled`; new instance → `_is_healthy=False` (was `True` before fix)
- Router E2E `route_and_execute` → `success=True` (41.9s, poolside)
- Workflow ECC 8-step → `✅ Learning recorded` (kg warning gone)
- `runtime_wiring`: 37/0/0; `orphan_wiring`: 24/24
- Browser policy `config.yaml` 100% matches SOUL.md Phase 69

## Commit trail
- Gelombang 1: `b1206c8`
- Gelombang 2: `4a92a84` (both via `git push origin HEAD`, HTTPS PAT — SSH key not on GitHub)

## Reproduction commands
```bash
# Circuit-breaker durability test
python3 - <<'PY'
from ilma_model_router import ILMAUnifiedRouter
r=ILMAUnifiedRouter(); mid="test/x"
for i in range(5): r.mark_failure(mid,"empty_response")
print("after 5 fails _is_healthy:", r._is_healthy(mid))   # expect False
r2=ILMAUnifiedRouter()                                       # simulate restart
print("after restart _is_healthy:", r2._is_healthy(mid))  # expect False (fixed)
PY

# Router E2E
python3 -c "from ilma_subagent_router import SubAgentRouter as S; \
r=S(); print(r.route_and_execute(message='Say hi in 2 words', \
task_type_or_desc='writing', thinking='off', allow_paid=False, stateless=True))"
```
