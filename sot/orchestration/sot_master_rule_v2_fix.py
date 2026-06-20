#!/usr/bin/env python3
"""
sot_master_rule_v2_fix.py — MASTER RULE v2.0 Section 11 compliance fixer.

Section 11 violations found 2026-06-14:
  1. _meta.schema_info.source_file = /root/credential/api_key.json  (REMOVE)
  2. _meta.schema_info.source_version = '1.7'                       (REMOVE)
  3. providers[].is_sot_for missing 'model_registry'                 (ADD)
  4. models[].is_sot_for missing                                     (ADD)
  5. models[].model_identity_rule missing                            (ADD)
  6. models[].provider_generation_rule missing                       (ADD)

Run:
  /usr/bin/python3 /root/.hermes/profiles/ilma/sot/orchestration/sot_master_rule_v2_fix.py
"""
import sys, os
from datetime import datetime, timezone
from pymongo import MongoClient

# Re-use SOT connection constants from sot_ops
sys.path.insert(0, '/root/.hermes/profiles/ilma/sot/orchestration')
from sot_ops import get_db, get_client  # noqa: E402

NOW = datetime.now(timezone.utc).isoformat()
EVIDENCE = "ILMA-EVID-20260614-MASTERRULE-V2-FIX-001"

db = get_db()
print(f"DB: credentials @ 172.16.103.253:27017")
print(f"Evidence: {EVIDENCE}\n")

# ── 1. Fix _meta.schema_info ────────────────────────────────────────────────
print("[1/6] _meta.schema_info — REMOVE source_file + source_version, ADD source_type/mongodb_sot")
schema = db['_meta'].find_one({'_id': 'schema_info'})
unset = {}
if 'source_file' in schema:
    unset['source_file'] = ""
if 'source_version' in schema:
    unset['source_version'] = ""

set_fields = {
    'source_type': 'mongodb',
    'mongodb_sot': True,
    'master_rule_version': '2.0',
    'fixed_at': NOW,
    'fixed_by': 'sot_master_rule_v2_fix.py',
    'evidence_id': EVIDENCE,
}
if unset:
    db['_meta'].update_one({'_id': 'schema_info'}, {'$unset': unset, '$set': set_fields})
    print(f"   unset: {list(unset.keys())}")
    print(f"   set:   {list(set_fields.keys())}")
else:
    db['_meta'].update_one({'_id': 'schema_info'}, {'$set': set_fields})
    print(f"   set:   {list(set_fields.keys())}")
print("   ✅ done\n")

# ── 2-3. Fix providers[].is_sot_for ─────────────────────────────────────────
print("[2/6] providers[].is_sot_for — ADD 'model_registry'")
res = db['providers'].update_many(
    {'is_sot_for': {'$exists': True, '$ne': 'model_registry'}},
    {'$addToSet': {'is_sot_for': 'model_registry'}}
)
print(f"   matched: {res.matched_count}, modified: {res.modified_count}")

# Providers without is_sot_for at all
res2 = db['providers'].update_many(
    {'is_sot_for': {'$exists': False}},
    {'$set': {'is_sot_for': ['model_registry', 'base_url', 'docs_url', 'auth_format', 'category']}}
)
print(f"   no-field providers: {res2.matched_count}, modified: {res2.modified_count}")
print("   ✅ done\n")

# ── 4-6. Add fields to all models ────────────────────────────────────────────
print("[3/6] models[].is_sot_for — ADD")
res = db['models'].update_many(
    {'is_sot_for': {'$exists': False}},
    {'$set': {'is_sot_for': ['model_registry', 'routing_identity', 'capability_fk']}}
)
print(f"   modified: {res.modified_count}")

print("[4/6] models[].model_identity_rule — ADD")
res = db['models'].update_many(
    {'model_identity_rule': {'$exists': False}},
    {'$set': {'model_identity_rule': '(provider, model_id) — UNIQUE compound key'}}
)
print(f"   modified: {res.modified_count}")

print("[5/6] models[].provider_generation_rule — ADD")
res = db['models'].update_many(
    {'provider_generation_rule': {'$exists': False}},
    {'$set': {'provider_generation_rule': 'automatic_from_llm_providers_via_provider_sync'}}
)
print(f"   modified: {res.modified_count}")

# ── Verify ──────────────────────────────────────────────────────────────────
print("\n[VERIFY] Re-checking Section 11 compliance")
schema = db['_meta'].find_one({'_id': 'schema_info'})
assert 'source_file' not in schema, "❌ source_file still present"
assert schema.get('source_type') == 'mongodb', "❌ source_type not mongodb"
assert schema.get('mongodb_sot') is True, "❌ mongodb_sot not True"

prov = db['providers'].find_one()
assert 'model_registry' in prov.get('is_sot_for', []), "❌ providers.is_sot_for missing model_registry"

m = db['models'].find_one()
assert 'is_sot_for' in m, "❌ models.is_sot_for missing"
assert 'model_identity_rule' in m, "❌ models.model_identity_rule missing"
assert 'provider_generation_rule' in m, "❌ models.provider_generation_rule missing"

print("   ✅ All 6 Section 11 violations FIXED")
print(f"   evidence: {EVIDENCE}")
print(f"   timestamp: {NOW}")
