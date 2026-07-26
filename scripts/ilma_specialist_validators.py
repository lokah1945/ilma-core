#!/usr/bin/env python3
"""
ILMA Specialist Validators — Shim for backward compatibility
Phase 54E: Services decomposition
Original: scripts/ilma_specialist_validators.py
Canonical: scripts/services/validators/core.py
"""
import sys
import os

# Add base path for relative imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Re-export all public classes from canonical location
from services.validators import (
    ValidatorResult,
    ArchitectValidator,
    QAValidator,
    SecurityValidator,
    EvidenceValidator,
    PerformanceValidator,
    TruthfulnessValidator,
    RegressionValidator,
    DocumentationValidator,
    SpecialistValidatorOrchestrator,
)

__all__ = [
    'ValidatorResult',
    'ArchitectValidator',
    'QAValidator',
    'SecurityValidator',
    'EvidenceValidator',
    'PerformanceValidator',
    'TruthfulnessValidator',
    'RegressionValidator',
    'DocumentationValidator',
    'SpecialistValidatorOrchestrator',
]