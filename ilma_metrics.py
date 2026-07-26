#!/usr/bin/env python3
"""
ILMA Metrics v1.0 (Phase P / TASK 3.1)
======================================
Prometheus metrics for ILMA runtime.
Exposed at /metrics endpoint (when dashboard runs).

Feature flag: config.yaml `prometheus_metrics_enabled` (default: False)
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Optional

try:
    from prometheus_client import (
        Counter, Histogram, Gauge, Info, Summary, generate_latest,
        CONTENT_TYPE_LATEST, CollectorRegistry, REGISTRY,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Stubs so module imports cleanly
    Counter = Histogram = Gauge = Info = Summary = None
    def generate_latest(*args, **kwargs): return b""
    CONTENT_TYPE_LATEST = "text/plain"
    CollectorRegistry = type("R", (), {})
    REGISTRY = None

logger = logging.getLogger("ilma.metrics")

# ILMA Build info
BUILD_INFO = None
REQUEST_COUNT = None
REQUEST_DURATION = None
ERROR_COUNT = None
ACTIVE_MODELS = None
CACHE_HIT_RATIO = None
FREE_MODEL_RATIO = None
DAILY_COST = None
REQUEST_COST = None


def init_metrics():
    """Initialize all metrics. Idempotent."""
    global BUILD_INFO, REQUEST_COUNT, REQUEST_DURATION, ERROR_COUNT
    global ACTIVE_MODELS, CACHE_HIT_RATIO, FREE_MODEL_RATIO, DAILY_COST, REQUEST_COST

    if not PROMETHEUS_AVAILABLE:
        logger.warning("[Metrics] prometheus_client not installed — metrics disabled")
        return False

    if BUILD_INFO is not None:
        return True  # Already initialized

    try:
        BUILD_INFO = Info("ilma_build", "ILMA build information")
        BUILD_INFO.info({"version": "0.16.0", "phase": "P"})

        REQUEST_COUNT = Counter(
            "ilma_requests_total", "Total requests",
            ["model", "provider", "status"]
        )
        REQUEST_DURATION = Histogram(
            "ilma_request_duration_seconds", "Request duration",
            ["model", "provider"],
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
        )
        ERROR_COUNT = Counter(
            "ilma_errors_total", "Total errors",
            ["error_type", "provider"]
        )
        ACTIVE_MODELS = Gauge(
            "ilma_active_models", "Number of active models"
        )
        CACHE_HIT_RATIO = Gauge(
            "ilma_cache_hit_ratio", "Cache hit ratio (0-1)"
        )
        FREE_MODEL_RATIO = Gauge(
            "ilma_free_model_ratio", "Ratio of free models used (0-1)"
        )
        DAILY_COST = Gauge(
            "ilma_daily_cost_usd", "Daily cost in USD"
        )
        REQUEST_COST = Counter(
            "ilma_request_cost_usd", "Cost per request (USD)",
            ["model"]
        )
        logger.info("[Metrics] Initialized successfully")
        return True
    except Exception as e:
        logger.error(f"[Metrics] Init failed: {e}")
        return False


def record_request(model: str, provider: str, status: str = "success"):
    """Record a request outcome."""
    if REQUEST_COUNT:
        REQUEST_COUNT.labels(model=model, provider=provider, status=status).inc()


@contextmanager
def time_request(model: str, provider: str):
    """Context manager to time a request."""
    start = time.time()
    try:
        yield
    finally:
        if REQUEST_DURATION:
            duration = time.time() - start
            REQUEST_DURATION.labels(model=model, provider=provider).observe(duration)


def record_error(error_type: str, provider: str = "unknown"):
    if ERROR_COUNT:
        ERROR_COUNT.labels(error_type=error_type, provider=provider).inc()


def set_active_models(count: int):
    if ACTIVE_MODELS:
        ACTIVE_MODELS.set(count)


def set_cache_hit_ratio(ratio: float):
    if CACHE_HIT_RATIO:
        CACHE_HIT_RATIO.set(min(1.0, max(0.0, ratio)))


def set_free_model_ratio(ratio: float):
    if FREE_MODEL_RATIO:
        FREE_MODEL_RATIO.set(min(1.0, max(0.0, ratio)))


def set_daily_cost(cost_usd: float):
    if DAILY_COST:
        DAILY_COST.set(cost_usd)


def record_cost(model: str, cost_usd: float):
    if REQUEST_COST:
        REQUEST_COST.labels(model=model).inc(cost_usd)


def get_metrics_text() -> bytes:
    """Generate Prometheus exposition format."""
    if not PROMETHEUS_AVAILABLE:
        return b"# prometheus_client not installed\n"
    return generate_latest(REGISTRY)


# Auto-init on import
_init_ok = init_metrics()


if __name__ == "__main__":
    print("=== ILMA Metrics Demo ===")
    init_metrics()
    record_request("test_model", "test_provider", "success")
    record_request("test_model", "test_provider", "error")
    record_error("timeout", "test_provider")
    set_active_models(2178)
    set_cache_hit_ratio(0.85)
    set_free_model_ratio(1.0)  # all free
    set_daily_cost(0.05)
    record_cost("test_model", 0.001)

    with time_request("m1", "nvidia"):
        time.sleep(0.05)

    print("Metrics initialized:", _init_ok)
    print("PROMETHEUS_AVAILABLE:", PROMETHEUS_AVAILABLE)
    output = get_metrics_text().decode()
    # Print first 30 lines
    for line in output.split("\n")[:30]:
        if line and not line.startswith("# HELP") and not line.startswith("# TYPE"):
            print(line)
