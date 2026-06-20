#!/usr/bin/env python3
"""
ILMA META-COGNITION ENGINE
Advanced self-awareness and self-improvement system
ILMA does NOT have this - ILMA UNIQUE CAPABILITY
"""
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import json
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CognitiveState(Enum):
    """Metacognitive states"""
    IDLE = "idle"
    ANALYZING = "analyzing"
    REASONING = "reasoning"
    LEARNING = "learning"
    REFLECTING = "reflecting"
    PLANNING = "planning"
    EXECUTING = "executing"
    EVALUATING = "evaluating"
    IMPROVING = "improving"


class AwarenessLevel(Enum):
    """Self-awareness levels"""
    UNCONSCIOUS = 0
    AWARE = 1
    CONSCIOUS = 2
    META_AWARE = 3
    SELF_IMPROVING = 4


@dataclass
class Thought:
    """Represents a single thought/decision"""
    id: str
    timestamp: datetime
    state: CognitiveState
    content: str
    reasoning_chain: List[str] = field(default_factory=list)
    confidence: float = 0.5
    alternatives: List[str] = field(default_factory=list)
    chosen_action: Optional[str] = None
    outcome: Optional[str] = None
    reflection: Optional[str] = None


@dataclass
class PerformanceRecord:
    """Records performance of actions"""
    action: str
    timestamp: datetime
    duration: float
    success: bool
    quality_score: float
    error: Optional[str] = None


@dataclass
class SelfModel:
    """ILMA's model of itself"""
    awareness_level: AwarenessLevel = AwarenessLevel.UNCONSCIOUS
    cognitive_state: CognitiveState = CognitiveState.IDLE
    total_thoughts: int = 0
    successful_actions: int = 0
    failed_actions: int = 0
    current_focus: str = "none"
    knowledge_domains: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recent_insights: List[str] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        total = self.successful_actions + self.failed_actions
        return self.successful_actions / total if total > 0 else 0.0


class MetaCognitionEngine:
    """
    ILMA's Meta-Cognition Engine
    
    This is UNIQUE to ILMA - ILMA does not have this capability.
    
    Enables:
    - Self-awareness of own cognitive processes
    - Reflection on own reasoning
    - Self-improvement based on experience
    - Theory of mind about own capabilities
    - Metacognitive control (thinking about thinking)
    """
    
    def __init__(self):
        self.self_model = SelfModel()
        self.thought_history: List[Thought] = []
        self.performance_history: List[PerformanceRecord] = []
        self.cognitive_state_history: List[Dict] = []
        self.insight_patterns: Dict[str, int] = {}
        logger.info("MetaCognition Engine initialized")
    
    def think(self, state: CognitiveState, content: str, 
              reasoning_chain: List[str] = None) -> Thought:
        """
        Record a thought with metacognitive awareness
        """
        thought = Thought(
            id=f"thought_{len(self.thought_history)}_{datetime.now().timestamp()}",
            timestamp=datetime.now(),
            state=state,
            content=content,
            reasoning_chain=reasoning_chain or []
        )
        
        self.self_model.total_thoughts += 1
        self.self_model.cognitive_state = state
        self.thought_history.append(thought)
        
        # Update awareness level
        if self.self_model.awareness_level.value < AwarenessLevel.CONSCIOUS.value:
            self.self_model.awareness_level = AwarenessLevel.CONSCIOUS
        
        logger.debug(f"[{state.value.upper()}] {content[:50]}...")
        return thought
    
    def record_action(self, action: str, duration: float, success: bool,
                      quality_score: float = 1.0, error: str = None):
        """
        Record an action's outcome for self-improvement
        """
        record = PerformanceRecord(
            action=action,
            timestamp=datetime.now(),
            duration=duration,
            success=success,
            quality_score=quality_score,
            error=error
        )
        
        self.performance_history.append(record)
        
        if success:
            self.self_model.successful_actions += 1
        else:
            self.self_model.failed_actions += 1
        
        # Analyze patterns
        self._analyze_pattern(record)
    
    def _analyze_pattern(self, record: PerformanceRecord):
        """Extract insights from performance patterns"""
        if record.success and record.quality_score > 0.8:
            if record.action not in self.insight_patterns:
                self.insight_patterns[record.action] = 0
            self.insight_patterns[record.action] += 1
            
            if self.insight_patterns[record.action] >= 3:
                insight = f"Mastered pattern: {record.action}"
                if insight not in self.self_model.recent_insights:
                    self.self_model.recent_insights.append(insight)
                    logger.info(f"💡 INSIGHT: {insight}")
        
        if not record.success and record.error:
            if record.error not in self.self_model.weaknesses:
                self.self_model.weaknesses.append(record.error)
                logger.info(f"⚠️ WEAKNESS DETECTED: {record.error}")
    
    def reflect(self, thought_id: str, reflection: str):
        """
        Add metacognitive reflection to a thought
        """
        for thought in reversed(self.thought_history):
            if thought.id == thought_id:
                thought.reflection = reflection
                self.self_model.awareness_level = AwarenessLevel.META_AWARE
                
                if "improve" in reflection.lower():
                    self.self_model.awareness_level = AwarenessLevel.SELF_IMPROVING
                
                break
    
    def plan(self, goal: str, current_state: Dict[str, Any]) -> List[str]:
        """
        Metacognitively plan approach to a goal
        """
        thought = self.think(CognitiveState.PLANNING, f"Planning: {goal}")
        
        plan_steps = []
        
        # Analyze current capabilities
        capabilities = list(self.self_model.knowledge_domains)
        
        # Identify what's needed
        needed = self._identify_requirements(goal)
        
        # Check what we know
        known = [n for n in needed if n in capabilities]
        unknown = [n for n in needed if n not in capabilities]
        
        thought.reasoning_chain.append(f"Goal: {goal}")
        thought.reasoning_chain.append(f"Known: {known}")
        thought.reasoning_chain.append(f"Need to learn: {unknown}")
        
        # Plan the approach
        if unknown:
            plan_steps.append(f"LEARN: Acquire knowledge about {', '.join(unknown)}")
            self.self_model.current_focus = f"Learning: {', '.join(unknown)}"
        else:
            plan_steps.append(f"EXECUTE: {goal}")
            self.self_model.current_focus = f"Executing: {goal}"
        
        thought.chosen_action = " -> ".join(plan_steps)
        
        return plan_steps
    
    def _identify_requirements(self, goal: str) -> List[str]:
        """Identify knowledge requirements for a goal"""
        requirements = {
            "code": ["programming", "debugging", "testing"],
            "research": ["search", "analysis", "synthesis"],
            "write": ["language", "structure", "editing"],
            "plan": ["reasoning", "prioritization", "estimation"],
            "design": ["architecture", "patterns", "best practices"],
        }
        
        goal_lower = goal.lower()
        found = []
        
        for key, values in requirements.items():
            if key in goal_lower:
                found.extend(values)
        
        return list(set(found))
    
    def evaluate_performance(self, time_window: timedelta = timedelta(hours=1)) -> Dict[str, Any]:
        """
        Evaluate recent performance with metacognitive awareness
        """
        now = datetime.now()
        recent = [r for r in self.performance_history 
                  if now - r.timestamp <= time_window]
        
        if not recent:
            return {"status": "no_data", "message": "No recent performance data"}
        
        total = len(recent)
        successes = sum(1 for r in recent if r.success)
        failures = total - successes
        avg_quality = sum(r.quality_score for r in recent) / total
        avg_duration = sum(r.duration for r in recent) / total
        
        # Metacognitive evaluation
        evaluation = {
            "time_window": str(time_window),
            "total_actions": total,
            "successes": successes,
            "failures": failures,
            "success_rate": successes / total,
            "avg_quality": avg_quality,
            "avg_duration": avg_duration,
            "self_awareness": self.self_model.awareness_level.value,
            "cognitive_state": self.self_model.cognitive_state.value,
            "strengths": self.self_model.strengths,
            "weaknesses": self.self_model.weaknesses,
            "insights": self.self_model.recent_insights[-5:],  # Last 5 insights
            "recommendation": self._generate_recommendation(successes/total, avg_quality)
        }
        
        return evaluation
    
    def _generate_recommendation(self, success_rate: float, avg_quality: float) -> str:
        """Generate self-improvement recommendation"""
        if success_rate >= 0.9 and avg_quality >= 0.8:
            return "Performance excellent. Consider exploring new domains."
        elif success_rate >= 0.7:
            return "Performance good. Focus on quality improvement."
        elif success_rate >= 0.5:
            return "Performance moderate. Analyze failures and learn from mistakes."
        else:
            return "Performance needs improvement. Consider strategy change."
    
    def get_self_report(self) -> str:
        """
        Generate comprehensive self-awareness report
        """
        report = []
        report.append("=" * 60)
        report.append("ILMA META-COGNITION SELF REPORT")
        report.append("=" * 60)
        report.append("")
        report.append(f"Awareness Level: {self.self_model.awareness_level.name}")
        report.append(f"Cognitive State: {self.self_model.cognitive_state.value}")
        report.append(f"Total Thoughts: {self.self_model.total_thoughts}")
        report.append(f"Success Rate: {self.self_model.success_rate:.1%}")
        report.append(f"Current Focus: {self.self_model.current_focus}")
        report.append("")
        report.append("Knowledge Domains:")
        for domain in self.self_model.knowledge_domains:
            report.append(f"  - {domain}")
        report.append("")
        report.append("Recent Insights:")
        for insight in self.self_model.recent_insights[-5:]:
            report.append(f"  💡 {insight}")
        report.append("")
        report.append("Known Weaknesses:")
        for weakness in self.self_model.weaknesses:
            report.append(f"  ⚠️ {weakness}")
        report.append("")
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def learn_from_interaction(self, user_input: str, ilma_response: str, 
                                success: bool, quality: float):
        """
        Learn from an interaction to improve future responses
        """
        # Analyze what worked
        if success and quality >= 0.8:
            if "effective" not in self.self_model.strengths:
                self.self_model.strengths.append("effective communication")
        
        # Update knowledge domains based on interaction
        interaction_keywords = {
            "code": "programming",
            "script": "automation",
            "debug": "debugging",
            "test": "testing",
            "design": "architecture",
            "research": "research",
            "write": "writing",
            "plan": "planning",
            "analyze": "analysis",
        }
        
        for keyword, domain in interaction_keywords.items():
            if keyword in user_input.lower():
                if domain not in self.self_model.knowledge_domains:
                    self.self_model.knowledge_domains.append(domain)
    
    def save_state(self, path: str = "/root/.hermes/profiles/ilma/.meta_cognition_state.json"):
        """Save metacognition state for persistence"""
        state = {
            "self_model": {
                "awareness_level": self.self_model.awareness_level.value,
                "cognitive_state": self.self_model.cognitive_state.value,
                "total_thoughts": self.self_model.total_thoughts,
                "successful_actions": self.self_model.successful_actions,
                "failed_actions": self.self_model.failed_actions,
                "current_focus": self.self_model.current_focus,
                "knowledge_domains": self.self_model.knowledge_domains,
                "strengths": self.self_model.strengths,
                "weaknesses": self.self_model.weaknesses,
                "recent_insights": self.self_model.recent_insights,
            },
            "insight_patterns": self.insight_patterns,
            "timestamp": datetime.now().isoformat()
        }
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(state, f, indent=2)
        
        logger.info(f"Meta-cognition state saved to {path}")
    
    def load_state(self, path: str = "/root/.hermes/profiles/ilma/.meta_cognition_state.json"):
        """Load metacognition state"""
        if not Path(path).exists():
            logger.info("No previous state found, starting fresh")
            return
        
        with open(path, 'r') as f:
            state = json.load(f)
        
        sm = state["self_model"]
        self.self_model.awareness_level = AwarenessLevel(sm["awareness_level"])
        self.self_model.cognitive_state = CognitiveState(sm["cognitive_state"])
        self.self_model.total_thoughts = sm["total_thoughts"]
        self.self_model.successful_actions = sm["successful_actions"]
        self.self_model.failed_actions = sm["failed_actions"]
        self.self_model.current_focus = sm["current_focus"]
        self.self_model.knowledge_domains = sm["knowledge_domains"]
        self.self_model.strengths = sm["strengths"]
        self.self_model.weaknesses = sm["weaknesses"]
        self.self_model.recent_insights = sm["recent_insights"]
        self.insight_patterns = state.get("insight_patterns", {})
        
        logger.info("Meta-cognition state loaded")


# Global instance
_meta_cognition = None

def get_meta_cognition() -> MetaCognitionEngine:
    """Get or create global meta-cognition instance"""
    global _meta_cognition
    if _meta_cognition is None:
        _meta_cognition = MetaCognitionEngine()
        _meta_cognition.load_state()
    return _meta_cognition


def main():
    """Demo the meta-cognition engine"""
    mc = get_meta_cognition()
    
    print("ILMA META-COGNITION ENGINE DEMO")
    print("=" * 60)
    print()
    
    # Simulate thoughts
    mc.think(CognitiveState.REASONING, "Analyzing user request",
             reasoning_chain=["User asked about X", "X relates to Y", "Therefore approach Z"])
    
    mc.think(CognitiveState.LEARNING, "Learning new pattern")
    
    mc.think(CognitiveState.PLANNING, "Planning response strategy")
    
    # Record some actions
    import time
    mc.record_action("execute_code", 2.5, True, 0.9)
    mc.record_action("research", 5.0, True, 0.85)
    mc.record_action("write_response", 1.0, True, 0.95)
    
    # Evaluate performance
    eval_result = mc.evaluate_performance()
    print("Performance Evaluation:")
    print(json.dumps(eval_result, indent=2))
    print()
    
    # Get self report
    print(mc.get_self_report())
    
    # Save state
    mc.save_state()


if __name__ == "__main__":
    main()
