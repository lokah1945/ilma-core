#!/usr/bin/env python3
"""
sot_billing_classify.py — FINAL free/paid decision baked into the models SOT (T3)
=================================================================================
Bos 2026-06-20: do the free/paid determination ONCE, at sync/enrich time, and store
the FINAL verdict on each `models` doc. Runtime then just reads a boolean — no
per-request computation, no delay. `models` becomes the ready-to-use T3 SOT so that
delegated work (sub-agents, sub-processes, parallel tasks, kanban, etc.) can pick the
best FREE model dynamically and cheaply.

Trap-safe policy (when not explicitly free → PAID):
  1. force_free hardcode (providers.force_free=True)  → FREE  (bypasses all)
  2. paid-keyword in id/name (pro/premium/turbo/...)    → PAID
  3. MIXED providers (openrouter/blackbox/opencode) are trap-prone (price can read $0
     while billing) → FREE only via explicit ':free' or '-free' suffix, else PAID
  4. direct providers → free ONLY via force_free (verified all-free, e.g. nvidia/groq/
     cerebras) or confirmed per-model $0 pricing; the provider-level is_free/free_tier
     flag is NOT trusted (it falsely freed all of paid Together AI). Else PAID.

Writes to each models doc: is_free_final(bool), billing_class('free'|'paid'),
free_reason(str), billing_classified_at.

CLI: python3 sot_billing_classify.py --full | --provider X | --dry-run | --stats
"""
from __future__ import annotations
import os, re, sys, json, time, argparse, logging
from datetime import datetime, timezone
import pymongo

logger = logging.getLogger("ilma.sot.billing")

MONGO = dict(host="172.16.103.253", port=27017, username="quantumtraffic",
             password=(__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), "")), authSource="admin", directConnection=True,
             serverSelectionTimeoutMS=10000)

MIXED_PROVIDERS = {"openrouter", "blackbox", "opencode"}
_PAID_KW = re.compile(r"(^|[/:_\-\s])(paid|premium|pro|enterprise|plus|turbo|max|ultra)($|[/:_\-\s])")
_PRICE_KEYS = ("price_per_m_input", "price_per_m_output",
               "input_cost_per_1m", "output_cost_per_1m")


def get_db():
    return pymongo.MongoClient(**MONGO)["credentials"]


def now_utc():
    return datetime.now(timezone.utc)


def _price(v) -> float:
    if v is None or v == "":
        return 0.0
    if isinstance(v, str):
        s = v.strip().lower().replace("$", "")
        if s in {"", "0", "0.0", "0.00", "free", "none", "null"}:
            return 0.0
        try:
            return float(s)
        except ValueError:
            return 1.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 1.0


def classify(model: dict, force_free: set) -> tuple:
    """Return (billing_class, reason). Mirrors the trap-safe policy."""
    prov = model.get("provider")
    mid = str(model.get("model_id") or "")
    name = str(model.get("model_name") or "")
    midl = mid.lower()
    combined = f"{prov}/{mid} {name}".lower()

    # 1) hardcode override
    if prov in force_free:
        return "free", "force_free:provider"
    # 2) paid keyword
    if _PAID_KW.search(combined):
        return "paid", "paid_keyword"
    # 3) mixed providers — explicit free suffix only (trap-safe)
    if prov in MIXED_PROVIDERS:
        if midl.endswith(":free") or ":free" in midl or midl.endswith("-free"):
            return "free", "mixed_free_suffix"
        return "paid", "mixed_no_free_suffix"
    # 4) direct providers. The provider-level is_free/free_tier flag is UNRELIABLE — it
    #    marks ALL of a provider's models free even on paid providers (e.g. Together AI
    #    is pay-per-token yet every model carried free_tier=True, wrongly freeing 237).
    #    So free requires EITHER force_free (verified all-free provider, handled in rule 1)
    #    OR confirmed per-model $0 pricing (real price fields present and all zero).
    #    No reliable per-model evidence → PAID (Bos policy: when in doubt, paid).
    pricing = model.get("pricing") or {}
    pvals = [pricing.get("input_per_1m"), pricing.get("output_per_1m"),
             pricing.get("prompt"), pricing.get("completion")] + \
            [model.get(k) for k in _PRICE_KEYS]
    present = [v for v in pvals if v is not None]
    if any(_price(v) > 0 for v in present):
        return "paid", "price>0"
    if present and all(_price(v) == 0 for v in present):
        return "free", "confirmed_zero_price"
    return "paid", "no_per_model_price_evidence"


def _force_free_providers(db) -> set:
    return {d["provider"] for d in db.providers.find({"force_free": True}, {"provider": 1})}


def run(provider: str = None, dry_run: bool = False) -> dict:
    db = get_db()
    force_free = _force_free_providers(db)
    q = {} if not provider else {"provider": provider}
    proj = {"provider": 1, "model_id": 1, "model_name": 1, "is_free": 1, "free_tier": 1,
            "pricing": 1, **{k: 1 for k in _PRICE_KEYS}}
    ops, counts, now = [], {"free": 0, "paid": 0}, now_utc()
    reasons = {}
    for m in db.models.find(q, proj):
        cls, reason = classify(m, force_free)
        counts[cls] += 1
        reasons[reason] = reasons.get(reason, 0) + 1
        if dry_run:
            continue
        ops.append(pymongo.UpdateOne(
            {"_id": m["_id"]},
            {"$set": {"is_free_final": cls == "free", "billing_class": cls,
                      "free_reason": reason, "billing_classified_at": now}}))
    if not dry_run and ops:
        for i in range(0, len(ops), 1000):
            db.models.bulk_write(ops[i:i + 1000], ordered=False)
    return {"provider": provider or "ALL", "dry_run": dry_run,
            "free": counts["free"], "paid": counts["paid"], "reasons": reasons}


def stats() -> dict:
    db = get_db()
    return {
        "total": db.models.count_documents({}),
        "is_free_final=True": db.models.count_documents({"is_free_final": True}),
        "is_free_final=False": db.models.count_documents({"is_free_final": False}),
        "unclassified": db.models.count_documents({"is_free_final": {"$exists": False}}),
        "active_free_final": db.models.count_documents({"is_active": True, "is_free_final": True}),
    }


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--provider")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()
    if args.stats:
        print(json.dumps(stats(), indent=2, default=str)); return
    print(json.dumps(run(provider=args.provider, dry_run=args.dry_run), indent=2, default=str))


if __name__ == "__main__":
    main()
