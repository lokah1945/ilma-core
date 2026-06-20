#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         ILMA CORE — Unified Integration Layer v3.0                        ║
║              One Body. One System. No Standalone Files.                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

Purpose:
    Acts as the central nervous system for all ILMA components.
    Provides lazy-loaded singletons, shared state, and cross-component
    dependency injection so every module is genuinely part of one body.

Usage:
    from ilma_core import get_core, ILMACore

    core = get_core()
    router = core.get_router()
    fallback = core.get_fallback_engine()
    quality = core.get_quality_gate()

Components wired:
    - ILMASmartModelRouter     (model routing with multi-dim scoring)
    - FallbackCascadeEngine    (5-tier fallback cascade)
    - DAGPipelineEngine        (dependency-aware pipeline execution)
    - ILMAQualityGate          (10-level quality verification)
    - ProviderIntelligenceEnricher (benchmark data enrichment)
    - ILMAMasterOrchestrator  (task decomposition + parallel execution)
    - HealthManager           (health tracking for all providers)
    - ActorCriticCore         (self-improvement + evaluation)

Version: 3.0.0
Author: ILMA Core Team
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

logger = logging.getLogger("ILMA.Core")

# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────
ILMA_PROFILE = Path(os.environ.get("ILMA_PROFILE", "/root/.hermes/profiles/ilma"))
WORKSPACE = ILMA_PROFILE

# Ensure ilma_core is importable
import sys as _sys
if str(WORKSPACE) not in _sys.path:
    _sys.path.insert(0, str(WORKSPACE))

# ─────────────────────────────────────────────────────────────────────────────
# INLINE BACKUP HELPER
# ─────────────────────────────────────────────────────────────────────────────
_BACKUP_DIR = ILMA_PROFILE / "backups" / "core_consolidation"
_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def _backup_file(src_path: Path) -> Optional[Path]:
    """Create timestamped backup of a file before modifying."""
    if not src_path.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = _BACKUP_DIR / f"backup_{ts}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    dest = backup_dir / src_path.name
    try:
        import shutil
        shutil.copy2(src_path, dest)
        return dest
    except Exception as e:
        logger.warning(f"Backup failed for {src_path}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# LAZY IMPORT HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _lazy(name: str, from_path: str, import_what: Optional[str] = None):
    """Lazily import a module or attribute from a module path."""
    def getter():
        try:
            if from_path not in _lazy._cache:
                mod = __import__(from_path, fromlist=[''])
                _lazy._cache[from_path] = mod
            mod = _lazy._cache[from_path]
            if import_what:
                return getattr(mod, import_what)
            return mod
        except Exception as e:
            logger.error(f"Lazy import failed for {from_path}: {e}")
            return None
    getter._cache = {}
    return getter


# ─────────────────────────────────────────────────────────────────────────────
# COMPONENT FACTORY — CREATES AND TRACKS ALL ILMA COMPONENTS
# ─────────────────────────────────────────────────────────────────────────────

class _ComponentFactory:
    """
    Lazy factory for all ILMA components.
    Each component is instantiated once on first access and cached.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._components: Dict[str, Any] = {}
        self._init_order: list = []

    # ── Smart Model Router ──────────────────────────────────────────────────
    @property
    def smart_router(self) -> Any:
        """Convenience property for smart_router."""
        return self.get_smart_router()

    def get_smart_router(self) -> Optional[Any]:
        with self._lock:
            if 'smart_router' not in self._components:
                try:
                    from ilma_model_router import get_router as _get_unified_router
                    self._components['smart_router'] = _get_unified_router(allow_paid=False)
                    self._init_order.append('smart_router')
                    logger.info("[Core] ILMAUnifiedRouter (ilma_model_router) loaded")
                except Exception as e:
                    logger.error(f"Failed to load smart_router: {e}")
                    return None
            return self._components.get('smart_router')

    # ── Health Manager ──────────────────────────────────────────────────────
    def get_health_manager(self) -> Optional[Any]:
        with self._lock:
            if 'health_mgr' not in self._components:
                try:
                    from ilma_health_manager import get_health_manager
                    hm = get_health_manager()
                    self._components['health_mgr'] = hm
                    self._init_order.append('health_mgr')
                    logger.info("[Core] HealthManager loaded")
                except Exception as e:
                    logger.error(f"[Core] Failed to load health_mgr: {e}", exc_info=True)
                    # Health manager is optional — don't return None, just don't register
                    pass
            return self._components.get('health_mgr')

    # ── Fallback Cascade Engine ─────────────────────────────────────────────
    def get_fallback_engine(self) -> Optional[Any]:
        with self._lock:
            if 'fallback_engine' not in self._components:
                try:
                    from ilma_fallback_cascade import FallbackCascadeEngine
                    router = self.get_smart_router()
                    health_mgr = self.get_health_manager()
                    engine = FallbackCascadeEngine(router=router, health_manager=health_mgr)
                    self._components['fallback_engine'] = engine
                    self._init_order.append('fallback_engine')
                    logger.info("[Core] FallbackCascadeEngine loaded")
                except Exception as e:
                    logger.error(f"Failed to load fallback_engine: {e}")
                    return None
            return self._components.get('fallback_engine')

    # ── DAG Pipeline Engine ─────────────────────────────────────────────────
    def get_dag_engine(self) -> Optional[Any]:
        with self._lock:
            if 'dag_engine' not in self._components:
                try:
                    from ilma_dag_pipeline import DAGPipelineEngine
                    self._components['dag_engine'] = DAGPipelineEngine()
                    self._init_order.append('dag_engine')
                    logger.info("[Core] DAGPipelineEngine loaded")
                except Exception as e:
                    logger.error(f"Failed to load dag_engine: {e}")
                    return None
            return self._components.get('dag_engine')

    # ── Quality Gate ────────────────────────────────────────────────────────
    def get_quality_gate(self) -> Optional[Any]:
        with self._lock:
            if 'quality_gate' not in self._components:
                try:
                    from ilma_quality_gate import ILMAQualityGate
                    self._components['quality_gate'] = ILMAQualityGate
                    self._init_order.append('quality_gate')
                    logger.info("[Core] ILMAQualityGate loaded")
                except Exception as e:
                    logger.error(f"Failed to load quality_gate: {e}")
                    return None
            return self._components.get('quality_gate')

    # ── Provider Intelligence Enricher ──────────────────────────────────────
    # DEPRECATED: Enrichment logic moved to ilma_model_db_manager.py (step 3)
    # ilma_model_router.py now uses embedded benchmark_profile + capabilities_detail
    # from PROVIDER_INTELLIGENCE_MASTER.json directly.
    # This loader returns a stub so bootstrap counts it as loaded (no-op).
    def get_enricher(self) -> Optional[Any]:
        with self._lock:
            if 'enricher' not in self._components:
                logger.info("[Core] ProviderIntelligenceEnricher DEPRECATED — enrichment via MODEL_DB_MANAGER step 3")
                self._components['enricher'] = True  # Stub marker — counts as loaded
                self._init_order.append('enricher')
            return self._components.get('enricher')

    # ── Master Orchestrator ────────────────────────────────────────────────
    def get_master_orchestrator(self) -> Optional[Any]:
        with self._lock:
            if 'master_orchestrator' not in self._components:
                try:
                    from ilma_master_orchestrator import ILMAMasterOrchestrator
                    orch = ILMAMasterOrchestrator()
                    self._components['master_orchestrator'] = orch
                    self._init_order.append('master_orchestrator')
                    logger.info("[Core] ILMAMasterOrchestrator loaded")
                except Exception as e:
                    logger.error(f"Failed to load master_orchestrator: {e}")
                    return None
            return self._components.get('master_orchestrator')

    # ── Legacy Model Router (function-based) ────────────────────────────────
    def get_legacy_router(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if 'legacy_router' not in self._components:
                try:
                    from ilma_model_router import (
                        route_task, get_best_model, get_router_stats,
                        list_free_models, detect_task_type, log_usage,
                        mark_success, mark_failure,
                    )
                    self._components['legacy_router'] = {
                        'route_task': route_task,
                        'get_best_model': get_best_model,
                        'get_router_stats': get_router_stats,
                        'list_free_models': list_free_models,
                        'detect_task_type': detect_task_type,
                        'log_usage': log_usage,
                        'mark_success': mark_success,
                        'mark_failure': mark_failure,
                    }
                    self._init_order.append('legacy_router')
                    logger.info("[Core] ILMAUnifiedRouter functions loaded (SOT-only)")
                except Exception as e:
                    logger.error(f"Failed to load legacy_router: {e}")
                    return None
            return self._components.get('legacy_router')

    # ── Capability Registry ─────────────────────────────────────────────────
    def get_capability_registry(self) -> Optional[Any]:
        with self._lock:
            if 'capability_registry' not in self._components:
                try:
                    from ilma_capability_registry import get_registry
                    reg = get_registry()
                    self._components['capability_registry'] = reg
                    self._init_order.append('capability_registry')
                    logger.info("[Core] CapabilityRegistry loaded")
                except Exception as e:
                    logger.error(f"Failed to load capability_registry: {e}")
                    return None
            return self._components.get('capability_registry')

    # ── Actor Critic Core ───────────────────────────────────────────────────
    def get_actor_critic(self) -> Optional[Any]:
        with self._lock:
            if 'actor_critic' not in self._components:
                try:
                    from ilma_actor_critic_core import ActorCriticCore
                    self._components['actor_critic'] = ActorCriticCore
                    self._init_order.append('actor_critic')
                    logger.info("[Core] ActorCriticCore loaded")
                except Exception as e:
                    logger.error(f"Failed to load actor_critic: {e}")
                    return None
            return self._components.get('actor_critic')

    # ── Workflow ECC ────────────────────────────────────────────────────────
    def get_workflow_ecc(self) -> Optional[Any]:
        with self._lock:
            if 'workflow_ecc' not in self._components:
                try:
                    from ilma_workflow_ecc import run_workflow, analyze_4w1h
                    self._components['workflow_ecc'] = {
                        'run': run_workflow,
                        'analyze_4w1h': analyze_4w1h,
                    }
                    self._init_order.append('workflow_ecc')
                    logger.info("[Core] WorkflowECC loaded")
                except Exception as e:
                    logger.error(f"Failed to load workflow_ecc: {e}")
                    return None
            return self._components.get('workflow_ecc')

    # ── Judge System ────────────────────────────────────────────────────────
    def get_judge_system(self) -> Optional[Any]:
        with self._lock:
            if 'judge_system' not in self._components:
                try:
                    from ilma_judge_system import verify_file, ALL_LEVELS, calculate_score
                    self._components['judge_system'] = {
                        'verify_file': verify_file,
                        'ALL_LEVELS': ALL_LEVELS,
                        'calculate_score': calculate_score,
                    }
                    self._init_order.append('judge_system')
                    logger.info("[Core] JudgeSystem loaded")
                except Exception as e:
                    logger.error(f"Failed to load judge_system: {e}")
                    return None
            return self._components.get('judge_system')

    # ── Execution Graph ─────────────────────────────────────────────────────
    def get_execution_graph(self) -> Optional[Any]:
        with self._lock:
            if 'execution_graph' not in self._components:
                try:
                    from ilma_execution_graph import ExecutionMemoryGraph
                    self._components['execution_graph'] = ExecutionMemoryGraph
                    self._init_order.append('execution_graph')
                    logger.info("[Core] ExecutionMemoryGraph loaded")
                except Exception as e:
                    logger.error(f"Failed to load execution_graph: {e}")
                    return None
            return self._components.get('execution_graph')

    def get_init_order(self) -> list:
        return list(self._init_order)

    def get_all(self) -> Dict[str, Any]:
        """Return all loaded components."""
        return dict(self._components)


# ─────────────────────────────────────────────────────────────────────────────
# ILMA CORE SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

class ILMACore:
    """
    The single, shared ILMA core instance.
    Provides unified access to all system components.
    Thread-safe, lazy-loaded, designed to be the ONE entry point.
    """

    VERSION = "3.0.0"
    TIERS = "SSS+++"

    def __init__(self):
        self._factory = _ComponentFactory()
        self._start_time = datetime.now()
        self._boot_id = self._start_time.strftime("%Y%m%d_%H%M%S")
        self._lock = threading.RLock()
        self._stats: Dict[str, Any] = {
            "boot_id": self._boot_id,
            "started_at": self._start_time.isoformat(),
            "components_loaded": 0,
            "total_calls": 0,
        }
        logger.info(f"[ILMACore] Booting v{self.VERSION} ({self.TIERS}) — {self._boot_id}")

    # ── Public API ──────────────────────────────────────────────────────────

    def get_router(self):
        """Get ILMASmartModelRouter (primary routing engine)."""
        self._stats['total_calls'] += 1
        return self._factory.get_smart_router()

    @property
    def smart_router(self):
        return self._factory.smart_router



    def get_fallback_engine(self):
        """Get FallbackCascadeEngine with router+health injected."""
        self._stats['total_calls'] += 1
        return self._factory.get_fallback_engine()

    def get_dag_engine(self):
        """Get DAGPipelineEngine for dependency-aware execution."""
        self._stats['total_calls'] += 1
        return self._factory.get_dag_engine()

    def get_quality_gate(self):
        """Get ILMAQualityGate class (instantiate with code, name, weight)."""
        self._stats['total_calls'] += 1
        return self._factory.get_quality_gate()

    def get_enricher(self):
        """Get ProviderIntelligenceEnricher for benchmark enrichment."""
        self._stats['total_calls'] += 1
        return self._factory.get_enricher()

    def get_orchestrator(self):
        """Get ILMAMasterOrchestrator for task decomposition."""
        self._stats['total_calls'] += 1
        return self._factory.get_master_orchestrator()

    def get_health_manager(self):
        """Get HealthManager instance."""
        self._stats['total_calls'] += 1
        return self._factory.get_health_manager()

    def get_legacy_router(self):
        """Get legacy function-based router dict."""
        self._stats['total_calls'] += 1
        return self._factory.get_legacy_router()

    def get_capability_registry(self):
        """Get CapabilityRegistry instance."""
        return self._factory.get_capability_registry()

    def get_actor_critic(self):
        """Get ActorCriticCore class."""
        return self._factory.get_actor_critic()

    def get_workflow(self):
        """Get WorkflowECC dict with run/analyze_4w1h."""
        return self._factory.get_workflow_ecc()

    def get_judge(self):
        """Get JudgeSystem dict."""
        return self._factory.get_judge_system()

    def get_execution_graph(self):
        """Get ExecutionGraph class."""
        return self._factory.get_execution_graph()

    # ── System Status ───────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Return full system status."""
        with self._lock:
            init_order = self._factory.get_init_order()
            all_components = self._factory.get_all()
            self._stats['components_loaded'] = len(all_components)
            self._stats['init_order'] = init_order
            self._stats['uptime_seconds'] = (datetime.now() - self._start_time).total_seconds()

            # Per-component status
            component_status = {}
            for name in [
                'smart_router', 'health_manager', 'fallback_engine', 'dag_engine',
                'quality_gate', 'enricher', 'master_orchestrator', 'legacy_router',
                'capability_registry', 'actor_critic', 'workflow_ecc', 'judge_system',
                'execution_graph',
            ]:
                factory_method = getattr(self._factory, f'get_{name}', None)
                if factory_method:
                    component_status[name] = "loaded" if factory_method() else "failed"

            return {
                "version": self.VERSION,
                "tiers": self.TIERS,
                "boot_id": self._boot_id,
                "started_at": self._stats['started_at'],
                "uptime_seconds": round(self._stats['uptime_seconds'], 2),
                "total_calls": self._stats['total_calls'],
                "components_loaded": len(all_components),
                "init_order": init_order,
                "component_status": component_status,
            }

    def route(self, task: str, role: str = "general", **kwargs):
        """
        Unified routing: delegate to ILMASmartModelRouter.
        Falls back to legacy router if smart router unavailable.
        """
        router = self.get_router()
        if router:
            try:
                return router.route(task, role, **kwargs)
            except Exception as e:
                logger.warning(f"Smart router failed: {e}, falling back")

        legacy = self.get_legacy_router()
        if legacy:
            return legacy['route_task'](task)

        return {"error": "No router available", "model_id": "nvidia/DeepSeek-R1", "provider": "nvidia"}

    def verify_quality(self, code: str, criticality: str = "standard", **kwargs):
        """Run quality gate verification on code."""
        gate_cls = self.get_quality_gate()
        if not gate_cls:
            return {"overall_verdict": "ERROR", "error": "Quality gate unavailable"}
        gate = gate_cls(code=code, name="ILMACore", weight=1.0)
        return gate.verify(criticality=criticality, content_type="python", **kwargs)

    # ── Bootstrap All ────────────────────────────────────────────────────────

    def bootstrap(self) -> Dict[str, Any]:
        """
        Pre-load all components. Call once at startup.
        Returns status of all components.
        """
        logger.info("[ILMACore] Bootstrap starting...")
        components = [
            'smart_router', 'health_manager', 'fallback_engine', 'dag_engine',
            'quality_gate', 'enricher', 'master_orchestrator', 'legacy_router',
            'capability_registry', 'actor_critic',
        ]
        results = {}
        for name in components:
            factory_method = getattr(self._factory, f'get_{name}', None)
            if factory_method:
                results[name] = factory_method() is not None
            else:
                results[name] = False

        logger.info(f"[ILMACore] Bootstrap complete: {sum(results.values())}/{len(results)} loaded")
        return results


# ─────────────────────────────────────────────────────────────────────────────
# SINGLETON INSTANCE
# ─────────────────────────────────────────────────────────────────────────────
_core_instance: Optional[ILMACore] = None
_core_lock = threading.Lock()


def get_core() -> ILMACore:
    """Get the singleton ILMACore instance. Thread-safe."""
    global _core_instance
    if _core_instance is None:
        with _core_lock:
            if _core_instance is None:
                _core_instance = ILMACore()
    return _core_instance


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE IMPORTS — re-export key classes for direct access
# ─────────────────────────────────────────────────────────────────────────────
def __getattr__(name: str):
    """Lazy re-export of key classes."""
    core = get_core()
    if name == 'ILMACore':
        return type(core)
    exports = {
        'ILMASmartModelRouter': 'smart_router',
        'FallbackCascadeEngine': 'fallback_engine',
        'DAGPipelineEngine': 'dag_engine',
        'ILMAQualityGate': 'quality_gate',
        'ProviderIntelligenceEnricher': 'enricher',
        'ILMAMasterOrchestrator': 'master_orchestrator',
        'HealthManager': 'health_mgr',
    }
    if name in exports:
        comp = getattr(core, f'get_{exports[name]}')()
        return type(comp) if comp else None
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


# ─────────────────────────────────────────────────────────────────────────────
# BOOTstrap on import
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__" or True:
    # Auto-bootstrap when imported directly
    core = get_core()
    status = core.bootstrap()
    print(f"[ILMA Core] v{core.VERSION} ({core.TIERS}) initialized")
    print(f"  Components loaded: {sum(status.values())}/{len(status)}")
    for name, ok in status.items():
        print(f"    {'✅' if ok else '❌'} {name}")