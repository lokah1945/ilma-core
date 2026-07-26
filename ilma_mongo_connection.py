#!/usr/bin/env python3
"""
ILMA MongoDB Connection Manager v1.0 (Phase P / TASK 1.2)
=========================================================
Fixes SCRAM-SHA-256 reconnection stability issue:
- Singleton client with connection pooling
- Reconnect on auth failure with exponential backoff
- Class-level cache survives multiple ILMAModelRouter() instances

Feature flag: config.yaml `mongodb_connection_manager_enabled` (default: True)
"""
from __future__ import annotations

import logging
import os
import random
import threading
import time
from typing import Optional

logger = logging.getLogger("ilma.mongo")


class MongoConnectionManager:
    """Singleton MongoDB connection with reconnection stability."""

    _instance: Optional["MongoConnectionManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._client = None
        self._last_connected = 0.0
        self._reconnect_attempts = 0
        self._max_retries = 3

    @classmethod
    def get_instance(cls) -> "MongoConnectionManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_client(self,
                   host: str = "127.0.0.1",
                   port: int = 27017,
                   username: str = "",
                   password: str = os.environ.get("ILMA_MONGO_LOCAL_PASS", ""),
                   authSource: str = "admin",
                   serverSelectionTimeoutMS: int = 5000,
                   socketTimeoutMS: int = 30000,
                   maxPoolSize: int = 10,
                   minPoolSize: int = 1,
                   retryWrites: bool = True,
                   directConnection: bool = True):
        """Get or create MongoDB client. Returns cached instance if healthy.
        
        v1.1 FIX: If username/password are empty, skip auth entirely (no-auth MongoDB).
        """
        if self._client is not None:
            return self._client
        return self._create_client(
            host=host, port=port, username=username, password=password,
            authSource=authSource, serverSelectionTimeoutMS=serverSelectionTimeoutMS,
            socketTimeoutMS=socketTimeoutMS, maxPoolSize=maxPoolSize,
            minPoolSize=minPoolSize, retryWrites=retryWrites,
        )

    def _create_client(self, **kwargs):
        """Create a new MongoDB client with retry logic.
        
        v1.1 FIX: Skip username/password when both are empty → no-auth connection.
        """
        from pymongo import MongoClient
        from pymongo.errors import OperationFailure, ServerSelectionTimeoutError

        for attempt in range(self._max_retries):
            try:
                # v1.1: Build connection kwargs — skip auth if no credentials
                conn_kwargs = {
                    "host": kwargs.get("host"),
                    "port": kwargs.get("port"),
                    "serverSelectionTimeoutMS": kwargs.get("serverSelectionTimeoutMS", 5000),
                    "socketTimeoutMS": kwargs.get("socketTimeoutMS", 30000),
                    "maxPoolSize": kwargs.get("maxPoolSize", 10),
                    "minPoolSize": kwargs.get("minPoolSize", 1),
                    "retryWrites": kwargs.get("retryWrites", True),
                    "directConnection": True,  # Avoid replica set discovery issues
                }
                _user = kwargs.get("username", "")
                _pass = kwargs.get("password", "")
                if _user and _pass:
                    conn_kwargs["username"] = _user
                    conn_kwargs["password"] = _pass
                    conn_kwargs["authSource"] = kwargs.get("authSource", "admin")
                else:
                    logger.info("[MongoManager] No auth credentials provided — connecting without auth")

                self._client = MongoClient(**conn_kwargs)
                # Verify with ping
                self._client.admin.command("ping")
                self._last_connected = time.time()
                self._reconnect_attempts = 0
                logger.info(f"[MongoManager] Client connected on attempt {attempt+1}")
                return self._client
            except (OperationFailure, ServerSelectionTimeoutError) as e:
                self._reconnect_attempts += 1
                if attempt < self._max_retries - 1:
                    delay = min(30, (2 ** attempt) + random.uniform(0, 1))
                    logger.warning(
                        f"[MongoManager] Auth/connection failed (attempt {attempt+1}/{self._max_retries}): {e}. "
                        f"Retrying in {delay:.2f}s"
                    )
                    self._client = None
                    time.sleep(delay)
                else:
                    logger.error(f"[MongoManager] All {self._max_retries} connection attempts failed: {e}")
                    raise

    def reconnect(self):
        """Force a fresh client (used by self-healing monitor)."""
        logger.info("[MongoManager] Forcing reconnect — clearing client")
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
        self._client = None
        return self.get_client()

    def health_check(self) -> bool:
        """Check if current client is healthy."""
        if self._client is None:
            # Try to create one
            try:
                self.get_client()
            except Exception:
                return False
        if self._client is None:
            return False
        try:
            self._client.admin.command("ping")
            return True
        except Exception as e:
            logger.warning(f"[MongoManager] Health check failed: {e}")
            return False

    def close(self):
        """Close the client."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None


# Singleton accessor
def get_mongo_manager() -> MongoConnectionManager:
    return MongoConnectionManager.get_instance()


if __name__ == "__main__":
    # Smoke test
    mgr = get_mongo_manager()
    client = mgr.get_client()
    print("Connection OK:", client.admin.command("ping"))
    print("Healthy:", mgr.health_check())
