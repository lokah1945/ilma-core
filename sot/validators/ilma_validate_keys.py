#!/usr/bin/env python3
"""
ilma_validate_keys.py — Tier-1 key validator (1-shot probe = key_status outcome)
=================================================================================

Concept (Bos 2026-06-23): `key_status` reflects whether the API key is *usable*.
A single successful HTTP probe (200 OK with parseable body) is sufficient to mark
the key VALID. Anything else maps to a specific status code:
  HTTP 200              → VALID
  HTTP 401/403          → INVALID
  HTTP 402/429/QUOTA    → QUOTA_EXCEEDED
  HTTP 5xx              → SERVER_ERROR
  timeout/SSL/DNS       → TIMEOUT
  connection refused    → UNREACHABLE

This module does NOT mutate models collection. It only:
  1. Reads llm_providers (Tier-1)
  2. Probes each UNVERIFIED candidate against its registered URL (Bearer auth)
  3. Writes key_status + verified_at + verified_by + last_valid_evidence back via
     `sot_api_key_middleware.safe_update_provider` (which blocks api_key edits)
  4. Appends an entry to model_audit_trail per transition

CLI:
    python3 ilma_validate_keys.py --all              # validate every UNVERIFIED
    python3 ilma_validate_keys.py --provider z.ai    # one provider
    python3 ilma_validate_keys.py --dry-run          # probe only, no writes
    python3 ilma_validate_keys.py --list-pending     # show UNVERIFIED count
"""
from __future__ import annotations
import os, sys, json, ssl, time, argparse, hashlib, urllib.request, urllib.error
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pymongo

# ── Resolve paths ─────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "discovery"))
sys.path.insert(0, os.path.join(_HERE, "..", "orchestration"))
sys.path.insert(0, os.path.join(_HERE, ".."))  # for sot_api_key_middleware at sot/
import provider_sync
from sot_api_key_middleware import safe_update_provider  # noqa: E402

# ── MongoDB connection (same pattern as the rest of SOT) ──────────────────────
MONGO_HOST = "127.0.0.1"
MONGO_PORT = 27017
MONGO_USER = "ilma_sync"
MONGO_PASS = (__import__("os").environ.get("ILMA_MONGO_PASS")
              or next((_l.split("=", 1)[1].strip()
                       for _l in open("/root/.hermes/.env")
                       if _l.startswith("ILMA_MONGO_PASS=")), ""))
DB_NAME = "credentials"

VERIFIER_NAME = "ilma_validate_keys"

_SSL_CTX = ssl.create_default_context()


def get_db():
    return pymongo.MongoClient(
        host=MONGO_HOST, port=MONGO_PORT,
        username=MONGO_USER, password=MONGO_PASS,
        authSource="admin", directConnection=True,
        serverSelectionTimeoutMS=8000,
    )[DB_NAME]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _read_provider_meta(db, pname: str) -> Dict[str, Any]:
    """auth_format lives in providers (Tier-2). Default Bearer."""
    try:
        doc = db["providers"].find_one({"provider": pname}, {"auth_format": 1})
        if doc and doc.get("auth_format"):
            return {"auth_format": doc["auth_format"]}
    except Exception:
        pass
    return {"auth_format": "Bearer"}


def probe_url(url: str, key: str, auth_format: str = "Bearer") -> Tuple[str, str]:
    """Single HTTP probe. Returns (status_code, body_excerpt).

    Raises on transport failure (caller maps to TIMEOUT/UNREACHABLE).
    """
    req = urllib.request.Request(url)
    if key and key != "dummy":
        if auth_format == "x-goog-api-key":
            req.add_header("x-goog-api-key", key)
        elif auth_format in ("x-api-key", "ApiKey_Header"):
            req.add_header("x-api-key", key)
        else:
            req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent",
                   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "Chrome/135.0.0.0 Safari/537.36")
    with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
        body = resp.read()
        if len(body) > 4096:
            body = body[:4096]
        try:
            json.loads(body)
            ok = "json_ok"
        except Exception:
            ok = "non_json_ok"
        return (str(resp.status), ok)


def map_status(http_code: str) -> str:
    """HTTP code → SOT key_status enum (from llm_providers.schema.json)."""
    if http_code == "200":
        return "VALID"
    if http_code in ("401", "403"):
        return "INVALID"
    if http_code in ("402", "429"):
        return "QUOTA_EXCEEDED"
    if http_code in ("404", "400"):
        return "INVALID"  # key rejected OR wrong endpoint — both = unusable for THIS url
    if http_code.startswith("5"):
        return "SERVER_ERROR"
    return "INVALID"


def classify_exception(e: Exception) -> str:
    name = type(e).__name__
    if "timeout" in name.lower() or "Timeout" in str(e):
        return "TIMEOUT"
    if "SSLError" in name or "ssl" in str(e).lower():
        return "SSL_ERROR"
    if "ConnectionRefused" in name or "refused" in str(e).lower():
        return "UNREACHABLE"
    if "NameResolution" in name or "getaddrinfo" in str(e).lower():
        return "DNS_FAIL"
    return "TIMEOUT"  # catch-all for unknown network errors


def validate_provider(
    db, pname: str, *, dry_run: bool = False
) -> Dict[str, Any]:
    """Probe every UNVERIFIED row for `pname` and update key_status accordingly."""
    cfg = provider_sync.PROVIDER_CONFIGS.get(pname)
    if not cfg:
        return {"provider": pname, "status": "skipped", "reason": "no_provider_config"}
    if cfg.get("skip_sync"):
        return {"provider": pname, "status": "skipped", "reason": "skip_sync"}
    url = cfg.get("url", "")
    if not url:
        return {"provider": pname, "status": "skipped", "reason": "no_url"}

    auth_format = _read_provider_meta(db, pname).get("auth_format", "Bearer")
    coll = db["llm_providers"]
    audit = db["model_audit_trail"]
    pending = list(coll.find({
        "provider": pname,
        "key_status": {"$in": ["UNVERIFIED", "TIMEOUT", "SERVER_ERROR"]},
        "is_active": {"$ne": False},
        "api_key": {"$exists": True, "$nin": [None, ""]},
    }))
    if not pending:
        return {"provider": pname, "status": "skipped", "reason": "no_pending_keys"}

    out = {"provider": pname, "probed": 0, "transitions": []}
    for d in pending:
        key = d.get("api_key") or ""
        if cfg.get("skip_key"):
            key = "dummy"
        out["probed"] += 1
        ok = False
        result = None
        try:
            code, evidence = probe_url(url, key, auth_format=auth_format)
            ok = code == "200"
            new_status = map_status(code)
            last_valid = f"GET {url} -> HTTP {code} ({evidence}) {now_utc().isoformat()[:19]}Z"
            result = {"code": code, "evidence": last_valid}
        except Exception as e:
            new_status = classify_exception(e)
            last_valid = f"GET {url} -> {type(e).__name__}: {str(e)[:80]}"
            result = {"code": None, "evidence": last_valid, "exception": True}

        transition = {
            "account_email": d.get("account_email"),
            "old": d.get("key_status"),
            "new": new_status,
            "evidence": last_valid,
        }
        out["transitions"].append(transition)

        if dry_run:
            continue

        update = {
            "key_status": new_status,
            "verified_at": now_utc(),
            "verified_by": VERIFIER_NAME,
            "last_valid_evidence": last_valid,
        }
        # safe_update_provider blocks api_key field writes (immutable rule)
        res = safe_update_provider(coll, d["account_email"], {"$set": update})
        if res.matched_count == 0:
            # single (provider, account_email) row expected. If matched_count==0,
            # there are multiple rows sharing the same account_email — update by _id.
            coll.update_one({"_id": d["_id"]}, {"$set": update})

        audit.insert_one({
            "provider": pname, "model_id": "*",
            "event_type": "key_validated",
            "actor": VERIFIER_NAME,
            "source_collection": "llm_providers",
            "event_at": now_utc(),
            "evidence_id": f"VALID-{pname}-{int(time.time()*1000) % 10**8:08d}",
            "account_email": d.get("account_email"),
            "old_status": d.get("key_status"),
            "new_status": new_status,
            "probe_result": result,
        })
    out["status"] = "success"
    return out


def validate_all(*, dry_run: bool = False, only_providers: Optional[List[str]] = None
                 ) -> Dict[str, Any]:
    db = get_db()
    targets = set()
    if only_providers:
        targets = set(only_providers)
    else:
        for cfg_name, cfg in provider_sync.PROVIDER_CONFIGS.items():
            if cfg.get("skip_sync") or not cfg.get("url"):
                continue
            targets.add(cfg_name)
        # also any llm_providers rows pointing to a provider not in configs
        for d in db["llm_providers"].find({}, {"provider": 1}):
            targets.add(d["provider"])

    targets = sorted(targets)
    print(f"[{VERIFIER_NAME}] probing {len(targets)} providers (dry_run={dry_run})...")
    summary = {"providers": len(targets), "transitions": [], "errors": [], "skipped": []}
    for pname in targets:
        try:
            r = validate_provider(db, pname, dry_run=dry_run)
            if r.get("status") == "skipped":
                summary["skipped"].append({"provider": pname, "reason": r.get("reason")})
                continue
            for t in r.get("transitions", []):
                txt = (f"  {pname:<20} {t['account_email']:<28} "
                       f"{str(t['old']):<14} → {t['new']}")
                print(txt)
                summary["transitions"].append({"provider": pname, **t})
        except Exception as e:
            err = {"provider": pname, "error": str(e)[:120]}
            summary["errors"].append(err)
            print(f"  ❌ {pname}: {str(e)[:120]}")
    summary["status"] = "success"
    return summary


def list_pending(db=None) -> Dict[str, List[str]]:
    if db is None:
        db = get_db()
    coll = db["llm_providers"]
    pending = {}
    for d in coll.find(
        {"key_status": {"$in": ["UNVERIFIED", "TIMEOUT", "SERVER_ERROR"]}},
        {"provider": 1, "account_email": 1, "is_active": 1, "key_status": 1},
    ):
        p = d.get("provider")
        pending.setdefault(p, [])
        pending[p].append({
            "account_email": d.get("account_email"),
            "key_status": d.get("key_status"),
            "is_active": d.get("is_active", True),
        })
    return pending


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="validate every pending key")
    ap.add_argument("--provider", help="validate one provider only")
    ap.add_argument("--dry-run", action="store_true",
                    help="probe only, do not write key_status")
    ap.add_argument("--list-pending", action="store_true",
                    help="show pending (UNVERIFIED/TIMEOUT/SERVER_ERROR) keys")
    args = ap.parse_args()

    if args.list_pending:
        pending = list_pending()
        total = sum(len(v) for v in pending.values())
        print(f"Pending keys: {total} across {len(pending)} providers\n")
        for p, rows in sorted(pending.items()):
            print(f"  {p:<22} {len(rows)}")
            for r in rows:
                print(f"    - {r['account_email']:<28} {r['key_status']:<14} active={r['is_active']}")
        return

    if not (args.all or args.provider):
        ap.print_help()
        sys.exit(1)

    only = [args.provider] if args.provider else None
    out = validate_all(dry_run=args.dry_run, only_providers=only)

    print(f"\n=== summary ===")
    print(f"  probed: {len(out.get('transitions', []))} transitions "
          f"across {out.get('providers', 0)} providers")
    if out.get("errors"):
        print(f"  ERRORS: {len(out['errors'])}")
        for e in out["errors"]:
            print(f"    - {e['provider']}: {e['error']}")
    if out.get("skipped"):
        print(f"  SKIPPED: {len(out['skipped'])}")
        for s in out["skipped"]:
            print(f"    - {s['provider']}: {s['reason']}")
    # Final tallies
    table = {}
    for t in out.get("transitions", []):
        table[t["new"]] = table.get(t["new"], 0) + 1
    if table:
        print("  new statuses:")
        for k, v in sorted(table.items(), key=lambda kv: -kv[1]):
            print(f"    {k:<14} {v}")


if __name__ == "__main__":
    main()
