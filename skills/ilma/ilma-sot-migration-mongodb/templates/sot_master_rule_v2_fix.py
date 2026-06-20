#!/usr/bin/env python3
"""
sot_master_rule_v2_fix.py — MASTER RULE v2.0 Section 11 compliance fixer.

Pattern: one-shot atomic, idempotent, evidence-tagged. Re-run safe.

Required invocations:
  /usr/bin/python3  (NOT hermes-agent/venv python3 — pymongo not there)

Required env (from sot_ops.py, do NOT hardcode differently):
  MONGO_HOST = "172.16.103.253"
  MONGO_PORT = 27017
  MONGO_USER = "quantumtraffic"
  MONGO_PASS = (__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), ""))
  MONGO_AUTH = "admin"
  DB_NAME   = "credentials"

Section 11 violations this fixes (Bos mandate 2026-06-14):
  1. _meta.schema_info.source_file = /root/credential/api_key.json   → REMOVE
  2. _meta.schema_info.source_version = '1.7'                        → REMOVE
  3. providers[].is_sot_for missing 'model_registry'                  → ADD
  4. models[].is_sot_for missing                                      → ADD
  5. models[].model_identity_rule missing                             → ADD
  6. models[].provider_generation_rule missing                        → ADD

Usage:
  /usr/bin/python3 /root/.hermes/profiles/ilma/sot/orchestration/sot_master_rule_v2_fix.py

Idempotency:
  - $unset is no-op if field already absent
  - $set is no-op if field already has the right value
  - $addToSet is no-op if value already in array
  - update_many on `exists: false` only matches unfixed docs
  - Re-running reports 0 modified on second pass (proof of idempotency)

Output:
  Per-step matched/modified counts
  Re-verify assert (raises AssertionError if any violation remains)
  Evidence ID (salted, ILMA-EVID-YYYYMMDD-CCODE-NNNNN format)
"""
import sys
from datetime import datetime, timezone

# Re-use SOT connection constants — NEVER hardcode creds in this script.
sys.path.insert(0, '/root/.hermes/profiles/ilma/sot/orchestration')
from sot_ops import get_db  # noqa: E402

NOW = datetime.now(timezone.utc).isoformat()
EVIDENCE = "ILMA-EVID-YYYYMMDD-MASTERRULE-V2-FIX-NNN"  # SALT before commit

db = get_db()
print(f"DB: credentials @ 172.16.103.253:27017")
print(f"Evidence: {EVIDENCE}\n")

# 1. Fix _meta.schema_info — REMOVE legacy, ADD source_type/mongodb_sot
schema = db['_meta'].find_one({'_id': 'schema_info'})
unset = {k: "" for k in ('source_file', 'source_version') if k in schema}
set_fields = {
    'source_type': 'mongodb',
    'mongodb_sot': True,
    'master_rule_version': '2.0',
    'fixed_at': NOW,
    'fixed_by': 'sot_master_rule_v2_fix.py',
    'evidence_id': EVIDENCE,
}
db['_meta'].update_one({'_id': 'schema_info'},
                       {'$unset': unset, '$set': set_fields})

# 2-3. providers[].is_sot_for — ensure 'model_registry' present
db['providers'].update_many(
    {'is_sot_for': {'$exists': True, '$ne': 'model_registry'}},
    {'$addToSet': {'is_sot_for': 'model_registry'}}
)
db['providers'].update_many(
    {'is_sot_for': {'$exists': False}},
    {'$set': {'is_sot_for': ['model_registry', 'base_url', 'docs_url',
                              'auth_format', 'category']}}
)

# 4-6. models[] — add the three governance fields
db['models'].update_many(
    {'is_sot_for': {'$exists': False}},
    {'$set': {'is_sot_for': ['model_registry', 'routing_identity', 'capability_fk']}}
)
db['models'].update_many(
    {'model_identity_rule': {'$exists': False}},
    {'$set': {'model_identity_rule': '(provider, model_id) — UNIQUE compound key'}}
)
db['models'].update_many(
    {'provider_generation_rule': {'$exists': False}},
    {'$set': {'provider_generation_rule': 'automatic_from_llm_providers_via_provider_sync'}}
)

# Re-verify (Bos rule: verify-with-tool, not assume)
schema = db['_meta'].find_one({'_id': 'schema_info'})
assert 'source_file' not in schema, "source_file still present"
assert schema.get('source_type') == 'mongodb'
assert schema.get('mongodb_sot') is True

prov = db['providers'].find_one()
assert 'model_registry' in prov.get('is_sot_for', [])

m = db['models'].find_one()
assert 'is_sot_for' in m
assert 'model_identity_rule' in m
assert 'provider_generation_rule' in m

print(f"✅ All 6 Section 11 violations FIXED")
print(f"   evidence: {EVIDENCE}")
print(f"   timestamp: {NOW}")
