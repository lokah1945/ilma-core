#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          ILMA SYSTEM — SINGLE ENTRY POINT v1.0                              ║
║          Autonomous Production Mode: INTEGRATED                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Integrates: Router + Client + Scheduler + Auto-healing                     ║
║  SOT: PROVIDER_INTELLIGENCE_MASTER.json                                     ║
║  Non-negotiable: is_active gate, free-only policy                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

PHASE 3: End-to-End System Integration

Single entry point that wires all ILMA components into one coherent system:
  1. ILMAUnifiedRouter     — model selection (is_active + free filter enforced)
  2. ILMAClient            — HTTP inference, NVIDIA key rotation, model fallback
  3. Background Scheduler  — DB sync + benchmark autoloop (thread-based)
  4. Auto-healing          — circuit breaker, 429 key rotation, model fallback

Workflow: generate(prompt) → route → execute → respond
No admin intervention required after init.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Core ILMA components ────────────────────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).parent))

from ilma_model_router import ILMAUnifiedRouter
from ilma_client import _FallbackHTTPClient, generate as _ilma_generate, generate_batch
HTTPClient = _FallbackHTTPClient  # alias for readability

logger = logging.getLogger("ILMA.System")


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

DATA_DIR = Path(__file__).parent / "ilma_model_router_data"
SCRIPTS_DIR = Path(__file__).parent / "scripts"

# Scheduler intervals (seconds)
DB_SYNC_INTERVAL = 5 * 60     # 5 minutes — sync is_active from SOT
BENCHMARK_INTERVAL = 15 * 60   # 15 minutes
HEALTH_CHECK_INTERVAL = 60    # 1 minute

# System state
class SystemState:
    STARTED_AT: Optional[datetime] = None
    ROUTER: Optional[ILMAUnifiedRouter] = None
    CLIENT: Optional[HTTPClient] = None   # _FallbackHTTPClient instance
    SCHEDULERS: List[threading.Thread] = []
    _running: bool = False

    # Per-key usage counters (for monitoring balance)
    NVIDIA_KEY_USAGE: Dict[int, int] = {}  # key_idx → request_count

    @classmethod
    def reset(cls):
        cls.STARTED_AT = None
        cls.ROUTER = None
        cls.CLIENT = None
        cls.SCHEDULERS = []
        cls._running = False
        cls.NVIDIA_KEY_USAGE = {}

SYSTEM = SystemState()


# ══════════════════════════════════════════════════════════════════════════════
# BACKGROUND SCHEDULERS
# ══════════════════════════════════════════════════════════════════════════════

def _run_db_sync():
    """
    DB sync scheduler: runs ilma_db_pipeline.py --cron every DB_SYNC_INTERVAL.
    This syncs is_active changes from MASTER to runtime state.
    Any manual admin edit to MASTER is picked up within 5 minutes automatically.
    """
    logger.info("[Scheduler] DB Sync: starting")
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "ilma_db_pipeline.py"), "--cron"],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(Path(__file__).parent),
        )
        if result.returncode == 0:
            logger.info("[Scheduler] DB Sync: completed successfully")
        else:
            logger.warning(f"[Scheduler] DB Sync: exit {result.returncode}\n{result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        logger.warning("[Scheduler] DB Sync: timed out after 300s")
    except Exception as e:
        logger.error(f"[Scheduler] DB Sync: {e}")


def _run_benchmark_autoloop():
    """
    Benchmark autoloop scheduler: runs benchmark pipeline every BENCHMARK_INTERVAL.
    Accumulates real performance data to replace synthetic benchmark scores.
    """
    logger.info("[Scheduler] Benchmark Autoloop: starting")
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "ilma_benchmark_autoloop.py")],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(Path(__file__).parent),
        )
        if result.returncode == 0:
            logger.info("[Scheduler] Benchmark Autoloop: completed")
        else:
            logger.warning(f"[Scheduler] Benchmark: exit {result.returncode}\n{result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        logger.warning("[Scheduler] Benchmark: timed out after 600s")
    except Exception as e:
        logger.error(f"[Scheduler] Benchmark: {e}")


def _run_health_check():
    """
    Health check scheduler: probes active cloud providers and updates health state.
    Phase 1 ensures unhealthy providers are skipped at candidate pool level.
    """
    logger.info("[Scheduler] Health check: starting")
    try:
        sys.path.insert(0, str(Path(__file__).parent / "scripts"))
        from ilma_health_check import ILMAHealthChecker
        checker = ILMAHealthChecker()
        # Probe all active providers
        providers = ["nvidia", "openrouter", "minimax", "xai", "cohere", "ollama"]
        for prov in providers:
            try:
                status = checker.check_provider_health(prov)
                logger.debug(f"[Scheduler] Health check {prov}: {status}")
            except Exception as e:
                logger.debug(f"[Scheduler] Health check {prov}: error — {e}")
    except Exception as e:
        logger.warning(f"[Scheduler] Health check: {e}")


def _start_background_threads():
    """
    Start all background schedulers as daemon threads.
    Each thread runs its target function in a loop with the configured interval.
    """
    schedulers = [
        ("DB-Sync", _run_db_sync, DB_SYNC_INTERVAL),
        ("Benchmark", _run_benchmark_autoloop, BENCHMARK_INTERVAL),
        ("HealthCheck", _run_health_check, HEALTH_CHECK_INTERVAL),
    ]

    for name, target, interval in schedulers:
        def make_loop(target_fn, interval_secs, sched_name):
            def loop():
                logger.info(f"[Scheduler:{sched_name}] Starting (interval={interval_secs}s)")
                while SYSTEM._running:
                    try:
                        target_fn()
                    except Exception as e:
                        logger.error(f"[Scheduler:{sched_name}] Error: {e}")
                    time.sleep(interval_secs)
                logger.info(f"[Scheduler:{sched_name}] Stopped")
            return loop

        t = threading.Thread(
            target=make_loop(target, interval, name),
            name=f"ILMA-Scheduler-{name}",
            daemon=True,
        )
        SYSTEM.SCHEDULERS.append(t)
        t.start()
        logger.info(f"[Scheduler] {name} thread started (daemon)")


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API: generate()
# ══════════════════════════════════════════════════════════════════════════════

async def generate(
    prompt: str,
    task_type: str = "general",
    allow_paid: bool = False,
    model_id: Optional[str] = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Main public API: interpret prompt → route → execute → respond.

    PHASE 4: Full autonomous pipeline from simple prompt to response.

    Non-negotiable enforcement:
    - is_active=False → NEVER selected (router enforces at candidate pool level)
    - allow_paid=False + pricing_tier!=free → NEVER selected (router enforces)
    - Provider health check → unhealthy providers excluded from pool
    """
    if not SYSTEM._running:
        raise RuntimeError("ILMA System not started. Call ilma_system.start() first.")

    # Delegate to module-level generate() which handles routing + execution
    # + key rotation + fallback internally. The module-level function uses
    # the ILMAUnifiedRouter (cached singleton) and _FallbackHTTPClient.
    result = await _ilma_generate(
        prompt=prompt,
        max_tokens=2048,
        task_type=task_type,
        model_override=model_id,
        timeout=timeout,
    )

    return {
        "provider": result.provider,
        "model_id": result.model_id,
        "response": result.content,
        "routing": {"routing_method": "ILMAUnifiedRouter_v1.0"},
        "success": result.success,
        "latency_ms": result.latency_ms,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PROVIDER-SPECIFIC REQUEST BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def _build_request_body(provider: str, model_id: str, prompt: str) -> dict:
    """Build provider-specific JSON body. Mirrors ilma_client body builders."""
    messages = [{"role": "user", "content": prompt}]

    if provider == "nvidia":
        return {
            "model": model_id,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048,
        }
    elif provider == "minimax":
        return {
            "model": model_id,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048,
            "stream": False,
        }
    elif provider == "openrouter":
        return {
            "model": model_id,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048,
        }
    elif provider == "xai":
        return {
            "model": model_id,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048,
        }
    else:
        return {
            "model": model_id,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2048,
        }


def _is_success_response(response: dict) -> bool:
    """Check if HTTP response indicates success."""
    status = response.get("status", 0)
    return 200 <= status < 300


def _extract_text(response: dict) -> str:
    """Extract text content from provider response. Handles common formats."""
    # OpenAI-compatible: response.choices[0].message.content
    choices = response.get("choices", [])
    if choices:
        msg = choices[0].get("message", {})
        return msg.get("content", "").strip()

    # NVIDIA NIM format
    if "choices" in response:
        for choice in response["choices"]:
            msg = choice.get("message", {})
            if msg.get("content"):
                return msg["content"].strip()

    # Error response
    if response.get("error"):
        err = response["error"]
        if isinstance(err, dict):
            return f"Error: {err.get('message', str(err))}"
        return f"Error: {err}"

    # Empty
    return ""


# ══════════════════════════════════════════════════════════════════════════════
# SYNC WRAPPER FOR SYNCHRONOUS CODE
# ══════════════════════════════════════════════════════════════════════════════

def generate_sync(
    prompt: str,
    task_type: str = "general",
    allow_paid: bool = False,
    model_id: Optional[str] = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Synchronous wrapper around generate(). For use in non-async contexts.
    Creates a new event loop, runs generate(), returns result.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(
            generate(prompt, task_type, allow_paid, model_id, timeout)
        )
    finally:
        loop.close()


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM START / STOP
# ══════════════════════════════════════════════════════════════════════════════

def start(
    init_schedulers: bool = True,
    init_health_check: bool = False,
) -> None:
    """
    Initialize and start the ILMA system.

    Args:
        init_schedulers: Start background DB sync + benchmark threads.
                        Set False for one-shot usage (CLI tool).
        init_health_check: Start health monitoring thread.
    """
    if SYSTEM._running:
        logger.warning("[ILMA System] Already running")
        return

    logger.info("=" * 70)
    logger.info("ILMA SYSTEM STARTING")
    logger.info("=" * 70)

    # ── Init Router ───────────────────────────────────────────────────────
    SYSTEM.ROUTER = ILMAUnifiedRouter()

    # Pre-load MASTER so first query is fast
    master = SYSTEM.ROUTER._load_master()
    active_count = sum(
        1 for pdata in master.get("providers", {}).values()
        for mdata in pdata.get("models", {}).values()
        if mdata.get("is_active", False)
    )
    logger.info(f"[Router] Loaded MASTER: {active_count} active models")

    # ── Init Client (_FallbackHTTPClient wraps async HTTP) ──────────────
    from ilma_client import _AsyncHTTPClient
    http_client = _AsyncHTTPClient()
    SYSTEM.CLIENT = HTTPClient(http_client)   # _FallbackHTTPClient instance
    logger.info("[Client] HTTP client initialized")

    # Initialize NVIDIA keys (load from credentials)
    SYSTEM.CLIENT._init_nvidia_keys()
    if SYSTEM.CLIENT.NVIDIA_KEYS:
        logger.info(f"[Client] {len(SYSTEM.CLIENT.NVIDIA_KEYS)} NVIDIA API keys loaded for round-robin")

    # ── Init Schedulers ───────────────────────────────────────────────────
    if init_schedulers:
        _start_background_threads()
        logger.info("[Scheduler] All background threads started")

    SYSTEM._running = True
    SYSTEM.STARTED_AT = datetime.now()

    logger.info("=" * 70)
    logger.info("ILMA SYSTEM READY — Autonomous Production Mode: Active")
    logger.info(f"Active models: {active_count}")
    logger.info(f"Schedulers: {'running' if init_schedulers else 'disabled'}")
    logger.info("=" * 70)


def stop(graceful: bool = True) -> None:
    """
    Gracefully stop the ILMA system and all background threads.
    """
    if not SYSTEM._running:
        return

    logger.info("[ILMA System] Shutting down...")
    SYSTEM._running = False

    # Wait for scheduler threads to finish
    for t in SYSTEM.SCHEDULERS:
        t.join(timeout=5.0)

    logger.info("[ILMA System] Stopped")


def get_status() -> Dict[str, Any]:
    """Return current system status for monitoring."""
    if not SYSTEM._running:
        return {"status": "stopped"}

    master = SYSTEM.ROUTER._load_master() if SYSTEM.ROUTER else {}
    active = sum(
        1 for pdata in master.get("providers", {}).values()
        for m in pdata.get("models", {}).values()
        if m.get("is_active", False)
    )
    working = sum(
        1 for pdata in master.get("providers", {}).values()
        for m in pdata.get("models", {}).values()
        if m.get("is_active", False) and m.get("working", False)
    )

    return {
        "status": "running",
        "uptime_seconds": (datetime.now() - SYSTEM.STARTED_AT).total_seconds() if SYSTEM.STARTED_AT else 0,
        "active_models": active,
        "working_models": working,
        "nvidia_keys": len(SYSTEM.CLIENT.NVIDIA_KEYS) if SYSTEM.CLIENT else 0,
        "schedulers": len(SYSTEM.SCHEDULERS),
        "schedulers_running": SYSTEM._running,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="ILMA System — Single Entry Point")
    sub = parser.add_subparsers(dest="cmd", help="Commands")

    # start command
    start_p = sub.add_parser("start", help="Start ILMA system")
    start_p.add_argument("--no-scheduler", action="store_true", help="Disable background schedulers")

    # status command
    sub.add_parser("status", help="Show system status")

    # generate command
    gen_p = sub.add_parser("generate", help="Generate response")
    gen_p.add_argument("prompt", help="Prompt text")
    gen_p.add_argument("--task", default="general", help="Task type")
    gen_p.add_argument("--paid", action="store_true", help="Allow paid models")
    gen_p.add_argument("--model", help="Explicit model override")
    gen_p.add_argument("--timeout", type=int, default=60)

    args = parser.parse_args()

    if args.cmd == "start":
        start(init_schedulers=not args.no_scheduler)
        print("ILMA System started. Press Ctrl+C to stop.")
        try:
            while SYSTEM._running:
                time.sleep(1)
        except KeyboardInterrupt:
            stop()
    elif args.cmd == "status":
        start(init_schedulers=False)
        import json
        print(json.dumps(get_status(), indent=2, default=str))
    elif args.cmd == "generate":
        start(init_schedulers=False)
        result = generate_sync(args.prompt, args.task, args.paid, args.model, args.timeout)
        print(f"\nProvider: {result['provider']}")
        print(f"Model: {result['model_id']}")
        print(f"Success: {result['success']}")
        print(f"\nResponse:\n{result['response']}")
    else:
        parser.print_help()