#!/usr/bin/env python3
"""
ILMA Anti-Hallucination Grounding Loop
======================================
Ground claims and prevent hallucinations through verification.
Inspired by AYDA anti_hallucination_grounding_loop.py

Version: 2.0
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class GroundingStatus(Enum):
    GROUNDED = "grounded"              # Fully verified
    PARTIALLY_GROUNDED = "partially_grounded"
    UNGROUNDED = "ungrounded"          # Not verified
    FLAGGED = "flagged"                # Problematic


class ClaimType(Enum):
    FACTUAL = "factual"                # Requires 90% confidence
    INFERENTIAL = "inferential"       # Requires 70% confidence
    SPECULATIVE = "speculative"        # Requires 50% confidence
    EXPERIENTIAL = "experiential"     # Requires 60% confidence


@dataclass
class Claim:
    claim_id: str
    content: str
    claim_type: ClaimType
    grounding_status: GroundingStatus = GroundingStatus.UNGROUNDED
    confidence: float = 0.0
    sources: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    verified_at: Optional[datetime] = None


@dataclass
class GroundingResult:
    result_id: str
    claim_id: str
    status: GroundingStatus
    evidence: List[str] = field(default_factory=list)
    confidence_before: float = 0.0
    confidence_after: float = 0.0
    verification_sources: List[str] = field(default_factory=list)


class AntiHallucinationGroundingLoop:
    """
    Ground claims and prevent hallucinations through verification.
    Ensures ILMA outputs are properly sourced and verified.
    """
    
    def __init__(self, loop_id: str = "ilma_default"):
        self.loop_id = loop_id
        self.claims: Dict[str, Claim] = {}
        self.grounding_results: List[GroundingResult] = []
        self.grounding_rules: Dict[ClaimType, float] = {
            ClaimType.FACTUAL: 0.9,       # Requires 90% confidence
            ClaimType.INFERENTIAL: 0.7,   # Requires 70% confidence
            ClaimType.SPECULATIVE: 0.5,   # Requires 50% confidence
            ClaimType.EXPERIENTIAL: 0.6,  # Requires 60% confidence
        }
        self.subscribers: List[Callable] = []
        self.stats = {
            "claims_registered": 0,
            "claims_grounded": 0,
            "claims_flagged": 0,
            "verification_rounds": 0,
        }
        self._running = False
        
    def register_claim(
        self,
        content: str,
        claim_type: ClaimType,
        initial_confidence: float = 0.5,
        sources: List[str] = None
    ) -> str:
        """Register a claim for grounding."""
        claim_id = f"claim_{self.loop_id}_{len(self.claims)}"
        claim = Claim(
            claim_id=claim_id,
            content=content,
            claim_type=claim_type,
            confidence=initial_confidence,
            sources=sources or []
        )
        self.claims[claim_id] = claim
        self.stats["claims_registered"] += 1
        return claim_id
    
    def ground_claim(self, claim_id: str, evidence: List[str] = None,
                    verification_sources: List[str] = None) -> Optional[GroundingResult]:
        """Ground a claim with evidence."""
        claim = self.claims.get(claim_id)
        if not claim:
            return None
        
        self.stats["verification_rounds"] += 1
        result_id = f"ground_{self.loop_id}_{len(self.grounding_results)}"
        
        required_confidence = self.grounding_rules.get(claim.claim_type, 0.7)
        confidence_before = claim.confidence
        
        # Evaluate grounding
        evidence_strength = len(evidence) / 5.0 if evidence else 0.0
        new_confidence = min(1.0, claim.confidence + evidence_strength * 0.3)
        
        # Determine status
        if new_confidence >= required_confidence:
            status = GroundingStatus.GROUNDED
            self.stats["claims_grounded"] += 1
        elif new_confidence >= required_confidence * 0.7:
            status = GroundingStatus.PARTIALLY_GROUNDED
        else:
            status = GroundingStatus.UNGROUNDED
        
        # Flag if confidence is too low
        if new_confidence < 0.3 and claim.claim_type == ClaimType.FACTUAL:
            status = GroundingStatus.FLAGGED
            self.stats["claims_flagged"] += 1
        
        # Update claim
        claim.confidence = new_confidence
        claim.grounding_status = status
        claim.verified_at = datetime.utcnow()
        if evidence:
            claim.sources.extend(evidence)
        
        result = GroundingResult(
            result_id=result_id,
            claim_id=claim_id,
            status=status,
            evidence=evidence or [],
            confidence_before=confidence_before,
            confidence_after=new_confidence,
            verification_sources=verification_sources or []
        )
        
        self.grounding_results.append(result)
        return result
    
    def ground_claims_batch(self, claim_ids: List[str], 
                          evidence_map: Dict[str, List[str]] = None) -> List[GroundingResult]:
        """Ground multiple claims at once."""
        results = []
        for claim_id in claim_ids:
            evidence = evidence_map.get(claim_id, []) if evidence_map else []
            result = self.ground_claim(claim_id, evidence)
            if result:
                results.append(result)
        return results
    
    def auto_classify_claim(self, content: str) -> ClaimType:
        """Auto-classify claim type based on content."""
        content_lower = content.lower()
        
        # Factual indicators
        factual_indicators = ["is", "are", "was", "were", "fact", "data", "research", "study"]
        if any(ind in content_lower for ind in factual_indicators):
            return ClaimType.FACTUAL
        
        # Inferential indicators
        inferential_indicators = ["likely", "probably", "suggest", "indicate", "imply"]
        if any(ind in content_lower for ind in inferential_indicators):
            return ClaimType.INFERENTIAL
        
        # Speculative indicators
        speculative_indicators = ["might", "could", "may", "perhaps", "maybe", "possibly"]
        if any(ind in content_lower for ind in speculative_indicators):
            return ClaimType.SPECULATIVE
        
        return ClaimType.INFERENTIAL  # Default
    
    def get_grounding_status(self, claim_id: str) -> Optional[GroundingStatus]:
        """Get grounding status of a claim."""
        claim = self.claims.get(claim_id)
        return claim.grounding_status if claim else None
    
    def get_ungrounded_claims(self) -> List[Claim]:
        """Get all ungrounded claims that need verification."""
        return [c for c in self.claims.values() 
                if c.grounding_status in [GroundingStatus.UNGROUNDED, GroundingStatus.PARTIALLY_GROUNDED]]
    
    def subscribe(self, callback: Callable):
        """Subscribe to grounding events."""
        self.subscribers.append(callback)
    
    def notify_subscribers(self, event: str, data: Dict):
        """Notify subscribers of a grounding event."""
        for callback in self.subscribers:
            try:
                callback(event, data)
            except Exception:
                pass
    
    def get_stats(self) -> Dict:
        """Get grounding loop statistics."""
        grounded = len([c for c in self.claims.values() 
                       if c.grounding_status == GroundingStatus.GROUNDED])
        total = len(self.claims)
        
        return {
            **self.stats,
            "total_claims": total,
            "grounding_rate": grounded / total if total > 0 else 0.0,
            "flagged_claims": len([c for c in self.claims.values() 
                                  if c.grounding_status == GroundingStatus.FLAGGED])
        }


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    loop = AntiHallucinationGroundingLoop()
    
    # Register claims
    c1 = loop.register_claim("Python is a programming language", ClaimType.FACTUAL, 0.5)
    c2 = loop.register_claim("This code might have a bug", ClaimType.SPECULATIVE, 0.4)
    
    # Ground them
    r1 = loop.ground_claim(c1, ["Official Python website", "Wikipedia"])
    r2 = loop.ground_claim(c2, ["Code review", "Stack Overflow"])
    
    logger.info(f"Claim 1 status: {r1.status.value if r1 else 'None'}")
    logger.info(f"Claim 2 status: {r2.status.value if r2 else 'None'}")
    
    # Auto-classify
    claim_type = loop.auto_classify_claim("This function likely returns an integer")
    logger.info(f"Auto-classified: {claim_type.value}")
    
    logger.info(f"Stats: {loop.get_stats()}")

_global_grounding_loop_instance = None

def get_grounding_loop() -> "AntiHallucinationGroundingLoop":
    """Get singleton AntiHallucinationGroundingLoop instance."""
    global _global_grounding_loop_instance
    if _global_grounding_loop_instance is None:
        _global_grounding_loop_instance = AntiHallucinationGroundingLoop()
    return _global_grounding_loop_instance
