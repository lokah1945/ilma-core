#!/usr/bin/env python3
"""ILMA v3 PRODUCTION-style backup: dump all SOT collections to JSON + gzip.

Use this when `mongodump` is unavailable (containerized / minimal envs).
Pattern documented in `ilma-runtime-readiness-audit/references/sot-runtime-audit-v3-2026-06.md`.

Usage:
    python3 scripts/ilma_v3_backup.py
    python3 scripts/ilma_v3_backup.py --output /tmp/my_backup.json.gz

Output: single .json.gz file with all SOT collections as top-level keys.
Restoration: see rollback script pattern in the reference doc.
"""
import sys, json, gzip, os, argparse
from datetime import datetime, timezone

# Add pymongo to path (Hermes venv has it at /usr/local/lib/python3.11/dist-packages)
sys.path.insert(0, "/usr/local/lib/python3.11/dist-packages")

import pymongo

# ===== CONFIG — adjust for your env =====
MONGO_HOST = os.environ.get("ILMA_MONGO_HOST", "172.16.103.253")
MONGO_PORT = int(os.environ.get("ILMA_MONGO_PORT", "27017"))
MONGO_USER = os.environ.get("ILMA_MONGO_USER", "quantumtraffic")
MONGO_PASS = os.environ.get("ILMA_MONGO_PASS", (__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), "")))
MONGO_AUTH_SOURCE = os.environ.get("ILMA_MONGO_AUTH_SOURCE", "admin")
MONGO_REPLICA_SET = os.environ.get("ILMA_MONGO_REPLICA_SET", "rs0")
MONGO_DB = os.environ.get("ILMA_MONGO_DB", "credentials")
# ==========================================

# SOT collections per Master Prompt v2/v3 Section 2.2
SOT_COLLECTIONS = [
    "llm_providers",
    "providers",
    "models",
    "model_intelligence",
    "model_alias",
    "model_benchmark",
    "model_capabilities",
    "model_enrichment",
    # Optional / contextual:
    "model_audit_trail",
    "sot_jobs",
    "sot_meta",
]

# Connection — use keyword args form (P-36: works reliably, URI form can auth-fail)
def get_client():
    return pymongo.MongoClient(
        host=MONGO_HOST, port=MONGO_PORT,
        username=MONGO_USER, password=MONGO_PASS,
        authSource=MONGO_AUTH_SOURCE,
        directConnection=True, replicaSet=MONGO_REPLICA_SET,
        serverSelectionTimeoutMS=15000, connectTimeoutMS=15000,
    )

def backup_to_json_gz(db, output_path, sota_collections=SOT_COLLECTIONS):
    """Dump all SOT collections to a single JSON+gzip file."""
    backup = {}
    metadata = {"timestamp": datetime.now(timezone.utc).isoformat(),
                "database": db.name,
                "collections": {}}
    skipped = []

    for col in sota_collections:
        if col not in db.list_collection_names():
            skipped.append(col)
            continue
        docs = []
        n = 0
        for d in db[col].find({}):
            n += 1
            # BSON datetime → ISO string (JSON-safe)
            for k, v in list(d.items()):
                if isinstance(v, datetime):
                    d[k] = v.isoformat()
            d["_id"] = str(d["_id"])
            docs.append(d)
        backup[col] = docs
        metadata["collections"][col] = n

    metadata["skipped"] = skipped
    metadata["total_docs"] = sum(metadata["collections"].values())
    backup["__metadata__"] = metadata

    with gzip.open(output_path, "wt", encoding="utf-8") as f:
        json.dump(backup, f, indent=2, default=str)
    return metadata

def main():
    parser = argparse.ArgumentParser(description="ILMA v3 PRODUCTION backup")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--db", default=MONGO_DB, help="Database name")
    args = parser.parse_args()

    if args.output:
        out = args.output
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        out = f"/root/upload/backup_{ts}.json.gz"

    print(f"=== ILMA v3 PRODUCTION BACKUP ===")
    print(f"Database: {args.db}")
    print(f"Output: {out}")
    print()

    c = get_client()
    db = c[args.db]

    metadata = backup_to_json_gz(db, out)

    print(f"Backup complete!")
    print(f"  Total docs: {metadata['total_docs']}")
    print(f"  Collections backed up: {len(metadata['collections'])}")
    for col, n in metadata['collections'].items():
        print(f"    {col}: {n}")
    if metadata['skipped']:
        print(f"  Skipped (not in DB): {metadata['skipped']}")
    print(f"  Output: {out} ({os.path.getsize(out)} bytes)")

if __name__ == "__main__":
    main()
