#!/usr/bin/env python3
"""
model_intelligence validator — jsonschema draft-07 with BSON normalization.
"""
import json, sys, os
from datetime import datetime, date
from bson import ObjectId
from jsonschema import Draft7Validator

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(SCRIPT_DIR, "..", "schemas", "model_intelligence.schema.json")

def _normalize(value):
    if isinstance(value, datetime):
        return value.isoformat() + ("" if value.tzinfo else "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
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
            host="127.0.0.1", port=27017,
            username="ilma_sync", password=(__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), "")),
            authSource="admin", serverSelectionTimeoutMS=10000
        )
        c = client["credentials"]["model_intelligence"]
        total = c.count_documents({})
        print(f"Validating {total} docs in credentials.model_intelligence...")
        for doc in c.find({}):
            label = f"{doc.get('provider','?')}/{doc.get('model_id','?')}"
            do_validate(label, doc)
        print(f"Result: {errors_found}/{docs_checked} invalid")
        client.close()
    elif args and args[0] == "--sample":
        import pymongo
        client = pymongo.MongoClient(
            host="127.0.0.1", port=27017,
            username="ilma_sync", password=(__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), "")),
            authSource="admin", serverSelectionTimeoutMS=10000
        )
        c = client["credentials"]["model_intelligence"]
        docs = list(c.find({}).limit(5))
        if not docs:
            print("model_intelligence is EMPTY")
            client.close()
            sys.exit(0)
        print(f"Sample {len(docs)} docs...")
        for doc in docs:
            label = f"{doc.get('provider','?')}/{doc.get('model_id','?')}"
            do_validate(label, doc)
        client.close()
    elif args and args[0] == "--all":
        import pymongo
        client = pymongo.MongoClient(
            host="127.0.0.1", port=27017,
            username="ilma_sync", password=(__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), "")),
            authSource="admin", serverSelectionTimeoutMS=10000
        )
        c = client["credentials"]["model_intelligence"]
        total = c.count_documents({})
        print(f"Validating ALL {total} docs in credentials.model_intelligence...")
        for doc in c.find({}):
            label = f"{doc.get('provider','?')}/{doc.get('model_id','?')}"
            do_validate(label, doc)
        print(f"Result: {errors_found}/{docs_checked} invalid")
        client.close()
    else:
        path = args[0] if args else None
        if not path or not os.path.exists(path):
            print(f"Usage: {sys.argv[0]} [--mongo|--sample|--all|<json_file>]")
            sys.exit(0)
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, list):
            for doc in data:
                do_validate(doc.get("model_id", "?"), doc)
        elif isinstance(data, dict):
            do_validate(data.get("model_id", "file"), data)
        else:
            sys.exit(2)
    sys.exit(1 if errors_found > 0 else 0)

if __name__ == "__main__":
    main()
