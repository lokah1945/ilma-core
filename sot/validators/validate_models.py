#!/usr/bin/env python3
"""
models validator — jsonschema draft-07 with BSON type normalization.
Validates credentials.models collection.

Pre-processes docs to:
- Convert datetime objects to ISO 8601 strings
- Convert ObjectId to string
- Coerce numeric strings to actual numbers for known numeric fields
"""
import json, sys, os
from datetime import datetime, date
from bson import ObjectId
from jsonschema import Draft7Validator

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(SCRIPT_DIR, "..", "schemas", "models.schema.json")

# Fields that should be numeric (will coerce string→number if possible)
NUMERIC_FIELDS = {
    "price_per_m_input", "price_per_m_output",
    "context_window", "max_output_tokens",
    "score", "benchmark_score", "error_rate", "total_requests",
}

# Fields that should be integer
INTEGER_FIELDS = {
    "context_window", "max_output_tokens", "total_requests",
}

def _coerce_number(value, integer=False):
    """Coerce a string to a number. Returns original if already numeric or non-coercible."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if integer and isinstance(value, float) and value.is_integer():
            return int(value)
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return value
        try:
            if integer:
                return int(s)
            f = float(s)
            return f
        except (ValueError, TypeError):
            return value
    return value

def _normalize(value, key=None):
    """Recursively convert BSON types / numeric strings to JSON-compatible types."""
    # Type-specific coercion based on field name
    if key in NUMERIC_FIELDS and isinstance(value, str):
        value = _coerce_number(value, integer=(key in INTEGER_FIELDS))
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.isoformat() + "Z"
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {k: _normalize(v, key=k) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    return value

def load_schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)

def validate_doc(doc, schema=None):
    if schema is None:
        schema = load_schema()
    normalized = _normalize(doc)
    errors = list(Draft7Validator(schema).iter_errors(normalized))
    return len(errors) == 0, errors

def main():
    args = sys.argv[1:]
    schema = load_schema()
    errors_found = 0
    docs_checked = 0

    def do_validate(label, doc):
        nonlocal errors_found, docs_checked
        docs_checked += 1
        valid, errs = validate_doc(doc, schema)
        if not valid:
            errors_found += 1
            print(f"  FAIL {label}: {errs[0].message[:120]}")
        return valid

    if args and args[0] == "--mongo":
        import pymongo
        client = pymongo.MongoClient(
            host="172.16.103.253", port=27017,
            username="quantumtraffic", password=(__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), "")),
            authSource="admin", serverSelectionTimeoutMS=10000
        )
        coll = client["credentials"]["models"]
        total = coll.count_documents({})
        print(f"Validating {total} docs in credentials.models...")
        for doc in coll.find({}):
            label = f"{doc.get('provider','?')}/{doc.get('model_id','?')}"
            do_validate(label, doc)
        print(f"Result: {errors_found}/{docs_checked} invalid")
        client.close()
    elif args and args[0] == "--sample":
        import pymongo
        client = pymongo.MongoClient(
            host="172.16.103.253", port=27017,
            username="quantumtraffic", password=(__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), "")),
            authSource="admin", serverSelectionTimeoutMS=10000
        )
        coll = client["credentials"]["models"]
        docs = list(coll.find({}).limit(3))
        if not docs:
            print("models collection is EMPTY"); client.close(); sys.exit(0)
        print(f"Sample {len(docs)} docs...")
        for doc in docs:
            label = f"{doc.get('provider','?')}/{doc.get('model_id','?')}"
            do_validate(label, doc)
        client.close()
    elif args and args[0] == "--all":
        import pymongo
        client = pymongo.MongoClient(
            host="172.16.103.253", port=27017,
            username="quantumtraffic", password=(__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), "")),
            authSource="admin", serverSelectionTimeoutMS=10000
        )
        coll = client["credentials"]["models"]
        total = coll.count_documents({})
        print(f"Validating ALL {total} docs in credentials.models...")
        for doc in coll.find({}):
            label = f"{doc.get('provider','?')}/{doc.get('model_id','?')}"
            do_validate(label, doc)
        print(f"Result: {errors_found}/{docs_checked} invalid")
        client.close()
    else:
        path = args[0] if args else None
        if not path or not os.path.exists(path):
            print(__doc__); sys.exit(0)
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, list):
            for doc in data:
                do_validate(doc.get("model_id","?"), doc)
        elif isinstance(data, dict):
            do_validate(data.get("model_id","file"), data)
        else:
            sys.exit(2)
    sys.exit(1 if errors_found > 0 else 0)

if __name__ == "__main__":
    main()
