"""
ILMA Report Service Package
Phase 54E: Services decomposition
Canonical: scripts/services/report/core.py
Original: scripts/ilma_report_generator.py
"""
from services.report.core import (
    ReportFormat,
    EvidenceType,
    ConfidenceLevel,
    Evidence,
    Section,
    Report,
    EvidenceCollector,
    ReportBuilder,
    FormatRenderer,
)

# Import FinalReportGenerator
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
    'ReportFormat',
    'EvidenceType',
    'ConfidenceLevel',
    'Evidence',
    'Section',
    'Report',
    'EvidenceCollector',
    'ReportBuilder',
    'FormatRenderer',
    # Final Report Generator
    'FinalReportGenerator',
    'FinalReport',
    'TestResult',
    'FileChange',
    'EvidenceRef',
    'ClaimBoundary',
    'FinalDecision',
    'generate_final_report',
]