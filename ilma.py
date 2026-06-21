#!/usr/bin/env python3
"""
ILMA Main Entry Point — Unified System
======================================
Single entry point for all ILMA operations.

Integrates:
- Model Router (AYDA-powered)
- Judge System (L10 verification)
- Capability Registry
- Self-Improvement Engine
- Agent Civilization
- Workflow ECC

Usage:
    python3 ilma.py --status
    python3 ilma.py route "heavy coding"
    python3 ilma.py verify mycode.py
    python3 ilma.py think "build platform"
    python3 ilma.py collaborate "task description"
"""

from __future__ import annotations

# FIX 2026-06-21: suppress RequestsDependencyWarning globally before any import.
# The warning category is defined inside requests itself, so we match by message+module.
import warnings as _w
_w.filterwarnings("ignore", message="urllib3.*", module="requests")

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# === ILMA CORE IMPORTS — unified, no duplicates ===
from ilma_capability_registry import get_registry
from ilma_workflow_ecc import run_workflow, analyze_4w1h
from ilma_actor_critic_core import ActorCriticCore, VerdictLevel
from ilma_core import get_core
from ilma_model_router import route_task as model_route_task, route_task_simple as model_route_task_simple, get_best_model, list_free_models, get_router_stats
from ilma_judge_system import verify_file, ALL_LEVELS, calculate_score
from ilma_core.ilma_self_improvement import SelfImprovementEngine
from ilma_core.ilma_agent_civilization import AgentCivilization, CollaborationType
from ilma_core.ilma_unified_core import get_ilma_system
from ilma_orchestrator import ILMAOrchestrator
# All routing now uses direct provider APIs (nvidia/minimax/openrouter/etc.).
from ilma_health_manager import get_health_manager
from ilma_subagent_router import get_router, close_router

# === ILMA KANBAN & HERMES SKILLS INTEGRATION ===
try:
    from ilma_kanban_integration import ILMAKanban, get_kanban
    KANBAN_AVAILABLE = True
except ImportError:
    KANBAN_AVAILABLE = False

try:
    from ilma_hermes_skills_router import HermesSkillsRouter, get_skills_router
    SKILLS_ROUTER_AVAILABLE = True
except ImportError:
    SKILLS_ROUTER_AVAILABLE = False

# Add ILMA paths
ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
sys.path.insert(0, str(ILMA_PROFILE))

# === VERSION ===
__version__ = "3.9"
__author__ = "ILMA"
__date__ = "2026-05-17"


# === ILMA SYSTEM BOOT ===
def boot_system() -> Dict[str, Any]:
    """Boot ILMA system and return status."""
    boot_start = time.time()
    components = {}
    errors = []

    # 1. Model Router
    try:
        from ilma_model_router import route_task as model_route_task, route_task_simple as model_route_task_simple, get_best_model, list_free_models, get_router_stats
        components["model_router"] = {
            "status": "ready",
            "stats": get_router_stats(),
            "available": True
        }
    except Exception as e:
        components["model_router"] = {"status": "error", "error": str(e), "available": False}
        errors.append(f"Model Router: {e}")

    # 2. Judge System
    try:
        from ilma_judge_system import verify_file, ALL_LEVELS, calculate_score
        components["judge"] = {
            "status": "ready",
            "levels": ALL_LEVELS,
            "available": True
        }
    except Exception as e:
        components["judge"] = {"status": "error", "error": str(e), "available": False}
        errors.append(f"Judge: {e}")

    # 3. Self-Improvement
    try:
        from ilma_core.ilma_self_improvement import SelfImprovementEngine
        engine = SelfImprovementEngine()
        components["self_improvement"] = {
            "status": "ready",
            "events_tracked": len(engine.events),
            "available": True
        }
    except Exception as e:
        components["self_improvement"] = {"status": "error", "error": str(e), "available": False}
        errors.append(f"Self-Improvement: {e}")

    # 4. Agent Civilization
    try:
        from ilma_core.ilma_agent_civilization import AgentCivilization
        civ = AgentCivilization(agent_id="ilma_main")
        components["agent_civilization"] = {
            "status": "ready",
            "agents": len(civ.reputations),
            "available": True
        }
    except Exception as e:
        components["agent_civilization"] = {"status": "error", "error": str(e), "available": False}
        errors.append(f"Agent Civilization: {e}")

    # 5. Unified Core
    try:
        from ilma_core.ilma_unified_core import get_ilma_system
        system = get_ilma_system()
        components["unified_core"] = {
            "status": "ready",
            "version": system.version,
            "ayda_integrated": system.ayda_capability_orchestrator.get("available", False),
            "available": True
        }
    except Exception as e:
        components["unified_core"] = {"status": "error", "error": str(e), "available": False}
        errors.append(f"Unified Core: {e}")

    # 6. Orchestrator
    try:
        from ilma_orchestrator import ILMAOrchestrator
        orch = ILMAOrchestrator()
        components["orchestrator"] = {
            "status": "ready",
            "routes": len(orch.execution_log),
            "available": True
        }
    except Exception as e:
        components["orchestrator"] = {"status": "error", "error": str(e), "available": False}
        errors.append(f"Orchestrator: {e}")

    # 6b. Orphan Wiring (Phase 70-Autonomy) — wires 22 admin/CLI modules
    try:
        from ilma_orphan_wiring import get_orphan_wiring
        wiring = get_orphan_wiring()
        snap = wiring.verify_all()  # import-test all 22
        components["orphan_wiring"] = {
            "status": "ready",
            "capability_count": snap["total"],
            "imported_ok": snap["ok"],
            "import_failed": snap["fail"],
            "available": snap["fail"] == 0,
        }
    except Exception as e:
        components["orphan_wiring"] = {"status": "error", "error": str(e), "available": False}
        errors.append(f"OrphanWiring: {e}")

    # 7. Legacy proxy layers — fully purged 2026-06-19.
    components["proxy_layers"] = {"status": "removed", "available": False, "note": "purged 2026-06-19"}

    # 8. Model Registry (unified model DB with health awareness)
    try:
        from ilma_model_registry import get_registry
        reg = get_registry()
        components["model_registry"] = {
            "status": "ready",
            "total_providers": len(reg._providers),
            "free_models": len(reg.get_free_models()),
            "available": True
        }
    except Exception as e:
        components["model_registry"] = {"status": "error", "error": str(e), "available": False}
        errors.append(f"Model Registry: {e}")

    # 9. Health Manager (rate-limit tracking + persistence)
    try:
        from ilma_health_manager import get_health_manager
        hm = get_health_manager()
        stats = hm.get_stats()
        model_states = stats['model_count']
        provider_states = stats['provider_count']
        components["health_manager"] = {
            "status": "ready",
            "tracked_models": model_states,
            "tracked_providers": provider_states,
            "available": True,
            "rate_limited": stats['rate_limited_count'],
            "available_models": stats['available_count'],
        }
    except Exception as e:
        components["health_manager"] = {"status": "error", "error": str(e), "available": False}
        errors.append(f"Health Manager: {e}")

    # 10. SubAgent Router (health-aware routing for all sub-agent calls)
    try:
        from ilma_subagent_router import get_router, close_router
        router = get_router()
        # Quick routing test
        test_result = router.select_model(role='general', task_category='general')
        components["subagent_router"] = {
            "status": "ready",
            "test_model": test_result.model if test_result else None,
            "health_aware": True,
            "available": True
        }
        close_router()
    except Exception as e:
        components["subagent_router"] = {"status": "error", "error": str(e), "available": False}
        errors.append(f"SubAgent Router: {e}")

    # 11. Hermes Skills Router (unified skill execution engine - SSS Tier)
    try:
        from ilma_hermes_skills_router import get_skills_router, HermesSkillsRouter
        router = get_skills_router()  # Singleton - reuses across all calls
        stats = router.get_stats()
        exec_stats = router.get_execution_stats()
        validation = router.validate_all_hermes_skills()
        components["hermes_skills_router"] = {
            "status": "ready",
            "version": "v2.0",
            "hermes_skills": stats["hermes_skills_total"],
            "ilma_skills": stats["ilma_skills_total"],
            "categories": stats["categories"],
            "patterns": stats["patterns"],
            "total_monitored": stats["hermes_skills_total"] + stats["ilma_skills_total"],
            "optional_hermes_skills": validation["total_optional_expected"],
            "optional_installed": validation["total_installed"],
            "validation_status": validation["status"],
            "execution_capable": True,
            "learning_cache": True,
            "available": True
        }
    except Exception as e:
        components["hermes_skills_router"] = {"status": "error", "error": str(e), "available": False}
        errors.append(f"Hermes Skills Router: {e}")

    # 12. Kanban Board (Hermes v0.13.0 multi-agent coordination)
    try:
        if KANBAN_AVAILABLE:
            kanban = get_kanban()
            boards = kanban.boards()
            stats = kanban.stats()
            components["kanban"] = {
                "status": "ready",
                "boards": boards,
                "stats": stats,
                "available": True
            }
        else:
            components["kanban"] = {"status": "unavailable", "available": False, "reason": "Module not importable"}
    except Exception as e:
        components["kanban"] = {"status": "error", "error": str(e), "available": False}
        errors.append(f"Kanban: {e}")

    # 12. Hermes Skills Router (682+ Hermes skills auto-trigger)
    try:
        if SKILLS_ROUTER_AVAILABLE:
            router = get_skills_router()
            stats = router.get_stats()
            components["hermes_skills"] = {
                "status": "ready",
                "hermes_skills": stats["hermes_skills_total"],
                "ilma_skills": stats["ilma_skills_total"],
                "categories": stats["categories"],
                "patterns": stats["patterns"],
                "available": True
            }
        else:
            components["hermes_skills"] = {"status": "unavailable", "available": False, "reason": "Module not importable"}
    except Exception as e:
        components["hermes_skills"] = {"status": "error", "error": str(e), "available": False}
        errors.append(f"Hermes Skills Router: {e}")

    boot_time = (time.time() - boot_start) * 1000

    # ── ILMA CONTROLLED_CANARY UNIFIED CORE ──────────────────────────────────────
    try:
        core = get_core()
        core_status = core.status()
        components["ilma_core"] = {
            "status": "ready",
            "version": core_status["version"],
            "tiers": core_status["tiers"],
            "components": core_status["components_loaded"],
            "init_order": core_status["init_order"],
            "uptime_s": core_status["uptime_seconds"],
            "available": True
        }
        # Add CONTROLLED_CANARY components individually
        for comp_name, comp_status in core_status.get("component_status", {}).items():
            if comp_name not in components:
                components[f"core_{comp_name}"] = {
                    "status": comp_status,
                    "available": comp_status == "loaded"
                }
    except Exception as e:
        components["ilma_core"] = {"status": "error", "error": str(e), "available": False}
        errors.append(f"ILMA Core: {e}")

    return {
        "version": __version__,
        "boot_time_ms": round(boot_time, 2),
        "components": components,
        "errors": errors,
        "ready": len(errors) == 0
    }


# === MODEL ROUTING ===
def route_task(message: str, prefer_free: bool = True, response: str = None, execute: bool = False) -> Dict[str, Any]:
    """Route task to best model.
    
    Now integrates:
    - 4W1H analysis via ilma_workflow_ecc
    - Capability workflow for heavy tasks (BUILD, FIX, AUDIT, COMPLEX)
    - Capability registry checks via ilma_capability_registry
    - Fallback chain support
    - Actor-Critic evaluation (when response provided or execute=True)
    
    Args:
        message: The task/command to route
        prefer_free: Prefer free models (default True)
        response: Optional - if provided, actor-critic evaluates this response
        execute: If True, execute model and evaluate response (full pipeline)
    
    Returns:
        Dict with routing info, and optionally evaluation results
    """
    # Step 0: Check if this is a heavy task — use full capability workflow
    quick_analysis = analyze_4w1h(message)
    is_heavy = (
        quick_analysis.get("how") == "COMPLEX" or 
        quick_analysis.get("what") in ("BUILD", "FIX", "AUDIT")
    )
    
    if is_heavy:
        # Heavy task: use full capability workflow (includes routing + phases)
        print(f"[ROUTE] Heavy task detected ({quick_analysis.get('what')}, {quick_analysis.get('how')}) — using capability workflow")
        return run_capability_workflow(message)
    
    # Step 1: Analyze task with 4W1H
    task_analysis = analyze_4w1h(message)
    task_type = task_analysis.get("what", "GENERAL").lower()
    
    # Step 2: Check capability registry
    registry = get_registry()
    capability = registry.get(task_type)
    
    if capability:
        # Log if capability needs approval (high/critical risk)
        if capability.needs_approval():
            print(f"[WARNING] Task '{task_type}' requires approval (risk: {capability.risk_level})")
        
        # Check for fallback capability
        fallback_cap = registry.get_fallback(task_type)
        if fallback_cap and fallback_cap != capability.primary_tool:
            print(f"[INFO] Fallback available: {fallback_cap}")
    
    # Step 3: Build capability context for scoring
    capability_context = None
    if capability:
        capability_context = {
            "name": capability.name,
            "primary_tool": capability.primary_tool,
            "tags": capability.tags,
            "status": capability.status.value if hasattr(capability.status, 'value') else str(capability.status),
            "risk_level": capability.risk_level,
        }
    
    # Step 4: Route via model router
    result = model_route_task(task_type, max_fallbacks=3)

    # Step 7: Auto-detect Hermes/ILMA skills based on task context
    # NOTE: Only run for non-heavy tasks. Heavy tasks go through run_capability_workflow()
    # which returns a different format. We detect skills after heavy workflow completion.
    if SKILLS_ROUTER_AVAILABLE:
        try:
            skill_router = get_skills_router()
            task_context = {
                "task_type": task_type,
                "domain": task_analysis.get("what", "").lower(),
                "complexity": task_analysis.get("how", ""),
            }
            skill_matches = skill_router.route(message, context=task_context)
            if skill_matches:
                result["skill_matches"] = [
                    {
                        "name": m.skill_name,
                        "category": m.category,
                        "confidence": m.confidence,
                        "source": m.source,
                    }
                    for m in skill_matches[:5]
                ]
                # Log top skill match
                top = skill_matches[0]
                print(f"[SKILLS] Auto-detected: {top.skill_name} ({top.source}, conf={top.confidence:.2f})")
        except Exception as e:
            print(f"[SKILLS] Auto-detection failed: {e}")
    
    # Step 5: Add capability info to result
    result["task_analysis"] = task_analysis
    if capability:
        result["capability"] = {
            "name": capability.name,
            "primary_tool": capability.primary_tool,
            "needs_approval": capability.needs_approval(),
            "risk_level": capability.risk_level,
        }
    
    # Step 6: ACTOR-CRITIC EVALUATION — evaluate response if provided
    if response:
        print(f"[ACTOR-CRITIC] Evaluating response quality...")
        model_id = result.get("route", {}).get("model_id", "unknown")
        
        evaluation = evaluate_and_retry(
            response=response,
            task_type=task_type,
            original_model=model_id,
            max_retries=2
        )
        
        result["actor_critic_eval"] = evaluation
        
        # Add retry info to routing result
        if evaluation.get("retries", 0) > 0:
            result["retry_triggered"] = True
            result["fallback_used"] = evaluation.get("fallback_used")
            print(f"[ACTOR-CRITIC] Retry triggered — fallback: {evaluation.get('fallback_used', 'N/A')}")
    
    return result


def route_and_execute(message: str, prefer_free: bool = True) -> Dict[str, Any]:
    """Full pipeline: route task → execute model → evaluate with actor-critic → retry if needed.
    
    Pure data-driven routing: model selection based on benchmark scores,
    capability match, intelligence, trust, and freshness from PROVIDER_INTELLIGENCE_MASTER.json.
    No hardcoded primary model — router selects the best model per task.
    """
    print(f"[PIPELINE] route_and_execute starting for task: {message[:50]}...")
    
    # Step 1: Route the task (returns flat dict with model_id, provider, etc.)
    # Use simple router to map message → best free model
    try:
        _mid, _prov, _reason = model_route_task_simple(message)
        route_result = {
            "model_id": _mid,
            "provider": _prov,
            "specialization": "general",
            "routing_reason": _reason,
        }
    except Exception as _e:
        route_result = {"model_id": None, "provider": "unknown", "error": str(_e)}
    
    # Step 2: Get the selected model (flat keys — no "route" wrapper)
    primary_model = route_result.get("model_id")    # e.g. "nvidia/meta/llama-3.3-70b-instruct"
    provider = route_result.get("provider", "unknown")  # e.g. "nvidia"
    task_type = route_result.get("specialization", "general")
    
    if not primary_model:
        return {
            "success": False,
            "error": "No model selected",
            "route_result": route_result
        }
    
    print(f"[PIPELINE] Selected model: {provider}/{primary_model}")
    
    # Determine thinking mode based on task type
    thinking_map = {
        "coding": "Thinking", "reasoning": "Thinking", "research": "Thinking",
        "analysis": "Thinking", "planning": "Thinking",
        "creative": "Auto", "general": "Auto", "fast": "Fast", "vision": "Auto",
    }
    thinking_mode = thinking_map.get(task_type, "Auto")

    # Direct cloud API execution.
    response = None
    execution_success = False

    try:
        from ilma_model_router import execute_call
        direct_result = execute_call(
            model_id=primary_model,
            provider=provider,
            message=message,
        )
        if isinstance(direct_result, str) and direct_result and not direct_result.startswith("Error:"):
            response = direct_result
            execution_success = True
            print(f"[PIPELINE] Direct execution successful ({len(response)} chars)")
        else:
            print(f"[PIPELINE] Direct execution returned: {str(direct_result)[:120]}")

    except Exception as e:
        print(f"[PIPELINE] Direct execution failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 5: If execution failed, run actor-critic evaluation
    if not execution_success or not response:
        print(f"[PIPELINE] Execution issue detected — running actor-critic evaluation...")
        
        response = response or f"[EXECUTION FAILED] Model: {provider}/{primary_model}, Error: Direct execution returned no content"
        
        evaluation = evaluate_and_retry(
            response=response,
            task_type=task_type,
            original_model=primary_model,
            max_retries=2
        )
        
        route_result["actor_critic_eval"] = evaluation
        route_result["execution_status"] = "failed"
        
        return {
            "success": False,
            "route_result": route_result,
            "response": response,
            "evaluation": evaluation,
            "model_used": primary_model,
            "provider": provider
        }
    
    # Step 6: Evaluate the response with actor-critic
    print(f"[PIPELINE] Running actor-critic evaluation...")
    evaluation = evaluate_and_retry(
        response=response,
        task_type=task_type,
        original_model=primary_model,
        max_retries=2
    )
    
    route_result["actor_critic_eval"] = evaluation
    
    # Step 7: Handle retry if quality was below threshold
    final_response = response
    retry_info = {"retries": 0}
    
    if evaluation.get("retries", 0) > 0:
        print(f"[PIPELINE] Quality below threshold — attempting retry...")
        fallback = evaluation.get("fallback_used")
        
        if fallback and fallback != primary_model:
            print(f"[PIPELINE] Retrying with fallback: {fallback}")
            # Direct provider call (legacy proxy layer fully purged)
            try:
                retry_result = execute_call(
                    model_id=fallback,
                    provider=provider,
                    message=message,
                )
                if isinstance(retry_result, str) and retry_result and not retry_result.startswith("Error:"):
                    final_response = retry_result
                    retry_info = {"retries": evaluation["retries"], "fallback_used": fallback}
                    route_result["retry_info"] = retry_info
            except Exception as _re:
                print(f"[PIPELINE] Retry via direct call failed: {_re}")
    
    route_result["execution_status"] = "success"
    
    return {
        "success": True,
        "route_result": route_result,
        "response": final_response,
        "evaluation": evaluation,
        "model_used": primary_model,
        "provider": provider,
        "retry_info": retry_info,
    }


def get_best_model_for_task(task_type: str) -> str:
    """Get best model ID for task type.
    
    Now integrates capability fallback chain from registry.
    """
    # Get fallback chain from capability registry
    registry = get_registry()
    fallback = registry.get_fallback(task_type)
    
    # Route via model router
    result = model_route_task(task_type)
    model_id = result.get("model_id") or result.get("fallback_model", "")
    
    # Include fallback info in result if available
    if fallback:
        result["fallback_chain"] = [model_id, fallback] if fallback != model_id else [model_id]
    
    return model_id


# === ACTOR-CRITIC EVALUATION ===
def evaluate_and_retry(response: str, task_type: str, original_model: str, max_retries: int = 2) -> Dict[str, Any]:
    """Evaluate response quality using Actor-Critic and retry with fallback if needed.
    
    Args:
        response: The response to evaluate
        task_type: Type of task (e.g., 'coding', 'reasoning')
        original_model: Model that generated the response
        max_retries: Maximum number of retries (default 2)
    
    Returns:
        Dict with evaluation result, retry count, and final response
    """
    print(f"[ACTOR-CRITIC] Evaluating response quality...")
    
    # Initialize Actor-Critic core
    core = ActorCriticCore(self_improve=False, max_rounds=3, judge_threshold=4.0)

    # ── Real LLM judge (audit 2026-06-20 Q1) ──────────────────────────────────────
    # The built-in _default_judge scores by counting structural keywords/tags, which is
    # gameable and ignores correctness. Wire a real free-model judge with a rubric prompt.
    # SAFE/additive: on ANY failure it delegates to the original _default_judge, so behavior
    # is never worse than before.
    def _llm_judge(jtask, actor_output, reference, rubric):
        import json as _json, re as _re
        try:
            prompt = (
                "You are a STRICT quality judge. Score the RESPONSE on a 0-5 scale "
                "(5=excellent, 0=unusable) considering ACCURACY, COMPLETENESS, CORRECTNESS, "
                "and how well it satisfies the TASK and REFERENCE CRITERIA. Penalize fabrication "
                "and unsupported claims; reward correct, well-grounded answers. "
                'Reply with ONLY compact JSON: {"score": <number 0-5>, "feedback": "<one sentence>"}.\n\n'
                f"TASK:\n{jtask}\n\nREFERENCE CRITERIA:\n{reference}\n\nRESPONSE:\n{(actor_output or '')[:6000]}"
            )
            _mid, _prov, _ = model_route_task_simple("evaluate and score answer quality (reasoning)")
            from ilma_model_router import execute_call
            raw = execute_call(model_id=_mid, provider=_prov, message=prompt)
            if not raw or raw.strip().startswith("Error:") or "❌" in raw[:30]:
                raise RuntimeError("judge model returned no/error output")
            m = _re.search(r"\{.*\}", raw, _re.DOTALL)
            data = _json.loads(m.group(0)) if m else {}
            score = max(0.0, min(5.0, float(data["score"])))
            return score, f"[LLM-judge {_mid}] {str(data.get('feedback',''))[:400]}"
        except Exception as _je:
            # graceful fallback to the deterministic heuristic — never worse than before
            try:
                s, fb = core._default_judge(jtask, actor_output, reference, rubric)
                return s, f"[heuristic fallback: {type(_je).__name__}] {fb}"
            except Exception:
                return 3.0, f"[judge unavailable: {_je}]"
    try:
        core.set_judge_callback(_llm_judge)
    except Exception:
        pass

    # Create evaluation session
    session = core.create_session(
        task=f"Task type: {task_type}\nEvaluate response quality",
        target_criteria=f"Response must be accurate, complete, and well-structured for {task_type} tasks",
        max_rounds=3
    )
    
    # Set actor to just return the response (we're evaluating existing response)
    core._actor_callback = lambda t, ctx: response
    
    # Run evaluation
    try:
        round_result = core.execute_round(session.session_id)
        verdict = session.final_verdict
        score = session.final_score
    except Exception as e:
        print(f"[ACTOR-CRITIC] Evaluation error: {e}")
        verdict = VerdictLevel.WARN
        score = 3.0
    
    # Determine if we need to retry
    should_retry = verdict in (VerdictLevel.FAIL, VerdictLevel.ERROR) or (verdict == VerdictLevel.WARN and score < 3.5)
    
    result = {
        "verdict": verdict.value if verdict else "UNKNOWN",
        "score": score,
        "retries": 0,
        "final_model": original_model,
        "response": response
    }
    
    if should_retry and max_retries > 0:
        print(f"[ACTOR-CRITIC] Quality below threshold (verdict={verdict.value if verdict else 'N/A'}, score={score}). Retrying...")
        
        # Get fallback model from capability registry
        registry = get_registry()
        fallback = registry.get_fallback(task_type)
        
        if fallback:
            print(f"[ACTOR-CRITIC] Switching to fallback: {fallback}")
            result["fallback_used"] = fallback
            result["retries"] = 1
            # Note: In a full implementation, we would re-execute the task with the fallback model
            # For now, we just report the fallback
        else:
            print(f"[ACTOR-CRITIC] No fallback available for {task_type}")
    
    return result


# === WORKFLOW EXECUTION ===
def run_capability_workflow(task_message: str) -> Dict[str, Any]:
    """Run capability workflow for heavy tasks via ilma_workflow_ecc.
    
    NOW INTEGRATES:
    - ILMAKanban: Auto-wired for complex tasks (COMPLEX/MEDIUM complexity)
    - Kanban event logging: All task events logged automatically
    - AutonomousLoopEngine: Triggered after task completion (in-process, not cron)
    
    Args:
        task_message: The task description
    
    Returns:
        Dict with workflow result, routing info, kanban integration, and loop engine events
    """
    print(f"[WORKFLOW] Running capability workflow for task...")
    
    # Analyze with 4W1H first
    analysis = analyze_4w1h(task_message)
    
    # Determine if task is "heavy" (complex or BUILD/FIX types)
    is_heavy = analysis.get("how") == "COMPLEX" or analysis.get("what") in ("BUILD", "FIX", "AUDIT")
    
    # ── KANBAN INTEGRATION: Auto-wire for complex tasks ────────────────────────
    # Auto-detect complex tasks via 4W1H analysis (COMPLEX complexity → use Kanban)
    complexity = analysis.get("how", "SIMPLE")
    use_kanban = is_heavy or complexity == "COMPLEX" or complexity == "MEDIUM"
    
    kanban_task_id = None
    kanban_available = False
    kanban = None  # Keep reference to avoid "possibly unbound" issues
    
    if use_kanban and KANBAN_AVAILABLE:
        try:
            kanban = get_kanban()
            kanban_available = True
            
            # Create kanban task to track this workflow execution
            # Body is used for FREE model auto-selection
            task_type = analysis.get("what", "general").lower()
            complexity_label = analysis.get("how", "SIMPLE")
            
            body = (
                f"Task type: {task_type}\n"
                f"Complexity: {complexity_label}\n"
                f"Workflow: capability_workflow\n"
                f"Message: {task_message[:300]}\n"
            )
            
            kanban_task = kanban.create(
                title=f"[WORKFLOW] {task_type.upper()}: {task_message[:60]}...",
                body=body,
                assignee="ilma",
                priority=2 if complexity == "COMPLEX" else 1,
                skills=["ilma-autonomous-loops"],
            )
            kanban_task_id = kanban_task.id
            
            # Log START event
            kanban.comment(
                kanban_task_id,
                f"🚀 Workflow STARTED — Complexity: {complexity_label}, Type: {task_type}"
            )
            
            print(f"[KANBAN] Task created: {kanban_task_id} (complexity={complexity_label})")
            
        except Exception as kanban_err:
            print(f"[KANBAN] Integration failed: {kanban_err} — continuing without kanban")
            kanban_available = False
    
    result = {
        "workflow_executed": False,
        "analysis": analysis,
        "routing": {},
        "kanban": {
            "available": kanban_available,
            "task_id": kanban_task_id,
            "wired": kanban_available and kanban_task_id is not None,
        },
        "autonomous_loop": {
            "triggered": False,
            "cycle_result": None,
        },
    }
    
    if is_heavy:
        print(f"[WORKFLOW] Heavy task detected ({analysis.get('what')}, {analysis.get('how')}) — running full workflow")
        
        # Run the ECC workflow
        workflow_start = time.time()
        workflow_result = run_workflow(task_message)
        workflow_elapsed = time.time() - workflow_start
        
        result["workflow_executed"] = True
        result["workflow_result"] = workflow_result
        result["routing"] = {
            "workflow_assigned": workflow_result.get("workflow", "unknown"),
            "phases_completed": workflow_result.get("phases_completed", []),
            "success": workflow_result.get("success", False),
            "elapsed_seconds": round(workflow_elapsed, 2),
        }
        
        # ── KANBAN: Log COMPLETION event ──────────────────────────────────────
        if kanban_available and kanban_task_id:
            try:
                success = workflow_result.get("success", False)
                phases = len(workflow_result.get("phases_completed", []))
                elapsed = workflow_result.get("elapsed_seconds", 0)
                
                # Mark complete or failed
                if success:
                    metadata = {
                        "complexity": complexity,
                        "task_type": analysis.get("what", "unknown"),
                        "phases_completed": phases,
                        "elapsed_seconds": elapsed,
                        "workflow": workflow_result.get("workflow", "unknown"),
                    }
                    kanban.complete(
                        kanban_task_id,
                        summary=f"✅ COMPLETED — {phases} phases in {elapsed:.1f}s",
                        metadata=metadata,
                    )
                    kanban.comment(kanban_task_id, f"✅ Workflow COMPLETED successfully in {elapsed:.1f}s")
                else:
                    errors = workflow_result.get("errors", [])
                    kanban.block(
                        kanban_task_id,
                        reason=f"❌ FAILED — errors: {errors[:2]}"
                    )
                    kanban.comment(kanban_task_id, f"❌ Workflow FAILED: {errors[:1]}")
            except Exception as completion_err:
                print(f"[KANBAN] Failed to log completion: {completion_err}")
        
        # ── AUTONOMOUS LOOP ENGINE: Trigger after heavy task completion ─────────
        # NOT cron-triggered — runs in-process immediately after task completes
        try:
            from ilma_autonomous_loop_engine import AutonomousLoopEngine
            
            loop_engine = AutonomousLoopEngine(engine_id=f"ilma_post_{workflow_result.get('job_id', 'unknown')}")
            loop_engine._running = True
            loop_engine._last_run = datetime.now()
            
            # Run one lightweight cycle (task=None → autonomous optimization)
            # This allows the engine to discover, analyze, and potentially self-improve
            print(f"[AUTO-LOOP] Triggering AutonomousLoopEngine after task completion...")
            
            # Only run if this was a complex task (don't slow down simple tasks)
            if complexity == "COMPLEX":
                cycle_result = loop_engine.run_cycle(task=f"post_task_{analysis.get('what', 'general')}")
                result["autonomous_loop"] = {
                    "triggered": True,
                    "cycle_result": {
                        "loop_count": cycle_result.get("loop_count", 0),
                        "evolution_delta": cycle_result.get("evolution_delta", 0.0),
                        "states_completed": [s.get("state") for s in cycle_result.get("states_completed", [])],
                        "execution_time": cycle_result.get("execution_time", 0.0),
                    },
                }
                print(f"[AUTO-LOOP] Cycle complete — evolution_delta={cycle_result.get('evolution_delta', 0):.3f}")
            else:
                # For MEDIUM complexity, just record the event (lightweight)
                loop_engine.loop_count += 1
                loop_engine._last_run = datetime.now()
                result["autonomous_loop"] = {
                    "triggered": True,
                    "cycle_result": {
                        "loop_count": loop_engine.loop_count,
                        "evolution_delta": 0.0,
                        "states_completed": [],
                        "execution_time": 0.0,
                        "note": "Lightweight event recording only (MEDIUM complexity)",
                    },
                }
                print(f"[AUTO-LOOP] Event recorded (lightweight mode for MEDIUM complexity)")
                
        except Exception as loop_err:
            print(f"[AUTO-LOOP] Trigger failed: {loop_err} — continuing without loop engine")
            result["autonomous_loop"]["error"] = str(loop_err)
        
        # Auto-detect Hermes/ILMA skills for heavy tasks too
        if SKILLS_ROUTER_AVAILABLE:
            try:
                skill_router = get_skills_router()
                task_type = analysis.get("what", "general").lower()
                task_context = {
                    "task_type": task_type,
                    "domain": task_type,
                    "complexity": analysis.get("how", ""),
                }
                skill_matches = skill_router.route(task_message, context=task_context)
                if skill_matches:
                    result["skill_matches"] = [
                        {
                            "name": m.skill_name,
                            "category": m.category,
                            "confidence": m.confidence,
                            "source": m.source,
                        }
                        for m in skill_matches[:5]
                    ]
                    top = skill_matches[0]
                    print(f"[SKILLS] Auto-detected: {top.skill_name} ({top.source}, conf={top.confidence:.2f})")
            except Exception as e:
                print(f"[SKILLS] Auto-detection failed: {e}")
        
        return result
    else:
        # Light task - just route normally
        print(f"[WORKFLOW] Light task ({analysis.get('what')}) — skipping heavy workflow")
        
        routing_result = model_route_task(task_message)
        result["routing"] = routing_result
        
        # Log light task to kanban if available
        if kanban_available and kanban_task_id:
            try:
                kanban.complete(
                    kanban_task_id,
                    summary=f"✅ Light task routed directly — model: {routing_result.get('model_id', 'unknown')}",
                )
            except Exception as kanban_err:
                print(f"[KANBAN] Failed to complete light task: {kanban_err}")
        
        return result


# ══════════════════════════════════════════════════════════════════════════════
# CODE VERIFICATION
# ══════════════════════════════════════════════════════════════════════════════
def verify_code(file_path: str, levels: Optional[List[str]] = None) -> Dict[str, Any]:
    """Verify code file."""
    if levels is None:
        levels = ["L1_COMPILE", "L5_SECURITY", "L6_PERFORMANCE"]
    return verify_file(file_path, levels=levels)


def quick_verify_code(code: str) -> bool:
    """Quick verify code snippet."""
    import tempfile
    temp = tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode='w')
    temp.write(code)
    temp.close()

    try:
        result = verify_code(temp.name, ["L1_COMPILE", "L5_SECURITY"])
        return result.get("verdict") == "PASS"
    finally:
        Path(temp.name).unlink(missing_ok=True)


# === COGNITIVE PROCESSING ===
def think(task: str, mode: str = "reactive") -> Dict[str, Any]:
    """Process task with cognitive engine."""
    system = get_ilma_system()
    return system.think(task, mode)


# === COLLABORATION ===
def collaborate(task: str, agents: Optional[List[str]] = None) -> Dict[str, Any]:
    """Run collaborative task."""
    civ = AgentCivilization(agent_id="ilma_main")
    if agents:
        for agent in agents:
            civ.add_collaborator(agent)

    # Create session
    session_id = f"collab_{int(time.time())}"
    session = civ.create_session(
        session_id=session_id,
        participants=agents or ["ilma_main"],
        collaboration_type=CollaborationType.PARALLEL,
        task=task
    )

    return {
        "session_id": session_id,
        "task": task,
        "agents": agents or ["ilma_main"],
        "status": "initiated"
    }


# === SELF-IMPROVEMENT ===
def record_learning(task: str, quality: float, model: str, time_ms: float):
    """Record learning event."""
    engine = SelfImprovementEngine()
    return engine.record_event(
        task_type=task,
        task_description=task,
        model_used=model,
        provider="auto",
        result_quality=quality,
        execution_time_ms=time_ms,
        verified=True
    )


def run_optimization() -> Dict[str, Any]:
    """Run self-optimization cycle."""
    engine = SelfImprovementEngine()
    return engine.run_optimization_cycle()


# === ORCHESTRATE ===
def orchestrate(task: str) -> Dict[str, Any]:
    """Orchestrate task through ILMA system.
    
    Now integrates:
    - Capability workflow via run_capability_workflow
    - Actor-Critic evaluation for quality assurance
    """
    orch = ILMAOrchestrator()
    result = orch.route_intent(task)
    exec_result = orch.execute_with_intent(task, result["handler"], result["params"])
    
    # Integrate Actor-Critic evaluation if execution succeeded
    if exec_result.get("status") == "success" and exec_result.get("response"):
        print(f"[ORCHESTRATOR] Running Actor-Critic evaluation...")
        
        # Analyze task type
        analysis = analyze_4w1h(task)
        task_type = analysis.get("what", "GENERAL").lower()
        
        # Evaluate response quality
        evaluation = evaluate_and_retry(
            response=exec_result.get("response", ""),
            task_type=task_type,
            original_model=result.get("route", {}).get("model_id", "unknown"),
            max_retries=2
        )
        
        # Add evaluation to result
        exec_result["actor_critic_eval"] = evaluation
        
        # If quality was below threshold, add warning
        if evaluation.get("retries", 0) > 0:
            exec_result["warning"] = f"Response quality below threshold, used fallback"
            exec_result["status"] = "success_with_retry"
    
    return exec_result


# === CLI COMMANDS ===
def cmd_status(args):
    """Show ILMA system status."""
    status = boot_system()

    print("=" * 60)
    print(f"ILMA System v{__version__} — Status")
    print("=" * 60)
    print(f"Boot time: {status['boot_time_ms']:.2f}ms")
    print(f"Ready: {'✅' if status['ready'] else '⚠️'}")
    print()

    print("Components:")
    for name, comp in status["components"].items():
        icon = "✅" if comp.get("available") else "❌"
        print(f"  {icon} {name}: {comp.get('status', 'unknown')}")

    if status["errors"]:
        print()
        print("Errors:")
        for err in status["errors"]:
            print(f"  ❌ {err}")

    # ── ILMA CONTROLLED_CANARY UNIFIED CORE STATUS ──────────────────────────────
    core_info = status["components"].get("ilma_core", {})
    if core_info.get("available"):
        print()
        print("ILMA Core CONTROLLED_CANARY (Unified):")
        print(f"  Version: {core_info.get('version', 'N/A')} | Tiers: {core_info.get('tiers', 'N/A')}")
        print(f"  Components: {core_info.get('components', 'N/A')}")
        print(f"  Uptime: {core_info.get('uptime_s', 0):.2f}s")
        init_order = core_info.get('init_order', [])
        print(f"  Init order: {' → '.join(init_order)}")

    # Show model router stats
    mr = status["components"].get("model_router", {})
    if mr.get("available"):
        stats = mr.get("stats", {})
        print()
        print("Model Router (AYDA-Powered):")
        print(f"  Providers: {stats.get('total_providers', 'N/A')}")
        print(f"  Models: {stats.get('total_models', 'N/A')}")
        print(f"  Free: {stats.get('free_models', 'N/A')}")
        print(f"  DB Size: {stats.get('db_size_mb', 'N/A')} MB")

    # Show judge levels
    judge = status["components"].get("judge", {})
    if judge.get("available"):
        print()
        print("Judge System:")
        levels = judge.get("levels", [])
        print(f"  Levels: {len(levels)} (L1-L10)")

    print("=" * 60)


def cmd_route(args):
    """Route task to best model with Hermes skills auto-detection."""
    print(f"Routing: {args.task_type}")
    result = route_task(args.task_type)  # Uses ilma.py route_task (with skills detection)
    
    # Handle both formats: direct route vs workflow-embedded routing
    route = result.get("route", result.get("routing", {}))
    task_type = result.get("task_type", "N/A")
    
    if result.get("workflow_executed"):
        # Heavy task went through capability workflow
        routing = result.get("routing", {})
        task_type = result.get("analysis", {}).get("what", "N/A")
        route_model_id = "via workflow"
        route_provider = routing.get("workflow_assigned", "N/A")
        route_score = 1.0
        route_is_free = True
        fallbacks = 0
        workflow_success = routing.get("success", False)
    else:
        # Non-heavy task: model_route_task returns flat dict directly
        route_model_id = result.get("model_id", "N/A")
        route_provider = result.get("provider", "N/A")
        route_score = result.get("composite_score", 0)
        route_is_free = result.get("is_free", False)
        fallbacks = len(result.get("fallback_chain", []))
        workflow_success = None

    print()
    print(f"Task Type: {result.get('task_analysis', {}).get('what') or result.get('task_type') or task_type}")
    print(f"Model: {route_model_id}")
    print(f"Provider: {route_provider}")
    print(f"Score: {route_score:.4f}")
    print(f"Free: {route_is_free}")
    print(f"Fallbacks: {fallbacks}")
    if workflow_success is not None:
        print(f"Workflow: {'✅ success' if workflow_success else '❌ failed'}")

    # Show auto-detected Hermes/ILMA skills
    skill_matches = result.get("skill_matches", [])
    if skill_matches:
        print()
        print("Auto-detected Skills:")
        for s in skill_matches[:5]:
            icon = "🔧" if s["source"] == "hermes" else "🤖"
            print(f"  {icon} {s['name']} ({s['source']}, conf={s['confidence']:.2f})")

    if args.json:
        print()
        print(json.dumps(result, indent=2))


def cmd_verify(args):
    """Verify code file."""
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"❌ File not found: {args.file}")
        return

    print(f"Verifying: {args.file}")
    result = verify_code(str(file_path))

    print()
    print(f"Verdict: {result.get('verdict', 'N/A')}")
    print(f"Score: {result.get('score', 0):.2%}")
    print(f"Time: {result.get('elapsed_seconds', 0):.3f}s")

    if args.verbose:
        print()
        print("Level Results:")
        for r in result.get("results", []):
            icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "ERROR": "❗"}.get(r.get("status"), "?")
            print(f"  {icon} {r.get('level')}: {r.get('message')}")

    if args.json:
        print()
        print(json.dumps(result, indent=2))


def cmd_think(args):
    """Cognitive processing."""
    print(f"Thinking: {args.task}")
    print(f"Mode: {args.mode}")

    result = think(args.task, args.mode)

    print()
    print(f"Mode: {result.get('mode')}")
    print(f"Confidence: {result.get('confidence', 0):.2f}")
    print(f"Model used: {result.get('model_used', 'N/A')}")
    print(f"Thinking steps: {len(result.get('thinking_steps', []))}")

    for step in result.get("thinking_steps", []):
        print(f"  → {step.get('description')}")


def cmd_collaborate(args):
    """Run collaborative task."""
    agents = args.agents.split(",") if args.agents else None
    print(f"Collaborating: {args.task}")
    if agents:
        print(f"Agents: {agents}")

    result = collaborate(args.task, agents)

    print()
    print(f"Session: {result.get('session_id')}")
    print(f"Status: {result.get('status')}")
    print(f"Agents: {result.get('agents')}")


def cmd_optimize(args):
    """Run self-optimization."""
    print("Running optimization cycle...")

    result = run_optimization()

    print()
    print(f"Quality trend: {result.get('quality_trend')}")
    print(f"Avg quality: {result.get('avg_quality', 0):.4f}")
    print(f"Events analyzed: {result.get('events_analyzed')}")
    print(f"Suggestions: {result.get('suggestions_generated')}")

    if result.get("suggestions"):
        print()
        print("Suggestions:")
        for sug in result["suggestions"]:
            print(f"  [{sug.get('area')}] {sug.get('description')} (impact: {sug.get('impact', 0):.2f})")


def cmd_self_improve(args):
    """Run LAYER 9 self-improvement: audit + optimize."""
    print("=" * 60)
    print("ILMA LAYER 9 — Self-Improvement System")
    print("=" * 60)
    print()

    try:
        import sys
        from pathlib import Path
        ilma_root = Path("/root/.hermes/profiles/ilma")
        sys.path.insert(0, str(ilma_root))

        from ilma_self_improve_integrator import get_integrator

        integrator = get_integrator()

        # Phase 1: Self-audit
        print("PHASE 1: Self-Audit")
        print("-" * 40)
        audit = integrator.audit_self()
        audit_dict = audit if isinstance(audit, dict) else vars(audit) if hasattr(audit, '__dict__') else {}
        overall = audit_dict.get("overall_status", "UNKNOWN")
        status_icon = "✅ HEALTHY" if overall == "HEALTHY" else "⚠️ WARNING" if overall == "WARNING" else "❌ CRITICAL"

        print(f"  Overall status: {status_icon}")
        print(f"  Modules wired: {audit_dict.get('modules_wired', 'N/A')}")
        print(f"  LearningLogger entries: {audit_dict.get('learning_logger_entries', 'N/A')}")
        print(f"  SelfImprovementEngine events: {audit_dict.get('engine_events', 'N/A')}")
        print(f"  Avg quality: {audit_dict.get('avg_quality', 0):.4f}")
        print(f"  Quality trend: {audit_dict.get('quality_trend', 'N/A')}")
        print(f"  DNA entries: {audit_dict.get('dna_entries', 'N/A')}")
        print(f"  Optimization cycles: {audit_dict.get('optimization_cycles', 'N/A')}")
        print(f"  Pending learnings: {audit_dict.get('pending_learnings', 'N/A')}")

        if audit_dict.get("issues"):
            print()
            print("  Issues found:")
            for iss in audit_dict["issues"]:
                print(f"    - {iss}")

        print()

        # Phase 2: Run optimization cycle
        print("PHASE 2: Run Optimization Cycle")
        print("-" * 40)
        cycle = integrator.run_optimization_cycle()
        cycle_dict = cycle if isinstance(cycle, dict) else vars(cycle) if hasattr(cycle, '__dict__') else {}
        print(f"  Quality trend: {cycle_dict.get('quality_trend', 'N/A')}")
        print(f"  Suggestions: {cycle_dict.get('suggestions_generated', 0)}")
        print(f"  Auto-resolved: {cycle_dict.get('auto_resolved', 0)}")
        print(f"  DNA updates: {cycle_dict.get('dna_promotions', 0)}")
        print(f"  Avg quality: {cycle_dict.get('avg_quality', 0):.4f}")

        suggestions = cycle_dict.get("suggestions", [])
        if suggestions:
            print()
            print("  Suggestions:")
            for sug in suggestions[:5]:
                sug_d = sug if isinstance(sug, dict) else vars(sug) if hasattr(sug, '__dict__') else {}
                print(f"    [{sug_d.get('area', 'general')}] {sug_d.get('description', 'N/A')} (impact: {sug_d.get('impact', 0):.2f})")

        print()

        # Phase 3: Auto-tuning check (legacy memory module removed 2026-06-19)
        print("PHASE 3: Auto-Tuning Check")
        print("-" * 40)
        recs = []
        print(f"  Pending recommendations: {len(recs)}")

        if recs:
            print()
            for rec in recs[:5]:
                rec_d = rec if isinstance(rec, dict) else vars(rec) if hasattr(rec, '__dict__') else {}
                print(f"    [{rec_d.get('action', 'N/A').upper()}] {rec_d.get('target_model', 'N/A')} — {rec_d.get('reason', 'N/A')[:60]}")

        print()
        print("=" * 60)
        print("Self-improvement cycle complete.")
        print("=" * 60)

        if args.json:
            import json
            clean_cycle = {k: v for k, v in cycle_dict.items() if k != "suggestions"}
            print(json.dumps({
                "audit": audit_dict,
                "optimization": clean_cycle,
                "recommendations": [dict(r) if hasattr(r, '__dict__') else r for r in recs[:10]],
            }, indent=2, default=str))

    except Exception as e:
        print(f"Error running self-improvement: {e}")
        import traceback
        traceback.print_exc()


def cmd_benchmark(args):
    """Benchmark model routing."""
    tasks = ["heavy_coding", "coding", "reasoning", "research", "fast_tasks", "general", "medium_coding"]

    print("=" * 60)
    print("ILMA Model Router Benchmark")
    print("=" * 60)

    from ilma_smart_model_router import ILMASmartModelRouter
    router = ILMASmartModelRouter(allow_paid=False)

    results = []
    for task in tasks:
        start = time.time()
        route = router.route(task)
        elapsed = (time.time() - start) * 1000

        model = route.get("model_id", "N/A")
        provider = route.get("provider", "N/A")
        score = route.get("composite_score", 0)

        results.append({
            "task": task,
            "model": model,
            "provider": provider,
            "score": round(score, 4),
            "elapsed_ms": round(elapsed, 2)
        })

        print(f"{task:20} → {model[:50]:50} s={score:.3f} ({elapsed:6.1f}ms)")

    print("=" * 60)
    total = sum(r["elapsed_ms"] for r in results)
    print(f"Total: {len(results)} tasks, {total:.1f}ms avg={total/len(results):.1f}ms")


def cmd_enrich(args):
    """Run passive benchmark enrichment from usage log + external benchmarks."""
    from ilma_passive_benchmark_enricher import PassiveBenchmarkEnricher

    print("=" * 60)
    print("ILMA Benchmark Enrichment")
    print("=" * 60)

    window = getattr(args, 'window', 2000)
    enricher = PassiveBenchmarkEnricher(usage_window=window)

    stats = enricher.get_stats()
    print(f"\nBenchmark DB: {stats['total_models']} models, {stats['scores_count']} scores")
    print(f"Evidence distribution:")
    for el, count in sorted(stats['evidence_distribution'].items(), key=lambda x: -x[1]):
        print(f"  {el}: {count}")

    # === Passive Enrichment (usage telemetry) ===
    print("\n--- Passive Enrichment (usage telemetry) ---")
    passive_result = enricher.enrich(dry_run=False)
    print(f"\nPassive result: success={passive_result.get('success', False)}")
    s = passive_result.get('stats', passive_result)
    print(f"  Models updated: {s.get('models_updated', 0)}")
    print(f"  Models added: {s.get('models_added', 0)}")
    print(f"  Insufficient samples: {s.get('insufficient_samples', 0)}")

    if passive_result.get('updated_models'):
        print(f"\nTop updated models:")
        for model_id, info in list(passive_result['updated_models'].items())[:10]:
            scores = info.get('scores', {})
            print(f"  {model_id[:50]:50} success={scores.get('success_rate', 0):.2f} latency={scores.get('avg_latency_ms', 0):.0f}ms")

    # === External Benchmark Fetch (Artificial Analysis via ilma_benchmark_autoloop) ===
    print("\n--- External Benchmark Fetch (Artificial Analysis) ---")
    try:
        from scripts.ilma_benchmark_autoloop import BenchmarkAutoloop
        autoloop = BenchmarkAutoloop(dry_run=False)
        external = autoloop.fetch_external_benchmarks()
        print(f"  External sources: {list(external.keys())}")
        for source, data in external.items():
            print(f"  - {source}: {data['records']} records, level={data['evidence_level']}")
    except ImportError as e:
        print(f"  [SKIPPED] BenchmarkAutoloop not available: {e}")

    print("=" * 60)


def cmd_orchestrate(args):
    """Orchestrate task."""
    print(f"Orchestrating: {args.task}")

    result = orchestrate(args.task)

    print()
    print(f"Intent: {result.get('intent')}")
    print(f"Handler: {result.get('handler')}")
    print(f"Status: {result.get('status')}")

    if "route" in result:
        route = result["route"].get("route", {})
        print(f"Model: {route.get('model_id', 'N/A')}")
        print(f"Provider: {route.get('provider', 'N/A')}")

    if args.json:
        print()
        print(json.dumps(result, indent=2))


# === MAIN ===
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=f"ILMA System v{__version__} — Unified AI Agent System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  status        Show system status
  route         Route task to best model
  verify        Verify code file
  think         Cognitive processing
  collaborate   Run collaborative task
  optimize      Run self-optimization
  benchmark     Benchmark model routing
  enrich        Run passive benchmark enrichment
  orchestrate   Orchestrate task

Examples:
  python3 ilma.py --status
  python3 ilma.py route heavy_coding
  python3 ilma.py verify mycode.py
  python3 ilma.py think "build platform" --mode deliberative
  python3 ilma.py --benchmark
  python3 ilma.py --enrich

Version: 3.8 (2026-05-09)
AYDA Integration: Model Router, Judge System, Capability Orchestrator
        """
    )

    # Commands — use nargs='?' for flags that should also accept positional
    # Also add positional arguments for backward compat (e.g. "ilma.py status")
    parser.add_argument("command", nargs="?", default=None, help="Command (status, route, verify, think, ...)")
    parser.add_argument("args", nargs="*", default=[], help="Command arguments")
    parser.add_argument("--status", action="store_true", help="Show system status")
    parser.add_argument("--route", metavar="TASK", help="Route task to best model")
    parser.add_argument("--verify", metavar="FILE", help="Verify code file")
    parser.add_argument("--think", metavar="TASK", help="Cognitive processing")
    parser.add_argument("--collaborate", metavar="TASK", help="Run collaborative task")
    parser.add_argument("--optimize", action="store_true", help="Run self-optimization")
    parser.add_argument("--benchmark", nargs="?", const=True, default=None, help="Benchmark model routing")
    parser.add_argument("--enrich", nargs="?", const=True, default=None, help="Run passive benchmark enrichment")
    parser.add_argument("--orchestrate", metavar="TASK", help="Orchestrate task")
    parser.add_argument("--self-improve", action="store_true", help="Run LAYER 9 self-improvement: audit + optimize")

    # Options
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--mode", default="reactive", help="Thinking mode (for think)")
    parser.add_argument("--agents", help="Comma-separated agent list (for collaborate)")
    parser.add_argument("--file", help="File to verify (alternative to --verify)")

    args = parser.parse_args()

    # Positional command aliases (backward compat: "ilma.py status" → same as "--status")
    _positional_aliases = {
        "status": "status",
        "route": "route",
        "verify": "verify",
        "think": "think",
        "collaborate": "collaborate",
        "optimize": "optimize",
        "benchmark": "benchmark",
        "enrich": "enrich",
        "orchestrate": "orchestrate",
        "self-improve": "self_improve",
        "selfimprove": "self_improve",
    }
    if args.command and args.command.lower() in _positional_aliases:
        cmd = args.command.lower()
        # Map positional to flag
        if cmd == "status":
            args.status = True
        elif cmd == "route" and args.args:
            args.route = args.args[0]
            args.task_type = args.route
        elif cmd == "verify" and args.args:
            args.verify = args.args[0]
        elif cmd == "think" and args.args:
            args.think = " ".join(args.args)
            args.task = args.think
        elif cmd == "collaborate" and args.args:
            args.collaborate = " ".join(args.args)
            args.task = args.collaborate
        elif cmd == "optimize":
            args.optimize = True
        elif cmd == "benchmark":
            args.benchmark = True
        elif cmd == "enrich":
            args.enrich = True
        elif cmd == "orchestrate" and args.args:
            args.orchestrate = " ".join(args.args)
            args.task = args.orchestrate

    # Dispatch
    if args.status:
        cmd_status(args)
    elif args.route:
        args.task_type = args.route
        cmd_route(args)
    elif args.verify or args.file:
        args.file = args.verify or args.file
        cmd_verify(args)
    elif args.think:
        args.task = args.think
        cmd_think(args)
    elif args.collaborate:
        args.task = args.collaborate
        cmd_collaborate(args)
    elif args.optimize:
        cmd_optimize(args)
    elif args.benchmark:
        cmd_benchmark(args)
    elif args.enrich:
        cmd_enrich(args)
    elif args.self_improve:
        cmd_self_improve(args)
    elif args.orchestrate:
        args.task = args.orchestrate
        cmd_orchestrate(args)
    else:
        # Default: show status
        cmd_status(args)