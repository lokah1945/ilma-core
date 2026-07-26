#!/usr/bin/env python3
"""
ilma_model_status.py — ILMA Model Status Registry v2.0
======================================================
Reads availability from PROVIDER_INTELLIGENCE_MASTER.json (SOT).
No separate status JSON file. Status lives inside each model/provider entry.

Status values per entity:
  AVAILABLE    = Can be used, routing eligible (default)
  UNAVAILABLE  = Disabled / banned (Bos mandate / maintenance)
  MAINTENANCE  = Degraded / maintenance window
  DEPRECATED   = Deprecated, do not use

Design:
  - Optimistic default: unknown = AVAILABLE (fail-safe)
  - Explicit status: every model/provider has a "status" field
  - DB-first: status lives inside PROVIDER_INTELLIGENCE_MASTER.json
  - All pipeline modules import this module for availability checks

Usage:
    from ilma_model_status import (
        is_available, is_unavailable,
        is_provider_available, is_model_available,
        get_available_providers, get_unavailable_providers,
        get_available_models, filter_unavailable,
        set_status, disable, enable,
        get_registry_summary
    )
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ====================
# Paths
# ====================

ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
DB_PATH = ILMA_PROFILE / "ilma_model_router_data" / "PROVIDER_INTELLIGENCE_MASTER.json"

# ====================
# Status Constants
# ====================

STATUS_AVAILABLE = "AVAILABLE"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_MAINTENANCE = "MAINTENANCE"
STATUS_DEPRECATED = "DEPRECATED"

ALL_STATUSES = {STATUS_AVAILABLE, STATUS_UNAVAILABLE, STATUS_MAINTENANCE, STATUS_DEPRECATED}
INACTIVE_STATUSES = {STATUS_UNAVAILABLE, STATUS_MAINTENANCE, STATUS_DEPRECATED}

# ====================
# Model Status Registry (DB-backed)
# ====================

class ModelStatusRegistry:
    """
    Availability registry backed by PROVIDER_INTELLIGENCE_MASTER.json.
    
    Single Source of Truth: PROVIDER_INTELLIGENCE_MASTER.json
    - Each provider has a "status" field (default AVAILABLE)
    - Each model has a "status" field (default AVAILABLE)
    - Fallback to DEFAULT_DISABLED_PROVIDERS for any entity not yet
      annotated in the DB
    
    Status precedence (highest wins):
      1. Model-level "status" field in DB
      2. Provider-level "status" field in DB
      3. DEFAULT_DISABLED_* hardcoded list
      4. AVAILABLE (optimistic default)
    """

    _instance: Optional["ModelStatusRegistry"] = None
    _db_cache: Optional[Dict[str, Any]] = None
    _db_mtime: float = 0.0

    def __new__(cls, *args, **kwargs) -> "ModelStatusRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, reload: bool = False):
        if self._initialized and not reload:
            return
        self._initialized = True

    # ====================
    # DB access
    # ====================

    def _load_db(self, force: bool = False) -> Dict[str, Any]:
        """Load DB from disk with cache invalidation on mtime change."""
        if self._db_cache is not None and not force:
            return self._db_cache
        if not DB_PATH.exists():
            raise FileNotFoundError(f"DB not found: {DB_PATH}")
        mtime = os.path.getmtime(DB_PATH)
        if self._db_cache is None or mtime != self._db_mtime:
            with open(DB_PATH) as f:
                self._db_cache = json.load(f)
            self._db_mtime = mtime
            logger.debug(f"[ModelStatusRegistry] DB loaded from {DB_PATH}")
        return self._db_cache

    def reload(self) -> None:
        """Force reload DB from disk."""
        self._load_db(force=True)
        logger.info("[ModelStatusRegistry] DB reloaded")

    @property
    def _db(self) -> Dict[str, Any]:
        """Lazy DB accessor."""
        return self._load_db()

    # ====================
    # Core: Status Resolution
    # ====================

    def _provider_status(self, provider_id: str) -> str:
        """Get status of a provider from DB."""
        db = self._db
        providers = db.get("providers", {})
        if provider_id in providers:
            return providers[provider_id].get("status", STATUS_AVAILABLE)
        return STATUS_AVAILABLE

    def _model_status_in_db(self, provider_id: str, model_id: str) -> Optional[str]:
        """Get model status directly from DB. Returns None if not found."""
        db = self._db
        providers = db.get("providers", {})
        if provider_id in providers:
            models = providers[provider_id].get("models", {})
            if model_id in models:
                return models[model_id].get("status")
            # Also check without provider prefix in model_id
            clean_id = model_id.split("/")[-1]
            for mid, mdata in models.items():
                if mid == clean_id or mid.split("/")[-1] == clean_id:
                    return mdata.get("status")
        return None

    def get_status(self, entity: str) -> str:
        """
        Get status for any entity (provider, model).

        Resolves:
          - "nvidia"         → provider-level status
          - "useai"          → provider-level status
          - "openrouter"     → provider-level status
          - "nvidia/llama-3.1" → model-level status (with fallback)
        """
        entity = entity.strip()
        entity_lower = entity.lower()

        # === Model (contains "/") ===
        if "/" in entity:
            parts = entity.split("/", 1)
            provider_id = parts[0]
            model_id = parts[1]

            # DB model-level check (user-controlled)
            db_status = self._model_status_in_db(provider_id, model_id)
            if db_status:
                return db_status

            # DB provider-level fallback (user-controlled)
            prov_status = self._provider_status(provider_id)
            if prov_status != STATUS_AVAILABLE:
                return prov_status

            # All other entities → AVAILABLE (optimistic default)
            return STATUS_AVAILABLE

        # === Provider ID (no "/") ===
        # DB provider-level (user-controlled)
        prov_status = self._provider_status(entity)
        if prov_status != STATUS_AVAILABLE:
            return prov_status

        return STATUS_AVAILABLE

    def is_available(self, entity: str) -> bool:
        """True if entity status is AVAILABLE."""
        return self.get_status(entity) == STATUS_AVAILABLE

    def is_unavailable(self, entity: str) -> bool:
        """True if entity is UNAVAILABLE / MAINTENANCE / DEPRECATED."""
        return self.get_status(entity) in INACTIVE_STATUSES

    def is_provider_available(self, provider_id: str) -> bool:
        """True if provider is AVAILABLE."""
        return self.is_available(provider_id)

    def is_model_available(self, model_id: str) -> bool:
        """True if model is AVAILABLE (resolves provider + model level)."""
        return self.is_available(model_id)

    # ====================
    # Bulk / Filter
    # ====================

    def get_all_providers(self) -> List[str]:
        """Return all provider IDs in DB."""
        return list(self._db.get("providers", {}).keys())

    def get_available_providers(self) -> List[str]:
        """Return AVAILABLE provider IDs."""
        return [p for p in self.get_all_providers() if self.is_provider_available(p)]

    def get_unavailable_providers(self) -> List[str]:
        """Return UNAVAILABLE provider IDs."""
        return [p for p in self.get_all_providers()
                if not self.is_provider_available(p)]

    def filter_unavailable(
        self,
        candidates: List[Dict[str, Any]],
        key_field: str = "model_id",
        provider_field: str = "provider",
    ) -> List[Dict[str, Any]]:
        """
        Filter out UNAVAILABLE models/providers from candidate list.
        
        Args:
            candidates: List of model dicts
            key_field: Field containing model_id (e.g. "model_id", "id")
            provider_field: Field containing provider_id
            
        Returns:
            Filtered list — only AVAILABLE candidates
        """
        filtered = []
        skipped = []
        
        for candidate in candidates:
            mid = candidate.get(key_field, "")
            prov = candidate.get(provider_field, "")

            model_ok = self.is_model_available(mid) if mid else True
            prov_ok = self.is_provider_available(prov) if prov else True

            if model_ok and prov_ok:
                filtered.append(candidate)
            else:
                reasons = []
                if not model_ok:
                    reasons.append(f"model={self.get_status(mid)}")
                if not prov_ok:
                    reasons.append(f"provider={self.get_status(prov)}")
                skipped.append({"model": mid or prov, "reason": ", ".join(reasons)})

        if skipped:
            logger.info(f"[ModelStatusRegistry] Filtered {len(skipped)} unavailable: {skipped}")

        return filtered

    # ====================
    # Status mutation (writes back to DB)
    # ====================

    def _backup_db(self) -> None:
        """Backup DB before mutation."""
        if not DB_PATH.exists():
            return
        backup_dir = ILMA_PROFILE / "ilma_model_router_data" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"PROVIDER_INTELLIGENCE_MASTER.{ts}.json"
        with open(DB_PATH) as src:
            with open(backup_path, "w") as dst:
                dst.write(src.read())
        logger.info(f"[ModelStatusRegistry] Backup saved: {backup_path}")

    def _audit(self, action: str, entity: str, old: str, new: str, note: str = "") -> None:
        """Record audit in DB _meta."""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action,
            "entity": entity,
            "old_status": old,
            "new_status": new,
            "note": note,
        }
        self._db.setdefault("_audit", [])
        self._db["_audit"].insert(0, entry)
        self._db["_audit"] = self._db["_audit"][:100]  # keep last 100
        self._db["_meta"]["last_status_change"] = entry["timestamp"]

    def set_status(
        self,
        entity: str,
        status: str,
        note: str = "",
        updated_by: str = "runtime",
        save: bool = True,
    ) -> bool:
        """
        Set status for provider or model, persist to DB.
        Returns True if changed, False if no change.
        """
        if status not in ALL_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Must be one of {ALL_STATUSES}")

        old = self.get_status(entity)
        if old == status:
            logger.debug(f"No change needed for {entity}: already {status}")
            return False

        self._backup_db()
        self._audit("set_status", entity, old, status, note)

        if "/" in entity:
            # Model-level
            provider_id, model_id = entity.split("/", 1)
            providers = self._db.setdefault("providers", {})
            providers.setdefault(provider_id, {"models": {}})
            providers[provider_id]["models"].setdefault(model_id, {})
            providers[provider_id]["models"][model_id]["status"] = status
            providers[provider_id]["models"][model_id]["status_note"] = note
            providers[provider_id]["models"][model_id]["status_updated_at"] = (
                datetime.utcnow().isoformat() + "Z"
            )
            providers[provider_id]["models"][model_id]["status_updated_by"] = updated_by
        else:
            # Provider-level
            providers = self._db.setdefault("providers", {})
            providers.setdefault(entity, {"models": {}})
            providers[entity]["status"] = status
            providers[entity]["status_note"] = note
            providers[entity]["status_updated_at"] = (
                datetime.utcnow().isoformat() + "Z"
            )
            providers[entity]["status_updated_by"] = updated_by

        if save:
            with open(DB_PATH, "w") as f:
                json.dump(self._db, f, indent=2, ensure_ascii=False)
            self._db_cache = None  # invalidate cache

        logger.info(f"[ModelStatusRegistry] {entity}: {old} → {status} ({note})")
        return True

    def set_provider_status(self, provider: str, status: str, note: str = "") -> bool:
        """Set provider status."""
        return self.set_status(provider, status, note)

    def set_model_status(self, model: str, status: str, note: str = "") -> bool:
        """Set model status."""
        return self.set_status(model, status, note)

    def disable(self, entity: str, note: str = "") -> bool:
        """Convenience: set entity to UNAVAILABLE."""
        return self.set_status(entity, STATUS_UNAVAILABLE, note)

    def enable(self, entity: str, note: str = "") -> bool:
        """Convenience: set entity to AVAILABLE."""
        return self.set_status(entity, STATUS_AVAILABLE, note)

    # ====================
    # Summary / Report
    # ====================

    def summary(self) -> Dict[str, Any]:
        """Get registry summary."""
        providers = self._db.get("providers", {})
        available_providers = self.get_available_providers()
        unavailable_providers = self.get_unavailable_providers()

        # Count models — DB uses model_id as dict key, not field
        # Provider models: {"nvidia": {"models": {"DeepSeek-R1": {...}, ...}}}
        total_models = sum(len(p.get("models", {})) for p in providers.values())
        available_models = 0
        unavailable_models = 0
        for pdata in providers.values():
            for mid, mdata in pdata.get("models", {}).items():
                if "/" in str(mid):
                    entity_id = mid
                else:
                    entity_id = mid  # will resolve via provider-level check in get_status
                # get_status handles both bare model_id (provider-level) and canonical form
                if self.get_status(entity_id) == STATUS_AVAILABLE:
                    available_models += 1
                else:
                    unavailable_models += 1

        return {
            "total_providers": len(providers),
            "total_models": total_models,
            "available_providers": available_providers,
            "unavailable_providers": unavailable_providers,
            "available_models": available_models,
            "unavailable_models": unavailable_models,
            "db_path": str(DB_PATH),
            "db_mtime": datetime.fromtimestamp(self._db_mtime).isoformat() if self._db_mtime else None,
        }

    def dump(self) -> Dict[str, Any]:
        """Return full DB data."""
        return self._db.copy()


# ====================
# Module-level convenience functions (singleton)
# ====================

_registry: Optional[ModelStatusRegistry] = None

def get_registry() -> ModelStatusRegistry:
    global _registry
    if _registry is None:
        _registry = ModelStatusRegistry()
    return _registry


def is_available(entity: str) -> bool:
    """Check if entity is AVAILABLE."""
    return get_registry().is_available(entity)


def is_unavailable(entity: str) -> bool:
    """Check if entity is explicitly inactive (UNAVAILABLE/MAINTENANCE/DEPRECATED)."""
    return get_registry().is_unavailable(entity)


def is_provider_available(provider_id: str) -> bool:
    """Check if provider is AVAILABLE."""
    return get_registry().is_provider_available(provider_id)


def is_model_available(model_id: str) -> bool:
    """Check if model is AVAILABLE (provider + model level)."""
    return get_registry().is_model_available(model_id)


def filter_unavailable(
    candidates: List[Dict[str, Any]],
    key_field: str = "model_id",
) -> List[Dict[str, Any]]:
    """Filter unavailable models/providers from candidate list."""
    return get_registry().filter_unavailable(candidates, key_field=key_field)


def set_status(entity: str, status: str, note: str = "") -> bool:
    """Set entity status."""
    return get_registry().set_status(entity, status, note)


def disable(entity: str, note: str = "") -> bool:
    """Disable entity (set to UNAVAILABLE)."""
    return get_registry().disable(entity, note)


def enable(entity: str, note: str = "") -> bool:
    """Enable entity (set to AVAILABLE)."""
    return get_registry().enable(entity, note)


def get_registry_summary() -> Dict[str, Any]:
    """Get registry summary dict."""
    return get_registry().summary()


def reload_registry() -> None:
    """Reload DB from disk."""
    get_registry().reload()


# ====================
# CLI entrypoint
# ====================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="ILMA Model Status Registry CLI — DB-backed SOT"
    )
    parser.add_argument("--summary", action="store_true", help="Show registry summary")
    parser.add_argument("--status", metavar="ENTITY", help="Get status for entity")
    parser.add_argument("--set", nargs=3, metavar=("ENTITY", "STATUS", "NOTE"),
                        help="Set status: ENTITY STATUS NOTE")
    parser.add_argument("--enable", metavar="ENTITY", help="Enable entity")
    parser.add_argument("--disable", metavar="ENTITY", help="Disable entity")
    parser.add_argument("--list-providers", choices=["available", "unavailable"],
                        help="List providers by status")
    parser.add_argument("--reload", action="store_true", help="Force reload DB")
    args = parser.parse_args()

    reg = get_registry()
    if args.reload:
        reg.reload()
        print("✅ DB reloaded")

    if args.summary:
        import pprint
        pprint.pprint(reg.summary())
    elif args.status:
        st = reg.get_status(args.status)
        print(f"{args.status}: {st}")
    elif args.set:
        entity, status, note = args.set
        reg.set_status(entity, status, note)
        print(f"✅ {entity}: {status} ({note})")
    elif args.enable:
        reg.enable(args.enable)
        print(f"✅ {args.enable}: AVAILABLE")
    elif args.disable:
        reg.disable(args.disable)
        print(f"❌ {args.disable}: UNAVAILABLE")
    elif args.list_providers:
        if args.list_providers == "available":
            print("Available providers:", reg.get_available_providers())
        else:
            print("Unavailable providers:", reg.get_unavailable_providers())
    else:
        parser.print_help()