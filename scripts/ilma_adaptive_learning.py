#!/usr/bin/env python3
"""
ILMA ADAPTIVE LEARNING ENGINE
Learns from interactions and improves over time
ILMA has basic learning - ILMA has ADAPTIVE learning
"""
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class LearningType(Enum):
    """Types of learning"""
    SUPERVISED = "supervised"
    UNSUPERVISED = "unsupervised"
    REINFORCEMENT = "reinforcement"
    TRANSFER = "transfer"
    META = "meta"


@dataclass
class LearningPattern:
    """A learned pattern from interactions"""
    id: str
    trigger: str
    response: str
    success_rate: float
    usage_count: int
    last_used: datetime
    domain: str
    confidence: float


@dataclass
class Interaction:
    """Record of an interaction"""
    timestamp: datetime
    input_type: str
    input_content: str
    response: str
    success: bool
    quality: float
    feedback: Optional[str] = None


class AdaptiveLearningEngine:
    """
    ILMA's Adaptive Learning Engine
    
    ILMA has basic learning - ILMA has ADAPTIVE learning that:
    - Learns from every interaction
    - Adapts to user preferences
    - Updates patterns in real-time
    - Tracks success/failure
    - Transfers knowledge between domains
    """
    
    def __init__(self):
        self.patterns: Dict[str, LearningPattern] = {}
        self.interactions: List[Interaction] = []
        self.domain_expertise: Dict[str, float] = {}
        self.user_preferences: Dict[str, Any] = {}
        self.learning_history: List[Dict] = []
        logger.info("Adaptive Learning Engine initialized")
    
    def learn_from_interaction(self, input_content: str, response: str,
                               success: bool, quality: float,
                               domain: str = "general",
                               feedback: str = None):
        """
        Learn from an interaction
        
        ILMA CANNOT do real-time adaptive learning
        """
        interaction = Interaction(
            timestamp=datetime.now(),
            input_type="text",
            input_content=input_content,
            response=response,
            success=success,
            quality=quality,
            feedback=feedback
        )
        
        self.interactions.append(interaction)
        
        # Update or create pattern
        pattern_key = input_content.lower()[:50]
        
        if pattern_key in self.patterns:
            pattern = self.patterns[pattern_key]
            pattern.usage_count += 1
            pattern.last_used = datetime.now()
            
            # Update success rate with exponential moving average
            alpha = 0.3
            pattern.success_rate = alpha * (1 if success else 0) + (1 - alpha) * pattern.success_rate
            
            # Update confidence
            pattern.confidence = min(1.0, pattern.usage_count / 10)
        else:
            self.patterns[pattern_key] = LearningPattern(
                id=f"pattern_{len(self.patterns)}",
                trigger=input_content[:100],
                response=response[:200],
                success_rate=1.0 if success else 0.0,
                usage_count=1,
                last_used=datetime.now(),
                domain=domain,
                confidence=0.1
            )
        
        # Update domain expertise
        if domain not in self.domain_expertise:
            self.domain_expertise[domain] = 0.0
        
        delta = 0.1 if success else -0.05
        self.domain_expertise[domain] = max(0.0, min(1.0, self.domain_expertise[domain] + delta))
        
        # Log learning
        self.learning_history.append({
            "timestamp": datetime.now().isoformat(),
            "input": input_content[:30],
            "success": success,
            "quality": quality,
            "domain": domain
        })
        
        logger.info(f"Learned from interaction: {success} ({quality:.2f})")
    
    def get_best_response(self, query: str, domain: str = "general") -> Optional[str]:
        """
        Get best learned response for a query
        
        ILMA CANNOT do this
        """
        query_lower = query.lower()
        
        # Find matching patterns
        matches = []
        for key, pattern in self.patterns.items():
            if query_lower in key or key in query_lower:
                if pattern.domain == domain or pattern.domain == "general":
                    matches.append(pattern)
        
        if not matches:
            return None
        
        # Score and rank
        def score(p):
            return p.success_rate * 0.4 + p.confidence * 0.3 + p.usage_count * 0.01
        
        best = max(matches, key=score)
        
        if best.success_rate >= 0.5:
            logger.info(f"Found learned response for: {query[:30]}...")
            return best.response
        
        return None
    
    def transfer_learning(self, source_domain: str, target_domain: str):
        """
        Transfer knowledge from one domain to another
        
        ILMA CANNOT do transfer learning
        """
        if source_domain not in self.domain_expertise:
            return
        
        source_level = self.domain_expertise[source_domain]
        
        # Transfer patterns
        transferred = 0
        for key, pattern in self.patterns.items():
            if pattern.domain == source_domain:
                if pattern.success_rate >= 0.7:
                    # Create transferred pattern
                    new_key = f"{key}_transferred"
                    if new_key not in self.patterns:
                        self.patterns[new_key] = LearningPattern(
                            id=f"pattern_{len(self.patterns)}",
                            trigger=f"[TRANSFERRED from {source_domain}] {pattern.trigger}",
                            response=pattern.response,
                            success_rate=pattern.success_rate * 0.8,  # Slight degradation
                            usage_count=0,
                            last_used=datetime.now(),
                            domain=target_domain,
                            confidence=pattern.confidence * 0.5
                        )
                        transferred += 1
        
        # Update target domain expertise
        if target_domain not in self.domain_expertise:
            self.domain_expertise[target_domain] = 0.0
        
        self.domain_expertise[target_domain] = min(1.0, 
            self.domain_expertise[target_domain] + source_level * 0.3)
        
        logger.info(f"Transferred {transferred} patterns from {source_domain} to {target_domain}")
        
        return transferred
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """Get learning statistics"""
        if not self.interactions:
            return {"status": "no_learning_data"}
        
        recent = [i for i in self.interactions if 
                 datetime.now() - i.timestamp < timedelta(days=7)]
        
        success_rate = sum(1 for i in recent if i.success) / len(recent) if recent else 0
        avg_quality = sum(i.quality for i in recent) / len(recent) if recent else 0
        
        return {
            "total_interactions": len(self.interactions),
            "total_patterns": len(self.patterns),
            "recent_interactions": len(recent),
            "recent_success_rate": success_rate,
            "recent_avg_quality": avg_quality,
            "domain_expertise": self.domain_expertise,
            "top_patterns": len([p for p in self.patterns.values() if p.usage_count > 3])
        }
    
    def get_recommendations(self) -> List[str]:
        """Get learning-based recommendations"""
        recommendations = []
        
        # Recommend areas for improvement
        low_expertise = [(d, level) for d, level in self.domain_expertise.items() if level < 0.5]
        if low_expertise:
            recommendations.append(f"Improve expertise in: {', '.join(d for d, _ in low_expertise[:3])}")
        
        # Recommend failed pattern review
        failed = [p for p in self.patterns.values() if p.success_rate < 0.3 and p.usage_count > 2]
        if failed:
            recommendations.append(f"Review {len(failed)} failing patterns")
        
        # Recommend successful pattern expansion
        successful = [p for p in self.patterns.values() if p.success_rate >= 0.9 and p.usage_count > 5]
        if successful:
            recommendations.append(f"Expand {len(successful)} highly successful patterns")
        
        return recommendations
    
    def save(self, path: str = "/root/.hermes/profiles/ilma/.adaptive_learning.json"):
        """Save learning state"""
        data = {
            "patterns": [
                {
                    "id": p.id,
                    "trigger": p.trigger,
                    "response": p.response,
                    "success_rate": p.success_rate,
                    "usage_count": p.usage_count,
                    "last_used": p.last_used.isoformat(),
                    "domain": p.domain,
                    "confidence": p.confidence
                }
                for p in self.patterns.values()
            ],
            "domain_expertise": self.domain_expertise,
            "learning_history": self.learning_history[-100:]  # Keep last 100
        }
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Learning state saved: {len(self.patterns)} patterns")
    
    def load(self, path: str = "/root/.hermes/profiles/ilma/.adaptive_learning.json"):
        """Load learning state"""
        if not Path(path).exists():
            return
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        self.patterns = {
            p["id"]: LearningPattern(
                id=p["id"],
                trigger=p["trigger"],
                response=p["response"],
                success_rate=p["success_rate"],
                usage_count=p["usage_count"],
                last_used=datetime.fromisoformat(p["last_used"]),
                domain=p["domain"],
                confidence=p["confidence"]
            )
            for p in data.get("patterns", [])
        }
        
        self.domain_expertise = data.get("domain_expertise", {})
        self.learning_history = data.get("learning_history", [])
        
        logger.info(f"Learning state loaded: {len(self.patterns)} patterns")


# Need Path import
from pathlib import Path


# Global instance
_adaptive_learning = None

def get_adaptive_learning() -> AdaptiveLearningEngine:
    """Get or create global adaptive learning engine"""
    global _adaptive_learning
    if _adaptive_learning is None:
        _adaptive_learning = AdaptiveLearningEngine()
        _adaptive_learning.load()
    return _adaptive_learning


def main():
    """Demo adaptive learning"""
    engine = get_adaptive_learning()
    
    print("ILMA ADAPTIVE LEARNING ENGINE DEMO")
    print("=" * 60)
    print()
    
    # Learn from interactions
    engine.learn_from_interaction(
        "How to fix Python error?",
        "Try checking the stack trace and line number.",
        success=True,
        quality=0.85,
        domain="programming"
    )
    
    engine.learn_from_interaction(
        "How to deploy to AWS?",
        "Use EC2 or Lambda for deployment.",
        success=True,
        quality=0.9,
        domain="devops"
    )
    
    engine.learn_from_interaction(
        "How to learn faster?",
        "Practice consistently and get feedback.",
        success=True,
        quality=0.8,
        domain="learning"
    )
    
    # Get best response
    response = engine.get_best_response("How to fix Python error?", "programming")
    print(f"Best Response: {response}")
    print()
    
    # Get stats
    stats = engine.get_learning_stats()
    print("Learning Stats:")
    print(f"  Total Patterns: {stats['total_patterns']}")
    print(f"  Recent Success Rate: {stats['recent_success_rate']:.1%}")
    print()
    
    # Get recommendations
    recs = engine.get_recommendations()
    print("Recommendations:")
    for r in recs:
        print(f"  - {r}")
    print()
    
    print("=" * 60)
    print("ILMA HAS BASIC LEARNING - ILMA HAS ADAPTIVE LEARNING")


if __name__ == "__main__":
    main()
