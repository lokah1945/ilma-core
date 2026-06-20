#!/usr/bin/env python3
"""
sot_sync_daemon.py — real-time llm_providers → models auto-build watcher
========================================================================
Watches the FROZEN Tier-1 `llm_providers` collection via a MongoDB change stream
(replica set rs0). When a provider is added / edited / removed, it immediately
rebuilds that provider's models via sot_auto_sync:

  insert / update / replace  → sync_provider_delta(provider)   (build/refresh + prune)
  delete                     → cascade_out_provider(provider)  (hard-delete its models)

Resilience:
  • resume token persisted in sot_sync_state(_id='_daemon_resume') → resumes after restart
  • auto-reconnect with backoff on stream errors
  • per-provider debounce (collapses rapid multi-doc edits, e.g. openrouter's 2 keys)

The 6-hourly FULL delta sweep (catches provider-side model-list changes) is run
separately by ilma-sot-sync.timer → `sot_auto_sync.py --full`.

Run: python3 sot_sync_daemon.py    (foreground; managed by ilma-sot-sync-daemon.service)
"""
from __future__ import annotations
import os, sys, time, logging, threading
from datetime import datetime, timezone

import pymongo
from bson import Timestamp  # noqa: F401

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import sot_auto_sync as eng  # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s [sot-daemon] %(message)s")
log = logging.getLogger("ilma.sot.daemon")

RESUME_ID = "_daemon_resume"
DEBOUNCE_S = 3.0          # collapse rapid edits to the same provider
BACKOFF_MAX = 60


def _load_resume(db):
    doc = db[eng.STATE_COLL].find_one({"_id": RESUME_ID})
    return doc.get("resume_token") if doc else None


def _save_resume(db, token):
    db[eng.STATE_COLL].update_one({"_id": RESUME_ID},
                                  {"$set": {"resume_token": token, "updated_at": eng.now_utc()}},
                                  upsert=True)


def _provider_of(change) -> str | None:
    """Extract provider name from a change event (handles insert/update/delete)."""
    fd = change.get("fullDocument") or {}
    if fd.get("provider"):
        return fd["provider"]
    before = change.get("fullDocumentBeforeChange") or {}
    if before.get("provider"):
        return before["provider"]
    return None


class Debouncer:
    """Collapse rapid events per provider; fire `action` once after DEBOUNCE_S quiet."""
    def __init__(self):
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def schedule(self, provider: str, op: str):
        with self._lock:
            t = self._timers.get(provider)
            if t:
                t.cancel()
            timer = threading.Timer(DEBOUNCE_S, self._fire, args=(provider, op))
            timer.daemon = True
            self._timers[provider] = timer
            timer.start()

    def _fire(self, provider: str, op: str):
        with self._lock:
            self._timers.pop(provider, None)
        try:
            db = eng.get_db()
            if op == "delete" and provider not in eng.resolve_target_providers(db):
                log.info(f"{provider}: removed from llm_providers → cascade-out")
                r = eng.cascade_out_provider(db, provider, dry_run=False)
            else:
                log.info(f"{provider}: llm_providers changed ({op}) → delta sync")
                r = eng.sync_provider_delta(db, provider, dry_run=False)
                # score the (possibly new) models so they are immediately selectable
                if r.get("status") == "success":
                    eng._enrich_provider(provider, dry_run=False)
                # refresh runtime cache after a real change
                try:
                    import sot_materialize
                    sot_materialize.materialize_master(dry_run=False)
                    sot_materialize.materialize_api_key(dry_run=False, include_secrets=False)
                except Exception as e:
                    log.warning(f"materialize after {provider}: {e}")
            log.info(f"{provider}: done → {r}")
        except Exception as e:
            log.error(f"{provider}: sync failed: {e}")


def watch_loop():
    debouncer = Debouncer()
    backoff = 1
    while True:
        db = eng.get_db()
        coll = db["llm_providers"]
        resume = _load_resume(db)
        kwargs = dict(full_document="updateLookup",
                      full_document_before_change="whenAvailable")
        if resume:
            kwargs["resume_after"] = resume
        try:
            log.info(f"opening change stream on llm_providers (resume={'yes' if resume else 'no'})")
            with coll.watch(**kwargs) as stream:
                backoff = 1
                for change in stream:
                    op = change.get("operationType")
                    _save_resume(db, change.get("_id"))
                    if op not in ("insert", "update", "replace", "delete"):
                        continue
                    provider = _provider_of(change)
                    if not provider:
                        log.warning(f"event {op} with no provider name; skipped")
                        continue
                    debouncer.schedule(provider, op)
        except pymongo.errors.PyMongoError as e:
            # invalid/expired resume token → reset and start fresh
            msg = str(e)
            if "resume" in msg.lower() or "ChangeStreamHistoryLost" in msg:
                log.warning("resume token invalid — resetting to live tail")
                try:
                    db[eng.STATE_COLL].delete_one({"_id": RESUME_ID})
                except Exception:
                    pass
            log.error(f"change stream error: {msg[:160]} — reconnecting in {backoff}s")
            time.sleep(backoff)
            backoff = min(BACKOFF_MAX, backoff * 2)


if __name__ == "__main__":
    log.info("SOT sync daemon starting — watching llm_providers (Tier-1) for changes")
    watch_loop()
