#!/usr/bin/env python3
"""
sync_providers_from_llm_providers.py — Tier 1 → Tier 2 Cascade
==============================================================

Reads `llm_providers` (frozen credentials) and ensures `providers` collection
(Tier 2 general catalog) reflects them. Multiple keys for the same provider in
`llm_providers` (e.g. nvidia ×3) are CONSOLIDATED into one `providers` record
with `multi_account=True`, `key_count=N`, `act_key_count=M`.

Pipeline contract:
  - Adds/updates providers when llm_providers gains a new (provider, account_email)
  - Marks providers.status based on aggregate of all llm_providers sibling statuses
  - Preserves curated fields (endpoints, description, payload_format) from existing
    providers docs — Tier 2 is curated + cascade-updated
  - Runs idempotent — re-running yields the same end state
  - Per-provider fail-safe: each provider handled in own try/except

Aggregation rules for `status`:
  - If any sibling llm_providers doc has key_status='VALID' or 'UNVERIFIED' and
    api_key present → status='active'
  - Else → status='INVALID'

Pre-req:
  - Run after llm_providers schema has been slimmed (this script tolerates
    legacy fields during transition).

Usage:
  python3 sync_providers_from_llm_providers.py                  # dry-run
  python3 sync_providers_from_llm_providers.py --apply          # mutate
  python3 sync_providers_from_llm_providers.py --provider X     # single
  python3 sync_providers_from_llm_providers.py --json
"""
import os, sys, json, argparse, traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Set
import pymongo

MONGO_HOST = "172.16.103.253"
MONGO_PORT = 27017
MONGO_USER = "quantumtraffic"
MONGO_PASS = (__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), ""))
DB_NAME = "credentials"


def get_client():
    return pymongo.MongoClient(
        host=MONGO_HOST, port=MONGO_PORT,
        username=MONGO_USER, password=MONGO_PASS,
        serverSelectionTimeoutMS=10000,
    )


def now_utc():
    return datetime.now(timezone.utc)


def aggregate_provider_status(siblings: List[Dict]) -> str:
    """Aggregate status across multiple llm_providers sibling keys.

    Rule: any key with key_status in {'VALID', 'UNVERIFIED'} AND api_key present
    → 'active'. Else 'INVALID'.
    """
    active_states = {"VALID", "UNVERIFIED"}
    for s in siblings:
        if s.get("key_status") in active_states and s.get("api_key"):
            return "active"
    return "INVALID"


def consolidate_provider(pname: str, siblings: List[Dict], existing: Dict = None) -> Dict[str, Any]:
    """Build the consolidated providers record from llm_providers siblings + curated.

    Preserves existing curated fields like endpoints, description, etc.

    KEY DISTINCTION:
      - multi_account: more than one sibling
      - multi_purpose: siblings serve DIFFERENT surfaces (inference vs provisioning)
        E.g. openrouter has inference+provisioning keys → multi_purpose=True.
        This warns downstream consumers away from mis-using the wrong key.
    """
    status = aggregate_provider_status(siblings)
    base = dict(existing or {})
    base["provider"] = pname
    base["status"] = status
    base["multi_account"] = len(siblings) > 1
    purposes = {s.get("key_purpose") for s in siblings if s.get("key_purpose")}
    base["multi_purpose"] = len(purposes) > 1
    base["key_count"] = len(siblings)
    base["act_key_count"] = sum(
        1 for s in siblings
        if s.get("key_status") in {"VALID", "UNVERIFIED"} and s.get("api_key")
    )
    # Record per-key purpose breakdown for diagnostic
    base["key_purposes"] = sorted(purposes)
    base["last_synced_at"] = now_utc()
    return base


# ── main operations ─────────────────────────────────────────────────────────
def cascade_apply(db, apply: bool, target_provider: str = None) -> Dict[str, Any]:
    """Cascade llm_providers → providers for all providers (or one)."""
    llm = db["llm_providers"]
    prv = db["providers"]

    # Group llm_providers by provider name
    siblings_idx: Dict[str, List[Dict]] = {}
    for d in llm.find({"provider": target_provider} if target_provider else {}):
        siblings_idx.setdefault(d["provider"], []).append(d)

    # Index existing providers
    existing_idx: Dict[str, Dict] = {}
    for d in prv.find({"provider": target_provider} if target_provider else {}):
        existing_idx[d["provider"]] = d

    out = {
        "executed_at": now_utc().isoformat(),
        "mode": "apply" if apply else "dry-run",
        "llm_groups": len(siblings_idx),
        "providers_in_aoi": len(existing_idx),
        "plan": [],
        "errors": [],
    }

    for pname, siblings in siblings_idx.items():
        try:
            existing = existing_idx.get(pname)
            new_rec = consolidate_provider(pname, siblings, existing)
            if apply:
                prv.replace_one({"provider": pname}, new_rec, upsert=True)
                action = "upserted"
            else:
                action = "would_upsert"
            out["plan"].append({
                "provider": pname,
                "siblings": len(siblings),
                "status": new_rec["status"],
                "act_keys": new_rec["act_key_count"],
                "multi_account": new_rec["multi_account"],
                "had_existing": existing is not None,
                "action": action,
            })
        except Exception as e:
            out["errors"].append({"provider": pname, "err": f"{type(e).__name__}: {e}"})

    # Cascade-out: providers not in llm_providers → mark deprecated ONLY for shared providers
    # Preserve curated providers that don't exist in llm_providers (e.g. google, telegram,
    # system-level services like github/serper/puter) — they don't need llm_providers backing
    # because they're based on different credential stores (infra_providers, search_providers etc.)
    if not target_provider:
        # Curated providers (without llm_providers) are allowed:
        # - system-level services, search providers, messaging, etc.
        CURATED_ONLY_PREFIXES = ("system", "search_", "messaging", "browser_", "infra_",
                                  "crypto_", "gmail_", "puter", "you", "tavily",
                                  "serper", "github", "telegram", "cloudflare",
                                  "nicehash", "binance", "tokocrypto", "qwen_bridge",
                                  "useai_bridge", "artificial_analysis")
        # Only mark deprecated if provider appears in llm_providers historically (had_existing
        # was set earlier; we infer by name match in any previous sync) OR is an LLM-keyed provider
        llm_pnames = set(siblings_idx.keys())
        for pname in existing_idx:
            if pname not in llm_pnames and not any(pname.startswith(pfx) for pfx in CURATED_ONLY_PREFIXES):
                try:
                    if apply:
                        prv.update_one({"provider": pname},
                                       {"$set": {"status": "deprecated",
                                                 "last_synced_at": now_utc()}})
                    out["plan"].append({
                        "provider": pname,
                        "action": "would_mark_deprecated" if not apply else "marked_deprecated",
                        "reason": "not_in_llm_providers",
                    })
                except Exception as e:
                    out["errors"].append({"provider": pname, "err": str(e)})

    return out


# ── CLI ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--provider", help="Single provider name")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    db = get_client()[DB_NAME]
    result = cascade_apply(db, args.apply, args.provider)
    if args.json:
        print(json.dumps(result, default=str, indent=2, ensure_ascii=False))
    else:
        print(f"\n=== sync_providers_from_llm_providers [{result['mode']}] ===")
        print(f"  llm_provider groups: {result['llm_groups']}")
        print(f"  existing providers in scope: {result['providers_in_aoi']}")
        print(f"  Errors: {len(result['errors'])}")
        print()
        for p in result["plan"]:
            print(f"  {p}")
        if result["errors"]:
            print()
            print("Errors:")
            for e in result["errors"]:
                print(f"  {e}")


if __name__ == "__main__":
    main()
