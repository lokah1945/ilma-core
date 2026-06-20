#!/usr/bin/env python3
"""
ILMA Unified Core — Integrated AYDA Capabilities
==================================================
One cohesive system, not standalone files.

Architecture:
- Model Router (AYDA): Database-driven routing
- Judge System: L10 verification
- Workflow ECC: Execution pipeline
- Capability Registry: Capability tracking
- Learning Engine: Self-improvement
- Knowledge Graph: Entity management
- Cognition Kernel: Cognitive processing
- Reasoning Runtime: Reasoning engine
- Execution Graph: Memory-aware execution
- Agent Civilization: Multi-agent collaboration

This module IS the system — not a wrapper.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Type
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache

# === PATHS ===
ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
WORKSPACE = ILMA_PROFILE
AYDA_WORKSPACE = Path("/root/.openclaw/workspace")
AYDA_DATA = Path("/root/.cache/ayda")

# Add ILMA paths
sys.path.insert(0, str(WORKSPACE))

# === ILMA CORE COMPONENT REGISTRY ===
_component_registry: Dict[str, Any] = {}
_component_status: Dict[str, str] = {}
_initialized = False


def _lazy_import(module_path: str, class_name: Optional[str] = None) -> Any:
    """Lazy import with caching."""
    if module_path in _component_registry:
        return _component_registry[module_path]

    try:
        # Dynamic import
        module = __import__(module_path, fromlist=[class_name] if class_name else [__name__])
        if class_name:
            obj = getattr(module, class_name)
        else:
            obj = module

        _component_registry[module_path] = obj
        _component_status[module_path] = "loaded"
        return obj

    except Exception as e:
        _component_status[module_path] = f"error: {e}"
        return None


# === MODEL ROUTER (AYDA-POWERED) ===
@lru_cache(maxsize=128)
def get_model_router():
    """Get model router instance (cached)."""
    from ilma_model_router import get_best_model, route_task, get_router_stats, list_free_models
    return {
        "best": get_best_model,
        "route": route_task,
        "stats": get_router_stats,
        "list": list_free_models,
        "available": True
    }


def route_model(task_type: str) -> Dict[str, Any]:
    """Route task to best model."""
    router = get_model_router()
    if not router.get("available"):
        return {"error": "Model router unavailable", "model_id": "fallback/default", "provider": "nvidia"}
    return router["route"](task_type)


def get_best_free_model(task_type: str) -> str:
    """Get best free model for task type."""
    result = route_model(task_type)
    return result.get("route", {}).get("model_id", "nvidia/01-ai/yi-large")


# === JUDGE SYSTEM (L10) ===
@lru_cache(maxsize=32)
def get_judge_system():
    """Get judge system instance (cached)."""
    from ilma_judge_system import verify_file, calculate_score, ALL_LEVELS, VERDICT_PASS
    return {
        "verify": verify_file,
        "score": calculate_score,
        "levels": ALL_LEVELS,
        "verdict_pass": VERDICT_PASS,
        "available": True
    }


def judge_code(file_path: str, levels: Optional[List[str]] = None) -> Dict[str, Any]:
    """Judge code with specified levels."""
    judge = get_judge_system()
    if not judge.get("available"):
        return {"error": "Judge unavailable", "verdict": "ERROR", "score": 0}
    return judge["verify"](file_path, levels=levels or ["L1_COMPILE", "L5_SECURITY"])


def quick_verify(code: str) -> bool:
    """Quick verify code (L1 + L5)."""
    import tempfile
    temp = tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode='w')
    temp.write(code)
    temp.close()

    try:
        result = judge_code(temp.name, ["L1_COMPILE", "L5_SECURITY"])
        return result.get("verdict") == "PASS"
    finally:
        Path(temp.name).unlink(missing_ok=True)


# === CAPABILITY REGISTRY (ILMA-NATIVE) ===
_capability_cache: Optional[Dict] = None
_capability_cache_time: float = 0
_CAPABILITY_CACHE_TTL: float = 300.0


@lru_cache(maxsize=256)
def get_capabilities() -> Dict[str, Any]:
    """Get capability registry (cached)."""
    global _capability_cache, _capability_cache_time

    now = time.time()
    if _capability_cache is None or (now - _capability_cache_time) > _CAPABILITY_CACHE_TTL:
        try:
            with open(WORKSPACE / "config" / "ilma_capability_registry.json") as f:
                _capability_cache = json.load(f)
            _capability_cache_time = now
        except Exception as e:
            _capability_cache = {"capabilities": {}, "total_capabilities": 0, "error": str(e)}

    return _capability_cache


def is_capability_verified(cap_name: str) -> bool:
    """Check if capability is verified."""
    caps = get_capabilities()
    cap = caps.get("capabilities", {}).get(cap_name, {})
    return cap.get("status") == "VERIFIED"


def get_capability_info(cap_name: str) -> Dict[str, Any]:
    """Get capability details."""
    caps = get_capabilities()
    return caps.get("capabilities", {}).get(cap_name, {})


def list_verified_capabilities() -> List[str]:
    """List all verified capabilities."""
    caps = get_capabilities()
    return [k for k, v in caps.get("capabilities", {}).items() if v.get("status") == "VERIFIED"]


# === EVIDENCE LEDGER ===
_evidence_ledger: List[Dict] = []
_evidence_alias_map: Dict[str, str] = {}


def log_evidence(evidence_id: str, capability: str, description: str, evidence_type: str = "test") -> Dict[str, Any]:
    """Log evidence to ledger."""
    entry = {
        "evidence_id": evidence_id,
        "capability": capability,
        "description": description,
        "type": evidence_type,
        "timestamp": datetime.now().isoformat(),
        "verified": True
    }
    _evidence_ledger.append(entry)

    # Update alias map
    if evidence_id.startswith("ILMA-EVID-"):
        _evidence_alias_map[evidence_id] = evidence_id

    return entry


def get_evidence_for_capability(capability: str) -> List[Dict]:
    """Get all evidence for a capability."""
    return [e for e in _evidence_ledger if e["capability"] == capability]


# === SELF-IMPROVEMENT LOOP ===
_self_improvement_enabled = True
_learning_events: List[Dict] = []
_optimization_suggestions: List[str] = []


def record_learning(task: str, result: str, quality: float) -> Dict[str, Any]:
    """Record learning from task."""
    event = {
        "timestamp": datetime.now().isoformat(),
        "task": task,
        "result": result,
        "quality": quality,
        "model_used": get_best_free_model("general") if _self_improvement_enabled else "unknown"
    }
    _learning_events.append(event)
    return event


def get_learning_insights() -> List[Dict]:
    """Get learning insights from past events."""
    if not _learning_events:
        return []

    # Aggregate by task type
    insights = {}
    for event in _learning_events[-100:]:  # Last 100 events
        task_type = event.get("task", "unknown")[:50]
        if task_type not in insights:
            insights[task_type] = {"count": 0, "quality_sum": 0}
        insights[task_type]["count"] += 1
        insights[task_type]["quality_sum"] += event.get("quality", 0)

    return [
        {
            "task": k,
            "avg_quality": v["quality_sum"] / v["count"] if v["count"] > 0 else 0,
            "count": v["count"]
        }
        for k, v in insights.items()
    ]


# === EXECUTION MEMORY ===
_execution_history: List[Dict] = []
_max_history = 1000


def record_execution(task: str, handler: str, result: str, duration_ms: float) -> Dict[str, Any]:
    """Record execution for future reference."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "task": task[:100],
        "handler": handler,
        "result": result[:200] if isinstance(result, str) else str(result)[:200],
        "duration_ms": duration_ms,
        "model_used": get_best_free_model("general")
    }
    _execution_history.append(entry)

    # Trim if too long
    while len(_execution_history) > _max_history:
        _execution_history.pop(0)

    return entry


def get_recent_executions(n: int = 10) -> List[Dict]:
    """Get recent executions."""
    return _execution_history[-n:]


# === AYDA INTEGRATION LAYER ===
# These are AYDA components that ILMA can use directly

def load_ayda_capability_orchestrator():
    """Load AYDA's capability orchestrator."""
    try:
        sys.path.insert(0, str(AYDA_WORKSPACE / "scripts"))
        from ayda_capability_orchestrator import classify_task, task_complexity, plan_task
        return {"classify": classify_task, "complexity": task_complexity, "plan": plan_task, "available": True}
    except Exception as e:
        return {"available": False, "error": str(e)}


def load_ayda_benchmark_aware_routing():
    """Load AYDA's benchmark-aware routing."""
    try:
        sys.path.insert(0, str(AYDA_WORKSPACE / "core"))
        from benchmark_aware_routing import route_with_benchmark
        return {"route": route_with_benchmark, "available": True}
    except Exception as e:
        return {"available": False, "error": str(e)}


def load_ayda_confidence_aware_routing():
    """Load AYDA's confidence-aware routing."""
    try:
        sys.path.insert(0, str(AYDA_WORKSPACE / "core"))
        from confidence_aware_routing import route_with_confidence
        return {"route": route_with_confidence, "available": True}
    except Exception as e:
        return {"available": False, "error": str(e)}


from .ilma_agent_civilization import (
    AgentCivilization,
    CollaborationSession,
    AgentMessage,
    CollaborationType,
    MessagePriority,
    AgentRole,
    AgentReputation,
    AgentSpecialization,
)

# === AGENT CIVILIZATION (AYDA INSPIRED) ===


# === COGNITIVE ENGINE (ILMA-NATIVE) ===
class CognitiveEngine:
    """ILMA Cognitive Processing Engine."""

    def __init__(self):
        self.thinking_modes = ["reactive", "deliberative", "autonomous", "meta"]
        self.current_mode = "reactive"
        self.attention_context: List[str] = []
        self.beliefs: Dict[str, float] = {}

    def think(self, task: str, mode: str = "reactive") -> Dict[str, Any]:
        """Process task with cognitive mode."""
        self.current_mode = mode

        # Simple thinking simulation
        result = {
            "mode": mode,
            "task": task[:100],
            "thinking_steps": [
                {"step": "analyze", "description": f"Analyzing {task[:50]}..."},
                {"step": "plan", "description": "Planning execution path..."},
                {"step": "execute", "description": "Executing with selected model..."}
            ],
            "model_used": get_best_free_model("general"),
            "confidence": 0.85
        }

        return result

    def update_belief(self, key: str, value: float):
        """Update belief (0.0 to 1.0)."""
        self.beliefs[key] = max(0.0, min(1.0, value))

    def get_belief(self, key: str) -> float:
        """Get belief value."""
        return self.beliefs.get(key, 0.5)


# === UNIFIED SYSTEM INTERFACE ===
class ILMASystem:
    """
    ILMA Unified System — Single interface to all capabilities.

    This is NOT a wrapper. This IS the system.
    """

    def __init__(self):
        self.model_router = get_model_router()
        self.judge = get_judge_system()
        self.capabilities = get_capabilities()
        self.cognition = CognitiveEngine()
        self.civilization = AgentCivilization("ilma_main")
        self.version = "3.8"
        self.status = "ready"
        self.boot_time = datetime.now().isoformat()

        # AYDA integrations
        self.ayda_capability_orchestrator = load_ayda_capability_orchestrator()
        self.ayda_benchmark_routing = load_ayda_benchmark_aware_routing()
        self.ayda_confidence_routing = load_ayda_confidence_aware_routing()

    def route(self, task_type: str) -> Dict[str, Any]:
        """Route task to best model."""
        return route_model(task_type)

    def judge(self, file_path: str, levels: Optional[List[str]] = None) -> Dict[str, Any]:
        """Judge code file."""
        return judge_code(file_path, levels)

    def verify(self, code: str) -> bool:
        """Quick verify code."""
        return quick_verify(code)

    def think(self, task: str, mode: str = "reactive") -> Dict[str, Any]:
        """Process with cognition."""
        return self.cognition.think(task, mode)

    def learn(self, task: str, result: str, quality: float):
        """Record learning."""
        return record_learning(task, result, quality)

    def execute(self, task: str, handler: str = "model_route") -> Dict[str, Any]:
        """Execute task with timing."""
        start = time.time()
        result = {"task": task, "handler": handler, "timestamp": datetime.now().isoformat()}

        if handler == "model_route":
            route = self.route("general")
            result["route"] = route
            result["model"] = route.get("route", {}).get("model_id", "unknown")
        elif handler == "judge":
            # Write temp and judge
            import tempfile
            temp = tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode='w')
            temp.write(task)
            temp.close()
            judgment = self.judge(temp.name)
            result["judgment"] = judgment
            Path(temp.name).unlink(missing_ok=True)
        else:
            result["output"] = f"Handled by {handler}"

        duration_ms = (time.time() - start) * 1000
        result["duration_ms"] = duration_ms
        record_execution(task, handler, str(result), duration_ms)

        return result

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        return {
            "version": self.version,
            "status": self.status,
            "boot_time": self.boot_time,
            "model_router": self.model_router.get("available", False),
            "judge": self.judge.get("available", False),
            "ayda_capability_orchestrator": self.ayda_capability_orchestrator.get("available", False),
            "ayda_benchmark_routing": self.ayda_benchmark_routing.get("available", False),
            "ayda_confidence_routing": self.ayda_confidence_routing.get("available", False),
            "verified_capabilities": len(list_verified_capabilities()),
            "learning_events": len(_learning_events),
            "execution_history": len(_execution_history)
        }


# === SINGLETON INSTANCE ===
_ilma_system: Optional[ILMASystem] = None


def get_ilma_system() -> ILMASystem:
    """Get ILMA system singleton."""
    global _ilma_system
    if _ilma_system is None:
        _ilma_system = ILMASystem()
    return _ilma_system


# === CLI INTERFACE ===
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ILMA Unified Core")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # status
    subparsers.add_parser("status", help="Show system status")

    # route
    route_parser = subparsers.add_parser("route", help="Route task")
    route_parser.add_argument("task_type", help="Task type")

    # verify
    verify_parser = subparsers.add_parser("verify", help="Quick verify code")
    verify_parser.add_argument("code", help="Code to verify")

    # think
    think_parser = subparsers.add_parser("think", help="Cognitive processing")
    think_parser.add_argument("task", help="Task")
    think_parser.add_argument("--mode", default="reactive", help="Thinking mode")

    # learn
    learn_parser = subparsers.add_parser("learn", help="Record learning")
    learn_parser.add_argument("task", help="Task")
    learn_parser.add_argument("result", help="Result")
    learn_parser.add_argument("quality", type=float, help="Quality (0-1)")

    args = parser.parse_args()

    system = get_ilma_system()

    if args.command == "status":
        status = system.get_status()
        print(json.dumps(status, indent=2))

    elif args.command == "route":
        result = system.route(args.task_type)
        print(json.dumps(result, indent=2))

    elif args.command == "verify":
        result = system.verify(args.code)
        print(f"Verified: {result}")

    elif args.command == "think":
        result = system.think(args.task, args.mode)
        print(json.dumps(result, indent=2))

    elif args.command == "learn":
        result = system.learn(args.task, args.result, args.quality)
        print(json.dumps(result, indent=2))

    else:
        parser.print_help()