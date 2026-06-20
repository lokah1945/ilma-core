#!/usr/bin/env python3
"""
Query ILMA SOT for FREE + ACTIVE candidates of a given capability,
rank by score_tier then score, and print top N.

Usage:
  python3 sot_pick_free.py --cap image --top 5
  python3 sot_pick_free.py --cap tts --top 3
  python3 sot_pick_free.py --cap image --include-paid --top 10
"""
from __future__ import annotations
import argparse, json, os, sys
from pymongo import MongoClient

DEFAULT_HOST = "172.16.103.253"
DEFAULT_PORT = 27017
DEFAULT_USER = "quantumtraffic"
ADMIN_AUTH_DB = "admin"

TIER_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "": 4, None: 5}


def _mongo_pass() -> str:
    p = ""
    for line in open("/root/.hermes/.env"):
        if line.startswith("ILMA_MONGO_PASS="):
            p = line.split("=", 1)[1].strip()
            break
    return p


def get_client() -> MongoClient:
    return MongoClient(
        host=os.environ.get("SOT_MONGO_HOST", DEFAULT_HOST),
        port=int(os.environ.get("SOT_MONGO_PORT", DEFAULT_PORT)),
        username=os.environ.get("SOT_MONGO_USER", DEFAULT_USER),
        password=_mongo_pass(),
        authSource=ADMIN_AUTH_DB,
        directConnection=True,
        serverSelectionTimeoutMS=8000,
    )


def candidates_for_capability(db, cap: str, free_only: bool = True):
    """Match either capabilities=cap OR model_id regex match."""
    q = {
        "$or": [
            {"capabilities": cap},
            {"model_id": {"$regex": cap, "$options": "i"}},
        ],
        "status": "active",
        "is_active": True,
    }
    if free_only:
        q["is_free"] = True
    return list(db.models.find(q, {"_id": 0}))


def rank(models):
    return sorted(
        models,
        key=lambda m: (
            TIER_ORDER.get(m.get("score_tier"), 5),
            -float(m.get("score") or 0),
        ),
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cap", required=True, help="capability to filter (image/tts/embed/vision/...)")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--include-paid", action="store_true", help="do not filter by is_free")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()

    client = get_client()
    db = client["credentials"]
    try:
        candidates = candidates_for_capability(db, args.cap, free_only=not args.include_paid)
    finally:
        client.close()

    if not candidates:
        print(f"NO candidates for cap={args.cap} (free_only={not args.include_paid})")
        sys.exit(0)

    ranked = rank(candidates)[: args.top]

    if args.json:
        print(json.dumps(ranked, default=str, indent=2))
        return

    print(f"cap={args.cap}  free_only={not args.include_paid}  total={len(candidates)}  top={len(ranked)}")
    print(f"{'rank':>4}  {'tier':4} {'score':7} {'free':5}  provider/model_id")
    for i, m in enumerate(ranked, 1):
        tier = m.get("score_tier") or "-"
        score = m.get("score") or 0
        free = m.get("is_free") or False
        mid = m.get("model_id") or "?"
        pr = m.get("provider") or "?"
        print(f"{i:>4}  {tier:4} {score:7.2f} {'TRUE' if free else 'FALSE':5}  {pr}/{mid}")


if __name__ == "__main__":
    main()
