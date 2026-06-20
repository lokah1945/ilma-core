#!/usr/bin/env python3
"""
ILMA Tracing v1.0 (Phase P / TASK 3.2)
=====================================
Lightweight distributed tracing for ILMA. Uses OpenTelemetry API + console exporter.
Production deployment can switch to Jaeger/Zipkin via OTLP.

Feature flag: config.yaml `distributed_tracing_enabled` (default: False)
"""
from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable, Optional

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor,
    )
    from opentelemetry.sdk.resources import Resource
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None
    TracerProvider = None

logger = logging.getLogger("ilma.tracing")

# Module-level state
_provider: Optional[Any] = None
_tracer: Optional[Any] = None
_in_memory_spans: list = []


def init_tracing(service_name: str = "ilma", exporter: str = "console"):
    """Initialize OpenTelemetry tracing."""
    global _provider, _tracer

    if not OTEL_AVAILABLE:
        logger.warning("[Tracing] opentelemetry not installed — using in-memory fallback")
        _tracer = InMemoryTracer()
        return _tracer

    if _provider is not None:
        return _tracer

    resource = Resource.create({"service.name": service_name, "service.version": "0.16.0"})
    _provider = TracerProvider(resource=resource)

    if exporter == "console":
        # Use SimpleSpanProcessor so spans flush immediately (useful for testing)
        _provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    elif exporter == "memory":
        _provider.add_span_processor(SimpleSpanProcessor(InMemoryExporter()))
    # Production: use OTLP exporter to Jaeger/Tempo

    trace.set_tracer_provider(_provider)
    _tracer = trace.get_tracer("ilma")
    logger.info(f"[Tracing] Initialized with {exporter} exporter")
    return _tracer


def get_tracer():
    if _tracer is None:
        return init_tracing()
    return _tracer


def trace_route_task(func: Callable) -> Callable:
    """Decorator to trace a route_task call."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        tracer = get_tracer()
        if hasattr(tracer, "start_as_current_span"):
            with tracer.start_as_current_span("route_task") as span:
                span.set_attribute("task_type", str(kwargs.get("task_type", "unknown")))
                span.set_attribute("allow_paid", kwargs.get("allow_paid", False))
                result = func(*args, **kwargs)
                if isinstance(result, dict):
                    span.set_attribute("model_id", str(result.get("model_id", "none")))
                    span.set_attribute("provider", str(result.get("provider", "none")))
                return result
        else:
            # In-memory fallback
            span = tracer.start_span("route_task")
            result = func(*args, **kwargs)
            tracer.end_span(span)
            return result
    return wrapper


# Fallback in-memory tracer (no OTEL)
class InMemoryTracer:
    def __init__(self):
        self.spans = []

    def start_as_current_span(self, name, **kwargs):
        return _InMemorySpanContext(self, name, **kwargs)

    def start_span(self, name, **kwargs):
        span = _InMemorySpan(name)
        self.spans.append(span)
        return span

    def end_span(self, span):
        span.end_time = time.time()


class _InMemorySpanContext:
    def __init__(self, tracer, name, **kwargs):
        self.span = _InMemorySpan(name)
        self.tracer = tracer

    def __enter__(self):
        return self.span

    def __exit__(self, *args):
        self.span.end_time = time.time()
        self.tracer.spans.append(self.span)


class _InMemorySpan:
    def __init__(self, name):
        self.name = name
        self.attributes = {}
        self.start_time = time.time()
        self.end_time = None

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def set_status(self, status):
        self.attributes["status"] = str(status)


class InMemoryExporter:
    def export(self, spans):
        for span in spans:
            _in_memory_spans.append({
                "name": span.name,
                "attributes": getattr(span, "attributes", {}),
                "start_time": getattr(span, "start_time", time.time()),
            })
        return True

    def shutdown(self):
        pass


# Auto-init with in-memory exporter (no Jaeger needed for dev)
_init_ok = init_tracing(exporter="memory")


if __name__ == "__main__":
    print("=== ILMA Tracing Demo ===")
    print(f"OTEL_AVAILABLE: {OTEL_AVAILABLE}")

    tracer = get_tracer()

    @trace_route_task
    def fake_route_task(task_type, allow_paid=False):
        return {"model_id": "test_model", "provider": "test_provider", "score": 0.9}

    result = fake_route_task(task_type="chat", allow_paid=False)
    print(f"Result: {result}")

    # Check in-memory spans
    if hasattr(tracer, "spans"):
        print(f"\nIn-memory spans captured: {len(tracer.spans)}")
        for span in tracer.spans:
            print(f"  Span: {span.name} (attrs: {span.attributes})")
    else:
        print(f"\nIn-memory exporter captured: {len(_in_memory_spans)} spans")
        for s in _in_memory_spans:
            print(f"  Span: {s['name']} (attrs: {s['attributes']})")
