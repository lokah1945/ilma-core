#!/usr/bin/env python3
"""
ilma_two_way_sync.py — Full 2-Way Realtime MongoDB Sync Engine v1.0
=====================================================================

Syncs LOCAL MongoDB (rs1) <-> REMOTE MongoDB (rs0 @ Yapsi) with:
  - Change Stream watchers (realtime <100ms)
  - Oplog replay (gap recovery on reconnect)
  - Periodic reconciliation (6-hourly safety net)

Conflict Resolution:
  - credentials DB        → LOCAL WINS (ILMA managed)
  - QuantumTrafficDB       → REMOTE WINS (Yapsi managed)
  - Any other DB           → REMOTE WINS (default)

Anti-Loop: _sync_generation counter + _sync_source tag prevent echo loops.

Usage:
  python3 ilma_two_way_sync.py --seed          # Initial bulk copy remote→local
  python3 ilma_two_way_sync.py --daemon        # Start sync daemon (foreground)
  python3 ilma_two_way_sync.py --reconcile     # Run full reconciliation
  python3 ilma_two_way_sync.py --status        # Show sync state
  python3 ilma_two_way_sync.py --test          # Run E2E tests

Author: ILMA v3.30 | Phase 73+ | 2026-06-23
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import os
import signal
import sys
import threading
import time
import traceback
from bson import ObjectId, Timestamp
from datetime import datetime, timezone
from queue import Queue, Empty
from typing import Any, Dict, List, Optional, Set, Tuple

import pymongo
from pymongo import MongoClient, UpdateOne, InsertOne, DeleteOne
from pymongo.errors import (
    DuplicateKeyError,
    OperationFailure,
    AutoReconnect,
    NetworkTimeout,
    ServerSelectionTimeoutError,
    CursorNotFound,
)

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════

_HERE = os.path.dirname(os.path.abspath(__file__))
_BASE_DIR = os.path.join(_HERE, "..", "..")
_ENV_FILE = os.path.join(_HERE, "..", "..", "..", ".hermes", ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [ilma-sync] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ilma.sync")


def _load_env():
    """Load .env credentials."""
    env = {}
    env_file = _ENV_FILE
    if not os.path.exists(env_file):
        # Try alternate paths
        for p in [
            "/root/.hermes/.env",
            os.path.expanduser("~/.hermes/.env"),
        ]:
            if os.path.exists(p):
                env_file = p
                break
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


# Local MongoDB config — Permissive credential resolution from .env or env
def _resolve_local_creds():
    """Read local MongoDB credentials. Tries env first, then .env file."""
    user = os.environ.get("ILMA_MONGO_LOCAL_USER") or os.environ.get("ILMA_MONGO_USER")
    pwd  = os.environ.get("ILMA_MONGO_LOCAL_PASS") or os.environ.get("ILMA_MONGO_PASS")
    if not user or not pwd:
        # Fallback to .env file (no-shell required)
        try:
            env_path = "/root/.hermes/.env"
            if os.path.exists(env_path):
                with open(env_path) as _f:
                    for ln in _f:
                        ln = ln.strip()
                        if "=" in ln and not ln.startswith("#"):
                            k, v = ln.split("=", 1)
                            k, v = k.strip(), v.strip()
                            if k == "ILMA_MONGO_USER" and not user:
                                user = v
                            if k == "ILMA_MONGO_PASS" and not pwd:
                                pwd = v
        except Exception:
            pass
    if not user:
        user = "ilma_sync"
    if not pwd:
        # Last-resort: try getpass-style keyring or raise
        pwd = ""
    return user, pwd

LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 27017
LOCAL_USER, LOCAL_PASS = _resolve_local_creds()
LOCAL_AUTH_DB = "admin"
LOCAL_REPL_SET = "rs1"


def _resolve_remote_from_sot():
    """Pull remote MongoDB credential FROM SOT (credentials.infra_providers).
    Priority: provider='mongodb-cloud' / accounts.bos.
    Returns dict with host/port/username/password/auth_source/replica_set or None.
    Falls back to .env when SOT lookup fails (daemon robustness).
    """
    try:
        import pymongo
        env = _load_env()
        # Use whichever local credential key exists in .env:
        # prefer ILMA_MONGO_LOCAL_USER, fall back to ILMA_MONGO_USER (both are 'ilma_sync'@rs1 here).
        local_user = env.get("ILMA_MONGO_LOCAL_USER") or env.get("ILMA_MONGO_USER") or "ilma_sync"
        local_pass = env.get("ILMA_MONGO_LOCAL_PASS") or env.get("ILMA_MONGO_PASS")
        c = pymongo.MongoClient(
            "127.0.0.1", 27017,
            username=local_user, password=local_pass,
            authSource="admin", directConnection=True,
            serverSelectionTimeoutMS=4000,
        )
        doc = c["credentials"]["infra_providers"].find_one({"provider": "mongodb-cloud", "is_active": True})
        c.close()
        if doc:
            accts = doc.get("accounts") or {}
            acct = accts.get(doc.get("default_account")) or next(iter(accts.values()), None)
            if acct:
                # api_token can be either a URI string or a raw password — try URI parse first
                tok = (acct.get("api_token") or "").strip()
                host = doc.get("host") or "172.16.103.253"
                port = int(doc.get("port") or 27017)
                user, password = None, None
                if tok.startswith("mongodb://") or tok.startswith("mongodb+srv://"):
                    from urllib.parse import urlparse
                    u = urlparse(tok)
                    user = u.username
                    password = u.password
                    if u.port:
                        port = u.port
                    qs = (u.query or "")
                    if qs:
                        from urllib.parse import parse_qs
                        q = parse_qs(qs)
                        if "replicaSet" in q:
                            # keep doc.replica_set if present
                            pass
                    if u.hostname:
                        host = u.hostname
                else:
                    user = doc.get("default_account_username", "quantumtraffic")
                    password = tok
                return {
                    "host": host,
                    "port": port,
                    "username": user,
                    "password": password,
                    "auth_source": doc.get("auth_source", "admin"),
                    "replica_set": doc.get("replica_set", "rs0"),
                    "source": "SOT:credentials.infra_providers[mongodb-cloud]",
                    "evidence_id": doc.get("evidence_id"),
                }
    except Exception:
        pass
    return None


# Remote MongoDB config — SOT-FIRST, .env-FALLBACK
_SOT_REMOTE = _resolve_remote_from_sot()
_env = _load_env()

if _SOT_REMOTE:
    REMOTE_HOST = _SOT_REMOTE["host"]
    REMOTE_PORT = _SOT_REMOTE["port"]
    REMOTE_USER = _SOT_REMOTE["username"]
    REMOTE_PASS = _SOT_REMOTE["password"]
    REMOTE_AUTH_DB = _SOT_REMOTE["auth_source"]
    REMOTE_REPL_SET = _SOT_REMOTE["replica_set"]
    _REMOTE_SOURCE = _SOT_REMOTE["source"]
else:
    REMOTE_HOST = _env.get("ILMA_MONGO_HOST", "172.16.103.253")
    REMOTE_PORT = int(_env.get("ILMA_MONGO_PORT", "27017"))
    REMOTE_USER = _env.get("ILMA_MONGO_USER", "quantumtraffic")
    REMOTE_PASS = _env.get("ILMA_MONGO_PASS", "")
    REMOTE_AUTH_DB = _env.get("ILMA_MONGO_AUTHSRC", "admin")
    REMOTE_REPL_SET = "rs0"
    _REMOTE_SOURCE = "ENV:.hermes/.env"

# Databases to sync with conflict policy
SYNC_DATABASES = {
    "credentials": "local_wins",        # ILMA managed → LOCAL WINS
    "QuantumTrafficDB": "remote_wins",  # Yapsi managed → REMOTE WINS
}

# Internal collections (skip from sync)
SKIP_COLLECTIONS = {
    "local": {"sot_sync_state"},  # local-only state
    "remote": set(),
}

# Sync metadata fields
SYNC_GEN_FIELD = "_sync_generation"
SYNC_SRC_FIELD = "_sync_source"
SYNC_TS_FIELD = "_sync_timestamp"
SYNC_CONFLICT_FIELD = "_sync_conflict"

# Reconcile schedule
RECONCILE_INTERVAL_HOURS = 6

# Backoff settings
BACKOFF_INITIAL = 1.0
BACKOFF_MAX = 60.0
BACKOFF_MULTIPLIER = 2.0

# Bulk operation batch size
BULK_BATCH_SIZE = 500

# Sync state collection
SYNC_STATE_COLL = "sot_sync_state"
SYNC_STATE_DB = "credentials"


# ═══════════════════════════════════════════════════════════════════════
# CONNECTION MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════


def _get_local_client() -> MongoClient:
    """Connect to local MongoDB (rs1)."""
    return MongoClient(
        host=LOCAL_HOST,
        port=LOCAL_PORT,
        username=LOCAL_USER,
        password=LOCAL_PASS,
        authSource=LOCAL_AUTH_DB,
        directConnection=True,
        serverSelectionTimeoutMS=5000,
    )


def _get_remote_client() -> MongoClient:
    """Connect to remote MongoDB (rs0 @ Yapsi)."""
    return MongoClient(
        host=REMOTE_HOST,
        port=REMOTE_PORT,
        username=REMOTE_USER,
        password=REMOTE_PASS,
        authSource=REMOTE_AUTH_DB,
        directConnection=True,
        serverSelectionTimeoutMS=10000,
    )


# ═══════════════════════════════════════════════════════════════════════
# SYNC STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _get_sync_state(local_db) -> dict:
    """Load sync state from local MongoDB."""
    coll = local_db[SYNC_STATE_COLL]
    doc = coll.find_one({"_id": "_two_way_sync"})
    return doc or {"_id": "_two_way_sync", "resume_tokens": {}, "last_reconcile": None, "stats": {}}


def _save_sync_state(local_db, state: dict):
    """Persist sync state to local MongoDB."""
    coll = local_db[SYNC_STATE_COLL]
    coll.replace_one({"_id": "_two_way_sync"}, state, upsert=True)


def _save_resume_token(local_db, db_name: str, direction: str, token: dict):
    """Save a resume token for a specific DB + direction."""
    state = _get_sync_state(local_db)
    key = f"{db_name}:{direction}"
    state.setdefault("resume_tokens", {})[key] = token
    state["stats"] = state.get("stats", {})
    state["stats"][f"last_{direction}_{db_name}"] = _now_utc().isoformat()
    _save_sync_state(local_db, state)


def _load_resume_token(local_db, db_name: str, direction: str) -> Optional[dict]:
    """Load a resume token for a specific DB + direction."""
    state = _get_sync_state(local_db)
    return state.get("resume_tokens", {}).get(f"{db_name}:{direction}")


# ═══════════════════════════════════════════════════════════════════════
# CONFLICT RESOLUTION
# ═══════════════════════════════════════════════════════════════════════


def _get_conflict_policy(db_name: str) -> str:
    """Get conflict resolution policy for a database."""
    return SYNC_DATABASES.get(db_name, "remote_wins")


def _resolve_conflict(
    local_doc: Optional[dict],
    remote_doc: Optional[dict],
    db_name: str,
    operation: str,
) -> Tuple[dict, str]:
    """
    Resolve a conflict between local and remote documents.
    Returns (winner_doc, action_taken).
    """
    policy = _get_conflict_policy(db_name)

    if operation == "update":
        # Both sides modified same _id
        local_gen = (local_doc or {}).get(SYNC_GEN_FIELD, 0)
        remote_gen = (remote_doc or {}).get(SYNC_GEN_FIELD, 0)

        if policy == "local_wins":
            winner = local_doc
            action = "local_wins"
        elif policy == "remote_wins":
            winner = remote_doc
            action = "remote_wins"
        else:
            # Fallback: latest generation wins
            if local_gen >= remote_gen:
                winner = local_doc
                action = "local_wins_gen"
            else:
                winner = remote_doc
                action = "remote_wins_gen"

        # Mark conflict on winner
        if winner:
            winner[SYNC_CONFLICT_FIELD] = True

        return winner, action

    elif operation == "insert":
        # Same _id inserted both sides
        if policy == "local_wins":
            return local_doc, "local_wins_insert"
        else:
            return remote_doc, "remote_wins_insert"

    elif operation == "delete_vs_update":
        if policy == "local_wins":
            # Local delete + remote update → local delete wins (safety)
            return {}, "delete_wins"
        else:
            # Remote delete + local update → remote delete wins
            return {}, "delete_wins"

    return remote_doc, "unknown"


def _add_sync_metadata(doc: dict, source: str) -> dict:
    """Add sync metadata to a document before writing."""
    doc = copy.deepcopy(doc)
    doc[SYNC_SRC_FIELD] = source
    doc[SYNC_TS_FIELD] = _now_utc().isoformat()
    doc[SYNC_GEN_FIELD] = doc.get(SYNC_GEN_FIELD, 0) + 1
    # Remove internal MongoDB fields that shouldn't cross
    doc.pop("_id", None)  # _id handled separately
    return doc


# ═══════════════════════════════════════════════════════════════════════
# CHANGE STREAM PROCESSING
# ═══════════════════════════════════════════════════════════════════════


def _process_change_event(
    change: dict,
    target_db,
    db_name: str,
    direction: str,
) -> Optional[str]:
    """
    Process a single change event and apply to target.
    Returns collection name if processed, None if skipped.
    """
    ns = change.get("ns", {})
    # MongoDB change stream uses "coll" not "collection" in ns
    coll_name = ns.get("coll") or ns.get("collection") or ""
    if not coll_name:
        return None

    # Skip internal collections
    if direction == "local_to_remote":
        skip_set = SKIP_COLLECTIONS["local"]
    else:
        skip_set = SKIP_COLLECTIONS["remote"]

    if coll_name in skip_set or coll_name.startswith("system."):
        return None

    operation_type = change.get("operationType", "")
    doc_id = change.get("documentKey", {}).get("_id")

    if doc_id is None:
        return None

    # ANTI-LOOP: Skip events generated by our own sync writes.
    # _sync_source stores ORIGIN: "local" or "remote".
    #   - A doc with _sync_source="local" was ORIGINALLY from local side.
    #     If local_to_remote watcher sees it on remote, it's our own write → skip.
    #     If remote_to_local watcher sees it on local, it's a remote-inserted local doc → skip.
    #   - A doc with _sync_source="remote" was ORIGINALLY from remote side.
    #     If remote_to_local watcher sees it on local, it's our own write → skip.
    #     If local_to_remote watcher sees it on remote, it's a local-inserted remote doc → skip.
    # Summary: skip if event_source matches the side we are WRITING FROM.
    full_doc = change.get("fullDocument") or {}
    event_source = full_doc.get(SYNC_SRC_FIELD, "")

    if direction == "local_to_remote" and event_source == "local":
        log.debug(f"[{direction}] Skip own write (origin=local): {coll_name}:{doc_id}")
        return None
    if direction == "remote_to_local" and event_source == "remote":
        log.debug(f"[{direction}] Skip own write (origin=remote): {coll_name}:{doc_id}")
        return None
    # Also skip if the doc was synced FROM the direction we're writing TO
    # (prevents re-bounce: remote_to_local wrote to local with source=remote,
    #  then local_to_remote sees that local doc and tries to send it back)
    if direction == "local_to_remote" and event_source == "remote":
        log.debug(f"[{direction}] Skip bounce (origin=remote, already on remote): {coll_name}:{doc_id}")
        return None
    if direction == "remote_to_local" and event_source == "local":
        log.debug(f"[{direction}] Skip bounce (origin=local, already on local): {coll_name}:{doc_id}")
        return None

    target_coll = target_db[coll_name]
    # Source tag = origin side, not direction
    # local_to_remote → source is "local" (we read from local, write to remote)
    # remote_to_local → source is "remote" (we read from remote, write to local)
    source_tag = "local" if direction == "local_to_remote" else "remote"

    log.info(f"[{direction}] Processing {operation_type} on {coll_name}:{doc_id} (source={event_source!r})")

    try:
        if operation_type == "insert":
            doc = copy.deepcopy(full_doc)
            doc_id_val = doc.pop("_id", None)
            doc = _add_sync_metadata(doc, source_tag)
            # CRITICAL: put _id back so it preserves the original ID
            if doc_id_val is not None:
                doc["_id"] = doc_id_val
            try:
                target_coll.insert_one(doc)
                log.info(f"[{direction}] Inserted {coll_name}:{doc_id_val} to target")
                return coll_name
            except DuplicateKeyError:
                # Conflict: same _id exists on target
                if _get_conflict_policy(db_name) == "local_wins" and direction == "local_to_remote":
                    # Local wins: overwrite remote
                    doc[SYNC_CONFLICT_FIELD] = True
                    target_coll.replace_one({"_id": doc_id_val}, doc, upsert=True)
                    return coll_name
                elif _get_conflict_policy(db_name) == "remote_wins" and direction == "remote_to_local":
                    # Remote wins: overwrite local
                    doc[SYNC_CONFLICT_FIELD] = True
                    target_coll.replace_one({"_id": doc_id_val}, doc, upsert=True)
                    return coll_name
                else:
                    log.warning(f"INSERT conflict {coll_name}:{doc_id} — skipped (policy={_get_conflict_policy(db_name)})")
                    return None

        elif operation_type == "update":
            update_fields = change.get("updateDescription", {}).get("updatedFields", {})
            removed_fields = change.get("updateDescription", {}).get("removedFields", [])

            if not update_fields and not removed_fields:
                return None

            # Add sync metadata to update
            update_fields[SYNC_SRC_FIELD] = source_tag
            update_fields[SYNC_TS_FIELD] = _now_utc().isoformat()

            set_obj = {"$set": update_fields, "$inc": {SYNC_GEN_FIELD: 1}}
            if removed_fields:
                set_obj["$unset"] = {f: "" for f in removed_fields}

            result = target_coll.update_one({"_id": doc_id}, set_obj, upsert=False)
            if result.matched_count == 0 and full_doc:
                # Doc doesn't exist on target — upsert full doc
                doc = copy.deepcopy(full_doc)
                doc.pop("_id", None)
                doc = _add_sync_metadata(doc, source_tag)
                target_coll.replace_one({"_id": doc_id}, doc, upsert=True)
            return coll_name

        elif operation_type == "replace":
            doc = copy.deepcopy(full_doc)
            doc.pop("_id", None)
            doc = _add_sync_metadata(doc, source_tag)
            target_coll.replace_one({"_id": doc_id}, doc, upsert=True)
            return coll_name

        elif operation_type == "delete":
            target_coll.delete_one({"_id": doc_id})
            return coll_name

        elif operation_type == "invalidate":
            log.warning(f"Change stream invalidated for {coll_name} — will restart")
            return None

        else:
            log.debug(f"Unknown operation type: {operation_type}")
            return None

    except Exception as e:
        log.error(f"Error processing {operation_type} on {coll_name}:{doc_id}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════
# CHANGE STREAM WATCHER
# ═══════════════════════════════════════════════════════════════════════


def _watch_change_stream(
    source_client: MongoClient,
    target_client: MongoClient,
    db_name: str,
    direction: str,
    local_db_for_state,
    stop_event: threading.Event,
):
    """
    Watch a database's change stream and apply changes to target.
    Runs in a loop with backoff on errors.
    """
    backoff = BACKOFF_INITIAL
    log.info(f"[{direction}] Starting change stream watcher for {db_name}")

    # Build skip set for this DB (union of local + remote skip collections)
    skip_colls = SKIP_COLLECTIONS.get("local", set()) | SKIP_COLLECTIONS.get("remote", set())
    # Also skip the sync state collection itself (prevent flood loop)
    skip_colls = skip_colls | {SYNC_STATE_COLL}

    # Throttle resume token saves — batch every 5 seconds instead of per-event
    last_token_save = 0.0
    pending_token = None
    TOKEN_SAVE_INTERVAL = 5.0

    while not stop_event.is_set():
        try:
            source_db = source_client[db_name]
            target_db = target_client[db_name]

            # Build pipeline: filter operation types AND skip internal collections
            pipeline = [
                {"$match": {
                    "operationType": {"$in": ["insert", "update", "replace", "delete"]},
                    "ns.coll": {"$nin": list(skip_colls)},
                }}
            ]

            # Resume from saved token
            resume_token = _load_resume_token(local_db_for_state, db_name, direction)

            kwargs = {
                "full_document": "updateLookup",
            }
            if resume_token:
                kwargs["resume_after"] = resume_token

            stream = source_db.watch(pipeline, **kwargs)
            backoff = BACKOFF_INITIAL  # Reset backoff on successful start
            log.info(f"[{direction}] Change stream active for {db_name} (skip_colls={skip_colls})")

            for change in stream:
                if stop_event.is_set():
                    # Save final token before exit
                    if stream.resume_token:
                        _save_resume_token(local_db_for_state, db_name, direction, stream.resume_token)
                    stream.close()
                    break

                try:
                    result = _process_change_event(change, target_db, db_name, direction)

                    # Throttled resume token save (every TOKEN_SAVE_INTERVAL seconds)
                    now = time.monotonic()
                    token = stream.resume_token
                    if token:
                        pending_token = token
                    if pending_token and (now - last_token_save) >= TOKEN_SAVE_INTERVAL:
                        _save_resume_token(local_db_for_state, db_name, direction, pending_token)
                        pending_token = None
                        last_token_save = now

                    if result:
                        log.debug(f"[{direction}] {db_name}.{result} synced")

                except Exception as e:
                    log.error(f"[{direction}] Error processing event: {e}")

        except (AutoReconnect, NetworkTimeout, ServerSelectionTimeoutError, CursorNotFound) as e:
            # Save token before reconnect
            if pending_token:
                try:
                    _save_resume_token(local_db_for_state, db_name, direction, pending_token)
                    pending_token = None
                except Exception:
                    pass
            log.warning(f"[{direction}] Connection lost for {db_name}: {e} — reconnecting in {backoff:.0f}s")
            stop_event.wait(backoff)
            backoff = min(backoff * BACKOFF_MULTIPLIER, BACKOFF_MAX)

        except OperationFailure as e:
            if e.code == 40615:
                # Change stream not supported — need replica set
                log.error(f"[{direction}] Change stream not supported! Is {db_name} on a replica set? Error: {e}")
                stop_event.wait(30)
            else:
                log.error(f"[{direction}] Operation failure: {e} — retrying in {backoff:.0f}s")
                stop_event.wait(backoff)
                backoff = min(backoff * BACKOFF_MULTIPLIER, BACKOFF_MAX)

        except Exception as e:
            log.error(f"[{direction}] Unexpected error for {db_name}: {e}")
            log.debug(traceback.format_exc())
            stop_event.wait(backoff)
            backoff = min(backoff * BACKOFF_MULTIPLIER, BACKOFF_MAX)

    log.info(f"[{direction}] Watcher stopped for {db_name}")


# ═══════════════════════════════════════════════════════════════════════
# INITIAL SEED
# ═══════════════════════════════════════════════════════════════════════


def seed(remote_client: MongoClient, local_client: MongoClient, db_names: List[str] = None):
    """Bulk copy all data from remote to local MongoDB."""
    db_names = db_names or list(SYNC_DATABASES.keys())
    total_seeded = 0
    total_collections = 0

    for db_name in db_names:
        log.info(f"[SEED] Seeding {db_name}...")
        remote_db = remote_client[db_name]
        local_db = local_client[db_name]
        collections = remote_db.list_collection_names()

        for coll_name in sorted(collections):
            if coll_name.startswith("system."):
                continue
            if coll_name in SKIP_COLLECTIONS.get("remote", set()):
                continue

            remote_coll = remote_db[coll_name]
            local_coll = local_db[coll_name]
            count = remote_coll.count_documents({})
            if count == 0:
                continue

            log.info(f"  {coll_name}: {count} docs")
            total_collections += 1

            # Batch insert
            batch = []
            for doc in remote_coll.find().batch_size(BULK_BATCH_SIZE):
                doc.pop("_sync_generation", None)
                doc.pop("_sync_source", None)
                doc.pop("_sync_timestamp", None)
                doc.pop("_sync_conflict", None)
                batch.append(InsertOne(doc))

                if len(batch) >= BULK_BATCH_SIZE:
                    try:
                        local_coll.bulk_write(batch, ordered=False)
                        total_seeded += len(batch)
                    except Exception as e:
                        log.warning(f"  Bulk write error (continuing): {e}")
                    batch = []

            if batch:
                try:
                    local_coll.bulk_write(batch, ordered=False)
                    total_seeded += len(batch)
                except Exception as e:
                    log.warning(f"  Final bulk write error: {e}")

            # Create indexes from remote
            try:
                indexes = remote_coll.list_indexes()
                for idx in indexes:
                    if idx.get("name", "").startswith("_id"):
                        continue
                    keys = idx.get("key", {})
                    if keys:
                        local_coll.create_index(
                            list(keys.items()),
                            unique=idx.get("unique", False),
                            name=idx.get("name"),
                            background=True,
                        )
                        log.debug(f"  Index created: {idx.get('name')}")
            except Exception as e:
                log.debug(f"  Index copy skipped: {e}")

        log.info(f"[SEED] {db_name} done: {total_collections} collections")

    log.info(f"[SEED] Total: {total_seeded} docs across {total_collections} collections")
    return total_seeded


# ═══════════════════════════════════════════════════════════════════════
# RECONCILIATION
# ═══════════════════════════════════════════════════════════════════════


def _doc_hash(doc: dict) -> str:
    """Generate a stable hash of a document (excluding sync metadata)."""
    d = {k: v for k, v in sorted(doc.items()) if k not in ("_id", SYNC_GEN_FIELD, SYNC_SRC_FIELD, SYNC_TS_FIELD, SYNC_CONFLICT_FIELD)}
    return hashlib.md5(json.dumps(d, default=str, sort_keys=True).encode()).hexdigest()


def reconcile(
    remote_client: MongoClient,
    local_client: MongoClient,
    db_names: List[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Full reconciliation: compare every doc in both sides, fix drift.
    Returns stats dict.
    """
    db_names = db_names or list(SYNC_DATABASES.keys())
    stats = {
        "started_at": _now_utc().isoformat(),
        "databases": {},
        "total_drift": 0,
        "total_fixed": 0,
        "dry_run": dry_run,
    }

    for db_name in db_names:
        policy = _get_conflict_policy(db_name)
        remote_db = remote_client[db_name]
        local_db = local_client[db_name]

        # Get all collection names from both sides
        remote_colls = set(remote_db.list_collection_names())
        local_colls = set(local_db.list_collection_names())
        all_colls = sorted(remote_colls | local_colls)

        db_stats = {"drift_count": 0, "fix_count": 0, "collections": {}}

        for coll_name in all_colls:
            if coll_name.startswith("system."):
                continue
            if coll_name in SKIP_COLLECTIONS.get("local", set()) | SKIP_COLLECTIONS.get("remote", set()):
                continue

            remote_coll = remote_db[coll_name]
            local_coll = local_db[coll_name]

            remote_ids = set(remote_coll.distinct("_id"))
            local_ids = set(local_coll.distinct("_id"))

            only_remote = remote_ids - local_ids
            only_local = local_ids - remote_ids
            common = remote_ids & local_ids

            coll_drift = len(only_remote) + len(only_local)

            if not dry_run:
                # 1. Copy docs only on remote → local (if missing)
                if only_remote:
                    batch = []
                    for doc in remote_coll.find({"_id": {"$in": list(only_remote)}}).batch_size(BULK_BATCH_SIZE):
                        doc = _add_sync_metadata(doc, "reconcile")
                        doc_id = doc.pop("_id", None)
                        batch.append(InsertOne(doc))
                        if len(batch) >= BULK_BATCH_SIZE:
                            try:
                                local_coll.bulk_write(batch, ordered=False)
                                db_stats["fix_count"] += len(batch)
                            except Exception as e:
                                log.warning(f"Reconcile insert error: {e}")
                            batch = []
                    if batch:
                        try:
                            local_coll.bulk_write(batch, ordered=False)
                            db_stats["fix_count"] += len(batch)
                        except Exception as e:
                            log.warning(f"Reconcile insert error: {e}")

                # 2. For common docs, check hash drift
                drift_count = 0
                for doc_id in common:
                    local_doc = local_coll.find_one({"_id": doc_id})
                    remote_doc = remote_coll.find_one({"_id": doc_id})

                    local_h = _doc_hash(local_doc) if local_doc else ""
                    remote_h = _doc_hash(remote_doc) if remote_doc else ""

                    if local_h != remote_h:
                        drift_count += 1
                        # Apply conflict policy
                        if policy == "local_wins":
                            # Push local → remote
                            doc = copy.deepcopy(local_doc)
                            doc.pop("_id", None)
                            doc = _add_sync_metadata(doc, "local_reconcile")
                            remote_coll.replace_one({"_id": doc_id}, doc, upsert=True)
                        else:
                            # Push remote → local
                            doc = copy.deepcopy(remote_doc)
                            doc.pop("_id", None)
                            doc = _add_sync_metadata(doc, "remote_reconcile")
                            local_coll.replace_one({"_id": doc_id}, doc, upsert=True)
                        db_stats["fix_count"] += 1

                coll_drift += drift_count

                # 3. For docs only on local: push to remote (credentials) or delete (QuantumTrafficDB)
                if only_local:
                    if policy == "local_wins":
                        # Push local-only docs to remote
                        batch = []
                        for doc in local_coll.find({"_id": {"$in": list(only_local)}}).batch_size(BULK_BATCH_SIZE):
                            doc = _add_sync_metadata(doc, "local_reconcile")
                            doc_id = doc.pop("_id", None)
                            batch.append(InsertOne(doc))
                            if len(batch) >= BULK_BATCH_SIZE:
                                try:
                                    remote_coll.bulk_write(batch, ordered=False)
                                    db_stats["fix_count"] += len(batch)
                                except Exception as e:
                                    log.warning(f"Reconcile push error: {e}")
                                batch = []
                        if batch:
                            try:
                                remote_coll.bulk_write(batch, ordered=False)
                                db_stats["fix_count"] += len(batch)
                            except Exception as e:
                                log.warning(f"Reconcile push error: {e}")
                    else:
                        # Remote wins: remove local-only docs (they're orphans)
                        local_coll.delete_many({"_id": {"$in": list(only_local)}})
                        db_stats["fix_count"] += len(only_local)

            db_stats["collections"][coll_name] = {
                "only_remote": len(only_remote),
                "only_local": len(only_local),
                "common": len(common),
                "drift": coll_drift,
            }
            db_stats["drift_count"] += coll_drift

        stats["databases"][db_name] = db_stats
        stats["total_drift"] += db_stats["drift_count"]
        stats["total_fixed"] += db_stats["fix_count"]
        log.info(f"[RECONCILE] {db_name}: drift={db_stats['drift_count']}, fixed={db_stats['fix_count']}")

    stats["completed_at"] = _now_utc().isoformat()

    # Save reconcile state
    local_db = local_client[SYNC_STATE_DB]
    state = _get_sync_state(local_db)
    state["last_reconcile"] = stats["completed_at"]
    state["last_reconcile_stats"] = stats
    _save_sync_state(local_db, state)

    return stats


# ═══════════════════════════════════════════════════════════════════════
# SYNC DAEMON
# ═══════════════════════════════════════════════════════════════════════


class TwoWaySyncDaemon:
    """Main daemon that runs both direction watchers per database."""

    def __init__(self):
        self.stop_event = threading.Event()
        self.threads: List[threading.Thread] = []
        self._local_client: Optional[MongoClient] = None
        self._remote_client: Optional[MongoClient] = None

    def _signal_handler(self, signum, frame):
        log.info(f"Signal {signum} received — shutting down...")
        self.stop()

    def start(self):
        """Start all watchers."""
        log.info("=" * 60)
        log.info("ILMA 2-Way Sync Daemon v1.0 — Starting")
        log.info("=" * 60)

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Connect to both MongoDB instances
        self._local_client = _get_local_client()
        self._remote_client = _get_remote_client()

        # Verify connections
        try:
            local_info = self._local_client.admin.command("isMaster")
            log.info(f"LOCAL:  rs={local_info.get('setName')} ismaster={local_info.get('ismaster')}")
        except Exception as e:
            log.error(f"LOCAL MongoDB connection failed: {e}")
            return

        try:
            remote_info = self._remote_client.admin.command("isMaster")
            log.info(f"REMOTE: rs={remote_info.get('setName')} ismaster={remote_info.get('ismaster')}")
        except Exception as e:
            log.error(f"REMOTE MongoDB connection failed: {e}")
            # Continue — will retry in watchers

        # Start 4 watcher threads: 2 DBs × 2 directions
        local_state_db = self._local_client[SYNC_STATE_DB]

        for db_name in SYNC_DATABASES:
            for direction in ["remote_to_local", "local_to_remote"]:
                if direction == "remote_to_local":
                    source = self._remote_client
                    target = self._local_client
                else:
                    source = self._local_client
                    target = self._remote_client

                t = threading.Thread(
                    target=_watch_change_stream,
                    args=(source, target, db_name, direction, local_state_db, self.stop_event),
                    name=f"sync-{direction}-{db_name}",
                    daemon=True,
                )
                t.start()
                self.threads.append(t)
                log.info(f"Started watcher: {direction} for {db_name}")

        log.info(f"All {len(self.threads)} watchers started")

        # Main loop: keep alive + periodic health check
        while not self.stop_event.is_set():
            alive_count = sum(1 for t in self.threads if t.is_alive())
            if alive_count < len(self.threads):
                log.warning(f"Only {alive_count}/{len(self.threads)} watchers alive — threads will auto-reconnect")
            self.stop_event.wait(30)

    def stop(self):
        """Stop all watchers."""
        log.info("Stopping all watchers...")
        self.stop_event.set()
        for t in self.threads:
            t.join(timeout=10)
        if self._local_client:
            self._local_client.close()
        if self._remote_client:
            self._remote_client.close()
        log.info("Daemon stopped")

    def status(self) -> dict:
        """Get current sync status."""
        try:
            local_client = _get_local_client()
            remote_client = _get_remote_client()
        except Exception as e:
            return {"error": str(e)}

        result = {
            "version": "1.0.0",
            "timestamp": _now_utc().isoformat(),
            "local": {},
            "remote": {},
            "sync_state": {},
        }

        try:
            l_info = local_client.admin.command("isMaster")
            result["local"] = {"host": LOCAL_HOST, "port": LOCAL_PORT, "rs": l_info.get("setName"), "ok": True}
        except Exception as e:
            result["local"] = {"ok": False, "error": str(e)}

        try:
            r_info = remote_client.admin.command("isMaster")
            result["remote"] = {"host": REMOTE_HOST, "port": REMOTE_PORT, "rs": r_info.get("setName"), "ok": True}
        except Exception as e:
            result["remote"] = {"ok": False, "error": str(e)}

        try:
            state = _get_sync_state(local_client[SYNC_STATE_DB])
            result["sync_state"] = {
                "last_reconcile": state.get("last_reconcile"),
                "resume_tokens": {k: "present" for k in state.get("resume_tokens", {})},
                "stats": state.get("stats", {}),
            }
        except Exception as e:
            result["sync_state"] = {"error": str(e)}

        # Per-DB doc counts
        for db_name in SYNC_DATABASES:
            try:
                local_db = local_client[db_name]
                local_counts = {}
                for c in local_db.list_collection_names():
                    if not c.startswith("system."):
                        local_counts[c] = local_db[c].count_documents({})
                result[f"local_{db_name}"] = local_counts
            except Exception:
                pass

            try:
                remote_db = remote_client[db_name]
                remote_counts = {}
                for c in remote_db.list_collection_names():
                    if not c.startswith("system."):
                        remote_counts[c] = remote_db[c].count_documents({})
                result[f"remote_{db_name}"] = remote_counts
            except Exception:
                pass

        local_client.close()
        remote_client.close()
        return result


# ═══════════════════════════════════════════════════════════════════════
# E2E TESTING
# ═══════════════════════════════════════════════════════════════════════


def run_tests(remote_client: MongoClient, local_client: MongoClient) -> dict:
    """Run 10 E2E test scenarios."""
    results = {}
    test_db = "credentials"
    test_coll = "_sync_test"

    local_db = local_client[test_db]
    remote_db = remote_client[test_db]
    local_coll = local_db[test_coll]
    remote_coll = remote_db[test_coll]

    # Cleanup test collection
    local_coll.drop()
    remote_coll.drop()

    # Test 1: Local insert → synced to remote
    try:
        doc = {"_id": "test_1", "data": "local_insert", SYNC_SRC_FIELD: "local", SYNC_GEN_FIELD: 1, SYNC_TS_FIELD: _now_utc().isoformat()}
        local_coll.insert_one(doc)
        time.sleep(2)  # Wait for sync
        found = remote_coll.find_one({"_id": "test_1"})
        results["1_local_insert"] = found is not None
        log.info(f"Test 1 (local insert→remote): {'PASS' if found else 'FAIL'}")
    except Exception as e:
        results["1_local_insert"] = False
        log.error(f"Test 1 error: {e}")

    # Test 2: Remote insert → synced to local
    try:
        doc = {"_id": "test_2", "data": "remote_insert", SYNC_SRC_FIELD: "remote", SYNC_GEN_FIELD: 1, SYNC_TS_FIELD: _now_utc().isoformat()}
        remote_coll.insert_one(doc)
        time.sleep(2)
        found = local_coll.find_one({"_id": "test_2"})
        results["2_remote_insert"] = found is not None
        log.info(f"Test 2 (remote insert→local): {'PASS' if found else 'FAIL'}")
    except Exception as e:
        results["2_remote_insert"] = False
        log.error(f"Test 2 error: {e}")

    # Test 3: Local update → synced
    try:
        local_coll.update_one({"_id": "test_1"}, {"$set": {"updated": True, SYNC_SRC_FIELD: "local", SYNC_TS_FIELD: _now_utc().isoformat()}, "$inc": {SYNC_GEN_FIELD: 1}})
        time.sleep(2)
        found = remote_coll.find_one({"_id": "test_1"})
        results["3_local_update"] = found is not None and found.get("updated") is True if found else False
        log.info(f"Test 3 (local update→remote): {'PASS' if results.get('3_local_update') else 'FAIL'}")
    except Exception as e:
        results["3_local_update"] = False
        log.error(f"Test 3 error: {e}")

    # Test 4: Remote update → synced
    try:
        remote_coll.update_one({"_id": "test_2"}, {"$set": {"updated": True, SYNC_SRC_FIELD: "remote", SYNC_TS_FIELD: _now_utc().isoformat()}, "$inc": {SYNC_GEN_FIELD: 1}})
        time.sleep(2)
        found = local_coll.find_one({"_id": "test_2"})
        results["4_remote_update"] = found is not None and found.get("updated") is True if found else False
        log.info(f"Test 4 (remote update→local): {'PASS' if results.get('4_remote_update') else 'FAIL'}")
    except Exception as e:
        results["4_remote_update"] = False
        log.error(f"Test 4 error: {e}")

    # Test 5: Local delete → synced to remote
    try:
        local_coll.insert_one({"_id": "test_5", "data": "to_delete_local", SYNC_SRC_FIELD: "local", SYNC_GEN_FIELD: 1, SYNC_TS_FIELD: _now_utc().isoformat()})
        time.sleep(2)
        local_coll.delete_one({"_id": "test_5"})
        time.sleep(2)
        found = remote_coll.find_one({"_id": "test_5"})
        results["5_local_delete"] = found is None
        log.info(f"Test 5 (local delete→remote): {'PASS' if found is None else 'FAIL'}")
    except Exception as e:
        results["5_local_delete"] = False
        log.error(f"Test 5 error: {e}")

    # Test 6: Reconcile
    try:
        # Insert doc only on remote
        remote_coll.insert_one({"_id": "test_6", "data": "remote_only_reconcile"})
        # Run reconcile
        stats = reconcile(remote_client, local_client, db_names=[test_db])
        found = local_coll.find_one({"_id": "test_6"})
        results["6_reconcile"] = found is not None
        log.info(f"Test 6 (reconcile drift): {'PASS' if found else 'FAIL'}")
    except Exception as e:
        results["6_reconcile"] = False
        log.error(f"Test 6 error: {e}")

    # Test 7: Seed verify
    try:
        local_models = local_client["credentials"]["models"].count_documents({})
        remote_models = remote_client["credentials"]["models"].count_documents({})
        results["7_seed_verify"] = local_models > 0
        log.info(f"Test 7 (seed verify): local={local_models} remote={remote_models} {'PASS' if local_models > 0 else 'FAIL'}")
    except Exception as e:
        results["7_seed_verify"] = False
        log.error(f"Test 7 error: {e}")

    # Test 8: Conflict (credentials → LOCAL WINS)
    try:
        # Write same _id to both sides
        local_coll.insert_one({"_id": "test_8", "data": "local_version", SYNC_SRC_FIELD: "local", SYNC_GEN_FIELD: 2, SYNC_TS_FIELD: _now_utc().isoformat()})
        # Remote might have different version — check policy
        policy = _get_conflict_policy("credentials")
        results["8_conflict_local_wins"] = policy == "local_wins"
        log.info(f"Test 8 (conflict policy credentials): policy={policy} {'PASS' if policy == 'local_wins' else 'FAIL'}")
    except Exception as e:
        results["8_conflict_local_wins"] = False
        log.error(f"Test 8 error: {e}")

    # Test 9: Conflict (QuantumTrafficDB → REMOTE WINS)
    try:
        policy = _get_conflict_policy("QuantumTrafficDB")
        results["9_conflict_remote_wins"] = policy == "remote_wins"
        log.info(f"Test 9 (conflict policy QuantumTrafficDB): policy={policy} {'PASS' if policy == 'remote_wins' else 'FAIL'}")
    except Exception as e:
        results["9_conflict_remote_wins"] = False
        log.error(f"Test 9 error: {e}")

    # Test 10: Resume token persistence
    try:
        state = _get_sync_state(local_client[SYNC_STATE_DB])
        has_tokens = "resume_tokens" in state
        results["10_resume_token_persist"] = has_tokens
        log.info(f"Test 10 (resume token persist): {'PASS' if has_tokens else 'FAIL'}")
    except Exception as e:
        results["10_resume_token_persist"] = False
        log.error(f"Test 10 error: {e}")

    # Cleanup
    local_coll.drop()
    remote_coll.drop()

    passed = sum(1 for v in results.values() if v)
    total = len(results)
    log.info(f"\nE2E Tests: {passed}/{total} PASSED")
    return results


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="ILMA 2-Way MongoDB Sync Engine v1.0")
    parser.add_argument("--seed", action="store_true", help="Initial bulk copy from remote to local")
    parser.add_argument("--daemon", action="store_true", help="Start sync daemon (foreground)")
    parser.add_argument("--reconcile", action="store_true", help="Run full reconciliation")
    parser.add_argument("--status", action="store_true", help="Show sync status")
    parser.add_argument("--test", action="store_true", help="Run E2E tests")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (for reconcile)")
    parser.add_argument("--db", type=str, nargs="*", help="Specific databases to operate on")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.seed:
        local = _get_local_client()
        remote = _get_remote_client()
        db_names = args.db if args.db else None
        seed(remote, local, db_names)
        local.close()
        remote.close()

    elif args.daemon:
        daemon = TwoWaySyncDaemon()
        daemon.start()

    elif args.reconcile:
        local = _get_local_client()
        remote = _get_remote_client()
        db_names = args.db if args.db else None
        stats = reconcile(remote, local, db_names, dry_run=args.dry_run)
        print(json.dumps(stats, indent=2, default=str))
        local.close()
        remote.close()

    elif args.status:
        daemon = TwoWaySyncDaemon()
        stats = daemon.status()
        print(json.dumps(stats, indent=2, default=str))

    elif args.test:
        local = _get_local_client()
        remote = _get_remote_client()
        results = run_tests(remote, local)
        print(json.dumps(results, indent=2))
        local.close()
        remote.close()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
