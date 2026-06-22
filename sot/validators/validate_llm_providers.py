#!/usr/bin/env python3
"""
llm_providers validator — uses jsonschema (draft-07)
Validates against: ../schemas/llm_providers.schema.json

Usage:
    python3 validate_llm_providers.py <file.json>
    python3 validate_llm_providers.py --sample
    python3 validate_llm_providers.py --mongo
    python3 validate_llm_providers.py --all

Exit: 0=valid, 1=invalid, 2=error
"""

import json, sys, os
from datetime import datetime, date
from jsonschema import Draft7Validator, validators

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "schemas", "llm_providers.schema.json")


def _normalize_for_validation(doc):
    """Convert BSON-native types (datetime, date, etc.) to ISO strings so the JSON
    schema validator (draft-07, string-only) passes for fields like verified_at /
    restored_at / added that live in MongoDB as datetime objects."""
    if isinstance(doc, dict):
        return {k: _normalize_for_validation(v) for k, v in doc.items()}
    if isinstance(doc, list):
        return [_normalize_for_validation(v) for v in doc]
    if isinstance(doc, (datetime, date)):
        return doc.isoformat()
    return doc


def load_schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def validate_doc(doc, schema=None):
    if schema is None:
        schema = load_schema()
    doc_n = _normalize_for_validation(doc)
    errors = list(Draft7Validator(schema).iter_errors(doc_n))
    return len(errors) == 0, errors

def format_errors(errors):
    lines = []
    for e in errors:
        path = ".".join(str(p) for p in e.path) or "(root)"
        lines.append(f"  [{path}] {e.message}")
    return "\n".join(lines)

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)

    schema = load_schema()
    errors_found = 0

    def do_validate(label, doc):
        nonlocal errors_found
        valid, errs = validate_doc(doc, schema)
        if not valid:
            errors_found += 1
            print(f"  ❌ {label}: {errs[0].message[:100]}")
            for e in errs[:3]:
                print(f"      {format_errors([e])[:120]}")
        return valid

    if args[0] == "--mongo":
        import pymongo
        client = pymongo.MongoClient(
            host="172.16.103.253",
            port=27017,
            username="quantumtraffic",
            password=(__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), "")),
            serverSelectionTimeoutMS=5000
        )
        coll = client["credentials"]["llm_providers"]
        total = coll.count_documents({})
        print(f"Validating {total} docs in credentials.llm_providers...")
        for doc in coll.find({}):
            label = f"{doc.get('provider')}/{doc.get('account_email', '?')}"
            do_validate(label, doc)
        print(f"Result: {errors_found}/{total} invalid")
        client.close()

    elif args[0] == "--sample":
        import pymongo
        client = pymongo.MongoClient(
            host="172.16.103.253",
            port=27017,
            username="quantumtraffic",
            password=(__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), "")),
            serverSelectionTimeoutMS=5000
        )
        coll = client["credentials"]["llm_providers"]
        docs = list(coll.find({}).limit(3))
        if not docs:
            print("Collection is EMPTY")
            client.close()
            sys.exit(0)
        print(f"Validating {len(docs)} sample docs...")
        for doc in docs:
            label = f"{doc.get('provider')}/{doc.get('account_email', '?')}"
            do_validate(label, doc)
        client.close()

    elif args[0] == "--all":
        import pymongo
        client = pymongo.MongoClient(
            host="172.16.103.253",
            port=27017,
            username="quantumtraffic",
            password=(__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), "")),
            serverSelectionTimeoutMS=5000
        )
        coll = client["credentials"]["llm_providers"]
        total = coll.count_documents({})
        print(f"Validating ALL {total} docs...")
        for doc in coll.find({}):
            label = f"{doc.get('provider')}/{doc.get('account_email', '?')}"
            do_validate(label, doc)
        print(f"Result: {errors_found}/{total} invalid")
        client.close()

    else:
        path = args[0]
        if not os.path.exists(path):
            print(f"ERROR: file not found: {path}")
            sys.exit(2)
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, list):
            for doc in data:
                do_validate(doc.get("provider", "?"), doc)
        elif isinstance(data, dict):
            do_validate(data.get("provider", "file"), data)
        else:
            print(f"ERROR: unsupported JSON type: {type(data)}")
            sys.exit(2)

    sys.exit(1 if errors_found > 0 else 0)

if __name__ == "__main__":
    main()