#!/usr/bin/env python3
"""
ILMA Final Report Generator
============================
Generates final reports with claim boundary verification.

Features:
- Executive summary
- Exact tests listing
- Exact files changed
- Evidence IDs collection
- Claim boundary (can/cannot claim)
- Final decision
- Next action
- Machine-readable JSON summary

Supported Claims:
- SSS (Self-Sufficiency Score)
- SSS+ (provisional)
- production (verified production-ready)
- Any claim in ilma_evidence_ledger.json

Unsupported Claims Rejected:
- SSS+++ (not a valid tier)
- production_false (contradiction)
- Any claim not in evidence ledger

Author: ILMA Team
Phase: 54E
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Valid claim tiers
VALID_CLAIM_TIERS = {
    "SSS",      # Self-Sufficiency Score base
    "SSS+",     # Provisional SSS
    "production",  # Production-ready verified
    "research",     # Research-phase claim
    "experimental", # Experimental claim
}

# Claims that are explicit contradictions (rejected)
CONTRADICTION_CLAIMS = {
    "production_false",
    "sss_minus",
    "fail",
    "rejected",
}

# SSS tiers that are valid
SSS_TIERS = {"SSS", "SSS+"}


class ClaimBoundary(Enum):
    """Claim boundary status."""
    CAN_CLAIM = "can_claim"
    CANNOT_CLAIM = "cannot_claim"
    PARTIAL_CLAIM = "partial_claim"
    UNSUPPORTED = "unsupported"


class FinalDecision(Enum):
    """Final decision status."""
    APPROVED = "approved"
    REJECTED = "rejected"
    CONDITIONAL = "conditional"
    PENDING = "pending"
    NEEDS_EVIDENCE = "needs_evidence"


@dataclass
class TestResult:
    """Single test result."""
    test_name: str
    status: str  # "pass", "fail", "skip"
    duration_ms: float = 0.0
    error_message: Optional[str] = None


@dataclass
class FileChange:
    """Single file change record."""
    file_path: str
    change_type: str  # "added", "modified", "deleted"
    lines_added: int = 0
    lines_deleted: int = 0


@dataclass
class EvidenceRef:
    """Evidence reference with validation."""
    evidence_id: str
    title: str
    evidence_type: str
    confidence: str
    verified: bool = False


@dataclass
class FinalReport:
    """
    Final report structure with all required sections.
    
    Required sections:
    1. executive_summary - High-level overview
    2. exact_tests - List of tests run
    3. exact_files_changed - List of files modified
    4. evidence_ids - List of evidence IDs referenced
    5. claim_boundary - Can/cannot claim determination
    6. final_decision - Approved/rejected decision
    7. next_action - Recommended next steps
    8. machine_readable_json - JSON summary
    """
    report_id: str
    created_at: float = field(default_factory=time.time)
    
    # Core report data
    executive_summary: str = ""
    claim: str = ""  # e.g., "SSS", "SSS+", "production"
    claim_boundary: ClaimBoundary = ClaimBoundary.UNSUPPORTED
    claim_boundary_reason: str = ""
    
    # Test results
    tests: List[TestResult] = field(default_factory=list)
    test_summary: Dict[str, int] = field(default_factory=lambda: {"passed": 0, "failed": 0, "skipped": 0})
    
    # File changes
    files_changed: List[FileChange] = field(default_factory=list)
    
    # Evidence
    evidence_ids: List[str] = field(default_factory=list)
    evidence_refs: List[EvidenceRef] = field(default_factory=list)
    
    # Decision
    final_decision: FinalDecision = FinalDecision.PENDING
    decision_rationale: str = ""
    
    # Next action
    next_action: str = ""
    next_action_priority: str = "medium"  # "low", "medium", "high", "critical"
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "report_id": self.report_id,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "created_at_timestamp": self.created_at,
            "executive_summary": self.executive_summary,
            "claim": self.claim,
            "claim_boundary": self.claim_boundary.value if isinstance(self.claim_boundary, ClaimBoundary) else self.claim_boundary,
            "claim_boundary_reason": self.claim_boundary_reason,
            "tests": [
                {
                    "test_name": t.test_name,
                    "status": t.status,
                    "duration_ms": t.duration_ms,
                    "error_message": t.error_message
                }
                for t in self.tests
            ],
            "test_summary": self.test_summary,
            "files_changed": [
                {
                    "file_path": f.file_path,
                    "change_type": f.change_type,
                    "lines_added": f.lines_added,
                    "lines_deleted": f.lines_deleted
                }
                for f in self.files_changed
            ],
            "evidence_ids": self.evidence_ids,
            "evidence_refs": [
                {
                    "evidence_id": e.evidence_id,
                    "title": e.title,
                    "evidence_type": e.evidence_type,
                    "confidence": e.confidence,
                    "verified": e.verified
                }
                for e in self.evidence_refs
            ],
            "final_decision": self.final_decision.value if isinstance(self.final_decision, FinalDecision) else self.final_decision,
            "decision_rationale": self.decision_rationale,
            "next_action": self.next_action,
            "next_action_priority": self.next_action_priority,
            "metadata": self.metadata
        }


class FinalReportGenerator:
    """
    Generate final reports with claim boundary verification.
    
    Usage:
        generator = FinalReportGenerator()
        generator.set_claim("SSS+")
        generator.add_tests([...])
        generator.add_files_changed([...])
        generator.add_evidence([...])
        
        report = generator.generate()
        markdown = generator.to_markdown(report)
        json_output = generator.to_json(report)
    """

    def __init__(self, evidence_ledger_path: Optional[Path] = None):
        """
        Initialize final report generator.
        
        Args:
            evidence_ledger_path: Path to ilma_evidence_ledger.json
        """
        self.logger = logging.getLogger(f"{__name__}.FinalReportGenerator")
        
        # Load evidence ledger if available
        self.evidence_ledger_path = evidence_ledger_path or Path("/root/.hermes/profiles/ilma/ilma_evidence_ledger.json")
        self.evidence_ledger: Dict[str, Any] = {}
        self._load_evidence_ledger()
        
        # Report data
        self.report = FinalReport(report_id=f"fr_{uuid.uuid4().hex[:12]}")
        
        self.logger.info(f"FinalReportGenerator initialized with {len(self.evidence_ledger)} evidence entries")

    def _load_evidence_ledger(self):
        """Load evidence ledger from JSON file."""
        try:
            if self.evidence_ledger_path.exists():
                with open(self.evidence_ledger_path, 'r') as f:
                    data = json.load(f)
                    # Ledger has 'evidence_records' as a list, not 'claims' as a dict
                    # Build a lookup dict: evidence_id -> entry for fast access
                    records = data.get("evidence_records", data.get("entries", []))
                    if isinstance(records, list):
                        self.evidence_ledger = {entry.get("evidence_id"): entry for entry in records if entry.get("evidence_id")}
                    else:
                        self.evidence_ledger = records
                self.logger.info(f"Loaded evidence ledger with {len(self.evidence_ledger)} entries")
            else:
                self.logger.warning(f"Evidence ledger not found at {self.evidence_ledger_path}")
        except Exception as e:
            self.logger.error(f"Failed to load evidence ledger: {e}")

    def set_claim(self, claim: str) -> "FinalReportGenerator":
        """
        Set the claim being verified.
        
        Args:
            claim: Claim string like "SSS", "SSS+", "production"
            
        Returns:
            Self for chaining
            
        Raises:
            ValueError: If claim is unsupported
        """
        # Check for contradictions
        if claim.lower() in CONTRADICTION_CLAIMS:
            raise ValueError(f"Contradiction claim '{claim}' is explicitly rejected. "
                           f"Supported claims: {VALID_CLAIM_TIERS}")
        
        # Check for invalid SSS tiers
        if claim.startswith("SSS"):
            # SSS+++ is not a valid tier
            if "+++" in claim:
                raise ValueError(f"Invalid SSS tier '{claim}'. Valid tiers: SSS, SSS+. "
                               f"+++ is not a valid qualifier.")
            if claim not in SSS_TIERS and claim != "SSS":
                raise ValueError(f"Invalid SSS tier '{claim}'. Valid tiers: SSS, SSS+")
        
        # Check if claim is in valid tiers
        if claim not in VALID_CLAIM_TIERS:
            # Check if it's a valid ledger entry
            if claim not in self.evidence_ledger:
                raise ValueError(f"Unsupported claim '{claim}'. "
                               f"Valid claims: {VALID_CLAIM_TIERS}. "
                               f"Or provide evidence ledger entry.")
        
        self.report.claim = claim
        return self

    def add_tests(self, tests: List[TestResult]) -> "FinalReportGenerator":
        """Add test results to the report."""
        self.report.tests.extend(tests)
        self._update_test_summary()
        return self

    def add_test(self, test_name: str, status: str, duration_ms: float = 0.0,
                 error_message: Optional[str] = None) -> "FinalReportGenerator":
        """Add a single test result."""
        self.report.tests.append(TestResult(
            test_name=test_name,
            status=status,
            duration_ms=duration_ms,
            error_message=error_message
        ))
        self._update_test_summary()
        return self

    def _update_test_summary(self):
        """Update test summary counts."""
        self.report.test_summary = {"passed": 0, "failed": 0, "skipped": 0}
        for test in self.report.tests:
            if test.status == "pass":
                self.report.test_summary["passed"] += 1
            elif test.status == "fail":
                self.report.test_summary["failed"] += 1
            elif test.status == "skip":
                self.report.test_summary["skipped"] += 1

    def add_files_changed(self, files: List[FileChange]) -> "FinalReportGenerator":
        """Add file change records to the report."""
        self.report.files_changed.extend(files)
        return self

    def add_file_changed(self, file_path: str, change_type: str,
                        lines_added: int = 0, lines_deleted: int = 0) -> "FinalReportGenerator":
        """Add a single file change record."""
        self.report.files_changed.append(FileChange(
            file_path=file_path,
            change_type=change_type,
            lines_added=lines_added,
            lines_deleted=lines_deleted
        ))
        return self

    def add_evidence(self, evidence_ids: List[str]) -> "FinalReportGenerator":
        """
        Add evidence IDs to the report.
        
        Args:
            evidence_ids: List of evidence IDs to include
        """
        for eid in evidence_ids:
            if eid not in self.report.evidence_ids:
                self.report.evidence_ids.append(eid)
                # Try to get evidence details from ledger
                if eid in self.evidence_ledger:
                    entry = self.evidence_ledger[eid]
                    self.report.evidence_refs.append(EvidenceRef(
                        evidence_id=eid,
                        title=entry.get("title", eid),
                        evidence_type=entry.get("type", "unknown"),
                        confidence=entry.get("confidence", "medium"),
                        verified=entry.get("verified", False)
                    ))
                else:
                    # Add placeholder if not in ledger
                    self.report.evidence_refs.append(EvidenceRef(
                        evidence_id=eid,
                        title=eid,
                        evidence_type="unknown",
                        confidence="unknown",
                        verified=False
                    ))
        return self

    def set_executive_summary(self, summary: str) -> "FinalReportGenerator":
        """Set the executive summary."""
        self.report.executive_summary = summary
        return self

    def set_decision(self, decision: FinalDecision, rationale: str = "") -> "FinalReportGenerator":
        """Set the final decision."""
        self.report.final_decision = decision
        self.report.decision_rationale = rationale
        return self

    def set_claim_boundary(self, boundary: ClaimBoundary, reason: str = "") -> "FinalReportGenerator":
        """Set the claim boundary."""
        self.report.claim_boundary = boundary
        self.report.claim_boundary_reason = reason
        return self

    def set_next_action(self, action: str, priority: str = "medium") -> "FinalReportGenerator":
        """Set the next action recommendation."""
        self.report.next_action = action
        self.report.next_action_priority = priority
        return self

    def add_metadata(self, key: str, value: Any) -> "FinalReportGenerator":
        """Add metadata to the report."""
        self.report.metadata[key] = value
        return self

    def _determine_claim_boundary(self) -> tuple:
        """
        Automatically determine claim boundary based on evidence.
        
        Returns:
            (ClaimBoundary, reason)
        """
        claim = self.report.claim
        
        # No claim set
        if not claim:
            return ClaimBoundary.UNSUPPORTED, "No claim specified"
        
        # Check if evidence exists for this claim
        if claim in self.evidence_ledger:
            entry = self.evidence_ledger[claim]
            if entry.get("verified", False):
                return ClaimBoundary.CAN_CLAIM, f"Claim '{claim}' is verified by evidence"
            else:
                return ClaimBoundary.PARTIAL_CLAIM, f"Claim '{claim}' has partial evidence"
        
        # SSS claims
        if claim in SSS_TIERS:
            # Check if tests passed
            if self.report.test_summary["failed"] > 0:
                return ClaimBoundary.CANNOT_CLAIM, "Test failures prevent SSS claim"
            if self.report.test_summary["passed"] == 0:
                return ClaimBoundary.CANNOT_CLAIM, "No passing tests for SSS claim"
            
            # Check evidence
            if len(self.report.evidence_ids) == 0:
                return ClaimBoundary.PARTIAL_CLAIM, "No evidence IDs provided for SSS claim"
            
            return ClaimBoundary.CAN_CLAIM, f"SSS claim supported by {len(self.report.evidence_ids)} evidence items"
        
        # Production claim
        if claim == "production":
            if self.report.test_summary["failed"] > 0:
                return ClaimBoundary.CANNOT_CLAIM, "Production claim requires all tests to pass"
            if len(self.report.evidence_ids) == 0:
                return ClaimBoundary.PARTIAL_CLAIM, "Production claim requires evidence"
            return ClaimBoundary.CAN_CLAIM, "Production-ready verified"
        
        return ClaimBoundary.UNSUPPORTED, f"Unknown claim: {claim}"

    def _determine_decision(self) -> tuple:
        """
        Automatically determine final decision.
        
        Returns:
            (FinalDecision, rationale)
        """
        boundary, _ = self._determine_claim_boundary()
        
        if boundary == ClaimBoundary.CANNOT_CLAIM:
            return FinalDecision.REJECTED, "Claim boundary analysis indicates claim cannot be made"
        
        if boundary == ClaimBoundary.UNSUPPORTED:
            return FinalDecision.REJECTED, "Claim is unsupported"
        
        if self.report.test_summary["failed"] > 0:
            return FinalDecision.CONDITIONAL, "Tests failed but claim boundary allows partial claim"
        
        if self.report.test_summary["passed"] > 0 and boundary == ClaimBoundary.CAN_CLAIM:
            return FinalDecision.APPROVED, "All requirements met for claim"
        
        return FinalDecision.PENDING, "Insufficient data for decision"

    def generate(self) -> FinalReport:
        """
        Generate the final report with automatic boundary/decision if not set.
        
        Returns:
            Complete FinalReport
        """
        # Auto-determine claim boundary if not set
        if self.report.claim_boundary == ClaimBoundary.UNSUPPORTED and self.report.claim:
            boundary, reason = self._determine_claim_boundary()
            if not self.report.claim_boundary_reason:
                self.report.claim_boundary = boundary
                self.report.claim_boundary_reason = reason
        
        # Auto-determine decision if not set
        if self.report.final_decision == FinalDecision.PENDING:
            decision, rationale = self._determine_decision()
            if not self.report.decision_rationale:
                self.report.final_decision = decision
                self.report.decision_rationale = rationale
        
        # Auto-generate executive summary if not set
        if not self.report.executive_summary:
            self.report.executive_summary = self._generate_executive_summary()
        
        self.logger.info(f"Generated final report: {self.report.report_id}")
        return self.report

    def _generate_executive_summary(self) -> str:
        """Generate executive summary text."""
        parts = []
        
        parts.append(f"Final Report for Claim: {self.report.claim or 'N/A'}")
        parts.append("")
        
        # Test summary
        ts = self.report.test_summary
        parts.append(f"Test Results: {ts['passed']} passed, {ts['failed']} failed, {ts['skipped']} skipped")
        
        # Files changed
        parts.append(f"Files Changed: {len(self.report.files_changed)}")
        
        # Evidence
        parts.append(f"Evidence Items: {len(self.report.evidence_ids)}")
        
        # Claim boundary
        if isinstance(self.report.claim_boundary, ClaimBoundary):
            parts.append(f"Claim Boundary: {self.report.claim_boundary.value}")
        else:
            parts.append(f"Claim Boundary: {self.report.claim_boundary}")
        
        # Decision
        if isinstance(self.report.final_decision, FinalDecision):
            parts.append(f"Final Decision: {self.report.final_decision.value}")
        else:
            parts.append(f"Final Decision: {self.report.final_decision}")
        
        return "\n".join(parts)

    def to_markdown(self, report: Optional[FinalReport] = None) -> str:
        """
        Render report as Markdown.
        
        Args:
            report: Report to render (uses self.report if None)
            
        Returns:
            Markdown string
        """
        if report is None:
            report = self.report
        
        lines = []
        
        # Header
        lines.append("# Final Report")
        lines.append("")
        lines.append(f"**Report ID:** {report.report_id}")
        lines.append(f"**Generated:** {datetime.fromtimestamp(report.created_at).strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # Executive Summary
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(report.executive_summary)
        lines.append("")
        
        # Claim
        if report.claim:
            lines.append("## Claim")
            lines.append("")
            lines.append(f"**Claim:** {report.claim}")
            lines.append("")
            lines.append(f"**Boundary:** {report.claim_boundary.value if isinstance(report.claim_boundary, ClaimBoundary) else report.claim_boundary}")
            lines.append("")
            lines.append(f"**Reason:** {report.claim_boundary_reason}")
            lines.append("")
        
        # Test Results
        lines.append("## Test Results")
        lines.append("")
        lines.append(f"Passed: {report.test_summary['passed']} | "
                    f"Failed: {report.test_summary['failed']} | "
                    f"Skipped: {report.test_summary['skipped']}")
        lines.append("")
        
        if report.tests:
            lines.append("### Test Details")
            lines.append("")
            for test in report.tests:
                status_icon = "✅" if test.status == "pass" else "❌" if test.status == "fail" else "⏭️"
                lines.append(f"{status_icon} **{test.test_name}** - {test.status} ({test.duration_ms:.2f}ms)")
                if test.error_message:
                    lines.append(f"   - Error: {test.error_message}")
            lines.append("")
        
        # Files Changed
        lines.append("## Files Changed")
        lines.append("")
        if report.files_changed:
            lines.append(f"{'File':<50} {'Type':<10} {'+':<6} {'-'}")
            lines.append("-" * 75)
            for fc in report.files_changed:
                lines.append(f"{fc.file_path:<50} {fc.change_type:<10} {fc.lines_added:<6} {fc.lines_deleted}")
            lines.append("")
        else:
            lines.append("No files changed.")
            lines.append("")
        
        # Evidence IDs
        lines.append("## Evidence IDs")
        lines.append("")
        if report.evidence_ids:
            for eid in report.evidence_ids:
                # Find evidence ref
                ref = next((r for r in report.evidence_refs if r.evidence_id == eid), None)
                if ref:
                    lines.append(f"- **{eid}**: {ref.title} ({ref.evidence_type}, {ref.confidence})")
                else:
                    lines.append(f"- {eid}")
            lines.append("")
        else:
            lines.append("No evidence IDs provided.")
            lines.append("")
        
        # Final Decision
        lines.append("## Final Decision")
        lines.append("")
        lines.append(f"**Decision:** {report.final_decision.value if isinstance(report.final_decision, FinalDecision) else report.final_decision}")
        lines.append("")
        lines.append(f"**Rationale:** {report.decision_rationale}")
        lines.append("")
        
        # Next Action
        if report.next_action:
            lines.append("## Next Action")
            lines.append("")
            lines.append(f"**Priority:** {report.next_action_priority}")
            lines.append("")
            lines.append(report.next_action)
            lines.append("")
        
        # Machine-Readable Summary
        lines.append("## Machine-Readable Summary")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(report.to_dict(), indent=2))
        lines.append("```")
        
        return "\n".join(lines)

    def to_json(self, report: Optional[FinalReport] = None) -> str:
        """
        Render report as JSON.
        
        Args:
            report: Report to render (uses self.report if None)
            
        Returns:
            JSON string
        """
        if report is None:
            report = self.report
        return json.dumps(report.to_dict(), indent=2)


# Shim for backwards compatibility
def generate_final_report(claim: str, tests: List[Dict], files_changed: List[Dict],
                          evidence_ids: List[str], **kwargs) -> FinalReport:
    """
    Generate a final report with the given data.
    
    This is a convenience function for simple report generation.
    
    Args:
        claim: The claim being verified (e.g., "SSS", "SSS+", "production")
        tests: List of test result dicts with keys: test_name, status, duration_ms, error_message
        files_changed: List of file change dicts with keys: file_path, change_type, lines_added, lines_deleted
        evidence_ids: List of evidence IDs
        **kwargs: Additional report parameters
        
    Returns:
        FinalReport object
    """
    generator = FinalReportGenerator()
    
    # Set claim
    try:
        generator.set_claim(claim)
    except ValueError as e:
        logger.error(f"Invalid claim: {e}")
        raise
    
    # Add tests
    for t in tests:
        generator.add_test(
            test_name=t.get("test_name", "unknown"),
            status=t.get("status", "unknown"),
            duration_ms=t.get("duration_ms", 0.0),
            error_message=t.get("error_message")
        )
    
    # Add files
    for f in files_changed:
        generator.add_file_changed(
            file_path=f.get("file_path", "unknown"),
            change_type=f.get("change_type", "modified"),
            lines_added=f.get("lines_added", 0),
            lines_deleted=f.get("lines_deleted", 0)
        )
    
    # Add evidence
    generator.add_evidence(evidence_ids)
    
    # Set optional params
    if "executive_summary" in kwargs:
        generator.set_executive_summary(kwargs["executive_summary"])
    if "next_action" in kwargs:
        generator.set_next_action(
            kwargs["next_action"],
            kwargs.get("next_action_priority", "medium")
        )
    if "decision" in kwargs:
        generator.set_decision(
            FinalDecision[kwargs["decision"].upper()] if isinstance(kwargs["decision"], str) else kwargs["decision"],
            kwargs.get("decision_rationale", "")
        )
    
    return generator.generate()


if __name__ == "__main__":
    # Demo usage
    print("=" * 60)
    print("ILMA Final Report Generator v1.0")
    print("=" * 60)
    
    # Example: Generate SSS+ report
    generator = FinalReportGenerator()
    
    generator.set_claim("SSS+")
    generator.add_test("test_lesson_memory_task_type.py::test_external_publish", "pass", 45.2)
    generator.add_test("test_lesson_memory_task_type.py::test_mark_reused_pass", "pass", 12.1)
    generator.add_test("test_lesson_memory_task_type.py::test_mark_reused_fail", "pass", 8.5)
    generator.add_file_changed("scripts/ilma_lesson_memory.py", "modified", 45, 12)
    generator.add_evidence(["ev_001", "ev_002", "ev_003"])
    generator.set_next_action("Continue with Phase 55 implementation", "high")
    
    report = generator.generate()
    
    print("\n[Markdown Report]")
    print("-" * 40)
    print(generator.to_markdown(report))
    
    print("\n[JSON Summary]")
    print("-" * 40)
    print(generator.to_json(report))
    
    print("\n[Demo: Invalid Claim Rejection]")
    try:
        generator2 = FinalReportGenerator()
        generator2.set_claim("SSS+++")
    except ValueError as e:
        print(f"Correctly rejected: {e}")
    
    try:
        generator3 = FinalReportGenerator()
        generator3.set_claim("production_false")
    except ValueError as e:
        print(f"Correctly rejected: {e}")