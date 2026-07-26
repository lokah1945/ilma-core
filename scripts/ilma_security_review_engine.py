#!/usr/bin/env python3
"""
ILMA Security Review Engine - Security audit and vulnerability assessment.

This module provides:
- VulnerabilityScanner: Scan for security vulnerabilities
- ThreatDetector: Detect potential threats
- SecurityReportGenerator: Generate security reports

Usage:
    python ilma_security_review_engine.py --scan /path/to/code --severity high
    python ilma_security_review_engine.py --threats --rules custom_rules.json
    python ilma_security_review_engine.py --full-audit --output security_report.json

Author: ILMA Team
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Severity(Enum):
    """Vulnerability severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VulnerabilityCategory(Enum):
    """Categories of vulnerabilities."""
    INJECTION = "injection"
    AUTHENTICATION = "authentication"
    SENSITIVE_DATA = "sensitive_data"
    CRYPTOGRAPHY = "cryptography"
    CONFIGURATION = "configuration"
    INPUT_VALIDATION = "input_validation"
    ACCESS_CONTROL = "access_control"
    SECURITY_MISCONFIG = "security_misconfiguration"


@dataclass
class Vulnerability:
    """Represents a discovered vulnerability."""
    vuln_id: str
    title: str
    description: str
    severity: Severity
    category: VulnerabilityCategory
    file_path: str
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None
    confidence: float = 1.0
    false_positive_likelihood: float = 0.0
    remediation: Optional[str] = None
    references: List[str] = field(default_factory=list)


@dataclass
class Threat:
    """Represents a detected threat."""
    threat_id: str
    title: str
    description: str
    severity: Severity
    indicators: List[str]
    affected_assets: List[str]
    mitigation: Optional[str] = None
    detected_at: float = field(default_factory=time.time)


@dataclass
class SecurityCheck:
    """A security check definition."""
    check_id: str
    name: str
    description: str
    severity: Severity
    category: VulnerabilityCategory
    pattern: str  # Regex pattern
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None
    remediation_template: Optional[str] = None
    false_positive_patterns: List[str] = field(default_factory=list)


class VulnerabilityScanner:
    """
    Scans code for security vulnerabilities.
    
    Features:
    - Pattern-based detection
    - Multiple language support
    - Custom rule sets
    - False positive filtering
    - Severity assessment
    """

    # Built-in security checks
    DEFAULT_CHECKS: List[SecurityCheck] = [
        SecurityCheck(
            check_id="sql_injection",
            name="SQL Injection",
            description="Potential SQL injection vulnerability",
            severity=Severity.CRITICAL,
            category=VulnerabilityCategory.INJECTION,
            pattern=r'(execute|cursor\.execute|raw\(|query\s*\().*%(?:format|fstring)',
            cwe_id="CWE-89",
            owasp_category="A1:2017-Injection",
            remediation_template="Use parameterized queries instead of string formatting"
        ),
        SecurityCheck(
            check_id="command_injection",
            name="Command Injection",
            description="Potential OS command injection",
            severity=Severity.CRITICAL,
            category=VulnerabilityCategory.INJECTION,
            pattern=r'os\.system\(|subprocess\..*shell\s*=\s*True|subprocess\..*\(.*os\.environ',
            cwe_id="CWE-78",
            owasp_category="A1:2017-Injection",
            remediation_template="Avoid shell commands with user input; use subprocess with shell=False"
        ),
        SecurityCheck(
            check_id="eval_usage",
            name="Code Injection via eval()",
            description="Use of eval() with potential user input",
            severity=Severity.HIGH,
            category=VulnerabilityCategory.INJECTION,
            pattern=r'\beval\s*\(',
            cwe_id="CWE-95",
            remediation_template="Avoid eval(); use ast.literal_eval() for safe parsing"
        ),
        SecurityCheck(
            check_id="pickle_load",
            name="Insecure Deserialization",
            description="Use of pickle for deserialization",
            severity=Severity.HIGH,
            category=VulnerabilityCategory.INJECTION,
            pattern=r'pickle\.loads?\(',
            cwe_id="CWE-502",
            owasp_category="A8:2017-Insecure Deserialization",
            remediation_template="Use JSON or other safe serialization formats"
        ),
        SecurityCheck(
            check_id="hardcoded_secret",
            name="Hardcoded Secret",
            description="Potential hardcoded password or secret",
            severity=Severity.HIGH,
            category=VulnerabilityCategory.SENSITIVE_DATA,
            pattern=r'(password|secret|api_key|token)\s*=\s*["\'][^"\']{8,}["\']',
            cwe_id="CWE-798",
            owasp_category="A2:2017-Broken Authentication",
            remediation_template="Use environment variables or secure credential storage"
        ),
        SecurityCheck(
            check_id="weak_crypto",
            name="Weak Cryptographic Hash",
            description="Use of MD5 or SHA1 for security purposes",
            severity=Severity.MEDIUM,
            category=VulnerabilityCategory.CRYPTOGRAPHY,
            pattern=r'hashlib\.(md5|sha1)\s*\(',
            cwe_id="CWE-327",
            owasp_category="A6:2017-Security Misconfiguration",
            remediation_template="Use SHA-256 or stronger hashing algorithms"
        ),
        SecurityCheck(
            check_id="ssl_verify_disabled",
            name="Disabled SSL Verification",
            description="SSL/TLS certificate verification is disabled",
            severity=Severity.HIGH,
            category=VulnerabilityCategory.CONFIGURATION,
            pattern=r'verify\s*=\s*False|ssl._create_unverified_context',
            cwe_id="CWE-295",
            owasp_category="A6:2017-Security Misconfiguration",
            remediation_template="Enable SSL certificate verification"
        ),
        SecurityCheck(
            check_id="debug_true",
            name="Debug Mode Enabled",
            description="Debug mode is enabled in production",
            severity=Severity.MEDIUM,
            category=VulnerabilityCategory.CONFIGURATION,
            pattern=r'debug\s*=\s*True|DEBUG\s*=\s*True',
            cwe_id="CWE-489",
            remediation_template="Disable debug mode in production"
        ),
        SecurityCheck(
            check_id="path_traversal",
            name="Path Traversal",
            description="Potential path traversal vulnerability",
            severity=Severity.HIGH,
            category=VulnerabilityCategory.INPUT_VALIDATION,
            pattern=r'open\s*\(.*\+|os\.path\.join.*request\.(args|values|form)',
            cwe_id="CWE-22",
            owasp_category="A5:2017-Broken Access Control",
            remediation_template="Validate and sanitize all file paths"
        ),
        SecurityCheck(
            check_id="xss_reflection",
            name="Reflected XSS",
            description="Potential cross-site scripting vulnerability",
            severity=Severity.HIGH,
            category=VulnerabilityCategory.INJECTION,
            pattern=r'flask\.(render_template|send_file|make_response).*request\.(args|values|form)',
            cwe_id="CWE-79",
            owasp_category="A7:2017-Cross-Site Scripting (XSS)",
            remediation_template="Escape user input before rendering"
        ),
        SecurityCheck(
            check_id="yaml_load",
            name="YAML Deserialization",
            description="Use of unsafe yaml.load()",
            severity=Severity.HIGH,
            category=VulnerabilityCategory.INJECTION,
            pattern=r'yaml\.load\s*\(',
            cwe_id="CWE-502",
            remediation_template="Use yaml.safe_load() instead"
        ),
        SecurityCheck(
            check_id="jwt_none",
            name="JWT Algorithm None",
            description="JWT with algorithm 'none'",
            severity=Severity.CRITICAL,
            category=VulnerabilityCategory.AUTHENTICATION,
            pattern=r'algorithm\s*=\s*["\']none["\']',
            cwe_id="CWE-345",
            remediation_template="Use RS256 or ES256 algorithms"
        ),
    ]

    def __init__(self, checks: Optional[List[SecurityCheck]] = None):
        """
        Initialize vulnerability scanner.
        
        Args:
            checks: Custom security checks (uses defaults if not provided)
        """
        self.checks = checks or self.DEFAULT_CHECKS
        self.vulnerabilities: List[Vulnerability] = []
        self.scanned_files: Set[str] = set()
        self.logger = logging.getLogger(f"{__name__}.VulnerabilityScanner")

    def scan_file(self, file_path: Path, content: Optional[str] = None) -> List[Vulnerability]:
        """
        Scan a single file for vulnerabilities.
        
        Args:
            file_path: Path to file to scan
            content: File content (reads from disk if not provided)
            
        Returns:
            List of discovered vulnerabilities
        """
        findings = []
        
        try:
            if content is None:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            
            lines = content.split("\n")
            self.scanned_files.add(str(file_path))
            
            for check in self.checks:
                try:
                    pattern = re.compile(check.pattern, re.IGNORECASE | re.MULTILINE)
                    
                    for i, line in enumerate(lines, 1):
                        matches = pattern.finditer(line)
                        for match in matches:
                            # Check false positive patterns
                            if self._is_false_positive(check, line, match.group()):
                                continue
                            
                            vuln = Vulnerability(
                                vuln_id=f"vuln_{uuid.uuid4().hex[:10]}",
                                title=check.name,
                                description=check.description,
                                severity=check.severity,
                                category=check.category,
                                file_path=str(file_path),
                                line_number=i,
                                code_snippet=line.strip(),
                                cwe_id=check.cwe_id,
                                owasp_category=check.owasp_category,
                                confidence=0.85,
                                false_positive_likelihood=check.false_positive_patterns and 0.3 or 0.1,
                                remediation=check.remediation_template
                            )
                            findings.append(vuln)
                            
                except re.error as e:
                    self.logger.warning(f"Invalid regex pattern in check {check.check_id}: {e}")
                    
        except (IOError, PermissionError) as e:
            self.logger.warning(f"Could not scan {file_path}: {e}")
        
        return findings

    def scan_directory(
        self,
        directory: Path,
        extensions: Optional[List[str]] = None,
        exclude_dirs: Optional[Set[str]] = None
    ) -> List[Vulnerability]:
        """
        Recursively scan a directory for vulnerabilities.
        
        Args:
            directory: Directory to scan
            extensions: File extensions to scan (default: common code files)
            exclude_dirs: Directories to exclude
            
        Returns:
            List of all discovered vulnerabilities
        """
        extensions = extensions or {".py", ".js", ".ts", ".java", ".go", ".rb", ".php", ".cs"}
        exclude_dirs = exclude_dirs or {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build"}
        
        all_vulnerabilities = []
        
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix in extensions:
                # Check if in excluded directory
                if any(ex in path.parts for ex in exclude_dirs):
                    continue
                
                vulns = self.scan_file(path)
                all_vulnerabilities.extend(vulns)
        
        self.vulnerabilities = all_vulnerabilities
        self.logger.info(f"Scanned {len(self.scanned_files)} files, found {len(all_vulnerabilities)} vulnerabilities")
        
        return all_vulnerabilities

    def _is_false_positive(self, check: SecurityCheck, line: str, match: str) -> bool:
        """Check if a match is likely a false positive."""
        # Check against false positive patterns
        for fp_pattern in check.false_positive_patterns:
            if re.search(fp_pattern, line, re.IGNORECASE):
                return True
        
        # Common false positive heuristics
        if "#" in line:
            # Check if match is in a comment
            code_part = line.split("#")[0]
            if match not in code_part:
                return True
        
        # Check if value is a variable, not a literal
        if "password" in check.name.lower() or "secret" in check.name.lower():
            if match.strip().endswith(")"):  # Likely a function call, not assignment
                return True
        
        return False

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of scan results."""
        by_severity = {s.value: 0 for s in Severity}
        by_category = {c.value: 0 for c in VulnerabilityCategory}
        
        for vuln in self.vulnerabilities:
            by_severity[vuln.severity.value] += 1
            by_category[vuln.category.value] += 1
        
        return {
            "total_vulnerabilities": len(self.vulnerabilities),
            "scanned_files": len(self.scanned_files),
            "by_severity": by_severity,
            "by_category": by_category
        }


class ThreatDetector:
    """
    Detects potential security threats based on patterns and heuristics.
    
    Features:
    - Anomaly detection
    - Behavioral analysis
    - Threat pattern matching
    - Asset tracking
    """

    THREAT_PATTERNS: List[Dict[str, Any]] = [
        {
            "name": "Rapid Failed Logins",
            "description": "Multiple failed login attempts detected",
            "severity": Severity.MEDIUM,
            "indicator_pattern": r"failed.*login|authentication.*fail",
            "threshold": 5,
            "time_window": 60
        },
        {
            "name": "Suspicious File Access",
            "description": "Unusual file access patterns",
            "severity": Severity.HIGH,
            "indicator_pattern": r"(\.\./|\.\.\\|%2e%2e)",
            "threshold": 1
        },
        {
            "name": "Port Scanning Behavior",
            "description": "Sequential port access detected",
            "severity": Severity.MEDIUM,
            "indicator_pattern": r"port.*scan",
            "threshold": 10
        },
        {
            "name": "Data Exfiltration Risk",
            "description": "Large data transfer to external destination",
            "severity": Severity.HIGH,
            "indicator_pattern": r"upload.*external|send.*large.*data",
            "threshold": 1
        }
    ]

    def __init__(self):
        """Initialize threat detector."""
        self.threats: List[Threat] = []
        self.logger = logging.getLogger(f"{__name__}.ThreatDetector")

    def analyze_logs(self, log_content: str) -> List[Threat]:
        """
        Analyze log content for threats.
        
        Args:
            log_content: Log file content
            
        Returns:
            List of detected threats
        """
        detected_threats = []
        
        for pattern_def in self.THREAT_PATTERNS:
            pattern = re.compile(pattern_def["indicator_pattern"], re.IGNORECASE)
            matches = pattern.findall(log_content)
            
            if len(matches) >= pattern_def["threshold"]:
                threat = Threat(
                    threat_id=f"threat_{uuid.uuid4().hex[:10]}",
                    title=pattern_def["name"],
                    description=pattern_def["description"],
                    severity=pattern_def["severity"],
                    indicators=matches[:10],  # Limit to first 10
                    affected_assets=["system"]
                )
                detected_threats.append(threat)
        
        self.threats.extend(detected_threats)
        return detected_threats

    def detect_anomalies(self, baseline: Dict[str, Any], current: Dict[str, Any]) -> List[Threat]:
        """Detect anomalies between baseline and current metrics."""
        anomalies = []
        
        for key in baseline:
            if key not in current:
                continue
            
            baseline_val = baseline[key]
            current_val = current[key]
            
            # Simple anomaly detection
            if isinstance(baseline_val, (int, float)) and isinstance(current_val, (int, float)):
                if baseline_val > 0:
                    change_ratio = abs(current_val - baseline_val) / baseline_val
                    
                    if change_ratio > 0.5:  # 50% change
                        anomalies.append(Threat(
                            threat_id=f"threat_{uuid.uuid4().hex[:10]}",
                            title=f"Anomaly in {key}",
                            description=f"Metric {key} changed by {change_ratio:.1%}",
                            severity=Severity.MEDIUM,
                            indicators=[f"baseline: {baseline_val}", f"current: {current_val}"]
                        ))
        
        return anomalies


class SecurityReportGenerator:
    """
    Generates comprehensive security reports.
    
    Features:
    - Multiple output formats
    - Executive summaries
    - Technical details
    - Remediation recommendations
    - Compliance mapping
    """

    def __init__(self):
        """Initialize security report generator."""
        self.logger = logging.getLogger(f"{__name__}.SecurityReportGenerator")

    def generate(
        self,
        vulnerabilities: List[Vulnerability],
        threats: List[Threat],
        scan_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive security report.
        
        Args:
            vulnerabilities: List of vulnerabilities
            threats: List of threats
            scan_info: Scan metadata
            
        Returns:
            Complete report dictionary
        """
        report = {
            "report_id": f"sec_rpt_{uuid.uuid4().hex[:12]}",
            "generated_at": time.time(),
            "scan_info": scan_info,
            "executive_summary": self._generate_executive_summary(vulnerabilities, threats),
            "vulnerabilities": self._format_vulnerabilities(vulnerabilities),
            "threats": self._format_threats(threats),
            "remediation": self._generate_remediation_plan(vulnerabilities),
            "statistics": self._calculate_statistics(vulnerabilities, threats),
            "compliance": self._map_compliance(vulnerabilities)
        }
        
        return report

    def _generate_executive_summary(
        self,
        vulnerabilities: List[Vulnerability],
        threats: List[Threat]
    ) -> Dict[str, Any]:
        """Generate executive summary section."""
        critical_count = sum(1 for v in vulnerabilities if v.severity == Severity.CRITICAL)
        high_count = sum(1 for v in vulnerabilities if v.severity == Severity.HIGH)
        
        risk_level = "Critical" if critical_count > 0 else "High" if high_count > 0 else "Medium" if vulnerabilities else "Low"
        
        return {
            "overall_risk": risk_level,
            "total_vulnerabilities": len(vulnerabilities),
            "critical_vulnerabilities": critical_count,
            "high_vulnerabilities": high_count,
            "total_threats": len(threats),
            "recommendation": self._get_recommendation(risk_level)
        }

    def _get_recommendation(self, risk_level: str) -> str:
        """Get recommendation based on risk level."""
        recommendations = {
            "Critical": "Immediate action required. Address critical vulnerabilities before any deployment.",
            "High": "High priority. Schedule remediation within 1 week.",
            "Medium": "Medium priority. Schedule remediation within 30 days.",
            "Low": "Low priority. Address in normal maintenance cycle."
        }
        return recommendations.get(risk_level, "No immediate action required.")

    def _format_vulnerabilities(self, vulnerabilities: List[Vulnerability]) -> List[Dict[str, Any]]:
        """Format vulnerabilities for report."""
        return [
            {
                "id": v.vuln_id,
                "title": v.title,
                "description": v.description,
                "severity": v.severity.value,
                "category": v.category.value,
                "location": f"{v.file_path}:{v.line_number}" if v.line_number else v.file_path,
                "code_snippet": v.code_snippet,
                "cwe_id": v.cwe_id,
                "owasp_category": v.owasp_category,
                "confidence": f"{v.confidence:.0%}",
                "remediation": v.remediation
            }
            for v in vulnerabilities
        ]

    def _format_threats(self, threats: List[Threat]) -> List[Dict[str, Any]]:
        """Format threats for report."""
        return [
            {
                "id": t.threat_id,
                "title": t.title,
                "description": t.description,
                "severity": t.severity.value,
                "indicators": t.indicators,
                "affected_assets": t.affected_assets,
                "detected_at": t.detected_at
            }
            for t in threats
        ]

    def _generate_remediation_plan(self, vulnerabilities: List[Vulnerability]) -> List[Dict[str, Any]]:
        """Generate prioritized remediation plan."""
        # Group by severity
        by_severity = {s: [] for s in Severity}
        for vuln in vulnerabilities:
            by_severity[vuln.severity].append(vuln)
        
        plan = []
        
        for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
            for vuln in by_severity[severity]:
                if vuln.remediation:
                    plan.append({
                        "priority": severity.value.upper(),
                        "id": vuln.vuln_id,
                        "title": vuln.title,
                        "location": vuln.file_path,
                        "remediation": vuln.remediation,
                        "cwe_id": vuln.cwe_id
                    })
        
        return plan

    def _calculate_statistics(
        self,
        vulnerabilities: List[Vulnerability],
        threats: List[Threat]
    ) -> Dict[str, Any]:
        """Calculate security statistics."""
        return {
            "total_issues": len(vulnerabilities) + len(threats),
            "by_severity": {
                "critical": sum(1 for v in vulnerabilities if v.severity == Severity.CRITICAL),
                "high": sum(1 for v in vulnerabilities if v.severity == Severity.HIGH),
                "medium": sum(1 for v in vulnerabilities if v.severity == Severity.MEDIUM),
                "low": sum(1 for v in vulnerabilities if v.severity == Severity.LOW),
                "info": sum(1 for v in vulnerabilities if v.severity == Severity.INFO)
            },
            "by_category": self._count_by_category(vulnerabilities),
            "files_affected": len(set(v.file_path for v in vulnerabilities))
        }

    def _count_by_category(self, vulnerabilities: List[Vulnerability]) -> Dict[str, int]:
        """Count vulnerabilities by category."""
        counts = {}
        for vuln in vulnerabilities:
            cat = vuln.category.value
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def _map_compliance(self, vulnerabilities: List[Vulnerability]) -> Dict[str, Any]:
        """Map vulnerabilities to compliance frameworks."""
        owasp_top_10 = {
            "A1:2017-Injection": [],
            "A2:2017-Broken Authentication": [],
            "A3:2017-Sensitive Data Exposure": [],
            "A4:2017-XML External Entities (XXE)": [],
            "A5:2017-Broken Access Control": [],
            "A6:2017-Security Misconfiguration": [],
            "A7:2017-Cross-Site Scripting (XSS)": [],
            "A8:2017-Insecure Deserialization": [],
            "A9:2017-Using Components with Known Vulnerabilities": [],
            "A10:2017-Insufficient Logging & Monitoring": []
        }
        
        for vuln in vulnerabilities:
            if vuln.owasp_category and vuln.owasp_category in owasp_top_10:
                owasp_top_10[vuln.owasp_category].append(vuln.vuln_id)
        
        return {"owasp_top_10": owasp_top_10}

    def save_report(self, report: Dict[str, Any], output_path: str, format: str = "json") -> None:
        """Save report to file."""
        with open(output_path, "w") as f:
            if format == "json":
                json.dump(report, f, indent=2, default=str)
            elif format == "html":
                f.write(self._render_html(report))
        
        self.logger.info(f"Report saved to {output_path}")

    def _render_html(self, report: Dict[str, Any]) -> str:
        """Render report as HTML."""
        # Simplified HTML rendering
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Security Report</title></head>
        <body>
        <h1>Security Report: {report['report_id']}</h1>
        <h2>Executive Summary</h2>
        <p>Risk Level: {report['executive_summary']['overall_risk']}</p>
        <p>Total Vulnerabilities: {report['executive_summary']['total_vulnerabilities']}</p>
        </body>
        </html>
        """
        return html


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="ILMA Security Review Engine - Security audit and vulnerability assessment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --scan /root/.hermes/profiles/ilma/scripts --severity high
  %(prog)s --threats --logs /var/log/auth.log
  %(prog)s --full-audit --output security_report.json
        """
    )
    
    parser.add_argument("--scan", "-s", help="Directory to scan")
    parser.add_argument("--severity", choices=["critical", "high", "medium", "low", "all"],
                       default="all", help="Minimum severity to report")
    parser.add_argument("--extensions", nargs="+", help="File extensions to scan")
    
    parser.add_argument("--threats", "-t", action="store_true", help="Detect threats")
    parser.add_argument("--logs", "-l", help="Log file to analyze")
    
    parser.add_argument("--full-audit", "-a", action="store_true", help="Run full security audit")
    parser.add_argument("--output", "-o", help="Output file for report")
    parser.add_argument("--format", "-f", choices=["json", "html", "markdown"],
                       default="json", help="Output format")
    
    parser.add_argument("--json-output", "-j", action="store_true", help="JSON output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger = logging.getLogger(__name__)
    
    try:
        # Severity filter
        severity_filter = None
        if args.severity != "all":
            severity_filter = Severity(args.severity)
        
        # Initialize components
        scanner = VulnerabilityScanner()
        detector = ThreatDetector()
        report_gen = SecurityReportGenerator()
        
        vulnerabilities = []
        threats = []
        scan_info = {"scanned_at": time.time()}
        
        # Scan for vulnerabilities
        if args.scan:
            scan_path = Path(args.scan)
            if not scan_path.exists():
                logger.error(f"Scan path not found: {args.scan}")
                return 1
            
            logger.info(f"Scanning {args.scan}...")
            vulnerabilities = scanner.scan_directory(
                scan_path,
                extensions=set(args.extensions) if args.extensions else None
            )
            
            # Filter by severity
            if severity_filter:
                severity_order = [
                    Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, 
                    Severity.LOW, Severity.INFO
                ]
                min_idx = severity_order.index(severity_filter)
                allowed_severities = set(severity_order[:min_idx + 1])
                vulnerabilities = [v for v in vulnerabilities if v.severity in allowed_severities]
            
            scan_info["path"] = str(scan_path)
            scan_info["files_scanned"] = len(scanner.scanned_files)
        
        # Detect threats
        if args.threats:
            if args.logs:
                log_path = Path(args.logs)
                if log_path.exists():
                    with open(log_path) as f:
                        log_content = f.read()
                    threats = detector.analyze_logs(log_content)
                    scan_info["logs_analyzed"] = str(log_path)
            else:
                logger.warning("No logs specified for threat detection")
        
        # Full audit
        if args.full_audit:
            if not args.scan:
                logger.error("--scan required for full audit")
                return 1
            
            # Run both vulnerability scan and threat detection
            vulnerabilities = scanner.scan_directory(Path(args.scan))
            logger.info("Threat detection requires --logs option for detailed analysis")
        
        # Generate report
        if vulnerabilities or threats:
            report = report_gen.generate(vulnerabilities, threats, scan_info)
            
            if args.json_output or args.output:
                output = json.dumps(report, indent=2, default=str)
                
                if args.output:
                    report_gen.save_report(report, args.output, args.format)
                    logger.info(f"Report saved to {args.output}")
                    print(f"✓ Security report generated: {args.output}")
                else:
                    print(output)
            else:
                # Console output
                summary = report["executive_summary"]
                print("\n" + "=" * 60)
                print("SECURITY SCAN RESULTS")
                print("=" * 60)
                print(f"Risk Level: {summary['overall_risk']}")
                print(f"Total Vulnerabilities: {summary['total_vulnerabilities']}")
                print(f"Critical: {summary['critical_vulnerabilities']}")
                print(f"High: {summary['high_vulnerabilities']}")
                print(f"Total Threats: {summary['total_threats']}")
                print("\n" + summary['recommendation'])
                
                if vulnerabilities:
                    print("\nTop Vulnerabilities:")
                    for v in vulnerabilities[:5]:
                        print(f"  [{v.severity.value.upper()}] {v.title} - {v.file_path}:{v.line_number}")
        else:
            if not args.scan:
                parser.print_help()
            else:
                print("✓ No vulnerabilities found")
        
        return 0
        
    except Exception as e:
        logger.exception("Fatal error")
        return 1


if __name__ == "__main__":
    exit(main())