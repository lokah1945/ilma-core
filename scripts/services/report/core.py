#!/usr/bin/env python3
"""
ILMA Report Generator - Generate structured reports with evidence.

This module provides:
- ReportBuilder: Build structured reports
- EvidenceCollector: Collect and validate evidence
- FormatRenderer: Render reports in various formats

Usage:
    python ilma_report_generator.py --template analysis --output report.pdf
    python ilma_report_generator.py --from-evidence evidence.json --format markdown
    python ilma_report_generator.py --generate-dashboard --data metrics.json

Author: ILMA Team
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ReportFormat(Enum):
    """Output format for reports."""
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    PDF = "pdf"
    TEXT = "text"


class EvidenceType(Enum):
    """Types of evidence."""
    METRIC = "metric"
    LOG = "log"
    SCREENSHOT = "screenshot"
    CODE = "code"
    DOCUMENT = "document"
    TEST_RESULT = "test_result"
    AUDIT = "audit"


class ConfidenceLevel(Enum):
    """Evidence confidence levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Evidence:
    """Single piece of evidence."""
    evidence_id: str
    title: str
    description: str
    type: EvidenceType
    content: Any  # Flexible content type
    source: str
    timestamp: float = field(default_factory=time.time)
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    validated: bool = False
    validation_notes: Optional[str] = None


@dataclass
class Section:
    """Report section."""
    section_id: str
    title: str
    content: str
    level: int = 1  # Heading level
    evidence_refs: List[str] = field(default_factory=list)
    subsections: List['Section'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Report:
    """Complete report structure."""
    report_id: str
    title: str
    description: str
    author: str
    created_at: float = field(default_factory=time.time)
    sections: List[Section] = field(default_factory=list)
    evidence: Dict[str, Evidence] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0"


class EvidenceCollector:
    """
    Collects and validates evidence for reports.
    
    Features:
    - Multiple evidence type support
    - Validation checks
    - Evidence deduplication
    - Source tracking
    - Confidence scoring
    """

    def __init__(self):
        """Initialize evidence collector."""
        self.evidence: Dict[str, Evidence] = {}
        self.logger = logging.getLogger(f"{__name__}.EvidenceCollector")

    def collect(
        self,
        title: str,
        description: str,
        evidence_type: EvidenceType,
        content: Any,
        source: str,
        tags: Optional[List[str]] = None,
        confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    ) -> Evidence:
        """
        Collect a piece of evidence.
        
        Args:
            title: Evidence title
            description: Detailed description
            evidence_type: Type of evidence
            content: Evidence content (flexible type)
            source: Source system/path
            tags: Optional tags
            confidence: Confidence level
            
        Returns:
            Collected Evidence object
        """
        evidence_id = f"ev_{uuid.uuid4().hex[:12]}"
        
        evidence = Evidence(
            evidence_id=evidence_id,
            title=title,
            description=description,
            type=evidence_type,
            content=content,
            source=source,
            tags=tags or [],
            confidence=confidence
        )
        
        self.evidence[evidence_id] = evidence
        self.logger.info(f"Collected evidence: {evidence_id} ({evidence_type.value})")
        
        return evidence

    def validate(self, evidence_id: str) -> bool:
        """
        Validate a piece of evidence.
        
        Args:
            evidence_id: Evidence to validate
            
        Returns:
            True if validation passed
        """
        if evidence_id not in self.evidence:
            return False
        
        evidence = self.evidence[evidence_id]
        
        # Type-specific validation
        if evidence.type == EvidenceType.METRIC:
            valid = self._validate_metric(evidence)
        elif evidence.type == EvidenceType.TEST_RESULT:
            valid = self._validate_test_result(evidence)
        elif evidence.type == EvidenceType.CODE:
            valid = self._validate_code(evidence)
        else:
            valid = self._validate_generic(evidence)
        
        evidence.validated = valid
        evidence.validation_notes = "Validated" if valid else "Validation failed"
        
        return valid

    def _validate_metric(self, evidence: Evidence) -> bool:
        """Validate metric evidence."""
        if not isinstance(evidence.content, (int, float)):
            return False
        
        # Check for reasonable bounds
        value = evidence.content
        if value < -1e9 or value > 1e9:
            evidence.validation_notes = "Value out of reasonable range"
            return False
        
        return True

    def _validate_test_result(self, evidence: Evidence) -> bool:
        """Validate test result evidence."""
        if not isinstance(evidence.content, dict):
            return False
        
        required_keys = {"passed", "failed", "total"}
        return required_keys.issubset(evidence.content.keys())

    def _validate_code(self, evidence: Evidence) -> bool:
        """Validate code evidence."""
        if not isinstance(evidence.content, str):
            return False
        
        # Basic syntax check for common languages
        content = evidence.content
        if evidence.metadata.get("language") == "python":
            return "def " in content or "class " in content or "import " in content
        
        return len(content) > 0

    def _validate_generic(self, evidence: Evidence) -> bool:
        """Generic validation."""
        return evidence.content is not None and evidence.content != ""

    def add_evidence_to_report(self, report: Report) -> None:
        """Add all collected evidence to a report."""
        report.evidence.update(self.evidence)
        self.logger.info(f"Added {len(self.evidence)} evidence items to report")

    def get_evidence_summary(self) -> Dict[str, Any]:
        """Get summary of collected evidence."""
        by_type: Dict[str, int] = defaultdict(int)
        by_confidence: Dict[str, int] = defaultdict(int)
        validated_count = 0
        
        for ev in self.evidence.values():
            by_type[ev.type.value] += 1
            by_confidence[ev.confidence.value] += 1
            if ev.validated:
                validated_count += 1
        
        return {
            "total": len(self.evidence),
            "by_type": dict(by_type),
            "by_confidence": dict(by_confidence),
            "validated": validated_count,
            "unvalidated": len(self.evidence) - validated_count
        }


class ReportBuilder:
    """
    Builds structured reports from evidence and content.
    
    Features:
    - Hierarchical sections
    - Evidence linking
    - Auto-toc generation
    - Template support
    - Metadata management
    """

    def __init__(self, title: str, author: str, description: str = ""):
        """
        Initialize report builder.
        
        Args:
            title: Report title
            author: Report author
            description: Report description
        """
        self.report = Report(
            report_id=f"rpt_{uuid.uuid4().hex[:12]}",
            title=title,
            author=author,
            description=description
        )
        self.logger = logging.getLogger(f"{__name__}.ReportBuilder")

    def add_section(
        self,
        title: str,
        content: str,
        level: int = 1,
        evidence_refs: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Section:
        """
        Add a section to the report.
        
        Args:
            title: Section title
            content: Section content
            level: Heading level (1-6)
            evidence_refs: List of evidence IDs to reference
            metadata: Additional metadata
            
        Returns:
            Created Section object
        """
        section = Section(
            section_id=f"sec_{uuid.uuid4().hex[:8]}",
            title=title,
            content=content,
            level=level,
            evidence_refs=evidence_refs or [],
            metadata=metadata or {}
        )
        
        self.report.sections.append(section)
        self.logger.debug(f"Added section: {title}")
        
        return section

    def add_subsection(
        self,
        parent_section: Section,
        title: str,
        content: str,
        level: int = 2,
        evidence_refs: Optional[List[str]] = None
    ) -> Section:
        """Add a subsection to a parent section."""
        subsection = Section(
            section_id=f"sec_{uuid.uuid4().hex[:8]}",
            title=title,
            content=content,
            level=level,
            evidence_refs=evidence_refs or []
        )
        
        parent_section.subsections.append(subsection)
        return subsection

    def add_evidence(self, evidence: Evidence) -> None:
        """Add evidence to the report."""
        self.report.evidence[evidence.evidence_id] = evidence

    def generate_summary(self) -> Dict[str, Any]:
        """Generate report summary."""
        section_count = len(self.report.sections)
        
        # Count all subsections recursively
        def count_subsections(sections: List[Section]) -> int:
            count = 0
            for sec in sections:
                count += 1
                count += count_subsections(sec.subsections)
            return count
        
        total_sections = count_subsections(self.report.sections)
        
        return {
            "report_id": self.report.report_id,
            "title": self.report.title,
            "author": self.report.author,
            "created_at": datetime.fromtimestamp(self.report.created_at).isoformat(),
            "sections": section_count,
            "total_sections": total_sections,
            "evidence_count": len(self.report.evidence)
        }


class FormatRenderer:
    """
    Renders reports in various formats.
    
    Supported formats:
    - Markdown
    - HTML
    - JSON
    - Text
    """

    def __init__(self):
        """Initialize format renderer."""
        self.logger = logging.getLogger(f"{__name__}.FormatRenderer")

    def render(self, report: Report, format: ReportFormat) -> str:
        """
        Render a report in the specified format.
        
        Args:
            report: Report to render
            format: Output format
            
        Returns:
            Rendered report string
        """
        if format == ReportFormat.MARKDOWN:
            return self._render_markdown(report)
        elif format == ReportFormat.HTML:
            return self._render_html(report)
        elif format == ReportFormat.JSON:
            return self._render_json(report)
        elif format == ReportFormat.TEXT:
            return self._render_text(report)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _render_markdown(self, report: Report) -> str:
        """Render report as Markdown."""
        lines = []
        
        # Title
        lines.append(f"# {report.title}")
        lines.append("")
        lines.append(f"**Report ID:** {report.report_id}")
        lines.append(f"**Author:** {report.author}")
        lines.append(f"**Date:** {datetime.fromtimestamp(report.created_at).strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        if report.description:
            lines.append(f"*{report.description}*")
            lines.append("")
        
        # Table of contents
        lines.append("## Table of Contents")
        lines.append("")
        for i, section in enumerate(report.sections, 1):
            lines.append(f"{i}. [{section.title}](#{self._slugify(section.title)})")
            for j, subsection in enumerate(section.subsections, 1):
                lines.append(f"   {i}.{j}. [{subsection.title}](#{self._slugify(subsection.title)})")
        lines.append("")
        
        # Evidence section
        if report.evidence:
            lines.append("## Evidence")
            lines.append("")
            for ev_id, ev in report.evidence.items():
                lines.append(f"### {ev.title}")
                lines.append(f"**ID:** {ev_id}")
                lines.append(f"**Type:** {ev.type.value}")
                lines.append(f"**Confidence:** {ev.confidence.value}")
                lines.append(f"**Source:** {ev.source}")
                lines.append("")
                lines.append(ev.description)
                lines.append("")
                if isinstance(ev.content, (dict, list)):
                    lines.append("```")
                    lines.append(json.dumps(ev.content, indent=2))
                    lines.append("```")
                elif isinstance(ev.content, str) and len(ev.content) < 200:
                    lines.append(f"```\n{ev.content}\n```")
                lines.append("")
        
        # Sections
        for section in report.sections:
            lines.extend(self._render_section_markdown(section))
        
        return "\n".join(lines)

    def _render_section_markdown(self, section: Section) -> List[str]:
        """Render a section and its subsections as Markdown."""
        lines = []
        
        lines.append(f"{'#' * section.level} {section.title}")
        lines.append("")
        lines.append(section.content)
        lines.append("")
        
        if section.evidence_refs:
            lines.append("**Referenced Evidence:**")
            for ref in section.evidence_refs:
                lines.append(f"- {ref}")
            lines.append("")
        
        for subsection in section.subsections:
            lines.extend(self._render_section_markdown(subsection))
        
        return lines

    def _render_html(self, report: Report) -> str:
        """Render report as HTML."""
        html_parts = []
        html_parts.append("<!DOCTYPE html>")
        html_parts.append("<html>")
        html_parts.append("<head>")
        html_parts.append(f"<title>{report.title}</title>")
        html_parts.append("<style>")
        html_parts.append(self._get_html_styles())
        html_parts.append("</style>")
        html_parts.append("</head>")
        html_parts.append("<body>")
        
        # Header
        html_parts.append("<header>")
        html_parts.append(f"<h1>{report.title}</h1>")
        html_parts.append(f"<p class='meta'>Report ID: {report.report_id} | Author: {report.author} | Date: {datetime.fromtimestamp(report.created_at).strftime('%Y-%m-%d %H:%M:%S')}</p>")
        html_parts.append("</header>")
        
        # Content
        html_parts.append("<main>")
        
        for section in report.sections:
            html_parts.extend(self._render_section_html(section))
        
        html_parts.append("</main>")
        html_parts.append("</body>")
        html_parts.append("</html>")
        
        return "\n".join(html_parts)

    def _render_section_html(self, section: Section) -> List[str]:
        """Render a section as HTML."""
        html = []
        html.append(f"<section class='level-{section.level}'>")
        html.append(f"<h{section.level}>{section.title}</h{section.level}>")
        html.append(f"<p>{section.content}</p>")
        
        for subsection in section.subsections:
            html.extend(self._render_section_html(subsection))
        
        html.append("</section>")
        return html

    def _render_json(self, report: Report) -> str:
        """Render report as JSON."""
        data = {
            "report_id": report.report_id,
            "title": report.title,
            "description": report.description,
            "author": report.author,
            "created_at": report.created_at,
            "version": report.version,
            "metadata": report.metadata,
            "evidence": {
                eid: {
                    "evidence_id": ev.evidence_id,
                    "title": ev.title,
                    "description": ev.description,
                    "type": ev.type.value,
                    "content": ev.content,
                    "source": ev.source,
                    "timestamp": ev.timestamp,
                    "confidence": ev.confidence.value,
                    "tags": ev.tags,
                    "metadata": ev.metadata,
                    "validated": ev.validated
                }
                for eid, ev in report.evidence.items()
            },
            "sections": [self._section_to_dict(s) for s in report.sections]
        }
        
        return json.dumps(data, indent=2, default=str)

    def _section_to_dict(self, section: Section) -> Dict[str, Any]:
        """Convert section to dictionary."""
        return {
            "section_id": section.section_id,
            "title": section.title,
            "content": section.content,
            "level": section.level,
            "evidence_refs": section.evidence_refs,
            "subsections": [self._section_to_dict(s) for s in section.subsections],
            "metadata": section.metadata
        }

    def _render_text(self, report: Report) -> str:
        """Render report as plain text."""
        lines = []
        
        lines.append("=" * 70)
        lines.append(report.title.upper())
        lines.append("=" * 70)
        lines.append(f"Report ID: {report.report_id}")
        lines.append(f"Author: {report.author}")
        lines.append(f"Date: {datetime.fromtimestamp(report.created_at).strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        if report.description:
            lines.append(report.description)
            lines.append("")
        
        for section in report.sections:
            lines.extend(self._render_section_text(section, 0))
        
        return "\n".join(lines)

    def _render_section_text(self, section: Section, indent: int) -> List[str]:
        """Render a section as plain text."""
        lines = []
        prefix = "  " * indent
        
        lines.append(f"{prefix}{'#' * section.level} {section.title}")
        lines.append("")
        
        # Word wrap content
        content_lines = section.content.split("\n")
        for cline in content_lines:
            if len(cline) > 80:
                words = cline.split()
                line = ""
                for word in words:
                    if len(line) + len(word) > 80:
                        lines.append(f"{prefix}  {line}")
                        line = word
                    else:
                        line = f"{line} {word}".strip()
                if line:
                    lines.append(f"{prefix}  {line}")
            else:
                lines.append(f"{prefix}  {cline}")
        
        lines.append("")
        
        for subsection in section.subsections:
            lines.extend(self._render_section_text(subsection, indent + 1))
        
        return lines

    def _get_html_styles(self) -> str:
        """Get CSS styles for HTML output."""
        return """
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                   max-width: 900px; margin: 0 auto; padding: 20px; line-height: 1.6; }
            header { border-bottom: 2px solid #333; margin-bottom: 20px; }
            h1 { color: #333; }
            .meta { color: #666; font-size: 0.9em; }
            section { margin: 20px 0; }
            .level-1 { border-left: 4px solid #3498db; padding-left: 15px; }
            .level-2 { border-left: 2px solid #ddd; padding-left: 10px; }
            code { background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }
            pre { background: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; }
        """

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to URL-friendly slug."""
        return text.lower().replace(" ", "-").replace("_", "-")


def create_analysis_report(
    title: str,
    findings: List[Dict[str, Any]],
    author: str = "ILMA System"
) -> Report:
    """
    Create a standard analysis report from findings.
    
    Args:
        title: Report title
        findings: List of finding dictionaries
        author: Report author
        
    Returns:
        Complete Report object
    """
    builder = ReportBuilder(
        title=title,
        author=author,
        description=f"Analysis report with {len(findings)} findings"
    )
    
    # Summary section
    builder.add_section(
        title="Executive Summary",
        content=f"This report presents the findings from the analysis conducted on {datetime.now().strftime('%Y-%m-%d')}.",
        level=1
    )
    
    # Findings section
    finding_sections = []
    for i, finding in enumerate(findings, 1):
        section = builder.add_section(
            title=f"Finding {i}: {finding.get('title', 'Untitled')}",
            content=finding.get("description", ""),
            level=2,
            evidence_refs=finding.get("evidence_ids", []),
            metadata={"severity": finding.get("severity", "unknown")}
        )
        finding_sections.append(section)
    
    # Conclusions
    builder.add_section(
        title="Conclusions",
        content=f"Based on {len(findings)} findings, the following recommendations are provided.",
        level=1
    )
    
    return builder.report


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="ILMA Report Generator - Generate structured reports with evidence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --template analysis --output report.md --findings findings.json
  %(prog)s --from-evidence evidence.json --format markdown --output report.md
  %(prog)s --generate-dashboard --data metrics.json --format html
        """
    )
    
    parser.add_argument("--template", choices=["analysis", "audit", "summary", "custom"],
                       help="Report template to use")
    parser.add_argument("--title", help="Report title")
    parser.add_argument("--author", default="ILMA System", help="Report author")
    
    parser.add_argument("--from-evidence", help="JSON file with collected evidence")
    parser.add_argument("--findings", help="JSON file with findings")
    parser.add_argument("--data", help="JSON file with report data")
    
    parser.add_argument("--format", "-f", choices=["markdown", "html", "json", "text"],
                       default="markdown", help="Output format")
    parser.add_argument("--output", "-o", help="Output file path")
    
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger = logging.getLogger(__name__)
    
    try:
        # Interactive mode
        if args.interactive:
            print("ILMA Report Generator - Interactive Mode")
            print("=" * 50)
            
            title = input("Report title: ").strip() or "Analysis Report"
            author = input("Author: ").strip() or "ILMA System"
            
            report_builder = ReportBuilder(title=title, author=author)
            
            while True:
                print("\n1. Add section")
                print("2. Add evidence")
                print("3. Add subsection to last section")
                print("4. Finish and generate")
                choice = input("Choice: ").strip()
                
                if choice == "1":
                    sec_title = input("Section title: ").strip()
                    sec_content = input("Section content: ").strip()
                    level = int(input("Heading level (1-6): ").strip() or "1")
                    report_builder.add_section(sec_title, sec_content, level)
                    print("Section added.")
                    
                elif choice == "2":
                    ev_title = input("Evidence title: ").strip()
                    ev_desc = input("Evidence description: ").strip()
                    ev_type = input("Type (metric/log/code): ").strip() or "metric"
                    ev_content = input("Content: ").strip()
                    source = input("Source: ").strip() or "manual"
                    
                    try:
                        evidence_type = EvidenceType(ev_type.lower())
                    except ValueError:
                        evidence_type = EvidenceType.METRIC
                    
                    evidence = EvidenceCollector().collect(
                        title=ev_title,
                        description=ev_desc,
                        evidence_type=evidence_type,
                        content=ev_content,
                        source=source
                    )
                    report_builder.add_evidence(evidence)
                    print(f"Evidence added: {evidence.evidence_id}")
                    
                elif choice == "3":
                    print("Not implemented - add a section first")
                    
                elif choice == "4":
                    break
            
            report = report_builder.report
            fmt = ReportFormat(args.format)
            renderer = FormatRenderer()
            output = renderer.render(report, fmt)
            
            if args.output:
                with open(args.output, "w") as f:
                    f.write(output)
                print(f"Report written to {args.output}")
            else:
                print("\n" + output)
            
            return 0
        
        # File-based report generation
        report_data = {}
        
        if args.data:
            with open(args.data) as f:
                report_data = json.load(f)
        
        findings = []
        if args.findings:
            with open(args.findings) as f:
                findings = json.load(f)
        
        evidence_list = []
        if args.from_evidence:
            with open(args.from_evidence) as f:
                evidence_data = json.load(f)
                if isinstance(evidence_data, dict):
                    evidence_list = evidence_data.get("evidence", [])
                elif isinstance(evidence_data, list):
                    evidence_list = evidence_data
        
        # Build report
        title = args.title or report_data.get("title", "Analysis Report")
        author = args.author or report_data.get("author", "ILMA System")
        
        if args.template == "analysis" or (not args.template and (findings or evidence_list)):
            # Create analysis report
            builder = ReportBuilder(title=title, author=author)
            
            # Add sections
            builder.add_section(
                title="Summary",
                content=report_data.get("summary", "This report contains analysis findings."),
                level=1
            )
            
            # Add findings
            for i, finding in enumerate(findings, 1):
                builder.add_section(
                    title=f"Finding {i}: {finding.get('title', 'Untitled')}",
                    content=finding.get("description", ""),
                    level=2
                )
            
            # Add evidence
            if evidence_list:
                evidence_collector = EvidenceCollector()
                for ev_data in evidence_list:
                    evidence_collector.collect(
                        title=ev_data.get("title", "Evidence"),
                        description=ev_data.get("description", ""),
                        evidence_type=EvidenceType(ev_data.get("type", "metric")),
                        content=ev_data.get("content", ""),
                        source=ev_data.get("source", "unknown")
                    )
                
                report = builder.report
                for ev in evidence_collector.evidence.values():
                    builder.add_evidence(ev)
            else:
                report = builder.report
        else:
            # Create custom report
            builder = ReportBuilder(title=title, author=author)
            builder.add_section(
                title="Report",
                content=report_data.get("content", "Report content"),
                level=1
            )
            report = builder.report
        
        # Render report
        renderer = FormatRenderer()
        output_format = ReportFormat(args.format)
        rendered = renderer.render(report, output_format)
        
        if args.output:
            with open(args.output, "w") as f:
                f.write(rendered)
            logger.info(f"Report written to {args.output}")
            print(f"✓ Report generated: {args.output}")
        else:
            print(rendered)
        
        return 0
        
    except Exception as e:
        logger.exception("Fatal error")
        return 1


if __name__ == "__main__":
    exit(main())