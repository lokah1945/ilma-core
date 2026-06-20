# Database Connection & Adapter Layer

**Created:** 2026-06-09 22:00 WIB
**Status:** Skeleton only — awaiting Phase 1 approval

---

## Connection Pattern (Canonical)

```python
# provider-intelligence/scripts/db/connection.py
from pymongo import MongoClient
import os
import logging

logger = logging.getLogger(__name__)

def get_client() -> MongoClient:
    """Returns a singleton MongoClient. Reuse across the process."""
    uri = os.environ.get('MONGO_URI')
    if uri:
        return MongoClient(uri, serverSelectionTimeoutMS=10000)

    return MongoClient(
        host=os.environ.get('MONGO_HOST', '172.16.103.253'),
        port=int(os.environ.get('MONGO_PORT', '27017')),
        username=os.environ.get('MONGO_USER', 'quantumtraffic'),
        password=os.environ.get('MONGO_PASS'),
        serverSelectionTimeoutMS=10000,
    )

def get_db(db_name: str = 'credentials'):
    """Returns a database handle."""
    return get_client()[db_name]
```

---

## Adapter Skeleton

```python
# provider-intelligence/scripts/db/adapter.py
from pymongo.database import Database
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ILMADBAdapter:
    """Read/write adapter for the 6 provider intelligence collections.

    ACCESS POLICY (per decisions/03-mongodb-access-policy.md):
    - READ-ONLY on: providers, llm_providers, search_providers, infra_providers,
      crypto_exchanges, messaging, sessions, system_credentials, _meta
    - READ+WRITE on: models, model_benchmarks, provider_intelligence,
      runtime_capabilities, enrichment_jobs, discovery_log
    """

    def __init__(self, db: Database = None):
        self.db = db or get_db('credentials')

    # ── PROVIDER DISCOVERY (READ) ─────────────────────────────────────
    def list_active_llm_providers(self) -> List[Dict]:
        return list(self.db['llm_providers'].find(
            {'status': 'active'}, {'_id': 0}
        ))

    def get_provider_metadata(self, provider: str) -> Optional[Dict]:
        return self.db['providers'].find_one(
            {'provider': provider}, {'_id': 0}
        )

    def get_llm_credentials(self, provider: str) -> List[Dict]:
        """Returns all active credentials for a provider (multi-account supported)."""
        return list(self.db['llm_providers'].find(
            {'provider': provider, 'status': 'active'}, {'_id': 0}
        ))

    def get_default_credentials(self, provider: str) -> Optional[Dict]:
        """Picks the first active credential, preferring 'owner' account."""
        creds = self.get_llm_credentials(provider)
        if not creds:
            return None
        owner = [c for c in creds if c.get('account_email') == 'owner']
        return owner[0] if owner else creds[0]

    # ── MODELS (READ+WRITE) ────────────────────────────────────────────
    def upsert_model(self, model_doc: Dict) -> None:
        model_doc.setdefault('discovered_at', datetime.utcnow())
        model_doc.setdefault('is_active', True)
        model_doc.setdefault('status', 'active')
        self.db['models'].update_one(
            {'provider': model_doc['provider'], 'model_id': model_doc['model_id']},
            {'$set': model_doc},
            upsert=True,
        )

    def get_model(self, provider: str, model_id: str) -> Optional[Dict]:
        return self.db['models'].find_one(
            {'provider': provider, 'model_id': model_id}, {'_id': 0}
        )

    def list_models_by_provider(self, provider: str) -> List[Dict]:
        return list(self.db['models'].find(
            {'provider': provider}, {'_id': 0}
        ))

    def mark_model_inactive(self, provider: str, model_id: str, reason: str) -> None:
        self.db['models'].update_one(
            {'provider': provider, 'model_id': model_id},
            {'$set': {'is_active': False, 'status': reason, 'deactivated_at': datetime.utcnow()}},
        )

    # ── BENCHMARKS (READ+WRITE) ────────────────────────────────────────
    def upsert_benchmark(self, bench_doc: Dict) -> None:
        bench_doc.setdefault('fetched_at', datetime.utcnow())
        self.db['model_benchmarks'].update_one(
            {'model_id': bench_doc['model_id'], 'source': bench_doc['source']},
            {'$set': bench_doc},
            upsert=True,
        )

    def get_benchmarks(self, model_id: str) -> List[Dict]:
        return list(self.db['model_benchmarks'].find(
            {'model_id': model_id}, {'_id': 0}
        ))

    # ── INTELLIGENCE (READ+WRITE) ──────────────────────────────────────
    def upsert_intelligence(self, intel_doc: Dict) -> None:
        intel_doc.setdefault('last_enriched_at', datetime.utcnow())
        self.db['provider_intelligence'].update_one(
            {'model_id': intel_doc['model_id']},
            {'$set': intel_doc},
            upsert=True,
        )

    def get_intelligence(self, model_id: str) -> Optional[Dict]:
        return self.db['provider_intelligence'].find_one(
            {'model_id': model_id}, {'_id': 0}
        )

    def list_intelligence_sorted(self, tier: str = None, limit: int = None) -> List[Dict]:
        q = {'score_tier': tier} if tier else {}
        cur = self.db['provider_intelligence'].find(q, {'_id': 0}).sort('composite_score', -1)
        if limit:
            cur = cur.limit(limit)
        return list(cur)

    # ── RUNTIME CAPABILITIES (READ+WRITE) ──────────────────────────────
    def get_runtime_health(self, model_id: str) -> Optional[Dict]:
        return self.db['runtime_capabilities'].find_one(
            {'model_id': model_id}, {'_id': 0}
        )

    def update_runtime_health(self, model_id: str, update: Dict) -> None:
        update['last_health_check'] = datetime.utcnow()
        self.db['runtime_capabilities'].update_one(
            {'model_id': model_id},
            {'$set': update},
            upsert=True,
        )

    def get_circuit_breaker_open_models(self) -> List[Dict]:
        return list(self.db['runtime_capabilities'].find(
            {'circuit_state': 'open'}, {'_id': 0}
        ))

    # ── ENRICHMENT JOBS (READ+WRITE) ───────────────────────────────────
    def start_job(self, job_type: str, triggered_by: str = 'cron') -> str:
        import uuid
        job_id = str(uuid.uuid4())
        self.db['enrichment_jobs'].insert_one({
            'job_id': job_id,
            'job_type': job_type,
            'started_at': datetime.utcnow(),
            'status': 'running',
            'triggered_by': triggered_by,
        })
        return job_id

    def complete_job(self, job_id: str, status: str, stats: Dict = None, errors: List = None) -> None:
        self.db['enrichment_jobs'].update_one(
            {'job_id': job_id},
            {'$set': {
                'completed_at': datetime.utcnow(),
                'status': status,
                'models_processed': (stats or {}).get('models_processed', 0),
                'providers_processed': (stats or {}).get('providers_processed', 0),
                'errors': errors or [],
            }},
        )

    # ── DISCOVERY LOG (READ+WRITE) ─────────────────────────────────────
    def log_discovery(self, log_doc: Dict) -> None:
        log_doc.setdefault('discovered_at', datetime.utcnow())
        self.db['discovery_log'].insert_one(log_doc)
```

---

## Tests (to write)

```python
# provider-intelligence/scripts/db/test_adapter.py
def test_get_default_credentials_prefers_owner():
    ...

def test_upsert_model_idempotent():
    ...

def test_circuit_breaker():
    ...
```

---

## Performance Notes

- All write operations use upsert (idempotent)
- Hot reads (router) should use in-memory cache, not DB (see `runtime/router_adapter.py`)
- Cold reads (admin) can hit DB directly
- Pool size: default (100 max) is fine for our workload
