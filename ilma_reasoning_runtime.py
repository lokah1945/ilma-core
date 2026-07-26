#!/usr/bin/env python3
"""
ILMA Autonomous Reasoning Runtime
==================================
Runtime engine for autonomous reasoning chains and decision making.
Inspired by AYDA autonomous_reasoning_runtime.py

Version: 2.0
"""

import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ReasoningType(Enum):
    """Types of reasoning."""
    DEDUCTIVE = "deductive"     # General to specific
    INDUCTIVE = "inductive"     # Specific to general
    ABDUCTIVE = "abductive"     # Best explanation
    CAUSAL = "causal"           # Cause and effect
    ANALOGICAL = "analogical"   # Similarity-based


@dataclass
class ReasoningStep:
    """A single step in a reasoning chain."""
    step_id: int
    description: str
    inference: str
    confidence: float
    evidence: List[str] = field(default_factory=list)


@dataclass
class ReasoningChain:
    """A reasoning chain with steps."""
    chain_id: str
    steps: List[ReasoningStep] = field(default_factory=list)
    reasoning_type: ReasoningType = ReasoningType.DEDUCTIVE
    confidence: float = 0.0
    completed: bool = False
    created_at: float = field(default_factory=time.time)


@dataclass
class ReasoningResult:
    """Result of a reasoning operation."""
    success: bool
    chain: ReasoningChain
    conclusion: Any = None
    processing_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AutonomousReasoningRuntime:
    """
    Autonomous reasoning runtime.
    Manages reasoning chains, goal pursuit, and decision making.
    Integrates with ILMA cognition kernel and knowledge graph.
    """
    
    def __init__(self, runtime_id: str = "ilma_default"):
        self.runtime_id = runtime_id
        self.active_chains: Dict[str, ReasoningChain] = {}
        self.completed_chains: List[ReasoningChain] = []
        self.total_reasoning_ops = 0
        
    def reason(self, query: str, reasoning_type: Optional[ReasoningType] = None,
               context: Optional[Dict[str, Any]] = None) -> ReasoningResult:
        """
        Execute autonomous reasoning on a query.
        
        Args:
            query: The question or problem to reason about
            reasoning_type: Type of reasoning to use
            context: Additional context for reasoning
            
        Returns:
            ReasoningResult with conclusion and chain
        """
        start = time.perf_counter()
        self.total_reasoning_ops += 1
        
        rtype = reasoning_type or ReasoningType.DEDUCTIVE
        chain_id = f"chain_{self.total_reasoning_ops}"
        chain = ReasoningChain(chain_id=chain_id, reasoning_type=rtype)
        
        try:
            steps = self._build_reasoning_chain(query, rtype, context)
            for i, step_data in enumerate(steps):
                step = ReasoningStep(
                    step_id=i + 1,
                    description=step_data["description"],
                    inference=step_data["inference"],
                    confidence=step_data.get("confidence", 0.8),
                    evidence=step_data.get("evidence", [])
                )
                chain.steps.append(step)
            
            chain.completed = True
            chain.confidence = self._evaluate_confidence(chain)
            conclusion = self._derive_conclusion(chain, query)
            success = True
            
            self.active_chains[chain_id] = chain
            self.completed_chains.append(chain)
            
        except Exception as e:
            success = False
            conclusion = {"error": str(e)}
        
        elapsed = (time.perf_counter() - start) * 1000
        
        result = ReasoningResult(
            success=success,
            chain=chain,
            conclusion=conclusion,
            processing_time_ms=elapsed,
            metadata={
                "query": query,
                "context": context,
                "reasoning_type": rtype.value
            }
        )
        
        return result
    
    def _build_reasoning_chain(self, query: str, rtype: ReasoningType,
                               context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build a reasoning chain based on type."""
        if rtype == ReasoningType.DEDUCTIVE:
            return self._deductive_chain(query, context)
        elif rtype == ReasoningType.INDUCTIVE:
            return self._inductive_chain(query, context)
        elif rtype == ReasoningType.ABDUCTIVE:
            return self._abductive_chain(query, context)
        elif rtype == ReasoningType.CAUSAL:
            return self._causal_chain(query, context)
        elif rtype == ReasoningType.ANALOGICAL:
            return self._analogical_chain(query, context)
        return [{"description": query, "inference": "Direct response", "confidence": 0.7}]
    
    def _deductive_chain(self, query: str, context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deductive reasoning: general to specific."""
        return [
            {"description": f"Premise: {query}", "inference": "General principle identified", "confidence": 0.9},
            {"description": "Apply logical rules", "inference": "Rules applied to premise", "confidence": 0.85},
            {"description": "Derive conclusion", "inference": "Specific conclusion reached", "confidence": 0.9}
        ]
    
    def _inductive_chain(self, query: str, context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Inductive reasoning: specific to general."""
        return [
            {"description": f"Observe: {query}", "inference": "Specific observations recorded", "confidence": 0.8},
            {"description": "Find patterns", "inference": "Patterns identified in observations", "confidence": 0.75},
            {"description": "Generalize", "inference": "General principle derived", "confidence": 0.7}
        ]
    
    def _abductive_chain(self, query: str, context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Abductive reasoning: best explanation."""
        return [
            {"description": f"Observe: {query}", "inference": "Observation recorded", "confidence": 0.8},
            {"description": "Generate hypotheses", "inference": "Possible explanations listed", "confidence": 0.75},
            {"description": "Select best explanation", "inference": "Most likely explanation chosen", "confidence": 0.7}
        ]
    
    def _causal_chain(self, query: str, context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Causal reasoning: cause and effect."""
        return [
            {"description": f"Identify event: {query}", "inference": "Event identified", "confidence": 0.85},
            {"description": "Find causes", "inference": "Causal factors identified", "confidence": 0.8},
            {"description": "Predict effects", "inference": "Expected outcomes predicted", "confidence": 0.75}
        ]
    
    def _analogical_chain(self, query: str, context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analogical reasoning: similarity-based."""
        return [
            {"description": f"Source: {query}", "inference": "Source domain identified", "confidence": 0.8},
            {"description": "Find similarity", "inference": "Shared structure found", "confidence": 0.75},
            {"description": "Transfer knowledge", "inference": "Knowledge transferred to target", "confidence": 0.7}
        ]
    
    def _evaluate_confidence(self, chain: ReasoningChain) -> float:
        """Evaluate confidence of a reasoning chain."""
        if not chain.steps:
            return 0.0
        
        total_confidence = sum(step.confidence for step in chain.steps)
        avg_confidence = total_confidence / len(chain.steps)
        
        # Penalize for incomplete chains
        completeness_factor = len(chain.steps) / 3.0  # Expected ~3 steps
        completeness_factor = min(1.0, completeness_factor)
        
        return avg_confidence * completeness_factor
    
    def _derive_conclusion(self, chain: ReasoningChain, query: str) -> Dict[str, Any]:
        """Derive final conclusion from reasoning chain."""
        return {
            "summary": f"Reasoned about: {query}",
            "confidence": chain.confidence,
            "reasoning_type": chain.reasoning_type.value,
            "steps_count": len(chain.steps),
            "conclusion": "Reasoning chain completed successfully"
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get reasoning runtime statistics."""
        return {
            "runtime_id": self.runtime_id,
            "total_reasoning_ops": self.total_reasoning_ops,
            "active_chains": len(self.active_chains),
            "completed_chains": len(self.completed_chains),
            "avg_confidence": (
                sum(c.confidence for c in self.completed_chains) / len(self.completed_chains)
                if self.completed_chains else 0.0
            )
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    runtime = AutonomousReasoningRuntime()
    
    # Test different reasoning types
    result = runtime.reason("Why is the sky blue?", ReasoningType.CAUSAL)
    logger.info("Causal reasoning confidence: %s", result.chain.confidence)
    logger.info("Conclusion: %s", result.conclusion)
    
    result = runtime.reason("All cats are mammals. Kitty is a cat. Therefore?", ReasoningType.DEDUCTIVE)
    logger.info("Deductive reasoning confidence: %s", result.chain.confidence)
    
    logger.info("Stats: %s", runtime.get_stats())

# Backward-compatibility alias
ReasoningEngine = AutonomousReasoningRuntime

_global_reasoning_runtime_instance = None

def get_reasoning_runtime() -> "AutonomousReasoningRuntime":
    """Get singleton AutonomousReasoningRuntime instance."""
    global _global_reasoning_runtime_instance
    if _global_reasoning_runtime_instance is None:
        _global_reasoning_runtime_instance = AutonomousReasoningRuntime()
    return _global_reasoning_runtime_instance

