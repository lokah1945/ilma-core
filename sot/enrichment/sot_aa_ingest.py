#!/usr/bin/env python3
"""
sot_aa_ingest.py — Artificial Analysis benchmark ingestion (the AA quality layer)
=================================================================================
Connects Artificial Analysis benchmark data to the `models` collection so the
scorer (sot_ops.compute_score) can produce REAL AA-weighted composite scores
instead of the capability heuristic (which caps at 60 → everything tier D/C).

Source of truth for the AA key: `search_providers` collection (provider=
artificial_analysis), per Bos. Endpoint: AA v2 llms/models.

Pipeline:
  1. fetch 540 AA model records (intelligence/coding/math indices)
  2. match AA slug → internal model_id by normalized name (strip provider prefix,
     ':free' and effort suffixes, alphanumeric-only)
  3. upsert into model_benchmark (benchmark_source='artificial_analysis') with
     aa_intelligence_index / aa_coding_index / aa_math_index
  4. caller then re-runs sot_enrich_models so compute_score picks up benchmark_aa

CLI:
  python3 sot_aa_ingest.py            # fetch + match + write benchmarks
  python3 sot_aa_ingest.py --dry-run  # report match rate only
"""
from __future__ import annotations
import os, sys, re, json, time, argparse, urllib.request
from datetime import datetime, timezone
import pymongo

MONGO = dict(host="127.0.0.1", port=27017, username="ilma_sync",
             password=(__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), "")), authSource="admin", directConnection=True,
             serverSelectionTimeoutMS=10000)
AA_URL = "https://artificialanalysis.ai/api/v2/data/llms/models"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                     "benchmark_aa_cache.json")


def get_db():
    return pymongo.MongoClient(**MONGO)["credentials"]


def _norm(s: str) -> str:
    """Canonical match key: lowercase, drop provider prefix + ':free'/effort suffixes,
    keep alphanumerics only."""
    if not s:
        return ""
    s = s.split("/")[-1]                      # strip provider prefix
    s = s.split(":")[0]                       # strip ':free'
    s = re.sub(r"-(low|high|medium|minimal|reasoning|thinking|instruct|chat)$", "", s.lower())
    return re.sub(r"[^a-z0-9]", "", s)


def fetch_aa(db):
    key = (db.search_providers.find_one({"provider": "artificial_analysis"}) or {}).get("api_key")
    if not key:
        raise RuntimeError("no AA api_key in search_providers")
    req = urllib.request.Request(AA_URL)
    req.add_header("x-api-key", key)
    r = json.load(urllib.request.urlopen(req, timeout=45))
    data = r.get("data") if isinstance(r, dict) else r
    try:
        with open(CACHE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass
    return data


def build_aa_index(records):
    """normalized-name → {ai_index, coding_index, math_index}. Best (max) wins on dup."""
    idx = {}
    for rec in records:
        ev = rec.get("evaluations") or {}
        ai = ev.get("artificial_analysis_intelligence_index")
        code = ev.get("artificial_analysis_coding_index")
        math = ev.get("artificial_analysis_math_index")
        if ai is None and code is None and math is None:
            continue
        entry = {"ai_index": ai, "coding_index": code, "math_index": math}
        for key in {_norm(rec.get("slug")), _norm(rec.get("name"))}:
            if not key:
                continue
            cur = idx.get(key)
            if cur is None or (ai or 0) > (cur.get("ai_index") or 0):
                idx[key] = entry
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    db = get_db()

    records = fetch_aa(db)
    aa_idx = build_aa_index(records)
    print(f"AA records: {len(records)} | with indices: {len(aa_idx)}")

    models = list(db.models.find({"is_active": True}, {"provider": 1, "model_id": 1}))
    matched, now = 0, datetime.now(timezone.utc)
    ops = []
    for m in models:
        nk = _norm(m["model_id"])
        aa = aa_idx.get(nk)
        if not aa:
            continue
        matched += 1
        if args.dry_run:
            continue
        ops.append(pymongo.UpdateOne(
            {"provider": m["provider"], "model_id": m["model_id"],
             "benchmark_source": "artificial_analysis"},
            {"$set": {
                "provider": m["provider"], "model_id": m["model_id"],
                "benchmark_source": "artificial_analysis", "evidence_type": "PROXY",
                "aa_intelligence_index": aa.get("ai_index"),
                "aa_coding_index": aa.get("coding_index"),
                "aa_math_index": aa.get("math_index"),
                "fetched_at": now,
            }}, upsert=True))

    print(f"models active: {len(models)} | AA-matched: {matched} "
          f"({round(100*matched/len(models),1)}%)")
    if args.dry_run:
        print("DRY-RUN: no writes. Re-run without --dry-run, then sot_enrich_models --full.")
        return
    if ops:
        res = db.model_benchmark.bulk_write(ops, ordered=False)
        print(f"wrote AA benchmarks: upserted={res.upserted_count} modified={res.modified_count}")


if __name__ == "__main__":
    main()
