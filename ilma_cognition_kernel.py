#!/usr/bin/env python3
"""
ILMA Cognition Kernel
=====================
Core cognitive execution engine.
Inspired by AYDA cognition_kernel.py

Version: 2.0
"""

import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum


class CognitiveMode(Enum):
    """Cognitive processing modes."""
    REACTIVE = "reactive"        # Fast direct response
    DELIBERATIVE = "deliberative"  # Thoughtful analysis
    AUTONOMOUS = "autonomous"   # Self-directed
    META = "meta"               # Self-reflection


@dataclass
class CognitiveResult:
    """Result of a cognitive operation."""
    success: bool
    output: Any = None
    confidence: float = 0.0
    processing_time_ms: float = 0.0
    mode: CognitiveMode = CognitiveMode.REACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CognitiveContext:
    """Context for cognitive operations."""
    task: str
    mode: CognitiveMode = CognitiveMode.REACTIVE
    priority: int = 5
    deadline: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class CognitionKernel:
    """
    Core cognitive execution kernel.
    Handles thought execution, reasoning chains, and cognitive state transitions.
    Integrates with ILMA capability registry and provider kernel.
    """
    
    def __init__(self, kernel_id: str = "ilma_default"):
        self.kernel_id = kernel_id
        self.mode = CognitiveMode.REACTIVE
        self.execution_count = 0
        self.total_processing_time = 0.0
        self.last_result: Optional[CognitiveResult] = None
        self.mode_history: List[CognitiveMode] = []
        
    def execute(self, task: str, context: Optional[Dict[str, Any]] = None,
                mode: Optional[CognitiveMode] = None) -> CognitiveResult:
        """
        Execute a cognitive task.
        
        Args:
            task: The task description or query
            context: Additional context for execution
            mode: Override the cognitive mode
            
        Returns:
            CognitiveResult with execution outcome
        """
        start = time.perf_counter()
        self.execution_count += 1
        
        effective_mode = mode or self.mode
        self.mode_history.append(effective_mode)
        
        try:
            output = self._process_task(task, context, effective_mode)
            success = True
            confidence = self._calculate_confidence(output, effective_mode)
        except Exception as e:
            output = {"error": str(e)}
            success = False
            confidence = 0.0
        
        elapsed = (time.perf_counter() - start) * 1000
        self.total_processing_time += elapsed
        
        result = CognitiveResult(
            success=success,
            output=output,
            confidence=confidence,
            processing_time_ms=elapsed,
            mode=effective_mode,
            metadata={
                "task": task,
                "context_keys": list(context.keys()) if context else [],
                "execution_number": self.execution_count
            }
        )
        self.last_result = result
        return result
    
    def _process_task(self, task: str, context: Optional[Dict[str, Any]], 
                      mode: CognitiveMode) -> Dict[str, Any]:
        """Process task based on cognitive mode."""
        if mode == CognitiveMode.REACTIVE:
            return self._reactive_processing(task, context)
        elif mode == CognitiveMode.DELIBERATIVE:
            return self._deliberative_processing(task, context)
        elif mode == CognitiveMode.AUTONOMOUS:
            return self._autonomous_processing(task, context)
        elif mode == CognitiveMode.META:
            return self._meta_processing(task, context)
        return {"response": f"Processed: {task}"}
    
    def _reactive_processing(self, task: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Fast reactive processing - direct response."""
        return {
            "response": f"Reactive response to: {task}",
            "mode": "reactive",
            "processing": "direct"
        }
    
    def _deliberative_processing(self, task: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Deliberative processing - analytical thinking."""
        steps = [
            {"step": 1, "action": "analyze", "description": f"Analyzing: {task}"},
            {"step": 2, "action": "evaluate", "description": "Evaluating options"},
            {"step": 3, "action": "decide", "description": "Making decision"}
        ]
        return {
            "response": f"Deliberative analysis of: {task}",
            "mode": "deliberative",
            "processing": "analytical",
            "steps": steps
        }
    
    def _autonomous_processing(self, task: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Autonomous processing - self-directed goal pursuit."""
        return {
            "response": f"Autonomous processing of: {task}",
            "mode": "autonomous",
            "processing": "self-directed",
            "goals": ["understand", "plan", "execute", "learn"]
        }
    
    def _meta_processing(self, task: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Meta processing - self-reflection and optimization."""
        return {
            "response": f"Meta-analysis of: {task}",
            "mode": "meta",
            "processing": "self-reflection",
            "insights": ["performance_review", "strategy_optimization"]
        }
    
    def _calculate_confidence(self, output: Any, mode: CognitiveMode) -> float:
        """Calculate confidence based on output and mode."""
        base_confidence = 0.7
        
        if isinstance(output, dict) and "error" in output:
            return 0.0
        
        # Higher confidence for deliberative modes
        if mode == CognitiveMode.DELIBERATIVE:
            base_confidence += 0.15
        elif mode == CognitiveMode.AUTONOMOUS:
            base_confidence += 0.1
        elif mode == CognitiveMode.META:
            base_confidence += 0.05
            
        return min(1.0, base_confidence)
    
    def set_mode(self, mode: CognitiveMode):
        """Set the default cognitive mode."""
        self.mode = mode
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cognition kernel statistics."""
        return {
            "kernel_id": self.kernel_id,
            "current_mode": self.mode.value,
            "execution_count": self.execution_count,
            "total_processing_time_ms": self.total_processing_time,
            "avg_processing_time_ms": (
                self.total_processing_time / self.execution_count 
                if self.execution_count > 0 else 0
            ),
            "mode_history": [m.value for m in self.mode_history[-10:]]
        }


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    kernel = CognitionKernel()
    
    # Test different modes
    result = kernel.execute("What is 2+2?", mode=CognitiveMode.REACTIVE)
    logger.info(f"Reactive: {result.output}")
    logger.info(f"Confidence: {result.confidence}")
    
    result = kernel.execute("Analyze this problem deeply", mode=CognitiveMode.DELIBERATIVE)
    logger.info(f"Deliberative: {result.output}")
    
    logger.info(f"Stats: {kernel.get_stats()}")

_global_cognition_kernel_instance = None

def get_cognition_kernel() -> "CognitionKernel":
    """Get singleton CognitionKernel instance."""
    global _global_cognition_kernel_instance
    if _global_cognition_kernel_instance is None:
        _global_cognition_kernel_instance = CognitionKernel()
    return _global_cognition_kernel_instance
