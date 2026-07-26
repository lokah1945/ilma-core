# PHASE INDEX — ILMA Evolution Reference Catalog

Last updated: 2026-06-03

## Active Phases

| Phase | Topic | File | Status |
|-------|-------|------|--------|
| 1 | Capability Inventory Audit — Evidence-Gated | phase1-audit-evidence-verification.md | ACTIVE |
| 14 | Evidence quality verification | phase14-capability-verification.md | ACTIVE |
| 25 | Evidence quality services decomposition | phase25-evidence-quality-services-decomposition.md | ACTIVE |
| 27 | Weak verified downgrade | phase27-weak-verified-downgrade.md | ACTIVE |
| 28 | Services decomposition behavioral proof | phase28-services-decomposition-behavioral-proof.md | ACTIVE |
| 38 | Needs small script behavioral proof | phase38-needs-small-script-behavioral-proof.md | ACTIVE |
| 39 | Extreme mission loop controller | phase39-extreme-mission-loop-controller.md | ACTIVE |
| 46-47 | Autonomous evolution | phase-46-47-autonomous-evolution.md | ACTIVE |
| 48a | Orchestrator gap fix | phase48a-orchestrator-gap-fix.md | ACTIVE |
| 48bclose | Status semantics truth lock | phase48bclose-status-semantics-truth-lock.md | ACTIVE |
| 48f | Behavior change chain | phase48f-behavior-change-chain.md | ACTIVE |
| 48g | Internal optimization gauntlet | phase48g-internal-optimization-gauntlet.md | ACTIVE |
| 49 | 300min autoloop body integration | phase49-300min-autoloop-body-integration.md | ACTIVE |
| 51/52 | Daemon session boundary | phase52-daemon-session-boundary.md | ACTIVE |
| 52R | Wall clock semantics fix | phase52r-wall-clock-semantics-fix.md | ACTIVE |
| 53-54 | Runtime wiring | phase-53-54-runtime-wiring.md | ACTIVE |
| 53-55 | Internal production candidate | phase-53-55-internal-production-candidate.md | ACTIVE |
| 56 | Production entrypoint | phase56-production-entrypoint.md | ACTIVE |
| 56R | Production entrypoint reexecution | phase56-production-entrypoint-reexecution.md | ACTIVE |
| 59 | Comprehensive optimization | phase59-comprehensive-optimization.md | ACTIVE |
| 62 | Codex OAuth bottleneck | phase62-codex-oauth-bottleneck.md | ACTIVE |
| 62 | Bootstrap name mismatch | phase62-bootstrap-name-mismatch.md | ACTIVE |
| 63 | End-to-end optimization | phase63-end-to-end-optimization.md | ACTIVE |
| 63 | End-to-end file optimization | phase63-end-to-end-file-optimization.md | ACTIVE |
| 63 | Consolidation | phase63-consolidation.md | ACTIVE |
| 64 | Optimizer model status audit | phase64-optimizer-model-status-audit.md | ACTIVE |
| **65** | **Execution vs Planning behavioral fix** | **phase65-execution-vs-planning-behavior.md** | **ACTIVE** |
| **69** | **Autonomous custom browser runtime** | **autonomous-runtime-20260601.md** | **ACTIVE** |

## Key Lessons

1. **Evidence before claim** — Never claim VERIFIED without evidence
2. **Execute, not plan** — When user provides plan, build immediately
3. **Small scripts > big plans** — Behavioral proof before architecture
4. **Return to original task** — Don't switch to unrelated cleanup when interrupted
5. **Session boundaries** — Daemon vs user sessions have different timing semantics
6. **Wiring verification** — Every module must be verified, not just present
7. **Git sync before moving on** — Every significant change must be committed
8. **Phase 1 lesson** — All 37 claimed capabilities were UNTESTED. Module existence ≠ capability verified. Test independently before claiming status.

--
Generated: 2026-06-03