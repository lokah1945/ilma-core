#!/usr/bin/env python3
"""
ilma_wrapper_nvidia_dashboard_sync.py — Sync wrapper-nvidia live models to dashboard DB.

Phase 72-fix: Dashboard DB model_ids table was empty (0 free models) because
SPEC_DB file missing. This script populates model_ids directly from wrapper-nvidia
live /v1/models endpoint so kanban_free_model_optimizer can use wrapper-nvidia models.

Usage:
    python3 ilma_wrapper_nvidia_dashboard_sync.py           # sync
    python3 ilma_wrapper_nvidia_dashboard_sync.py --verify  # verify only
"""

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List

import urllib.request
import urllib.error

ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
DASHBOARD_DB = ILMA_PROFILE / "data" / "ilma_dashboard.db"
WRAPPER_NVIDIA_URL = "http://127.0.0.1:9100/v1/models"
WRAPPER_NVIDIA_KEY = "wrapper-local-key"


def fetch_live_models() -> List[Dict]:
    """Fetch live model list from wrapper-nvidia."""
    req = urllib.request.Request(
        WRAPPER_NVIDIA_URL,
        headers={"Authorization": f"Bearer {WRAPPER_NVIDIA_KEY}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("data", [])
    except Exception as e:
        print(f"ERROR: Failed to fetch models from wrapper-nvidia: {e}")
        return []


def sync_to_dashboard_db(models: List[Dict]) -> Dict:
    """Insert/update wrapper-nvidia models in dashboard DB model_ids table."""
    if not DASHBOARD_DB.exists():
        print(f"ERROR: Dashboard DB not found at {DASHBOARD_DB}")
        return {"synced": 0, "error": "db_not_found"}

    conn = sqlite3.connect(str(DASHBOARD_DB))
    cur = conn.cursor()

    # Ensure table exists (match existing dashboard schema)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS model_ids (
            canonical_model_id TEXT,
            provider TEXT,
            provider_model_id TEXT,
            display_name TEXT,
            free_or_paid TEXT DEFAULT 'FREE',
            availability_status TEXT DEFAULT 'ACTIVE',
            allowed_by_policy INTEGER DEFAULT 1,
            context_window INTEGER DEFAULT 128000,
            max_output_tokens INTEGER DEFAULT 8192,
            modality TEXT DEFAULT 'text',
            supports_tools INTEGER DEFAULT 0,
            supports_json INTEGER DEFAULT 1,
            supports_vision INTEGER DEFAULT 0,
            supports_long_context INTEGER DEFAULT 1,
            quality_score REAL DEFAULT 0.5,
            coding_score REAL DEFAULT 0.0,
            reasoning_score REAL DEFAULT 0.0,
            tool_use_score REAL DEFAULT 0.0,
            specialization TEXT DEFAULT 'general',
            last_verified TEXT,
            benchmark_coverage TEXT DEFAULT 'wrapper-nvidia-live',
            caveat TEXT DEFAULT '',
            input_cost_per_1m REAL DEFAULT 0.0,
            output_cost_per_1m REAL DEFAULT 0.0,
            UNIQUE(provider, provider_model_id)
        )
    """)

    synced = 0
    skipped = 0
    for m in models:
        model_id = m.get("id", "")
        if not model_id:
            continue
        model_type = m.get("type", "chat")
        caps = m.get("capabilities", [])
        supports_vision = 1 if "vision" in caps or "image" in str(m.get("input", [])) else 0
        supports_tools = 1 if "tools" in caps or "function_calling" in caps else 0

        try:
            cur.execute("""
                INSERT OR REPLACE INTO model_ids
                    (canonical_model_id, provider, provider_model_id, display_name,
                     free_or_paid, allowed_by_policy, availability_status,
                     context_window, max_output_tokens, modality,
                     supports_tools, supports_vision, supports_long_context,
                     quality_score, specialization,
                     last_verified, benchmark_coverage)
                VALUES (?, ?, ?, ?, 'FREE', 1, 'ACTIVE',
                        128000, 8192, ?,
                        ?, ?, 1,
                        0.5, 'general',
                        ?, 'wrapper-nvidia-live')
            """, (
                model_id,
                "wrapper-nvidia",
                model_id,
                model_id,
                model_type,
                supports_tools,
                supports_vision,
                time.strftime("%Y-%m-%d %H:%M:%S"),
            ))
            synced += 1
        except sqlite3.IntegrityError:
            skipped += 1

    conn.commit()

    # Verify count
    cur.execute("SELECT COUNT(*) FROM model_ids WHERE provider = 'wrapper-nvidia'")
    total_wn = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM model_ids WHERE free_or_paid = 'FREE'")
    total_free = cur.fetchone()[0]

    conn.close()
    return {"synced": synced, "skipped": skipped, "total_wrapper_nvidia": total_wn, "total_free": total_free}


def verify() -> Dict:
    """Verify dashboard DB wrapper-nvidia models."""
    if not DASHBOARD_DB.exists():
        return {"error": "db_not_found", "wrapper_nvidia_count": 0, "free_count": 0}

    conn = sqlite3.connect(str(DASHBOARD_DB))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM model_ids WHERE provider = 'wrapper-nvidia'")
    wn_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM model_ids WHERE free_or_paid = 'FREE'")
    free_count = cur.fetchone()[0]
    cur.execute("SELECT provider_model_id FROM model_ids WHERE provider = 'wrapper-nvidia' LIMIT 5")
    sample = [r[0] for r in cur.fetchall()]
    conn.close()
    return {
        "wrapper_nvidia_count": wn_count,
        "free_count": free_count,
        "sample_models": sample,
    }


def main():
    parser = argparse.ArgumentParser(description="Sync wrapper-nvidia models to dashboard DB")
    parser.add_argument("--verify", action="store_true", help="Verify only, no sync")
    args = parser.parse_args()

    if args.verify:
        result = verify()
        print(f"Wrapper-nvidia models in DB: {result.get('wrapper_nvidia_count', 0)}")
        print(f"Total FREE models in DB: {result.get('free_count', 0)}")
        if result.get("sample_models"):
            print(f"Sample: {result['sample_models']}")
        return

    print("Fetching live models from wrapper-nvidia...")
    models = fetch_live_models()
    print(f"Live models fetched: {len(models)}")

    if not models:
        print("ERROR: No models fetched. Aborting.")
        sys.exit(1)

    print("Syncing to dashboard DB...")
    result = sync_to_dashboard_db(models)
    print(f"Synced: {result['synced']}, Skipped: {result['skipped']}")
    print(f"Wrapper-nvidia total in DB: {result['total_wrapper_nvidia']}")
    print(f"Total FREE models in DB: {result['total_free']}")


if __name__ == "__main__":
    main()
