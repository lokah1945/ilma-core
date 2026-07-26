#!/usr/bin/env python3
"""
Final Report Generator Tests
=============================
Tests: Blockers - report generation with claim verification.

Tests:
1. import old path (scripts/ilma_report_generator)
2. import new path (scripts.services.report.final_report_generator)
3. generate markdown
4. generate JSON
5. reject unsupported claim (SSS+++, production false claim)
6. include evidence IDs
"""
import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

import pytest


class TestFinalReportGeneratorImports:
    """Test that imports work from both old and new paths."""

    def test_import_old_path(self):
        """Import from deprecated shim should work with warning."""
        # Suppress deprecation warning for test
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from ilma_report_generator import FinalReportGenerator, generate_final_report
        
        assert FinalReportGenerator is not None
        assert generate_final_report is not None

    def test_import_new_path(self):
        """Import from new path should work directly."""
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
        
        assert FinalReportGenerator is not None
        assert FinalReport is not None
        assert TestResult is not None
        assert FileChange is not None
        assert EvidenceRef is not None
        assert ClaimBoundary is not None
        assert FinalDecision is not None
        assert generate_final_report is not None

    def test_import_from_init(self):
        """Import from services.report package __init__ should expose FinalReportGenerator."""
        from services.report import (
            FinalReportGenerator,
            FinalReport,
            FinalDecision,
            ClaimBoundary,
        )
        
        assert FinalReportGenerator is not None
        assert FinalReport is not None
        assert FinalDecision is not None
        assert ClaimBoundary is not None


class TestFinalReportGeneratorBasic:
    """Basic functionality tests."""

    @pytest.fixture
    def generator(self):
        """FinalReportGenerator instance."""
        from services.report.final_report_generator import FinalReportGenerator
        return FinalReportGenerator()

    def test_generator_initialization(self, generator):
        """Generator initializes with report_id."""
        assert generator.report is not None
        assert generator.report.report_id.startswith("fr_")

    def test_set_claim(self, generator):
        """Set valid claim."""
        generator.set_claim("SSS")
        assert generator.report.claim == "SSS"

    def test_set_claim_sss_plus(self, generator):
        """Set SSS+ claim."""
        generator.set_claim("SSS+")
        assert generator.report.claim == "SSS+"

    def test_set_claim_production(self, generator):
        """Set production claim."""
        generator.set_claim("production")
        assert generator.report.claim == "production"

    def test_reject_invalid_claim_sss_plus_plus_plus(self, generator):
        """SSS+++ is invalid and should be rejected."""
        with pytest.raises(ValueError) as exc_info:
            generator.set_claim("SSS+++")
        assert "+++ is not a valid qualifier" in str(exc_info.value)

    def test_reject_contradiction_production_false(self, generator):
        """production_false is a contradiction and should be rejected."""
        with pytest.raises(ValueError) as exc_info:
            generator.set_claim("production_false")
        assert "Contradiction claim" in str(exc_info.value)

    def test_reject_unsupported_claim(self, generator):
        """Unsupported claims should be rejected."""
        with pytest.raises(ValueError) as exc_info:
            generator.set_claim("made_up_claim")
        assert "Unsupported claim" in str(exc_info.value)


class TestFinalReportGeneratorMarkdown:
    """Test markdown generation."""

    @pytest.fixture
    def generator(self):
        from services.report.final_report_generator import FinalReportGenerator
        return FinalReportGenerator()

    def test_generate_markdown_basic(self, generator):
        """Generate basic markdown report."""
        generator.set_claim("SSS+")
        generator.add_test("test_one", "pass", 10.5)
        generator.add_test("test_two", "fail", 5.2, "AssertionError: expected 1 got 2")
        generator.add_file_changed("scripts/test.py", "modified", 10, 5)
        generator.add_evidence(["ev_001", "ev_002"])
        generator.set_next_action("Fix failing test", "high")
        
        report = generator.generate()
        markdown = generator.to_markdown(report)
        
        assert "# Final Report" in markdown
        assert "SSS+" in markdown
        assert "test_one" in markdown
        assert "test_two" in markdown
        assert "ev_001" in markdown
        assert "ev_002" in markdown
        assert "Files Changed" in markdown
        assert "Evidence IDs" in markdown

    def test_markdown_includes_executive_summary(self, generator):
        """Markdown includes executive summary."""
        generator.set_executive_summary("Test summary for claim SSS+")
        report = generator.generate()
        markdown = generator.to_markdown(report)
        
        assert "## Executive Summary" in markdown
        assert "Test summary for claim SSS+" in markdown

    def test_markdown_includes_test_results(self, generator):
        """Markdown includes test results with pass/fail indicators."""
        generator.add_test("test_pass", "pass", 10.0)
        generator.add_test("test_fail", "fail", 5.0, "Error")
        
        report = generator.generate()
        markdown = generator.to_markdown(report)
        
        assert "✅" in markdown  # pass icon
        assert "❌" in markdown  # fail icon

    def test_markdown_includes_machine_readable_json(self, generator):
        """Markdown includes machine-readable JSON summary."""
        generator.set_claim("SSS+")
        report = generator.generate()
        markdown = generator.to_markdown(report)
        
        assert "## Machine-Readable Summary" in markdown
        assert "```json" in markdown
        assert '"report_id"' in markdown


class TestFinalReportGeneratorJSON:
    """Test JSON generation."""

    @pytest.fixture
    def generator(self):
        from services.report.final_report_generator import FinalReportGenerator
        return FinalReportGenerator()

    def test_generate_json_basic(self, generator):
        """Generate basic JSON report."""
        generator.set_claim("SSS+")
        generator.add_test("test_one", "pass", 10.5)
        generator.add_evidence(["ev_001", "ev_002"])
        
        report = generator.generate()
        json_str = generator.to_json(report)
        
        data = json.loads(json_str)
        
        assert data["claim"] == "SSS+"
        assert len(data["tests"]) == 1
        assert data["tests"][0]["test_name"] == "test_one"
        assert len(data["evidence_ids"]) == 2

    def test_json_contains_all_required_sections(self, generator):
        """JSON contains all required sections."""
        generator.set_claim("production")
        generator.add_test("test_one", "pass")
        generator.add_file_changed("scripts/test.py", "modified")
        generator.add_evidence(["ev_001"])
        generator.set_next_action("Deploy", "high")
        
        report = generator.generate()
        data = report.to_dict()
        
        assert "executive_summary" in data
        assert "tests" in data
        assert "files_changed" in data
        assert "evidence_ids" in data
        assert "claim_boundary" in data
        assert "final_decision" in data
        assert "next_action" in data

    def test_json_is_machine_readable(self, generator):
        """JSON output is valid and machine-readable."""
        generator.set_claim("SSS")
        report = generator.generate()
        json_str = generator.to_json(report)
        
        # Should not raise
        data = json.loads(json_str)
        
        assert isinstance(data, dict)
        assert "report_id" in data
        assert "created_at" in data


class TestFinalReportGeneratorEvidence:
    """Test evidence handling."""

    @pytest.fixture
    def generator(self):
        from services.report.final_report_generator import FinalReportGenerator
        return FinalReportGenerator()

    def test_add_evidence_ids(self, generator):
        """Add evidence IDs to report."""
        generator.add_evidence(["ev_001", "ev_002", "ev_003"])
        
        assert len(generator.report.evidence_ids) == 3
        assert "ev_001" in generator.report.evidence_ids
        assert "ev_002" in generator.report.evidence_ids
        assert "ev_003" in generator.report.evidence_ids

    def test_evidence_deduplication(self, generator):
        """Same evidence ID added twice should not duplicate."""
        generator.add_evidence(["ev_001"])
        generator.add_evidence(["ev_001"])
        
        assert len(generator.report.evidence_ids) == 1

    def test_evidence_refs_created(self, generator):
        """Evidence refs are created when evidence is added."""
        generator.add_evidence(["ev_001"])
        
        assert len(generator.report.evidence_refs) == 1
        assert generator.report.evidence_refs[0].evidence_id == "ev_001"

    def test_include_evidence_ids_in_markdown(self, generator):
        """Markdown output includes evidence IDs."""
        generator.add_evidence(["ev_001", "ev_002"])
        
        report = generator.generate()
        markdown = generator.to_markdown(report)
        
        assert "## Evidence IDs" in markdown
        assert "ev_001" in markdown
        assert "ev_002" in markdown


class TestFinalReportGeneratorClaimBoundary:
    """Test claim boundary determination."""

    @pytest.fixture
    def generator(self):
        from services.report.final_report_generator import FinalReportGenerator
        return FinalReportGenerator()

    def test_boundary_for_sss_with_passing_tests(self, generator):
        """SSS claim with passing tests and evidence should be CAN_CLAIM."""
        generator.set_claim("SSS")
        generator.add_test("test_one", "pass")
        generator.add_evidence(["ev_001"])
        
        report = generator.generate()
        
        assert report.claim_boundary.value == "can_claim"

    def test_boundary_for_sss_with_failing_tests(self, generator):
        """SSS claim with failing tests should be CANNOT_CLAIM."""
        generator.set_claim("SSS")
        generator.add_test("test_one", "fail")
        generator.add_evidence(["ev_001"])
        
        report = generator.generate()
        
        assert report.claim_boundary.value == "cannot_claim"

    def test_boundary_for_production_with_failing_tests(self, generator):
        """Production claim with failing tests should be CANNOT_CLAIM."""
        generator.set_claim("production")
        generator.add_test("test_one", "fail")
        generator.add_evidence(["ev_001"])
        
        report = generator.generate()
        
        assert report.claim_boundary.value == "cannot_claim"

    def test_claim_boundary_reason_provided(self, generator):
        """Claim boundary reason is populated."""
        generator.set_claim("SSS")
        generator.add_test("test_one", "fail")
        
        report = generator.generate()
        
        assert report.claim_boundary_reason != ""


class TestFinalReportGeneratorDecision:
    """Test final decision determination."""

    @pytest.fixture
    def generator(self):
        from services.report.final_report_generator import FinalReportGenerator
        return FinalReportGenerator()

    def test_decision_approved_when_all_pass(self, generator):
        """Decision APPROVED when all tests pass and claim is valid."""
        generator.set_claim("SSS")
        generator.add_test("test_one", "pass")
        generator.add_evidence(["ev_001"])
        
        report = generator.generate()
        
        assert report.final_decision.value == "approved"

    def test_decision_rejected_when_tests_fail(self, generator):
        """Decision REJECTED when tests fail."""
        generator.set_claim("SSS")
        generator.add_test("test_one", "fail")
        generator.add_evidence(["ev_001"])
        
        report = generator.generate()
        
        assert report.final_decision.value == "rejected"

    def test_decision_rejected_for_unsupported_claim(self, generator):
        """Decision REJECTED for unsupported claim (SSS+++ raises during set_claim)."""
        # SSS+++ is rejected at set_claim time, not generate time
        # Test that ValueError is raised for unsupported claims
        with pytest.raises(ValueError) as exc_info:
            generator.set_claim("SSS+++")
        assert "+++ is not a valid qualifier" in str(exc_info.value)


class TestFinalReportGeneratorHelper:
    """Test helper function generate_final_report."""

    def test_generate_final_report_function(self):
        """generate_final_report helper function works."""
        from services.report.final_report_generator import generate_final_report
        
        report = generate_final_report(
            claim="SSS+",
            tests=[
                {"test_name": "test_one", "status": "pass", "duration_ms": 10.5},
                {"test_name": "test_two", "status": "fail", "duration_ms": 5.0, "error_message": "Failed"}
            ],
            files_changed=[
                {"file_path": "scripts/test.py", "change_type": "modified", "lines_added": 10, "lines_deleted": 5}
            ],
            evidence_ids=["ev_001", "ev_002"],
            next_action="Continue testing",
            next_action_priority="high"
        )
        
        assert report.claim == "SSS+"
        assert len(report.tests) == 2
        assert len(report.files_changed) == 1
        assert len(report.evidence_ids) == 2
        assert report.next_action == "Continue testing"
        assert report.next_action_priority == "high"


class TestFinalReportDataClasses:
    """Test report data classes."""

    def test_test_result_dataclass(self):
        """TestResult dataclass works."""
        from services.report.final_report_generator import TestResult
        
        tr = TestResult(test_name="test_one", status="pass", duration_ms=10.5)
        assert tr.test_name == "test_one"
        assert tr.status == "pass"
        assert tr.duration_ms == 10.5

    def test_file_change_dataclass(self):
        """FileChange dataclass works."""
        from services.report.final_report_generator import FileChange
        
        fc = FileChange(file_path="test.py", change_type="modified", lines_added=10, lines_deleted=5)
        assert fc.file_path == "test.py"
        assert fc.change_type == "modified"

    def test_final_report_to_dict(self):
        """FinalReport.to_dict() returns proper structure."""
        from services.report.final_report_generator import FinalReport
        
        report = FinalReport(report_id="test_123", claim="SSS")
        data = report.to_dict()
        
        assert data["report_id"] == "test_123"
        assert data["claim"] == "SSS"
        assert "executive_summary" in data
        assert "tests" in data
        assert "files_changed" in data


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])