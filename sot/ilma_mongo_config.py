#!/usr/bin/env python3
"""
ilma_mongo_config.py — SINGLE SOURCE OF TRUTH for MongoDB connection params
==============================================================================

All ILMA modules MUST import from here instead of hardcoding host/user/pass.

Architecture:
  - READ operations → LOCAL (127.0.0.1:27017) — fast, always available
  - WRITE/ADMIN operations → configurable (local or remote)
  - SYNC engine ← uses its own config (ilma_two_way_sync.py)

Two-way sync (ilma-sync-daemon.service) keeps local ↔ remote in sync.
Reading from local means zero network latency for SOT queries.

Usage:
    from ilma_mongo_config import MONGO_LOCAL, get_local_client, get_remote_client

    # READ from local (default for SOT queries)
    client = get_local_client()
    db = client["credentials"]

    # ADMIN/MAINTENANCE on remote
    remote = get_remote_client()
    rdb = remote["credentials"]
"""
from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("ilma.mongo_config")

# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

def _load_env() -> Dict[str, str]:
    """Load .env file into dict."""
    env: Dict[str, str] = {}
    env_path = Path("/root/.hermes/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    # System env overrides file
    for k, v in os.environ.items():
        if k.startswith("ILMA_MONGO"):
            env[k] = v
    return env


_ENV = _load_env()

# ---------------------------------------------------------------------------
# Connection configs
# ---------------------------------------------------------------------------

MONGO_LOCAL: Dict[str, Any] = dict(
    host="127.0.0.1",
    port=27017,
    username=_ENV.get("ILMA_MONGO_LOCAL_USER", ""),
    password=_ENV.get("ILMA_MONGO_LOCAL_PASS", ""),
    authSource="admin",
    directConnection=True,
    serverSelectionTimeoutMS=5000,
)

MONGO_REMOTE: Dict[str, Any] = dict(
    host=_ENV.get("ILMA_MONGO_HOST", "172.16.103.253"),
    port=int(_ENV.get("ILMA_MONGO_PORT", "27017")),
    username=_ENV.get("ILMA_MONGO_USER", "ilma_sync"),
    password=_ENV.get("ILMA_MONGO_PASS", ""),
    authSource="admin",
    directConnection=True,
    serverSelectionTimeoutMS=10000,
)

# Backward-compatible dict for legacy code that does `from X import MONGO`
MONGO = MONGO_LOCAL  # Default = read from local!

# ---------------------------------------------------------------------------
# Client factories
# ---------------------------------------------------------------------------

_local_client: Optional[Any] = None
_remote_client: Optional[Any] = None


def get_local_client():
    """Get or create a singleton local MongoDB client."""
    global _local_client
    if _local_client is not None:
        try:
            _local_client.admin.command("ping")
            return _local_client
        except Exception:
            _local_client = None

    from pymongo import MongoClient
    _local_client = MongoClient(**MONGO_LOCAL)
    return _local_client


def get_remote_client():
    """Get or create a singleton remote MongoDB client (Yapsi)."""
    global _remote_client
    if _remote_client is not None:
        try:
            _remote_client.admin.command("ping")
            return _remote_client
        except Exception:
            _remote_client = None

    from pymongo import MongoClient
    _remote_client = MongoClient(**MONGO_REMOTE)
    return _remote_client


def health() -> Dict[str, Any]:
    """Quick health check for both local and remote MongoDB."""
    result = {"local": False, "remote": False}
    try:
        c = get_local_client()
        c.admin.command("ping")
        result["local"] = True
    except Exception as e:
        result["local_error"] = str(e)
    try:
        c = get_remote_client()
        c.admin.command("ping")
        result["remote"] = True
    except Exception as e:
        result["remote_error"] = str(e)
    return result


if __name__ == "__main__":
    import json
    h = health()
    print(json.dumps(h, indent=2))
    if h["local"]:
        c = get_local_client()
        for db_name in ["credentials", "QuantumTrafficDB"]:
            count = c[db_name]["models"].count_documents({})
            print(f"  local {db_name}.models: {count} docs")
