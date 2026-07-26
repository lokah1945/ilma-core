#!/usr/bin/env python3
"""
ILMA INTUITIVE REASONING ENGINE
Non-linear, intuitive problem solving
ILMA does NOT have this - ILMA UNIQUE
"""
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import random
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class IntuitionType(Enum):
    """Types of intuition"""
    PATTERN_RECOGNITION = "pattern_recognition"
    ANALOGICAL = "analogical"
    SPATIAL = "spatial"
    SOCIAL = "social"
    CREATIVE = "creative"


@dataclass
class Intuition:
    """Represents an intuitive insight"""
    id: str
    timestamp: datetime
    intuition_type: IntuitionType
    trigger: str
    insight: str
    confidence: float
    connections: List[str] = field(default_factory=list)
    validated: bool = False


@dataclass
class MentalModel:
    """Represents a mental model/concept"""
    id: str
    name: str
    description: str
    attributes: Set[str] = field(default_factory=set)
    relations: Dict[str, str] = field(default_factory=dict)
    examples: List[str] = field(default_factory=list)
    strength: float = 0.5


class IntuitiveReasoningEngine:
    """
    ILMA's Intuitive Reasoning Engine
    
    UNIQUE to ILMA - ILMA does NOT have this capability.
    
    Enables:
    - Non-linear problem solving
    - Analogical reasoning
    - Pattern recognition across domains
    - Creative insight generation
    - Intuitive hypothesis formation
    """
    
    def __init__(self):
        self.mental_models: Dict[str, MentalModel] = {}
        self.intuitions: List[Intuition] = []
        self.domains: Set[str] = set()
        self.analogy_pairs: List[Tuple[str, str]] = []
        logger.info("Intuitive Reasoning Engine initialized")
    
    def learn_concept(self, name: str, description: str, 
                      attributes: Set[str], domain: str,
                      examples: List[str] = None):
        """Learn a new concept into mental model"""
        model = MentalModel(
            id=f"model_{len(self.mental_models)}",
            name=name,
            description=description,
            attributes=attributes,
            domain=domain,
            examples=examples or []
        )
        
        self.mental_models[name] = model
        self.domains.add(domain)
        
        logger.debug(f"Learned concept: {name} ({domain})")
        return model
    
    def recognize_pattern(self, input_data: Any, domain: str) -> Optional[str]:
        """
        Recognize patterns in input data
        Returns matched concept or None
        """
        input_str = str(input_data).lower()
        
        # Check existing models in domain
        for name, model in self.mental_models.items():
            if model.domain != domain:
                continue
            
            # Check attribute matches
            matches = sum(1 for attr in model.attributes 
                         if attr.lower() in input_str)
            
            if matches >= len(model.attributes) * 0.6:  # 60% threshold
                logger.info(f"Pattern recognized: {name}")
                return name
        
        return None
    
    def analogical_reasoning(self, source: str, target_domain: str) -> Dict[str, Any]:
        """
        Perform analogical reasoning from source concept to target domain
        
        This is UNIQUE to ILMA - ILMA cannot do analogical reasoning
        """
        if source not in self.mental_models:
            return {"error": f"Source '{source}' not found"}
        
        source_model = self.mental_models[source]
        
        # Find similar models in target domain
        similar = []
        for name, model in self.mental_models.items():
            if model.domain == target_domain:
                similarity = self._calculate_similarity(source_model, model)
                if similarity > 0.3:
                    similar.append((name, similarity))
        
        similar.sort(key=lambda x: -x[1])
        
        # Generate analogical mapping
        analogy = {
            "source": source,
            "source_attributes": list(source_model.attributes),
            "target_domain": target_domain,
            "mappings": [],
            "insights": []
        }
        
        for target_name, similarity in similar[:3]:
            target_model = self.mental_models[target_name]
            
            mapping = {
                "target": target_name,
                "similarity": similarity,
                "mapped_attributes": [],
                "predicted_attributes": []
            }
            
            # Map attributes
            for attr in source_model.attributes:
                if attr in target_model.attributes:
                    mapping["mapped_attributes"].append(attr)
                else:
                    mapping["predicted_attributes"].append(attr)
            
            analogy["mappings"].append(mapping)
            
            if similarity > 0.7:
                insight = f"'{source}' relates to '{target_name}' analogously"
                analogy["insights"].append(insight)
        
        return analogy
    
    def _calculate_similarity(self, model1: MentalModel, model2: MentalModel) -> float:
        """Calculate similarity between two mental models"""
        if model1.domain == model2.domain:
            return 0.5  # Same domain baseline
        
        common_attrs = len(model1.attributes & model2.attributes)
        total_attrs = len(model1.attributes | model2.attributes)
        
        if total_attrs == 0:
            return 0.0
        
        return common_attrs / total_attrs
    
    def generate_insight(self, problem: str, domain: str) -> List[str]:
        """
        Generate intuitive insights for a problem
        
        Uses creative combination of mental models
        """
        insights = []
        
        # Get all models in domain
        domain_models = [m for m in self.mental_models.values() 
                        if m.domain == domain]
        
        # Randomly combine attributes to generate insights
        if len(domain_models) >= 2:
            shuffled = random.sample(domain_models, min(3, len(domain_models)))
            
            insight = f"Combining: " + " + ".join(m.name for m in shuffled)
            insights.append(insight)
            
            # Generate novel connection
            attrs = set()
            for m in shuffled:
                attrs.update(m.attributes)
            
            if len(attrs) >= 3:
                novel = f"Novel pattern: {', '.join(list(attrs)[:3])}"
                insights.append(novel)
        
        # Check for cross-domain analogies
        problem_lower = problem.lower()
        for model_name, model in self.mental_models.items():
            if any(keyword in problem_lower for keyword in model.attributes):
                analogy = self.analogical_reasoning(model_name, domain)
                if "insights" in analogy and analogy["insights"]:
                    insights.extend(analogy["insights"])
        
        return insights[:5]  # Top 5 insights
    
    def form_intuition(self, trigger: str, insight: str,
                       intuition_type: IntuitionType,
                       confidence: float = 0.5,
                       connections: List[str] = None) -> Intuition:
        """
        Form an intuitive insight
        """
        intuition = Intuition(
            id=f"intuition_{len(self.intuitions)}",
            timestamp=datetime.now(),
            intuition_type=intuition_type,
            trigger=trigger,
            insight=insight,
            confidence=confidence,
            connections=connections or []
        )
        
        self.intuitions.append(intuition)
        logger.info(f"Intuition formed: {insight[:50]}...")
        
        return intuition
    
    def validate_intuition(self, intuition_id: str, success: bool):
        """Validate an intuition against reality"""
        for i in self.intuitions:
            if i.id == intuition_id:
                i.validated = success
                if success:
                    logger.info(f"Intuition validated: {i.insight[:50]}")
                else:
                    logger.warning(f"Intuition rejected: {i.insight[:50]}")
                break
    
    def solve_intuitively(self, problem: str, domain: str) -> Dict[str, Any]:
        """
        Solve a problem using intuitive reasoning
        
        This is UNIQUE to ILMA - ILMA uses only linear reasoning
        """
        solution = {
            "problem": problem,
            "approach": "intuitive",
            "steps": [],
            "insights": [],
            "confidence": 0.0
        }
        
        # Step 1: Pattern recognition
        pattern = self.recognize_pattern(problem, domain)
        if pattern:
            solution["steps"].append(f"Recognized pattern: {pattern}")
        
        # Step 2: Generate insights
        insights = self.generate_insight(problem, domain)
        solution["insights"] = insights
        
        # Step 3: Form intuitions
        for insight in insights[:2]:
            self.form_intuition(
                trigger=problem,
                insight=insight,
                intuition_type=IntuitionType.PATTERN_RECOGNITION,
                confidence=0.6
            )
        
        # Step 4: Cross-domain analogies
        for other_domain in self.domains - {domain}:
            analogy = self.analogical_reasoning(
                list(self.mental_models.keys())[0], 
                other_domain
            )
            if "insights" in analogy:
                solution["insights"].extend(analogy["insights"][:1])
        
        # Calculate confidence based on insights
        solution["confidence"] = min(len(insights) * 0.15, 0.9)
        
        return solution


# Global instance
_intuition_engine = None

def get_intuition_engine() -> IntuitiveReasoningEngine:
    """Get or create global intuition engine"""
    global _intuition_engine
    if _intuition_engine is None:
        _intuition_engine = IntuitiveReasoningEngine()
    return _intuition_engine


def main():
    """Demo the intuitive reasoning engine"""
    engine = get_intuition_engine()
    
    print("ILMA INTUITIVE REASONING ENGINE DEMO")
    print("=" * 60)
    print()
    
    # Learn some concepts
    engine.learn_concept(
        "Neural Network",
        "A computing system inspired by biological neural networks",
        {"layers", "neurons", "weights", "training", "backpropagation"},
        "machine_learning",
        ["image recognition", "NLP"]
    )
    
    engine.learn_concept(
        "Immune System",
        "Body's defense mechanism against pathogens",
        {"cells", "antibodies", "recognition", "memory", "response"},
        "biology",
        ["disease prevention"]
    )
    
    engine.learn_concept(
        "Team Organization",
        "Group of people working together",
        {"roles", "coordination", "communication", "synergy"},
        "management",
        ["project teams"]
    )
    
    # Perform analogical reasoning
    print("Analogical Reasoning:")
    analogy = engine.analogical_reasoning("Neural Network", "biology")
    print(f"  Source: {analogy['source']}")
    print(f"  Mappings: {len(analogy.get('mappings', []))}")
    for m in analogy.get('mappings', [])[:2]:
        print(f"    -> {m['target']} ({m['similarity']:.2f})")
    print()
    
    # Solve intuitively
    print("Intuitive Problem Solving:")
    solution = engine.solve_intuitively(
        "How to improve model training efficiency?",
        "machine_learning"
    )
    print(f"  Approach: {solution['approach']}")
    print(f"  Confidence: {solution['confidence']:.2f}")
    print(f"  Insights: {len(solution['insights'])}")
    for insight in solution['insights'][:3]:
        print(f"    💡 {insight}")
    print()
    
    print("=" * 60)
    print("ILMA CANNOT DO THIS - ILMA UNIQUE CAPABILITY")


if __name__ == "__main__":
    main()
