#!/usr/bin/env python3
"""
DEPRECATED SHIM: Use scripts/services.evidence.validator instead.
ILMA Phase 15D: Low-risk services decomposition.
This shim provides backwards compatibility.
Will be removed in Phase 17.
"""
import warnings
import sys
import os

# Ensure correct import path BEFORE any imports
script_dir = os.path.dirname(os.path.abspath(__file__))
workspace = os.path.dirname(script_dir)
if workspace not in sys.path:
    sys.path.insert(0, workspace)

warnings.warn(
    "scripts/ilma_evidence_validator.py is deprecated. "
    "Use scripts.services.evidence.validator instead.",
    DeprecationWarning,
    stacklevel=2
)

from scripts.services.evidence.validator import *
