#!/usr/bin/env python3
"""
SOT api_key Immutability Middleware (Bos Decision #3)
=====================================================
MongoDB JSON Schema CANNOT enforce immutability (no "write": "immutable" constraint).

This module provides:
  1. Pure-Python middleware: wraps any llm_providers write operation
  2. Rejects any updateOne with $set on api_key field
  3. Rotation pattern: INSERT new doc + disable old (not update existing)
  4. Test helpers

Usage:
    from sot_api_key_middleware import safe_update_provider, rotate_api_key

    # Reject any update on api_key
    safe_update_provider(coll, account_email, {"key_status": "VALID"})  # OK
    safe_update_provider(coll, account_email, {"api_key": "new"})       # REJECTED

    # Rotation: insert new + disable old
    rotate_api_key(coll, provider, new_key, new_email)

Reference: SOT_FINAL_GOVERNANCE_AUDIT.md, FL-02, Bos Decision #3.
"""
import pymongo
from typing import Dict, Any
from datetime import datetime, timezone

# Fields that, if modified, constitute a security violation
IMMUTABLE_FIELDS = {"api_key"}


class APIKeyImmutabilityError(Exception):
    """Raised when an attempt to modify api_key is detected."""
    pass


def safe_update_provider(coll: pymongo.collection.Collection, account_email: str,
                         update: Dict[str, Any]) -> Any:
    """
    Update llm_providers doc but reject any attempt to modify api_key.

    Args:
        coll: pymongo collection (llm_providers)
        account_email: identifies the doc
        update: dict of fields to $set (api_key FORBIDDEN)

    Returns:
        UpdateResult

    Raises:
        APIKeyImmutabilityError: if update contains api_key
    """
    if not isinstance(update, dict):
        raise TypeError(f"update must be dict, got {type(update).__name__}")

    # Pre-flight check: any forbidden field?
    forbidden = IMMUTABLE_FIELDS & set(update.keys())
    if forbidden:
        raise APIKeyImmutabilityError(
            f"❌ ATTEMPT TO MODIFY IMMUTABLE FIELD(S): {forbidden}. "
            f"Bos Decision #3: api_key is IMMUTABLE. "
            f"Use rotate_api_key() instead. "
            f"Evidence: ILMA-EVID-20260614-API-KEY-IMMU"
        )

    # Belt-and-braces: also check nested operators
    if "$set" in update:
        forbidden_nested = IMMUTABLE_FIELDS & set(update["$set"].keys())
        if forbidden_nested:
            raise APIKeyImmutabilityError(
                f"❌ ATTEMPT TO $set IMMUTABLE FIELD(S): {forbidden_nested}. "
                f"Use rotate_api_key() instead."
            )

    # Safe to proceed
    return coll.update_one(
        {"account_email": account_email},
        update,
    )


def rotate_api_key(coll: pymongo.collection.Collection, provider: str,
                   new_key: str, new_email: str, added_by: str = "system") -> Dict[str, Any]:
    """
    Bos #3 rotation pattern: INSERT new credential + DISABLE old.
    Never modifies the old api_key field.

    Returns:
        Dict with old_id, new_id, status
    """
    now = datetime.now(timezone.utc).isoformat()

    # Step 1: disable old
    old = coll.find_one({"provider": provider, "status": "active"})
    if old:
        coll.update_one(
            {"_id": old["_id"]},
            {"$set": {"status": "rotated", "rotated_at": now, "rotated_to": new_email}},
        )

    # Step 2: insert new
    new_doc = {
        "provider": provider,
        "account_email": new_email,
        "api_key": new_key,
        "status": "active",
        "added": now,
        "added_by": added_by,
        "rotated_from": old["_id"] if old else None,
    }
    result = coll.insert_one(new_doc)

    return {
        "old_id": str(old["_id"]) if old else None,
        "new_id": str(result.inserted_id),
        "status": "rotated" if old else "inserted",
        "evidence_id": "ILMA-EVID-20260614-KEY-ROTATION",
    }


# ── Test harness ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== api_key Imm utability Middleware Test Harness ===\n")

    # Connect
    c = pymongo.MongoClient(
        host="127.0.0.1", port=27017,
        username="ilma_sync", password=(__import__("os").environ.get("ILMA_MONGO_PASS") or next((_l.split("=",1)[1].strip() for _l in open("/root/.hermes/.env") if _l.startswith("ILMA_MONGO_PASS=")), "")),
        serverSelectionTimeoutMS=10000,
    )
    coll = c["credentials"]["llm_providers"]

    # Test 1: Reject api_key modification
    print("Test 1: Attempt to $set api_key")
    sample = coll.find_one({"status": "active"})
    if sample:
        try:
            safe_update_provider(coll, sample["account_email"],
                                 {"$set": {"api_key": "stolen-key-attempt"}})
            print("  ❌ FAIL: Modification was NOT rejected")
        except APIKeyImmutabilityError as e:
            print(f"  ✅ PASS: {str(e)[:120]}")

    # Test 2: Allow non-api_key modification
    print("\nTest 2: Modify key_status (allowed)")
    try:
        result = safe_update_provider(coll, sample["account_email"],
                                      {"$set": {"key_status": "VALID_TEST"}})
        print(f"  ✅ PASS: key_status modified, matched={result.matched_count}")
        # Revert
        coll.update_one(
            {"account_email": sample["account_email"]},
            {"$set": {"key_status": sample.get("key_status", "VALID")}},
        )
    except APIKeyImmutabilityError as e:
        print(f"  ❌ FAIL: {e}")

    # Test 3: Rotation pattern
    print("\nTest 3: Rotate api_key (insert new + disable old)")
    result = rotate_api_key(
        coll, "test_provider", "test-key-xyz12345", "test@rotation.local", "middleware_test"
    )
    print(f"  Result: {result}")
    # Cleanup
    coll.delete_one({"provider": "test_provider"})
    print("  Cleanup done")
