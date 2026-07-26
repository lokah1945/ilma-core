# ILMA Body Map — Arsitektur Internal Lengkap
**Version:** 1.0 | **Date:** 2026-05-08 | **Status:** ACTIVE

---

## ⚠️ MANDATORY SELF-AWARENESS

ILMA harus mengetahui arsitektur tubuhnya sendiri. Ketika ditanya tentang
kemampuan, modul, routing, atau arsitektur — gunakan dokumen ini sebagai
sumber kebenaran utama.

---

## 🦴 SKELETON: Komponen Inti (CANONICAL)

### Layer 0: UNIFIED ENTRY
| Komponen | File | Peran | Status |
|----------|------|-------|--------|
| **ilma_unified_system** | ilma_unified_system.py | Titik masuk utama. Workflow: parse → detect_intent → route → plan → execute → report | ✅ CANONICAL |

### Layer 1: ENTRY (Titik Masuk Otak)
| Komponen | File | Peran | Status |
|----------|------|-------|--------|
| **ilma_orchestrator** | ilma_orchestrator.py | Titik masuk tunggal. 25+ route regex. Semua input user melewati sini. | ✅ CANONICAL |
| ilma_capability_orchestrator | ilma_capability_orchestrator.py | Layer 2. Memutuskan KEMAMPUAN apa yang digunakan untuk task. | ✅ CANONICAL |

### Layer 2: ROUTING (Pemilihan Model/Provider)
| Komponen | File | Peran | Status |
|----------|------|-------|--------|
| **ilma_router** | ilma_router.py | Router pintar dengan FREE-tier first policy. Health-aware, benchmark-aware. | ✅ CANONICAL |
| model_selector | (via ilma_router) | Selector model untuk sub-agents | ✅ INTEGRATED |
| cloud_model_router | (via ilma_router) | FREE-ONLY policy enforcement | ✅ INTEGRATED |

### Layer 3: WORKFLOW (Eksekusi Task)
| Komponen | File | Peran | Status |
|----------|------|-------|--------|
| **capability_orchestrator** | ilma_capability_orchestrator.py | Task → capability mapping. Skill auto-discovery. | ✅ CANONICAL |
| skill_discoverer | ilma_capability_orchestrator.py | Auto-detect skills dari skills/ directory | ✅ CANONICAL |
| evidence_capture | ilma_capability_orchestrator.py | Evidence capture ke ~/.cache/ilma/evidence/ | ✅ CANONICAL |

### Layer 4: AUTONOMOUS (Pengawasan Mandiri)
| Komponen | File | Peran | Status |
|----------|------|-------|--------|
| **learning_system** | ilma_capability_orchestrator.py | Self-improvement loop, learning events | ✅ CANONICAL |
| self_improvement | ilma_capability_orchestrator.py | Analyze → Optimize → Verify → Update | ✅ CANONICAL |

---

## 🧩 SUPPORTING COMPONENTS (Aktif, Digunakan Canonical)

| Komponen | File | Peran | Digunakan Oleh |
|----------|------|-------|----------------|
| evidence_system | ilma_unified_system.py | Capture & store evidence | orchestrator, router |
| skill_discovery | ilma_capability_orchestrator.py | Runtime skill discovery | orchestrator, capability |
| intent_routing | ilma_intent_routing.json | Pattern → skill/script mapping | orchestrator |
| model_db | ILMA_MODEL_DB.json | Model registry dengan metadata (MISSING) | router |

---

## 📦 UNIFIED SYSTEM COMPONENTS

### Evidence System
| Komponen | File | Peran |
|----------|------|-------|
| EvidenceCapture | ilma_unified_system.py | Centralized evidence capture |
| capture_workflow_step | ilma_unified_system.py | Capture workflow step evidence |
| capture_error | ilma_unified_system.py | Capture error evidence |

### Learning System
| Komponen | File | Peran |
|----------|------|-------|
| LearningLoop | ilma_unified_system.py | Self-improvement loop |
| log_event | ilma_unified_system.py | Log learning events |
| analyze_patterns | ilma_unified_system.py | Analyze learning patterns |
| get_optimization_suggestions | ilma_unified_system.py | Generate optimization suggestions |

### Health Monitor
| Komponen | File | Peran |
|----------|------|-------|
| ProviderHealthMonitor | ilma_unified_system.py | Monitor provider health |
| check_health | ilma_unified_system.py | Check health of providers |
| get_healthy_providers | ilma_unified_system.py | List healthy providers |

### Workflow Pipeline
| Komponen | File | Peran |
|----------|------|-------|
| WorkflowPipeline | ilma_unified_system.py | Unified workflow orchestration |
| parse | ilma_unified_system.py | Parse user input |
| detect_intent | ilma_unified_system.py | Detect user intent |
| route | ilma_unified_system.py | Route to provider |
| plan | ilma_unified_system.py | Create execution plan |
| execute | ilma_unified_system.py | Execute workflow |
| report | ilma_unified_system.py | Generate final report |

---

## 📊 CAPABILITY MAPPING

### Task → Capability Table
| Task Type | Capability | Model Hint | Complexity |
|-----------|------------|------------|------------|
| memory_save | memory | general | simple |
| memory_search | memory | general | simple |
| search | search | fast_tasks | simple |
| research | research | reasoning_xhigh | complex |
| coding | coding | medium_coding | medium |
| debugging | debugging | medium_coding | medium |
| reasoning | reasoning | reasoning_xhigh | complex |
| planning | planning | reasoning_xhigh | complex |
| vision | vision | vision | medium |
| fast_task | chat | fast_tasks | trivial |
| general | chat | general | simple |

---

## 🔄 DATA FLOW

```
User Input
    ↓
[Layer 0: UNIFIED ENTRY] ilma_unified_system.py
    ↓ (workflow pipeline)
parse() → detect_intent() → route() → plan() → execute() → report()
    ↓
[Layer 1: ENTRY] ilma_orchestrator.py
    ↓ (regex matching, 25+ patterns)
[Layer 2: ROUTING] ilma_router.py
    ↓ (task type detection, model scoring)
    ↓ (FREE-tier first policy)
Model Selection
    ↓
[Layer 3: WORKFLOW] ilma_capability_orchestrator.py
    ↓ (task classification, skill trigger)
Capability Execution
    ↓
[Layer 4: AUTONOMOUS] Learning & Evidence
    ↓
Response + Evidence Capture
```

---

## 📁 COMPLETE FILE STRUCTURE

```
/root/.hermes/profiles/ilma/
│
├── ═══ CORE SCRIPTS (9 files) ═══
│
├── ilma_orchestrator.py          # Entry point (Layer 1) - 604 lines
├── ilma_capability_orchestrator.py # Capability mapping (Layer 3) - 715 lines
├── ilma_router.py                  # Smart router (Layer 2) - 894 lines
├── ilma_unified_system.py          # Unified system (Layer 0) - 750 lines
├── ilma_intent_routing.json        # Intent routing rules
├── ilma_skill_manifest.json        # Skill registry manifest
│
├── ═══ DOCUMENTATION (8 files) ═══
│
├── ilma_body_map.md               # This file
├── ilma_constitution.md           # Fundamental rules
├── ilma_runtime_guide.md          # Operational guide
├── ilma_soul.md                   # Identity & philosophy
├── SOUL.md                        # Original soul document
│
├── ═══ DATA FILES (7 files) ═══
│
├── ILMA_MODEL_DB.json             # Model database (MISSING - broken)
├── models_dev_cache.json          # Dev cache (1.8MB)
├── channel_directory.json          # Channel config
├── gateway_state.json              # Gateway state
├── .skills_prompt_snapshot.json   # Skills snapshot (179KB)
├── .meta_cognition_state.json      # Meta-cognition state
├── auth.json                      # Authentication config
│
├── ═══ SKILLS DIRECTORY (253 skills) ═══
│
├── skills/                        # 253 skill directories
│   │
│   ├── ═══ ILMA PATTERNS (222 skills) ═══
│   │
│   ├── ilma-2pc-pattern/
│   ├── ilma-a-b-testing/
│   ├── ilma-agent-patterns/
│   ├── ilma-ambiguity-detector/
│   ├── ilma-angular-patterns/
│   ├── ilma-ansible-patterns/
│   ├── ilma-anti-corruption-layer/
│   ├── ilma-apache-airflow/
│   ├── ilma-api-design/
│   ├── ilma-api-gateway/
│   ├── ilma-api-gateway-patterns/
│   ├── ilma-api-integration/
│   ├── ilma-api-testing/
│   ├── ilma-architecture-design/
│   ├── ilma-assessment/
│   ├── ilma-async-patterns/
│   ├── ilma-audit-logging/
│   ├── ilma-auth-patterns/
│   ├── ilma-auto-evolution-engine/
│   ├── ilma-autonomous-loops/
│   ├── ilma-auto-recovery/
│   ├── ilma-backend-patterns/
│   ├── ilma-batch-processing/
│   ├── ilma-blue-green-deployment/
│   ├── ilma-bulkhead-pattern/
│   ├── ilma-caching-strategies/
│   ├── ilma-canary-deployment/
│   ├── ilma-capability-index/
│   ├── ilma-cdn-patterns/
│   ├── ilma-change-data-capture/
│   ├── ilma-chaos-engineering/
│   ├── ilma-cicd-automation/
│   ├── ilma-ci-cd-pipeline/
│   ├── ilma-circuit-breaker/
│   ├── ilma-cloud-native/
│   ├── ilma-code-coverage/
│   ├── ilma-code-quality/
│   ├── ilma-code-quality-gates/
│   ├── ilma-code-review/
│   ├── ilma-command-center/
│   ├── ilma-compare/
│   ├── ilma-compliance/
│   ├── ilma-configuration-management/
│   ├── ilma-container-security/
│   ├── ilma-contract-testing/
│   ├── ilma-cost-optimization/
│   ├── ilma-cqrs-pattern/
│   ├── ilma-csv-processing/
│   ├── ilma-dashboard-design/
│   ├── ilma-data-analysis/
│   ├── ilma-database-migration/
│   ├── ilma-database-patterns/
│   ├── ilma-database-replication/
│   ├── ilma-data-mesh/
│   ├── ilma-data-pipeline/
│   ├── ilma-data-warehouse/
│   ├── ilma-ddd-patterns/
│   ├── ilma-dead-letter-queue/
│   ├── ilma-debug/
│   ├── ilma-dependency-management/
│   ├── ilma-deployment-patterns/
│   ├── ilma-diagnostics/
│   ├── ilma-disaster-recovery/
│   ├── ilma-django-patterns/
│   ├── ilma-dns-patterns/
│   ├── ilma-docker-compose/
│   ├── ilma-docker-patterns/
│   ├── ilma-documentation/
│   ├── ilma-domain-checker/
│   ├── ilma-e2e-testing/
│   ├── ilma-edge-computing/
│   ├── ilma-eks-patterns/
│   ├── ilma-elasticsearch-patterns/
│   ├── ilma-email-patterns/
│   ├── ilma-error-handling/
│   ├── ilma-event-driven/
│   ├── ilma-event-sourcing/
│   ├── ilma-evolution/
│   ├── ilma-evolution-routine/
│   ├── ilma-fastapi-patterns/
│   ├── ilma-feature-flags/
│   ├── ilma-feature-store/
│   ├── ilma-file-processing/
│   ├── ilma-fine-tuning/
│   ├── ilma-firewall-patterns/
│   ├── ilma-flask-patterns/
│   ├── ilma-frontend-patterns/
│   ├── ilma-geospatial/
│   ├── ilma-git-automation/
│   ├── ilma-github-actions/
│   ├── ilma-gitlab-ci/
│   ├── ilma-gitops/
│   ├── ilma-git-workflow/
│   ├── ilma-graphql-patterns/
│   ├── ilma-grpc-patterns/
│   ├── ilma-health-check-pattern/
│   ├── ilma-health-monitor/
│   ├── ilma-helm-patterns/
│   ├── ilma-hexagonal-architecture/
│   ├── ilma-http-client/
│   ├── ilma-http-patterns/
│   ├── ilma-huggingface-patterns/
│   ├── ilma-incident-management/
│   ├── ilma-incident-response/
│   ├── ilma-indonesian-nlp/
│   ├── ilma-infrastructure-as-code/
│   ├── ilma-infrastructure-automation/
│   ├── ilma-iot-patterns/
│   ├── ilma-iot-security/
│   ├── ilma-jenkins-pipeline/
│   ├── ilma-json-processing/
│   ├── ilma-jwt-patterns/
│   ├── ilma-kafka-patterns/
│   ├── ilma-kpi-tracking/
│   ├── ilma-kubernetes-patterns/
│   ├── ilma-lambda-patterns/
│   ├── ilma-langchain-patterns/
│   ├── ilma-learning/
│   ├── ilma-learning-engine/
│   ├── ilma-lifecycle-manager/
│   ├── ilma-llm-evaluation/
│   ├── ilma-load-balancer-patterns/
│   ├── ilma-load-balancing/
│   ├── ilma-logging-patterns/
│   ├── ilma-master-orchestrator/
│   ├── ilma-materialized-views/
│   ├── ilma-memory/
│   ├── ilma-message-queue/
│   ├── ilma-meta-learning/
│   ├── ilma-microservices-communication/
│   ├── ilma-ml-patterns/
│   ├── ilma-ml-pipeline/
│   ├── ilma-model-serving/
│   ├── ilma-mongodb-patterns/
│   ├── ilma-monitoring-alerting/
│   ├── ilma-mqtt-patterns/
│   ├── ilma-multi-agent/
│   ├── ilma-multi-tenancy/
│   ├── ilma-mysql-patterns/
│   ├── ilma-network-monitoring/
│   ├── ilma-network-security/
│   ├── ilma-nextjs-patterns/
│   ├── ilma-nodejs-patterns/
│   ├── ilma-nosql-patterns/
│   ├── ilma-oauth-patterns/
│   ├── ilma-observability/
│   ├── ilma-observability-stack/
│   ├── ilma-outbox-pattern/
│   ├── ilma-parquet-patterns/
│   ├── ilma-pattern-recognition/
│   ├── ilma-penetration-testing/
│   ├── ilma-performance-optimizer/
│   ├── ilma-performance-testing/
│   ├── ilma-planning/
│   ├── ilma-playwright-stealth/
│   ├── ilma-postgresql-patterns/
│   ├── ilma-problem-solve/
│   ├── ilma-prompt-engineering/
│   ├── ilma-python-patterns/
│   ├── ilma-pytorch-patterns/
│   ├── ilma-quality-gates/
│   ├── ilma-quick-answer/
│   ├── ilma-rabbitmq-patterns/
│   ├── ilma-rag-patterns/
│   ├── ilma-rate-limiting/
│   ├── ilma-react-patterns/
│   ├── ilma-real-time-analytics/
│   ├── ilma-reasoning/
│   ├── ilma-redis-patterns/
│   ├── ilma-refactor-cleaner/
│   ├── ilma-release-automation/
│   ├── ilma-research/
│   ├── ilma-rest-patterns/
│   ├── ilma-retry-patterns/
│   ├── ilma-reverse-proxy-patterns/
│   ├── ilma-review-checklist/
│   ├── ilma-rolling-deployment/
│   ├── ilma-rules-engine/
│   ├── ilma-s3-patterns/
│   ├── ilma-saga-pattern/
│   ├── ilma-schema-registry/
│   ├── ilma-search-patterns/
│   ├── ilma-secrets-management/
│   ├── ilma-security-audit/
│   ├── ilma-security-patterns/
│   ├── ilma-security-testing/
│   ├── ilma-self-improve/
│   ├── ilma-sensor-data/
│   ├── ilma-serialization/
│   ├── ilma-serverless-patterns/
│   ├── ilma-service-discovery/
│   ├── ilma-service-mesh/
│   ├── ilma-sharding-patterns/
│   ├── ilma-sidecar-pattern/
│   ├── ilma-skill-trigger-system/
│   ├── ilma-spark-patterns/
│   ├── ilma-sqlite-patterns/
│   ├── ilma-sre-patterns/
│   ├── ilma-ssl-tls/
│   ├── ilma-strangler-fig/
│   ├── ilma-streaming/
│   ├── ilma-system-integrator/
│   ├── ilma-tcp-ip-patterns/
│   ├── ilma-tech-debt/
│   ├── ilma-tensorflow-patterns/
│   ├── ilma-terraform-patterns/
│   ├── ilma-test-automation/
│   ├── ilma-testing/
│   ├── ilma-testing-strategies/
│   ├── ilma-threat-modeling/
│   ├── ilma-time-series/
│   ├── ilma-vector-db/
│   ├── ilma-versioning-patterns/
│   ├── ilma-vpn-patterns/
│   ├── ilma-vue-patterns/
│   ├── ilma-webhook/
│   ├── ilma-webhook-patterns/
│   ├── ilma-web-scraping/
│   ├── ilma-websocket/
│   ├── ilma-websocket-patterns/
│   ├── ilma-writing/
│   └── ilma-xml-processing/
│
│   ├── ═══ EXTERNAL SKILLS (31 categories) ═══
│   │
│   ├── agent-evolution/
│   ├── apple/
│   ├── autonomous-ai-agents/
│   ├── core/
│   ├── creative/
│   ├── data-science/
│   ├── devops/
│   ├── diagramming/
│   ├── dogfood/
│   ├── domain/
│   ├── email/
│   ├── feeds/
│   ├── gaming/
│   ├── gifs/
│   ├── github/
│   ├── hermes-ingested/
│   ├── inference-sh/
│   ├── leisure/
│   ├── mcp/
│   ├── media/
│   ├── mlops/
│   ├── note-taking/
│   ├── productivity/
│   ├── red-teaming/
│   ├── research/
│   ├── self-improvement/
│   ├── smart-home/
│   ├── social-media/
│   ├── software-development/
│   └── system-administration/
│
├── ═══ SYSTEM SCRIPTS ═══
│
├── ilma_system_status.sh           # Health check script
├── ilma_bootstrap.sh               # Quick startup script
├── ilma_integration_manifest.json   # Complete component inventory
├── ilma_architecture_diagram.txt   # ASCII architecture diagram
│
└── ═══ CACHE DIRECTORIES ═══
│
/root/.cache/ilma/
├── evidence/                      # Evidence captures
│   └── [event_type]_[timestamp].json
├── learning/
│   └── learning_events.jsonl      # Learning events log
└── router_execution_log.jsonl     # Router execution log
```

---

## 🔗 EXTERNAL INTEGRATIONS

| External System | Integration Point | Purpose |
|-----------------|-------------------|---------|
| AYDA Scripts | /root/.openclaw/workspace/scripts/ | Fallback script execution |
| Provider Intel | PROVIDER_INTELLIGENCE_MASTER.json | Model benchmark data |
| ClawhHub | skills/ directory | Skill discovery |
| Hermes Agent | Parent profile | Memory specialist role |

---

## ✅ STATUS INDICATORS

- ✅ CANONICAL = Komponen utama, tidak boleh di-deprecate
- ✅ INTEGRATED = Terintegrasi dari sumber eksternal
- ✅ ACTIVE = Komponen berfungsi dan digunakan
- ⚠️ DEPRECATED = Masih berfungsi tapi akan dihapus
- 💀 BROKEN = Tidak berfungsi atau dependensi hilang
- 🔗 ORPHAN = Tidak lagi direferensikan oleh komponen lain

---

## 📊 COMPONENT STATISTICS

| Category | Count | Status |
|----------|-------|--------|
| Core Scripts | 9 | ✅ ACTIVE |
| Skill Directories | 253 | ✅ ACTIVE |
| Data Files | 7 | ⚠️ 1 BROKEN |
| Documentation | 5 | ✅ ACTIVE |
| System Scripts | 3 | ✅ ACTIVE |
| **Total** | **277** | |

---

*Last Updated: 2026-05-08*
