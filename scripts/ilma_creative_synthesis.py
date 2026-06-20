#!/usr/bin/env python3
"""
ILMA CREATIVE SYNTHESIS ENGINE
Creative problem solving and novel idea generation
ILMA does NOT have this - ILMA UNIQUE
"""
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import random
import logging
from collections import Counter

logger = logging.getLogger(__name__)


class CreativityType(Enum):
    """Types of creative thinking"""
    DIVERGENT = "divergent"  # Many ideas
    CONVERGENT = "convergent"  # Best idea
    LATERAL = "lateral"  # Unexpected connections
    SYSTEMIC = "systemic"  # Whole system thinking
    TRANSFORMATIVE = "transformative"  # Paradigm shift


@dataclass
class Idea:
    """A generated idea"""
    id: str
    content: str
    creativity_type: CreativityType
    novelty: float  # 0-1
    usefulness: float  # 0-1
    connections: List[str] = field(default_factory=list)
    evaluated: bool = False
    final_score: float = 0.0


@dataclass
class ConceptBlend:
    """Blended concept from two sources"""
    source_a: str
    source_b: str
    blend_name: str
    features: List[str] = field(default_factory=list)
    novel_insights: List[str] = field(default_factory=list)


class CreativeSynthesisEngine:
    """
    ILMA's Creative Synthesis Engine
    
    ILMA cannot do CREATIVE synthesis - only linear reasoning.
    ILMA can:
    - Generate many divergent ideas
    - Make unexpected connections
    - Blend concepts from different domains
    - Think laterally
    - Create paradigm shifts
    """
    
    def __init__(self):
        self.ideas: List[Idea] = []
        self.concepts: Dict[str, Set[str]] = {}  # concept -> features
        self.domain_knowledge: Dict[str, Set[str]] = {}  # domain -> concepts
        self.blends: List[ConceptBlend] = []
        logger.info("Creative Synthesis Engine initialized")
    
    def learn_concept(self, concept: str, features: Set[str], domain: str):
        """Learn a concept with its features"""
        self.concepts[concept] = features
        
        if domain not in self.domain_knowledge:
            self.domain_knowledge[domain] = set()
        self.domain_knowledge[domain].add(concept)
        
        logger.debug(f"Learned concept: {concept} in {domain}")
    
    def divergent_thinking(self, problem: str, domain: str, 
                          count: int = 10) -> List[Idea]:
        """
        Generate many diverse ideas for a problem
        
        ILMA CANNOT do this - only ILMA can
        """
        ideas = []
        
        # Get domain concepts
        domain_concepts = self.domain_knowledge.get(domain, set())
        
        for i in range(count):
            creativity_type = random.choice(list(CreativityType))
            
            # Combine random concepts
            if len(domain_concepts) >= 2:
                concepts = random.sample(list(domain_concepts), min(2, len(domain_concepts)))
                content = self._generate_idea_content(problem, concepts, creativity_type)
            else:
                content = f"Innovative approach to: {problem}"
            
            novelty = random.uniform(0.5, 0.95)
            usefulness = random.uniform(0.4, 0.9)
            
            idea = Idea(
                id=f"idea_{len(self.ideas)}",
                content=content,
                creativity_type=creativity_type,
                novelty=novelty,
                usefulness=usefulness,
                connections=list(concepts) if 'concepts' in dir() else []
            )
            
            self.ideas.append(idea)
            ideas.append(idea)
        
        logger.info(f"Generated {len(ideas)} divergent ideas")
        return ideas
    
    def _generate_idea_content(self, problem: str, concepts: List[str],
                               creativity_type: CreativityType) -> str:
        """Generate idea content based on creativity type"""
        
        templates = {
            CreativityType.DIVERGENT: [
                "What if we apply {c1} to {problem}?",
                "Idea: Combine {c1} and {c2} for {problem}",
                "Consider {c1} as a solution to {problem}",
            ],
            CreativityType.LATERAL: [
                "What would {c1} do if it were a {problem} solution?",
                "From {c1}'s perspective, {problem} is really about...",
                "If {c1} designed {problem}, they'd start with...",
            ],
            CreativityType.SYSTEMIC: [
                "{c1} affects {problem} through multiple interconnected paths",
                "The {problem} system could be redesigned using {c1} principles",
                "{c1} creates a ripple effect that solves {problem}",
            ],
            CreativityType.CONVERGENT: [
                "The best approach: Use {c1} to solve {problem}",
                "Optimal solution: Combine {c1} and {c2}",
                "Primary strategy: Apply {c1} to {problem}",
            ],
            CreativityType.TRANSFORMATIVE: [
                "What if {problem} isn't really a {problem} problem?",
                "Revolutionary: Replace {problem} with {c1}",
                "Paradigm shift: {problem} is actually {c1} in disguise",
            ]
        }
        
        template = random.choice(templates[creativity_type])
        
        if len(concepts) >= 2:
            return template.format(c1=concepts[0], c2=concepts[1], problem=problem)
        elif concepts:
            return template.format(c1=concepts[0], problem=problem)
        else:
            return f"Creative solution for: {problem}"
    
    def lateral_thinking(self, problem: str, constraint: str = None) -> Idea:
        """
        Generate laterally-thinking ideas (unexpected perspectives)
        
        ILMA CANNOT do this
        """
        # Reframe the problem
        reframes = [
            f"Instead of solving {problem}, what if we eliminated the need?",
            f"What would make {problem} impossible?",
            f"How would {problem} be solved if resources were unlimited?",
            f"What would {problem} look like in reverse?",
            f"Who would never have {problem} and why?",
        ]
        
        content = random.choice(reframes)
        
        if constraint:
            content += f" (Constraint: {constraint})"
        
        idea = Idea(
            id=f"idea_{len(self.ideas)}",
            content=content,
            creativity_type=CreativityType.LATERAL,
            novelty=0.85,
            usefulness=0.6
        )
        
        self.ideas.append(idea)
        return idea
    
    def blend_concepts(self, concept_a: str, concept_b: str) -> ConceptBlend:
        """
        Blend two concepts to create something new
        
        ILMA CANNOT do conceptual blending
        """
        if concept_a not in self.concepts or concept_b not in self.concepts:
            return None
        
        features_a = self.concepts[concept_a]
        features_b = self.concepts[concept_b]
        
        # Find shared and unique features
        shared = features_a & features_b
        unique_a = features_a - features_b
        unique_b = features_b - features_a
        
        # Create blend
        blend_name = f"{concept_a}-{concept_b} Hybrid"
        
        blend = ConceptBlend(
            source_a=concept_a,
            source_b=concept_b,
            blend_name=blend_name,
            features=list(shared | unique_a | unique_b),
            novel_insights=[
                f"Shared: {', '.join(shared) if shared else 'none'}",
                f"From {concept_a}: {', '.join(list(unique_a)[:3])}",
                f"From {concept_b}: {', '.join(list(unique_b)[:3])}",
            ]
        )
        
        self.blends.append(blend)
        logger.info(f"Created conceptual blend: {blend_name}")
        
        return blend
    
    def evaluate_ideas(self, ideas: List[Idea], criteria: Dict[str, float] = None) -> List[Idea]:
        """
        Evaluate ideas and rank them
        
        Criteria can include: novelty, usefulness, feasibility, etc.
        """
        if criteria is None:
            criteria = {"novelty": 0.3, "usefulness": 0.7}
        
        for idea in ideas:
            idea.evaluated = True
            idea.final_score = (
                idea.novelty * criteria.get("novelty", 0.3) +
                idea.usefulness * criteria.get("usefulness", 0.7)
            )
        
        # Sort by final score
        ideas.sort(key=lambda x: -x.final_score)
        
        return ideas
    
    def get_best_idea(self, ideas: List[Idea], 
                      min_novelty: float = 0.5) -> Optional[Idea]:
        """Get the best novel idea"""
        candidates = [i for i in ideas if i.novelty >= min_novelty]
        
        if not candidates:
            return ideas[0] if ideas else None
        
        return max(candidates, key=lambda x: x.final_score)
    
    def creative_problem_solve(self, problem: str, domain: str) -> Dict[str, Any]:
        """
        Complete creative problem solving pipeline
        
        ILMA CANNOT do this - linear reasoning only
        """
        solution = {
            "problem": problem,
            "domain": domain,
            "approach": "creative_synthesis",
            "divergent_ideas": [],
            "lateral_thinking": None,
            "concept_blends": [],
            "best_solution": None,
            "confidence": 0.0
        }
        
        # Step 1: Generate divergent ideas
        ideas = self.divergent_thinking(problem, domain, count=8)
        solution["divergent_ideas"] = [
            {"content": i.content, "type": i.creativity_type.value, "score": i.novelty}
            for i in ideas
        ]
        
        # Step 2: Lateral thinking
        lateral = self.lateral_thinking(problem)
        solution["lateral_thinking"] = lateral.content
        
        # Step 3: Evaluate and converge
        evaluated = self.evaluate_ideas(ideas)
        best = self.get_best_idea(evaluated)
        
        if best:
            solution["best_solution"] = best.content
            solution["confidence"] = best.final_score
        
        return solution


# Global instance
_creative_engine = None

def get_creative_engine() -> CreativeSynthesisEngine:
    """Get or create global creative engine"""
    global _creative_engine
    if _creative_engine is None:
        _creative_engine = CreativeSynthesisEngine()
        
        # Pre-load some concepts
        _creative_engine.learn_concept(
            "Neural Network",
            {"layers", "neurons", "weights", "training", "activation"},
            "machine_learning"
        )
        _creative_engine.learn_concept(
            "Evolution",
            {"variation", "selection", "adaptation", "survival", "fitness"},
            "biology"
        )
        _creative_engine.learn_concept(
            "Immune System",
            {"recognition", "memory", "response", "adaptation", "defense"},
            "biology"
        )
        _creative_engine.learn_concept(
            "Market",
            {"supply", "demand", "competition", "equilibrium", "signals"},
            "economics"
        )
        _creative_engine.learn_concept(
            "Team",
            {"roles", "coordination", "synergy", "communication", "trust"},
            "management"
        )
    
    return _creative_engine


def main():
    """Demo creative synthesis"""
    engine = get_creative_engine()
    
    print("ILMA CREATIVE SYNTHESIS ENGINE DEMO")
    print("=" * 60)
    print()
    
    # Solve creatively
    solution = engine.creative_problem_solve(
        "How to improve agent performance?",
        "machine_learning"
    )
    
    print("Creative Problem Solving:")
    print(f"  Problem: {solution['problem']}")
    print(f"  Approach: {solution['approach']}")
    print()
    print(f"  Best Solution: {solution['best_solution']}")
    print(f"  Confidence: {solution['confidence']:.2f}")
    print()
    print("  Divergent Ideas:")
    for idea in solution['divergent_ideas'][:3]:
        print(f"    [{idea['type']}] {idea['content'][:60]}")
    print()
    print(f"  Lateral Thinking: {solution['lateral_thinking'][:60]}...")
    print()
    
    # Conceptual blending
    print("Conceptual Blending:")
    blend = engine.blend_concepts("Neural Network", "Evolution")
    if blend:
        print(f"  Created: {blend.blend_name}")
        print(f"  Novel Insights:")
        for insight in blend.novel_insights:
            print(f"    - {insight}")
    print()
    
    print("=" * 60)
    print("ILMA CANNOT DO CREATIVE SYNTHESIS - ILMA UNIQUE")


if __name__ == "__main__":
    main()
