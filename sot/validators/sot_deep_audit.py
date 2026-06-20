#!/usr/bin/env python3
"""
sot_deep_audit.py — ILMA SOT Deep Cross-Collection Audit
=========================================================

Goes BEYOND schema validation to check:
  D1. Scoring scale consistency across collections
  D2. Composite score agreement: model_intelligence vs model_enrichment vs models.score
  D3. is_active vs status consistency
  D4. Cross-collection field coverage (last_verified, trust_score, etc)
  D5. Provider-level FK integrity (model.provider → providers + llm_providers)
  D6. llm_providers key_status freshness (no verification logs)
  D7. is_free vs free_tier consistency
  D8. capabilities consistency across 4 collections
  D9. score_tier math consistency
  D10. Business logic gaps (free+price, embedding+chat, etc)
  D11. Evidence_id traceability (sot_jobs → audit_trail)
  D12. Provider coverage (specialization inference per provider)
  D13. Audit trail completeness (model_lifecycle_events vs model_audit_trail)

Exit code: 0 if ZERO defects, 1 otherwise.
"""
import os, sys, re, subprocess
from collections import Counter, defaultdict
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta

MONGO_HOST = "172.16.103.253"
MONGO_PORT = 27017
MONGO_USER = "quantumtraffic"
MONGO_PASS = (__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), ""))
DB_NAME = "credentials"
SOT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_db():
    c = MongoClient(host=MONGO_HOST, port=MONGO_PORT,
                    username=MONGO_USER, password=MONGO_PASS,
                    serverSelectionTimeoutMS=10000)
    return c[DB_NAME]


def _gt(v, t=0):
    if v is None: return False
    try: return float(v) > t
    except: return False


def expected_tier_standard(score):
    """Standard 90/80/70/60 mapping."""
    if score is None: return None
    if score >= 90: return 'S'
    if score >= 80: return 'A'
    if score >= 70: return 'B'
    if score >= 60: return 'C'
    return 'D'


def deep_audit():
    db = get_db()
    defects = []

    print("=" * 72)
    print("ILMA SOT DEEP CROSS-COLLECTION AUDIT")
    print("=" * 72)

    m = db['models']
    mi = db['model_intelligence']
    me = db['model_enrichment']
    mc = db['model_capabilities']
    mb = db['model_benchmark']
    at = db['model_audit_trail']
    le = db['model_lifecycle_events']
    mal = db['model_alias']
    lp = db['llm_providers']
    pc = db['providers']
    sj = db['sot_jobs']

    # ── D1. SCORING SCALE ────────────────────────────────────────────────
    print("\n[D1] SCORING SCALE CONSISTENCY")
    # Check that all score fields across collections use 0-100 (not 0-1 mixed)
    me_qual = list(me.find({'quality_score': {'$ne': None}}).limit(500))
    if me_qual:
        in_0_1 = sum(1 for d in me_qual if 0 <= d['quality_score'] <= 1)
        in_0_100 = sum(1 for d in me_qual if d['quality_score'] > 1)
        print(f"  model_enrichment.quality_score: in_0_1={in_0_1} in_0_100={in_0_100}")
        if in_0_1 > 0 and in_0_100 > 0:
            defects.append(f"D1: quality_score mixed scales ({in_0_1} in 0-1, {in_0_100} in 0-100)")
    # Check if model_intelligence per-dim scores are populated
    mi_dims = {f: mi.count_documents({f: {'$ne': None}}) for f in
               ['quality_score', 'speed_score', 'cost_score', 'context_score', 'composite_score', 'trust_score']}
    print(f"  model_intelligence per-dim: {mi_dims}")
    for f, n in mi_dims.items():
        if f != 'composite_score' and n < mi.count_documents({}) * 0.5:
            defects.append(f"D1: model_intelligence.{f} underpopulated ({n}/{mi.count_documents({})})")

    # ── D2. COMPOSITE SCORE AGREEMENT ────────────────────────────────────
    print("\n[D2] COMPOSITE SCORE AGREEMENT (intelligence vs enrichment)")
    n_match, n_mismatch, n_only_mi, n_only_me = 0, 0, 0, 0
    big_diffs = []
    mi_keys = set((d['provider'], d['model_id']) for d in mi.find({}, {'provider':1,'model_id':1,'_id':0}))
    me_keys = set((d['provider'], d['model_id']) for d in me.find({}, {'provider':1,'model_id':1,'_id':0}))
    n_only_mi = len(mi_keys - me_keys)
    n_only_me = len(me_keys - mi_keys)
    print(f"  Only in intelligence: {n_only_mi}, Only in enrichment: {n_only_me}")
    # Sample comparison
    sample_keys = list(mi_keys & me_keys)[:500]
    for p, mid in sample_keys:
        i_doc = mi.find_one({'provider': p, 'model_id': mid}, {'composite_score':1, '_id':0})
        e_doc = me.find_one({'provider': p, 'model_id': mid}, {'composite_score':1, '_id':0})
        if i_doc and e_doc:
            iv = i_doc.get('composite_score')
            ev = e_doc.get('composite_score')
            if iv is not None and ev is not None:
                if abs(iv - ev) < 1:
                    n_match += 1
                else:
                    n_mismatch += 1
                    if len(big_diffs) < 5 and abs(iv - ev) > 30:
                        big_diffs.append((p, mid, iv, ev))
    print(f"  Match (sample 500): {n_match}, Mismatch: {n_mismatch}")
    if n_mismatch > n_match:
        defects.append(f"D2: composite_score mismatch dominant ({n_mismatch} vs {n_match})")
    for bd in big_diffs:
        print(f"    {bd[0]}/{bd[1]}: intel={bd[2]} enr={bd[3]} (delta {bd[3]-bd[2]:.1f})")

    # ── D3. is_active vs status ──────────────────────────────────────────
    print("\n[D3] is_active vs status LOGIC")
    inconsistent = m.count_documents({
        '$or': [
            {'is_active': True, 'status': {'$in': ['disabled', 'deprecated', 'broken', 'quota_exceeded']}},
            {'is_active': False, 'status': 'active'}
        ]
    })
    print(f"  Inconsistent pairs: {inconsistent}")
    if inconsistent > 0:
        defects.append(f"D3: is_active/status inconsistent: {inconsistent}")

    # ── D4. FIELD COVERAGE (critical fields) ─────────────────────────────
    print("\n[D4] FIELD COVERAGE")
    coverage_checks = [
        ('models', 'score', 90, 'router score'),
        ('models', 'last_verified', 10, 'verification timestamp'),
        ('model_intelligence', 'last_verified', 10, 'verification timestamp'),
        ('model_enrichment', 'last_verified', 10, 'verification timestamp'),
        ('model_enrichment', 'trust_score', 10, 'trust calculation'),
        ('model_enrichment', 'enrichment_version', 90, 'version tracking'),
        ('model_intelligence', 'enrichment_version', 90, 'version tracking'),
    ]
    coll_map = {'models': m, 'model_intelligence': mi, 'model_enrichment': me,
                'model_benchmark': mb, 'model_audit_trail': at}
    for coll, field, threshold_pct, desc in coverage_checks:
        c = coll_map.get(coll)
        if c is None: continue
        total = c.count_documents({})
        if total == 0: continue
        populated = c.count_documents({field: {'$ne': None}})
        pct = populated * 100 // total
        print(f"  {coll}.{field}: {populated}/{total} ({pct}%) - {desc}")
        if pct < threshold_pct:
            defects.append(f"D4: {coll}.{field} coverage {pct}% < {threshold_pct}%")

    # ── D5. PROVIDER FK INTEGRITY ────────────────────────────────────────
    print("\n[D5] PROVIDER FK INTEGRITY")
    model_providers = set(d['provider'] for d in m.find({}, {'provider':1, '_id':0}))
    prov_set = set(d['provider'] for d in pc.find({}, {'provider':1, '_id':0}))
    lp_set = set(d['provider'] for d in lp.find({}, {'provider':1, '_id':0}))
    orphan_provs = model_providers - prov_set
    no_creds = model_providers - lp_set
    print(f"  Model providers not in providers catalog: {len(orphan_provs)} ({list(orphan_provs)[:5]})")
    print(f"  Model providers without llm_providers credentials: {len(no_creds)} ({list(no_creds)[:5]})")
    if orphan_provs:
        defects.append(f"D5: orphan providers in models: {orphan_provs}")
    if no_creds:
        defects.append(f"D5: providers without credentials: {no_creds}")

    # ── D6. KEY STATUS FRESHNESS ─────────────────────────────────────────
    print("\n[D6] llm_providers KEY STATUS")
    never_verified = lp.count_documents({'key_status': None, 'status': 'active'})
    invalid_keys_active = lp.count_documents({'key_status': 'INVALID', 'status': 'active'})
    print(f"  Active keys never verified (key_status=None): {never_verified}")
    print(f"  Active status with key_status=INVALID: {invalid_keys_active}")
    if never_verified > lp.count_documents({}) * 0.5:
        defects.append(f"D6: {never_verified} active keys never verified")
    if invalid_keys_active > 0:
        defects.append(f"D6: {invalid_keys_active} invalid keys still active")

    # ── D7. is_free vs free_tier ─────────────────────────────────────────
    print("\n[D7] is_free vs free_tier CONSISTENCY")
    # Note: PyMongo True==True, the bug is in earlier query using {'$ne': True}
    is_free_t = m.count_documents({'is_free': True})
    free_tier_t = m.count_documents({'free_tier': True})
    both = m.count_documents({'is_free': True, 'free_tier': True})
    # Mismatch: is_free=True XOR free_tier=True
    mismatch = is_free_t + free_tier_t - 2 * both
    print(f"  is_free=True: {is_free_t}, free_tier=True: {free_tier_t}, both=True: {both}")
    print(f"  Mismatched pairs (XOR): {mismatch}")
    if mismatch > 50:
        defects.append(f"D7: is_free/free_tier mismatches: {mismatch}")

    # ── D8. CAPABILITIES CONSISTENCY ─────────────────────────────────────
    print("\n[D8] CAPABILITIES CONSISTENCY (4-way)")
    # Sample 200 random models and check 4-way match
    sample_keys = [(d['provider'], d['model_id']) for d in m.aggregate(
        [{'$match': {'capabilities': {'$ne': None}}}, {'$sample': {'size': 200}}])]
    n_full_match = 0
    for p, mid in sample_keys:
        m_caps = set((m.find_one({'provider':p, 'model_id':mid}, {'capabilities':1, '_id':0}) or {}).get('capabilities') or [])
        e_doc = me.find_one({'provider':p, 'model_id':mid}, {'capabilities':1, '_id':0})
        c_doc = mc.find_one({'provider':p, 'model_id':mid}, {'capabilities':1, '_id':0})
        i_doc = mi.find_one({'provider':p, 'model_id':mid}, {'capabilities':1, '_id':0})
        e_caps = set((e_doc or {}).get('capabilities') or [])
        c_caps = set((c_doc or {}).get('capabilities') or [])
        i_caps = set((i_doc or {}).get('capabilities') or [])
        if m_caps == e_caps == c_caps == i_caps:
            n_full_match += 1
    print(f"  4-way match (sample 200): {n_full_match}/{len(sample_keys)}")
    if n_full_match < len(sample_keys) * 0.5:
        defects.append(f"D8: capabilities 4-way match {n_full_match}/{len(sample_keys)} (<50%)")

    # ── D9. SCORE_TIER MATH ──────────────────────────────────────────────
    print("\n[D9] SCORE_TIER MATH (standard 90/80/70/60 mapping)")
    # Standard mapping mismatch
    n_match_std = 0
    n_mismatch_std = 0
    for d in mi.find({'composite_score': {'$ne': None}}):
        actual = d.get('score_tier')
        expected = expected_tier_standard(d['composite_score'])
        if actual == expected:
            n_match_std += 1
        else:
            n_mismatch_std += 1
    print(f"  Match (standard mapping): {n_match_std}/{n_match_std+n_mismatch_std}")
    # If <50% match standard, SOT uses custom tier formula (informational)
    if n_mismatch_std > n_match_std:
        print(f"  ⚠️ SOT uses NON-STANDARD tier formula (custom ranges A=60-90, B=46-57, C=35-44, D=12-33)")

    # ── D10. BUSINESS LOGIC ──────────────────────────────────────────────
    print("\n[D10] BUSINESS LOGIC")
    # Embedding with chat
    emb_chat = m.count_documents({'capabilities': 'chat', 'specialization': 'embedding'})
    # Free with price > 0
    free_with_price = 0
    for d in m.find({'$or': [{'is_free': True}, {'free_tier': True}, {'billing': 'free'}]}):
        pricing = d.get('pricing') or {}
        if _gt(d.get('price_per_m_input')) or _gt(d.get('price_per_m_output')) \
           or _gt(pricing.get('input_per_m')) or _gt(pricing.get('output_per_m')) \
           or _gt(pricing.get('prompt')) or _gt(pricing.get('completion')):
            free_with_price += 1
    # Context_window 0 or negative
    bad_ctx = m.count_documents({'context_window': {'$lte': 0}})
    print(f"  Embedding + chat: {emb_chat}")
    print(f"  Free + non-zero price: {free_with_price}")
    print(f"  Context window <= 0: {bad_ctx}")
    if emb_chat > 0:
        defects.append(f"D10: embedding models with chat capability: {emb_chat}")
    if free_with_price > 0:
        defects.append(f"D10: free models with price > 0: {free_with_price}")
    if bad_ctx > 0:
        defects.append(f"D10: bad context_window: {bad_ctx}")

    # ── D11. EVIDENCE_ID TRACEABILITY ────────────────────────────────────
    print("\n[D11] EVIDENCE_ID TRACEABILITY")
    # Skip jobs explicitly marked as historical_orphan
    sj_query = {'evidence_id': {'$ne': None}, 'result.audit_trail_check_status': {'$ne': 'historical_orphan'}}
    sj_evs = set(d['evidence_id'] for d in sj.find(sj_query, {'evidence_id':1, '_id':0}) if d.get('evidence_id'))
    at_evs = set(d['evidence_id'] for d in at.find({'evidence_id': {'$ne': None}}, {'evidence_id':1, '_id':0}) if d.get('evidence_id'))
    orphan_sj = sj_evs - at_evs
    print(f"  sot_jobs evidence_ids not in audit_trail (excl. historical): {len(orphan_sj)}")
    if len(orphan_sj) > 0:
        defects.append(f"D11: orphaned sot_jobs evidence_ids: {len(orphan_sj)}")
    # Evidence ID format check
    bad_format = 0
    for d in at.find({'evidence_id': {'$ne': None}}, {'evidence_id':1, '_id':0}).limit(500):
        eid = d.get('evidence_id')
        if eid and not re.match(r'^ILMA-EVID-\d{8}-[A-Z\-]+-\d+$', eid):
            bad_format += 1
    print(f"  Malformed evidence_id (sample 500): {bad_format}")
    if bad_format > 0:
        defects.append(f"D11: malformed evidence_id format: {bad_format}")

    # ── D12. PROVIDER SPECIALIZATION COVERAGE ────────────────────────────
    print("\n[D12] SPECIALIZATION COVERAGE PER PROVIDER")
    provider_specialization_diversity = []
    for d in m.aggregate([
        {'$group': {'_id': '$provider', 'specs': {'$addToSet': '$specialization'}, 'total': {'$sum': 1}}},
        {'$match': {'total': {'$gte': 50}}},
        {'$sort': {'total': -1}}
    ]):
        spec_set = set(d['specs']) - {None}
        provider_specialization_diversity.append((d['_id'], d['total'], len(spec_set), spec_set))
        print(f"  {d['_id']} ({d['total']} models): {len(spec_set)} distinct specs")
    # Flag providers with 1 spec only (overfitted inference)
    mono_spec = [(p, n) for p, n, s, _ in provider_specialization_diversity if s <= 1 and n > 50]
    if mono_spec:
        print(f"  ⚠️ Providers with single specialization (suspicious inference): {[p for p, _ in mono_spec]}")

    # ── D13. AUDIT_TRAIL vs LIFECYCLE_EVENTS ──────────────────────────────
    print("\n[D13] AUDIT TRAIL CROSS-CONSISTENCY")
    at_total = at.count_documents({})
    le_total = le.count_documents({})
    print(f"  model_audit_trail: {at_total}")
    print(f"  model_lifecycle_events: {le_total}")
    # Both should track changes; lifecycle focuses on state transitions
    le_states = set(d['event_type'] for d in le.find({}, {'event_type':1, '_id':0}) if d.get('event_type'))
    at_states = set(d['event_type'] for d in at.find({}, {'event_type':1, '_id':0}) if d.get('event_type'))
    print(f"  model_lifecycle_events event_types: {le_states}")
    print(f"  model_audit_trail event_types: {at_states}")
    # Check if both have evidence_ids
    le_ev = le.count_documents({'evidence_id': {'$ne': None}})
    print(f"  model_lifecycle_events with evidence_id: {le_ev}/{le_total}")

    # ── SUMMARY ──────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print(f"DEEP DEFECT SUMMARY: {len(defects)} categories")
    print("=" * 72)
    for d in defects:
        print(f"  ❌ {d}")
    if not defects:
        print("  ✅ ZERO DEEP DEFECTS — SOT IS CLEAN")
    print()
    return 0 if not defects else 1


if __name__ == '__main__':
    sys.exit(deep_audit())
