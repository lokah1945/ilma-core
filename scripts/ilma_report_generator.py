#!/usr/bin/env python3
"""
ILMA Report Generator Shim
==========================
Deprecated shim - redirects to new path.
Use: from services.report.final_report_generator import FinalReportGenerator, generate_final_report
"""
import warnings
import logging

logger = logging.getLogger(__name__)

# Issue deprecation warning on import
warnings.warn(
    "scripts/ilma_report_generator is deprecated. "
    "Import from services.report.final_report_generator instead.",
    DeprecationWarning,
    stacklevel=2
)

# Redirect imports to new path
from services.report.final_report_generator import (
    FinalReportGenerator,
    FinalReport,
    TestResult,
    FileChange,
    EvidenceRef,
    ClaimBoundary,
    FinalDecision,
    generate_final_report,
)

__all__ = [
    "FinalReportGenerator",
    "FinalReport",
    "TestResult",
    "FileChange",
    "EvidenceRef",
    "ClaimBoundary",
    "FinalDecision",
    "generate_final_report",
]