# ILMA Core Repository

**ILMA** — Intelligent Language Model Architecture. Hermes Agent dengan kapabilitas reasoning, routing, bridging, autonomous learning, dan self-improvement.

**Version:** v3.30 | **Phase:** PHASE 72 COMPLETE | **Status:** FULL AUTONOMY ACTIVE

---

## 📊 ILMA At A Glance

| Metric | Value |
|--------|-------|
| **Total Models** | 1,240 across 25 providers |
| **Free Models** | 655+ available |
| **Capabilities** | 33 registered |
| **Core Modules** | 86 Python files |
| **Scripts** | 365 utility scripts |
| **Skills** | 1,255 skill files |

---

## 🏗️ Architecture — Canon8 Pipeline

```
╔══════════════════════════════════════════════════════════════════╗
║                    ILMA Canon8 PIPELINE                           ║
╠══════════════════════════════════════════════════════════════════╣
║ LAYER 0 - BOOT          ilma.py (CLI: --status, --route, etc.)    ║
║ LAYER 1 - ROUTING        model_router → subagent_router → health  ║
║ LAYER 2 - EXECUTION      capability → orchestrator → provider    ║
║ LAYER 3 - WORKFLOW       workflow_ecc (8-step ECC)                 ║
║ LAYER 4 - VERIFICATION   actor_critic → judge → grounding         ║
║ LAYER 5 - REASONING      cognition_kernel → reasoning_runtime     ║
║ LAYER 6 - KNOWLEDGE      knowledge_graph → ingestion → learning   ║
║ LAYER 7 - AUTONOMY       autonomous_loop_engine → model_registry  ║
║ LAYER 8 - SPECIALIZED    coding_command_center → partner_wrappers ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## 🌐 Model Ecosystem — 1,240 Models, 25 Providers

### Active Providers

| Provider | Type | Status |
|----------|------|--------|
| **minimax** | Cloud (API) | ✅ Active — default model: minimax-m3 |
| **nvidia** | Cloud (NIM) | ✅ Active — free NIM endpoints |
| **openrouter** | Aggregator (346 models) | ✅ Active |
| **blackbox** | AI Playground (139 models) | ✅ Active |
| **ollama** | Local | ✅ Active |
| **xai** | Cloud (9 models) | ✅ Active |
| **deepseek** | Cloud | ✅ Active |
| **google** | Cloud | ✅ Active |
| **anthropic** | Cloud | ✅ Active |
| **openai** | Cloud | ✅ Active |
| **meta** | Cloud | ✅ Active |
| **mistral** | Cloud | ✅ Active |
| **cohere** | Cloud | ⚠️ Skipped/failed |
| **perplexity** | Cloud | ⚠️ Skipped/failed |

### Free-Tier First Policy

1. **NVIDIA NIM** — Free endpoints, strong models (llama-3.3-70b, nemotron, etc.)
2. **MiniMax** — Free tier available (m3 default, m2.7, m2.5)
3. **OpenRouter Free** — 346 models with free quota
4. **BlackBox** — 139 models, free tier
5. **DeepSeek** — Free tier

---

## 🧩 10 Core Components

| # | Component | File | Peran |
|---|-----------|------|-------|
| 1 | knowledge_graph | ilma_knowledge_graph.py | Graph-based knowledge |
| 2 | learning_engine | ilma_learning_engine.py | Autonomous learning |
| 3 | capability_registry | ilma_capability_registry.py | 33 registered capabilities |
| 4 | provider_kernel | ilma_provider_kernel.py | Cloud provider management |
| 5 | cognition_kernel | ilma_cognition_kernel.py | Cognitive processing |
| 6 | reasoning_runtime | ilma_reasoning_runtime.py | 5 reasoning modes |
| 7 | grounding_loop | ilma_grounding_loop.py | Anti-hallucination verification |
| 8 | confidence_router | ilma_confidence_router.py | Confidence-aware routing |
| 9 | execution_graph | ilma_execution_graph.py | Execution memory graph |
| 10 | autonomous_loop_engine | ilma_autonomous_loop_engine.py | Self-improvement loop |

---

## 🔐 Security Rules

```gitignore
# Credentials — LOCAL ONLY
/root/credential/
auth.json
config.yaml
.env, *.env

# API Keys (scan ALL files)
ghp_*, sk-*, sk-ant-*, sk-or-*, sk-prod-*
AIzaSy*, nvapi-*, MINIMAX*, dashscope*

# Sensitif
*credential*, *secret*, *password*, *token*, *apikey*
```

---

## 📁 Repository Structure (Clean — Phase 72)

```
ilma-core/
├── .gitignore                          # 250+ patterns, credential + runtime
├── README.md                           # This file
│
├── ilma_*.py                           # 86 core modules (canonical root)
│   ├── ilma.py                          # Main entry point
│   ├── ilma_model_router.py             # Multi-provider routing
│   ├── ilma_workflow_ecc.py             # 8-step ECC workflow
│   ├── ilma_actor_critic_core.py        # Self-evaluation + retry
│   ├── ilma_judge_system.py             # L1-L10 verification
│   └── ... (80 more)
│
├── scripts/                            # 365 utility scripts
│   ├── ilma_browser_engine.py           # Playwright CDP browser
│   ├── ilma_model_db_manager.py         # DB pipeline (--full-sync)
│   ├── ilma_db_pipeline.py              # Provider sync + enrich
│   ├── ilma_claudecode_agent.py         # Parallel coding agent
│   └── ... (361 more)
│
├── skills/                              # 1,255 skill files (organized by category)
│   ├── ilma-*/                           # 100+ ILMA patterns (SSS tier)
│   ├── devops/
│   ├── mlops/
│   ├── creative/
│   └── ... (50+ categories)
│
├── docs/                                # Documentation
│   └── passive_benchmark_refresh/
├── hermes_profile_ilma/                # 132 legacy reference files
│   ├── SOUL.md, ilma_soul.md            # Core definitions
│   ├── ilma_body_map.md                 # Architecture map
│   ├── ilma_constitution.md             # Operational rules
│   └── config/, data/                   # Reference config + data
│
├── ilma_model_router_data/              # Model intelligence
│   ├── PROVIDER_INTELLIGENCE_MASTER.json  # 1,240 models, 25 providers
│   ├── benchmark_database.json          # 1,023 benchmark entries
│   └── ... (other data files — see .gitignore)
│
├── ilma_core/                           # 4 infrastructure files
│
├── dashboard/                           # 49 files (frontend + backend)
│
├── systemd/                             # Systemd services
│   └── ilma-chrome@.service             # Chrome CDP per profile
│
└── docs/                                # Documentation
    └── passive_benchmark_refresh/
```

---

## 🚀 Setup Instructions

### 1. Clone
```bash
git clone https://github.com/lokah1945/ilma-core.git
cd ilma-core
```

### 2. Credentials (LOCAL ONLY — never commit)
```bash
# Store at /root/credential/ — NOT in repo
cp /path/to/api_key.json /root/credential/api_key.json
chmod 700 /root/credential/
chmod 600 /root/credential/*.json
```

### 3. Model DB Sync (optional)
```bash
# Sync every 12h via cron or manual
python3 scripts/ilma_model_db_manager.py --full-sync --git-push
```

---

## 📜 MANDATORY SYNC RULE

Setiap perubahan di ILMA **WAJIB** di-commit dan push ke GitHub repo ini.

```bash
git add -A
git commit -m "description"
git push origin master
```

---

## 🔄 Self-Improvement Loop

```
DISCOVERY → ANALYSIS → OPTIMIZATION → VERIFICATION → DEPLOYMENT
    ↑__________________________________________________|
```

ILMA continuously improves through:
- **Evidence capture** — Every task captures evidence (ILMA-EVID-YYYYMMDD-*)
- **Benchmark tracking** — Model performance monitored
- **Health monitoring** — Provider health + rate-limit tracking
- **Parallel coding** — ClaudeCode-style multi-model fan-out
- **Passive enrichment** — Background DB updates via cron

---

## 📈 Performance Metrics

| Metric | Value |
|--------|-------|
| Total tracked files | 5,536 |
| Core modules | 86 Python files |
| Scripts | 365 |
| Skills | 1,255 |
| Bridges | 4 active |
| Model routing | 1,240 models, 25 providers |
| DB sync | Every 12h (cron) |

---

## ⚠️ What This Repo Is NOT

This repo contains **runtime Hermes profile state** + source code. It is NOT a clean source-only repo. Rekan yang clone perlu tahu:

- `skills/`, `scripts/`, `ilma_*.py` → **SOURCE** — ini yang perlu dipelajari
- `whatsapp/`, `memories/`, `evidence/`, `backups/` → **RUNTIME** — di-gitignore, tidak ada di repo
- `config.yaml`, `auth.json`, `memory.json` → **CREDENTIALS** — di-gitignore, local only
- Chrome browser profile (`/root/user-data/lokah2150`) → **PROTECTED** — admin identity, tidak di-repo

---

## License

Internal use only — YAPSI Darussalam Foundation

**Bos:** Huda Choirul Anam
**Last cleanup:** PHASE 72 (2026-06-07) — 2,164 files removed, .gitignore hardened