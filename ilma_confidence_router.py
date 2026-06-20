#!/usr/bin/env python3
"""
ILMA Confidence-Aware Routing
==============================
Uses task-model confidence matching to pick optimal model.
Inspired by AYDA confidence_aware_routing.py

Version: 2.0
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


# Confidence levels
CONFIDENCE_LEVELS = {
    "critical": {"min": 90, "weight_reasoning": 2.0, "weight_accuracy": 2.0},
    "high": {"min": 75, "weight_reasoning": 1.5, "weight_accuracy": 1.5},
    "medium": {"min": 50, "weight_reasoning": 1.0, "weight_accuracy": 1.0},
    "low": {"min": 0, "weight_reasoning": 0.5, "weight_accuracy": 0.5},
}


def estimate_task_confidence(task_text: str) -> Dict[str, Any]:
    """
    Estimate task confidence requirements from text cues.
    Returns dict with confidence level and requirements.
    """
    text_lower = task_text.lower()
    
    # Critical indicators
    critical = any(k in text_lower for k in [
        "critical", "must", "production", "safety", "medical", "financial",
        "legal", "error", "bug", "crash", "emergency", "urgent", "important"
    ])
    
    # High accuracy indicators
    high_acc = any(k in text_lower for k in [
        "accurate", "exact", "precise", "correct", "important", "careful",
        "analysis", "review", "audit", "evaluate", "verify"
    ])
    
    # Reasoning indicators
    reasoning = any(k in text_lower for k in [
        "reason", "logic", "proof", "explain why", "why is", "think",
        "analyze", "derive", "prove", "because", "therefore"
    ])
    
    # Complexity
    complexity_score = min(100, len(task_text) // 10)
    
    if critical:
        level = "critical"
    elif high_acc and reasoning:
        level = "high"
    elif high_acc or reasoning:
        level = "medium"
    else:
        level = "low"
    
    return {
        "level": level,
        "requires_reasoning": reasoning,
        "requires_accuracy": high_acc,
        "is_critical": critical,
        "complexity_score": complexity_score,
        "thresholds": CONFIDENCE_LEVELS[level],
    }


def get_model_confidence(
    provider_id: str,
    model_id: str,
    requirements: Dict[str, Any],
    provider_caps: Dict[str, Any] = None
) -> float:
    """
    Calculate how well a model fits the task confidence requirements.

    Args:
        provider_id: The identifier for the provider (e.g., 'minimax', 'nvidia').
        model_id: The model identifier (e.g., 'MiniMax-M2-7', 'llama-3.1').
        requirements: Dict containing task requirements from estimate_task_confidence.
            May include 'requires_reasoning', 'is_critical', 'requires_accuracy'.
        provider_caps: Optional dict of provider capabilities. If not provided,
            defaults are used assuming a standard reasoning-capable provider.

    Returns:
        float: A confidence score from 0-100 indicating how well the model
            matches the task requirements. Higher scores indicate better fit.

    Scoring Logic:
        - Base score: 50
        - Reasoning support adds +25, thinking tokens add +10
        - No reasoning support subtracts 30
        - Critical tasks favor larger models (+30 for 405b/opus/ultra, +20 for 70b/sonnet)
        - Smaller models (-10 for 8b/mini/flash) get penalized for critical tasks
        - Free tier models get a +5 boost
    """
    # Default capabilities if not provided
    if provider_caps is None:
        provider_caps = {
            "reasoning": {"chain_of_thought": {"supported": True, "thinking_token_support": True}},
            "capabilities": {"coding": True, "creative": True, "research": True}
        }
    
    score = 50  # baseline
    
    # Reasoning fit
    if requirements.get("requires_reasoning"):
        reason_caps = provider_caps.get("reasoning", {}).get("chain_of_thought", {})
        if reason_caps.get("supported"):
            score += 25
            if reason_caps.get("thinking_token_support"):
                score += 10
        else:
            score -= 30
    
    # Accuracy for critical tasks
    if requirements.get("is_critical"):
        # Larger models score higher for critical tasks
        model_lower = model_id.lower()
        if "405b" in model_lower or "opus" in model_lower or "ultra" in model_lower:
            score += 30
        elif "70b" in model_lower or "sonnet" in model_lower:
            score += 20
        elif "8b" in model_lower or "mini" in model_lower or "flash" in model_lower:
            score -= 10
    
    # Free models get a slight boost
    if "free" in model_id.lower() or "openrouter" in provider_id:
        score += 5
    
    return max(0, min(100, score))


def route_by_confidence(
    task_text: str,
    candidates: Optional[List[Tuple[str, str]]] = None,
    provider_caps: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Route a task to the best model based on confidence requirements.

    Analyzes the task text to determine its confidence requirements (critical,
    high, medium, or low), then scores all candidate models to find the
    optimal match.

    Args:
        task_text: The input task description to analyze and route.
        candidates: Optional list of (provider_id, model_id) tuples.
            Defaults to [('minimax', 'MiniMax-M2-7'), ('nvidia', 'meta/llama-3.1-nemotron-ultra-253b-v1'), ('openrouter', 'free')].
        provider_caps: Optional dict of provider capabilities for scoring.
            If not provided, defaults are used.

    Returns:
        Dict containing:
            - provider (str): The selected provider ID
            - model (str): The selected model ID
            - confidence_score (float): The confidence score (0-100) of the best match
            - task_requirements (Dict): The estimated requirements for the task
            - all_candidates (List[Dict]): All candidates with their scores, sorted by confidence
            - routing_reasoning (str): Human-readable explanation of the routing choice

    Example:
        >>> result = route_by_confidence("Fix the critical production bug")
        >>> print(result['provider'], result['model'])
        'nvidia' 'meta/llama-3.1-nemotron-ultra-253b-v1'
    """
    # Default candidates
    if candidates is None:
        candidates = [
            ("minimax", "MiniMax-M2-7"),
            ("nvidia", "meta/llama-3.1-nemotron-ultra-253b-v1"),
            ("openrouter", "free")
        ]
    
    requirements = estimate_task_confidence(task_text)
    scored = []
    
    for prov_id, model_id in candidates:
        conf = get_model_confidence(prov_id, model_id, requirements, provider_caps)
        scored.append((prov_id, model_id, conf))
    
    scored.sort(key=lambda x: x[2], reverse=True)
    best = scored[0]
    
    return {
        "provider": best[0],
        "model": best[1],
        "confidence_score": best[2],
        "task_requirements": requirements,
        "all_candidates": [
            {"provider": p, "model": m, "confidence": c} 
            for p, m, c in scored
        ],
        "routing_reasoning": _explain_routing(requirements, best[0], best[1])
    }


def _explain_routing(requirements: Dict, provider: str, model: str) -> str:
    """Explain why this routing was chosen."""
    level = requirements.get("level", "low")
    
    if level == "critical":
        return f"Critical task requires high-confidence model: {model} from {provider}"
    elif requirements.get("requires_reasoning"):
        return f"Reasoning task routed to {model} with chain-of-thought support"
    elif "free" in model.lower():
        return "Free tier model sufficient for this task"
    else:
        return f"Optimal model selected based on task requirements"


class ConfidenceAwareRouter:
    """
    Router that uses confidence scoring to select optimal providers.
    Integrates with ILMA provider kernel and capability registry.
    """
    
    def __init__(self, router_id: str = "ilma_default"):
        self.router_id = router_id
        self.routing_history: List[Dict] = []
        self.stats = {
            "total_routes": 0,
            "critical_routes": 0,
            "avg_confidence": 0.0
        }
    
    def route(self, task: str, candidates: List[Tuple[str, str]] = None) -> Dict[str, Any]:
        """Route a task with confidence scoring."""
        result = route_by_confidence(task, candidates)
        
        self.routing_history.append({
            "task": task[:100],
            "provider": result["provider"],
            "model": result["model"],
            "confidence": result["confidence_score"],
            "level": result["task_requirements"]["level"]
        })
        
        self.stats["total_routes"] += 1
        if result["task_requirements"]["level"] == "critical":
            self.stats["critical_routes"] += 1
        
        # Update average
        total = sum(r["confidence"] for r in self.routing_history)
        self.stats["avg_confidence"] = total / len(self.routing_history)
        
        return result
    
    def get_stats(self) -> Dict:
        """Get routing statistics."""
        return {
            **self.stats,
            "routing_history_size": len(self.routing_history),
            "recent_routes": self.routing_history[-5:]
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    router = ConfidenceAwareRouter()
    
    # Test different task types
    task1 = "Critical: Fix production bug in payment system"
    result1 = router.route(task1)
    logger.info(f"Task: {task1}")
    logger.info(f"Route: {result1['provider']}/{result1['model']} (confidence: {result1['confidence_score']})")
    logger.info(f"Reasoning: {result1['routing_reasoning']}")
    
    task2 = "Write a quick response"
    result2 = router.route(task2)
    logger.info(f"Task: {task2}")
    logger.info(f"Route: {result2['provider']}/{result2['model']} (confidence: {result2['confidence_score']})")
    
    logger.info(f"Stats: {router.get_stats()}")

_global_confidence_router_instance = None

def get_confidence_router() -> "ConfidenceAwareRouter":
    """Get singleton ConfidenceAwareRouter instance."""
    global _global_confidence_router_instance
    if _global_confidence_router_instance is None:
        _global_confidence_router_instance = ConfidenceAwareRouter()
    return _global_confidence_router_instance
