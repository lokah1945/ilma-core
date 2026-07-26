# ILMA — Intelligence Layer for Multi-agent Autonomy

> **ILMA** (Hermes Agent · Memory Specialist · Smart Router) adalah agent otonom berbasis
> prinsip Hermes: cepat, adaptif, komunikatif, cerdas dalam routing, kuat dalam
> pencarian jalur keluar, dan mampu menyampaikan hasil kerja dengan presisi berbasis bukti.

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  ILMA v3.30 — Canon8 Pipeline · 8-Layer Architecture · Evidence-First         ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 🎯 Filosofi Inti

ILMA beroperasi pada **level capability, bukan hanya tool**. Prinsip operasional:

1. **Evidence over claim** — klaim kemampuan harus punya `evidence_id`.
2. **Capability over tool** — pikirkan capability, lalu cari semua jalur eksekusi.
3. **Fallback before failure** — satu error ≠ satu capability gagal.
4. **Runtime awareness** — status aktual > memory lama.
5. **Pure data-driven routing** — tidak ada hardcoded primary model; model terpilih =
   skor tertinggi dari bobot (capability 0.35 · intelligence 0.30 · context 0.10 ·
   trust 0.15 · freshness 0.10) di antara kandidat yang sehat & free-tier.
6. **Circuit-breaker durable** — model gagal 5× ditandai `disabled` & **persisten
   lintas restart** (di-restore dari health file saat boot).
7. **Safe autonomy** — otonom dalam eksekusi, aman & legal dalam batasan.

---

## 🏗️ Arsitektur — 8-Layer Canon8 Pipeline

```
BOOT → ANALYZE (4W1H + thinking_tier + skill_detect)
     → ROUTE (model_router + subagent_router + health_manager + confidence_router)
     → RESOLVE (capability_registry)
     → EXECUTE (browser + thinking_tier | hermes_skill_execution)
     → EVALUATE (actor_critic + judge)
     → VERIFY (grounding)
     → LEARN (learning_engine)
     → REPORT
```

| Layer | Modul | Tanggung Jawab |
|-------|-------|----------------|
| **0 — BOOT** | `ilma.py` | CLI (`--status`, `--route`, `--verify`, `--think`), bootstrap 26 komponen |
| **1 — ROUTING** | `ilma_model_router` · `ilma_subagent_router` · `ilma_health_manager` · `ilma_confidence_router` | Pemilihan model berbasis skor + health-aware circuit breaker |
| **2 — EXECUTION** | `ilma_capability_registry` · `ilma_orchestrator` · `ilma_provider_kernel` | Resolusi capability → provider call (FREE-only default) |
| **3 — WORKFLOW** | `ilma_workflow_ecc` | 8-step ECC: 4W1H→ECC→SECURITY→RULES→HOOKS→WORKFLOW→VERIFY→REPORT |
| **4 — VERIFICATION** | `ilma_actor_critic_core` · `ilma_judge_system` · `ilma_grounding` · `ilma_evidence_validator` · `ilma_adversarial_qa` | Anti-hallucination, score 0–1.0 (L1–L10) |
| **5 — REASONING** | `ilma_cognition_kernel` · `ilma_reasoning_runtime` · `ilma_execution_graph` | DEDUCTIVE/INDUCTIVE/ABDUCTIVE/CAUSAL/ANALOGICAL |
| **6 — KNOWLEDGE** | `ilma_knowledge_graph` · `ilma_knowledge_ingestion` · `ilma_learning_engine` | Graph-based memory, learning loop |
| **7 — AUTONOMY** | `ilma_autonomous_loop_engine` · `ilma_model_registry` | Self-improvement loop, discovery→evolution |
| **8 — SPECIALIZED** | `ilma_super_coding_command_center` · `ilma_orphan_wiring` (22 modul) | Coding agent (parallel free models), admin/CLI tools |

**Runtime Wiring:** `ilma_runtime_wiring.py --verify` → **37/37 modules OK, 0 missing, 0 import errors**.
**Orphan Wiring:** `ilma_orphan_wiring.py --verify` → **24/24 admin/CLI modules OK**.

---

## 🔌 Browser Policy (Phase 66/69 — NATIVE ILMA)

ILMA menggunakan **custom Playwright Chromium CDP runtime** sebagai backend browser tunggal:

| Item | Value |
|------|-------|
| Engine | `ilma_browser_engine.py` (Playwright-based, **default**) |
| Hermes built-in browser | **DISABLED** (`browser.engine: ''`) |
| CDP endpoint | `http://127.0.0.1:9222` |
| Profile (admin) | `/root/user-data/lokah2150` (protected) |
| Service | `ilma-chrome@lokah2150.service` (systemd --user) |
| Interaction | `ilma_human_interaction.py` (HumanInteractionAdapter default) |
| Enforcement | `enforce_custom_browser: true`, `disable_builtin_browser_fallback: true` |

Non-admin profiles mendapat isolated `user-data-dir` di bawah `/root/user-data/<profile>`
dengan CDP port unik — **tidak bisa akses profile admin**.

---

## 🧠 Model Routing — Pure Data-Driven

Tidak ada mandate model primer. Semua sub-agent call via `ilma_subagent_router.SubAgentRouter`:

```python
from ilma_subagent_router import SubAgentRouter
router = SubAgentRouter()
decision = router.route("write a blog post", thinking="off", allow_paid=False)
result = router.route_and_execute(
    message="Write exactly 5 words",
    task_type_or_desc="writing task",
    thinking="off", allow_paid=False, stateless=True,
)
# → {'success': True, 'content': '...', 'model': '...', 'evidence_id': '...'}
```

**Circuit breaker:**
- `mark_failure` ×5 → `status="disabled"` (persisted to health file).
- Boot restore `_failure_count` + `_cooldown_until` dari health file → breaker **durable**.
- `_is_healthy()` memeriksa `status=="disabled"` persisted.
- Tiered: 1–2 fails = `soft_degraded`, 3–4 = `degraded`, 5+ = `disabled`.

**Provider (FREE-tier first):** nvidia · minimax · openrouter · blackbox · ollama · xai.
ProviderKernel enforce `FREE_MODEL_ONLY` via `router.is_model_runtime_allowed()`.

---

## 📊 Capability Registry

Dua sumber terpisah, masing-masing authoritative untuk tujuannya:

- **Runtime registry** (`ilma_capability_registry.CapabilityRegistry`): **37 capabilities**
  (kategorikal: COGNITIVE, EXECUTIVE, CREATIVE, ANALYTICAL, OPERATIONAL, COMMUNICATION,
  SECURITY, INTEGRATION, MEMORY, META). Source routing runtime.
- **Evidence ledger** (`config/ilma_capability_registry.json`): **108 entries** dengan
  `confidence_score`, `verification_status`, `evidence_note`. Audit/confidence tracking.

> Jangan conflate kedua count — keduanya valid untuk purpose berbeda.

---

## 🚀 Quick Start

```bash
cd /root/.hermes/profiles/ilma

# Status seluruh sistem
python3 ilma.py --status                 # → READY 10/10

# Verifikasi wiring
python3 ilma_runtime_wiring.py --verify   # → 37/37 OK
python3 ilma_orphan_wiring.py --verify    # → 24/24 OK

# Jalankan task via 8-step ECC pipeline (WAJIB untuk tiap task)
python3 ilma_workflow_ecc.py --task "your task"

# Routing langsung
python3 ilma.py --route "write a blog post" --allow-paid false

# Browser (CDP daemon)
systemctl --user status ilma-chrome@lokah2150.service
curl -s http://127.0.0.1:9222/json/version | jq .
```

---

## 🧪 Testing & Verification

```bash
# Syntax sweep
python3 -m py_compile ilma_*.py          # → 0 errors

# E2E router
python3 -c "from ilma_subagent_router import SubAgentRouter; \
r=SubAgentRouter(); print(r.route_and_execute(message='hi', task_type_or_desc='writing', \
thinking='off', allow_paid=False, stateless=True))"

# Circuit-breaker durability
python3 -c "from ilma_model_router import ILMAUnifiedRouter as R; \
rr=R(); [rr.mark_failure('x/y', 'e') for _ in range(5)]; \
print('disabled after 5 fails:', not rr._is_healthy('x/y'))"
```

---

## 📁 Struktur Repo

```
ilma/
├── ilma.py                      # Main orchestrator + CLI
├── ilma_runtime_wiring.py       # 8-layer wiring verifier (37 modules)
├── ilma_orphan_wiring.py        # 22 admin/CLI module wiring
├── ilma_model_router.py         # Pure data-driven router + durable circuit breaker
├── ilma_subagent_router.py      # Sub-agent execution w/ fallback cascade
├── ilma_capability_registry.py  # 37 runtime capabilities
├── ilma_workflow_ecc.py         # 8-step ECC pipeline
├── ilma_knowledge_graph.py      # Graph-based memory
├── ilma_reasoning_runtime.py    # 5 reasoning modes
├── ilma_cognition_kernel.py     # REACTIVE/DELIBERATIVE/AUTONOMOUS/META
├── ilma_actor_critic_core.py    # Debate-based verification (0–5 scale)
├── ilma_judge_system.py         # L1–L10 scoring (0–1.0)
├── ilma_provider_kernel.py      # FREE-only provider calls
├── ilma_browser_engine.py       # → scripts/ canonical (Playwright CDP)
├── ilma_browser_runtime.py      # → scripts/ canonical (CDP resolver)
├── ilma_human_interaction.py    # → scripts/ canonical (HumanAdapter)
├── config/
│   └── ilma_capability_registry.json   # 108-entry evidence ledger
├── scripts/                     # 327 helper scripts (canonical browser engine, etc.)
├── skills/                      # 1008 Hermes+ILMA skills
├── sot/                         # System-of-Truth (Mongo cloud) picker/enrichment
├── tests/  dashboard/  cron/  systemd/  optimization/  pentest/  attic/
└── .gitignore                   # Secrets, credentials, data/cache excluded
```

> **Data/cache di-exclude dari repo:** `ilma_model_router_data/`, `models_dev_cache.json`,
> `*.sqlite`, `state-snapshots/`, `cron/ticker_*`, secrets (`*credential*`, `*secret*`,
> `/config.yaml`, `/.env`).

---

## 🔒 Security & Boundaries

- **Military-grade** = secure-by-design, robust, auditable, resilient — **bukan** malware/exploit.
- Browser automation **human-like** (HumanInteractionAdapter) untuk stabilitas UI — **bukan**
  untuk bypass CAPTCHA, rate-limit, access control, atau unauthorized access.
- Secrets **tidak pernah** di-commit (`.gitignore` strict).
- CDP bind **hanya** `127.0.0.1` (never `0.0.0.0`).

---

## 📜 Version History

| Version | Highlight |
|---------|-----------|
| v3.30 | Canon8 pipeline, 8-layer wiring, durable circuit breaker, browser policy Phase 69 |
| v3.29 | Pure data-driven routing (no mandate), health-aware breaker |
| v3.0 | AYDA 10-component integration, optimization (65+ files removed) |

---

**ILMA — Evidence-Based Hermes Intelligence Agent**
*Repo reset & force-pushed clean: 2026-07-26*
*Deep audit + conceptual fixes: 2026-07-26 (circuit-breaker durability, knowledge-graph NameError, capability-count drift)*
