# Provider Intelligence — Centralized Workspace

**Created:** 2026-06-09 22:00 WIB
**Per:** Bos directive 2026-06-09 21:45 WIB (CENTRALIZATION REQUIREMENT)

---

## Purpose

Single source of truth for ALL provider intelligence code, schemas, jobs, docs, and logs. Eliminates the spread of provider-related logic across `/root/.hermes/profiles/ilma/scripts/ilma_*.py` (20+ files).

---

## Structure

```
provider-intelligence/
├── README.md                         # this file
├── scripts/
│   ├── db/                           # MongoDB access layer
│   │   ├── connection.py             # pymongo client factory + connection patterns
│   │   ├── adapter.py                # ILMADBAdapter (read/write for all 6 collections)
│   │   └── migrations/               # numbered migration scripts
│   │       ├── 001_create_intelligence_collections.py
│   │       ├── 002_populate_models.py
│   │       ├── 003_populate_benchmarks.py
│   │       ├── 004_populate_intelligence.py
│   │       └── 005_populate_runtime.py
│   ├── discovery/                    # Provider discovery
│   │   ├── provider_discoverer.py    # generic discovery from llm_providers
│   │   └── model_lister.py           # call /models endpoint + parse
│   ├── benchmark/                    # Benchmark fetchers
│   │   ├── aa_fetcher.py             # Artificial Analysis scraper
│   │   ├── openrouter_fetcher.py     # OpenRouter model metadata
│   │   └── passive.py                # Passive benchmark from usage logs
│   ├── enrichment/                   # Enrichment engines
│   │   ├── scorer.py                 # Composite score computation
│   │   ├── capability_tagger.py      # Heuristic capability tags
│   │   └── tier_assigner.py          # S/A/B/C/D tier
│   ├── sync/                         # DB ↔ cache sync
│   │   ├── db_to_cache.py            # Materialize MASTER.json from DB
│   │   ├── full_sync.py              # Cron entrypoint
│   │   └── discover_one.py           # Manual single-provider discovery
│   ├── runtime/                      # Runtime adapters
│   │   ├── router_adapter.py         # Hot path: read intelligence, pick model
│   │   ├── parallel_caller.py        # Multi-model parallel testing
│   │   └── health_check.py           # Circuit breaker + health update
│   └── validators/                   # SOT integrity checks
│       ├── gate.py                   # Pre-write validation
│       ├── url_drift_check.py        # RISK-001
│       └── key_health_check.py       # RISK-002
├── schemas/                          # JSON schemas
│   ├── model.schema.json
│   ├── benchmark.schema.json
│   ├── intelligence.schema.json
│   ├── runtime.schema.json
│   ├── enrichment_job.schema.json
│   └── discovery_log.schema.json
├── jobs/                             # Cron job definitions
│   ├── cron.json                     # New job definitions
│   └── pre-commit.py                 # Pre-commit gate
├── cache/                            # Intermediate caches
│   └── aa_scraper/                   # AA scraper output
├── docs/                             # Documentation
│   ├── topology.md
│   ├── schemas.md
│   ├── workflows.md
│   └── risks.md
└── logs/                             # Migration + sync logs
```

---

## Current State (2026-06-09 22:00 WIB)

- ✅ Directory structure created
- ✅ Shared memory docs in `/root/shared-memory/ilma/` reference this workspace
- ❌ Scripts not yet moved from `/root/.hermes/profiles/ilma/scripts/`
- ❌ Schemas not yet written
- ❌ Migrations not yet created

**Phase 1 status:** Awaiting Bos approval to begin coding.

---

## Migration Path (from existing `scripts/`)

| Old (in `scripts/`) | New (in `provider-intelligence/scripts/`) | Status |
|---------------------|-------------------------------------------|--------|
| `ilma_db_pipeline.py` | `scripts/sync/full_sync.py` (rewrite) | Planned |
| `ilma_model_db_manager.py` | `scripts/sync/db_to_cache.py` + `scripts/db/adapter.py` | Planned (rewrite) |
| `ilma_enrich_pim.py` | `scripts/enrichment/scorer.py` | Planned |
| `ilma_spec_db_enrich.py` | `scripts/enrichment/capability_tagger.py` | Planned |
| `ilma_unified_model_router.py` | `scripts/runtime/router_adapter.py` | Planned |
| `ilma_adaptive_model_selector.py` | `scripts/discovery/provider_discoverer.py` | Planned |
| `ilma_benchmark_autoloop.py` | `scripts/benchmark/aa_fetcher.py` | Planned |
| `ilma_openrouter_client.py` | `scripts/benchmark/openrouter_fetcher.py` | Planned |
| `ilma_health_check.py` | `scripts/runtime/health_check.py` | Planned |
| `ilma_claudecode_agent.py` (Phase 71) | `scripts/runtime/parallel_caller.py` | Planned |

Old scripts will be kept (not deleted) as historical reference but bypassed by new code. Cron jobs will be updated to new paths.

---

## Connection Pattern (canonical)

```python
from provider_intelligence.scripts.db.connection import get_db
db = get_db()  # returns client['credentials']
```

Or, for ad-hoc scripts:

```python
from pymongo import MongoClient
import os

client = MongoClient(
    host=os.environ.get('MONGO_HOST', '172.16.103.253'),
    port=int(os.environ.get('MONGO_PORT', '27017')),
    username=os.environ.get('MONGO_USER', 'quantumtraffic'),
    password=os.environ.get('MONGO_PASS'),  # from .env, not hardcoded
    serverSelectionTimeoutMS=10000,
)
db = client['credentials']
```

---

## Related Docs

- `/root/shared-memory/ilma/decisions/04-phase1-decisions-2026-06-09.md`
- `/root/shared-memory/ilma/migration/02-phase1-migration-plan-2026-06-09.md`
- `/root/shared-memory/ilma/workflows/02-phase1-workflows-2026-06-09.md`
- `/root/shared-memory/ilma/risks/02-phase1-risks-2026-06-09.md`
- `/root/shared-memory/ilma/migration/03-dependency-map-2026-06-09.md`
