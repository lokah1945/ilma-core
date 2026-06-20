#!/usr/bin/env python3
"""
ILMA Specialist Validators v1.0
================================
8 LOCAL_RULE_BASED specialist validators.
Phase 46 - Autonomous Evolution Foundation.

Validators (all LOCAL_RULE_BASED, [SIMULATED]):
1. ArchitectValidator
2. QAValidator
3. SecurityValidator
4. EvidenceValidator
5. PerformanceValidator
6. TruthfulnessValidator
7. RegressionValidator
8. DocumentationValidator

NOT separate model agents - rule-based checks.
"""

from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ILMA paths
ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
WORKSPACE = ILMA_PROFILE


@dataclass
class ValidatorResult:
    """Result from a validator."""
    validator: str
    status: str  # PASS, WARN, FAIL
    score: float  # 0-100
    issues: List[str]
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validator": self.validator,
            "status": self.status,
            "score": self.score,
            "issues": self.issues,
            "recommendations": self.recommendations
        }


class ArchitectValidator:
    """Validates architectural soundness. [LOCAL_RULE_BASED]"""
    
    def validate(self, artifact: str, context: Optional[Dict[str, Any]] = None) -> ValidatorResult:
        issues = []
        recommendations = []
        context = context or {}
        
        # Check for modularity
        function_count = len(re.findall(r'def\s+\w+\s*\(', artifact))
        class_count = len(re.findall(r'class\s+\w+', artifact))
        
        if function_count == 0 and class_count == 0:
            issues.append("No function or class definitions found")
            recommendations.append("Add function/class definitions for modularity")
        
        if function_count > 20:
            issues.append(f"Too many functions ({function_count}) - consider splitting")
            recommendations.append("Break into smaller modules")
        
        # Check for docstrings
        has_docstrings = bool(re.search(r'""".*?"""', artifact, re.DOTALL))
        if not has_docstrings and function_count > 3:
            issues.append("Missing docstrings for public API")
            recommendations.append("Add docstrings to functions")
        
        score = 100 - (len(issues) * 15)
        status = "PASS" if len(issues) == 0 else "WARN" if len(issues) <= 2 else "FAIL"
        
        return ValidatorResult(
            validator="ArchitectValidator",
            status=status,
            score=max(0, score),
            issues=issues,
            recommendations=recommendations
        )


class QAValidator:
    """Validates test coverage and quality. [LOCAL_RULE_BASED]"""
    
    def validate(self, artifact: str, context: Optional[Dict[str, Any]] = None) -> ValidatorResult:
        issues = []
        recommendations = []
        context = context or {}
        
        # Check for test functions
        has_tests = bool(re.search(r'def test_\w+\(', artifact))
        has_assert = 'assert' in artifact.lower()
        
        if not has_tests:
            issues.append("No test functions found (def test_*)")
            recommendations.append("Add test functions with 'def test_*' pattern")
        
        if not has_assert:
            issues.append("No assert statements found")
            recommendations.append("Add assertions to validate behavior")
        
        # Check for error handling tests
        has_error_test = bool(re.search(r'assert.*raises|pytest\.raises', artifact))
        if not has_error_test:
            issues.append("No error handling tests found")
            recommendations.append("Add tests for edge cases and exceptions")
        
        score = 100 - (len(issues) * 20)
        status = "PASS" if len(issues) == 0 else "WARN" if len(issues) <= 1 else "FAIL"
        
        return ValidatorResult(
            validator="QAValidator",
            status=status,
            score=max(0, score),
            issues=issues,
            recommendations=recommendations
        )


class SecurityValidator:
    """Validates security patterns. [LOCAL_RULE_BASED]"""
    
    def validate(self, artifact: str, context: Optional[Dict[str, Any]] = None) -> ValidatorResult:
        issues = []
        recommendations = []
        context = context or {}
        
        dangerous_patterns = [
            (r'eval\s*\(', "Use of eval() - code injection risk"),
            (r'exec\s*\(', "Use of exec() - code injection risk"),
            (r'__import__\s*\(', "Dynamic import - potential exploit"),
            (r'os\.system\s*\(', "Use of os.system() - shell injection risk"),
            (r'subprocess.*shell\s*=\s*True', "Shell=True in subprocess - injection risk"),
            (r'SQL\s*\+', "SQL concatenation - injection risk"),
            (r'password\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded password detected"),
            (r'api[_-]?key\s*=\s*["\'][a-zA-Z0-9_-]{20,}["\']', "Hardcoded API key detected"),
            (r'secret\s*=\s*["\'][^"\']{16,}["\']', "Hardcoded secret detected"),
            (r'token\s*=\s*["\'][a-zA-Z0-9_-]{20,}["\']', "Hardcoded token detected"),
            (r'os\.popen\s*\(', "Use of os.popen() - shell injection risk"),
        ]
        
        for pattern, description in dangerous_patterns:
            if re.search(pattern, artifact, re.IGNORECASE):
                issues.append(description)
                recommendations.append(f"Replace dangerous pattern with safer alternative: {description}")
        
        # Check for input validation
        has_input_validation = bool(re.search(r'if.*is None|if.*==\s*["\']|validate|check.*input', artifact, re.IGNORECASE))
        if not has_input_validation:
            recommendations.append("Add input validation for user-facing functions")
        
        score = 100 - (len(issues) * 25)
        status = "PASS" if len(issues) == 0 else "FAIL" if len(issues) >= 2 else "WARN"
        
        return ValidatorResult(
            validator="SecurityValidator",
            status=status,
            score=max(0, score),
            issues=issues,
            recommendations=recommendations
        )


class EvidenceValidator:
    """Validates evidence claims. [LOCAL_RULE_BASED]"""
    
    def validate(self, artifact: str, context: Optional[Dict[str, Any]] = None) -> ValidatorResult:
        issues = []
        recommendations = []
        context = context or {}
        
        # Check for evidence IDs
        evidence_patterns = [
            r'ILMA-EVID-\d{8}-[A-Z]+-\d{3}',
            r'EVID-\d{8}-[A-Z]+-\d{3}',
        ]
        
        found_evidence = []
        for pattern in evidence_patterns:
            found_evidence.extend(re.findall(pattern, artifact, re.IGNORECASE))
        
        if not found_evidence:
            issues.append("No evidence IDs found in artifact")
            recommendations.append("Add evidence IDs (format: ILMA-EVID-YYYYMMDD-PHASE-CAP-001)")
        
        # Check for unique evidence IDs
        if found_evidence:
            unique_ids = set(found_evidence)
            if len(unique_ids) < len(found_evidence):
                issues.append(f"Duplicate evidence IDs found: {len(found_evidence) - len(unique_ids)} duplicates")
                recommendations.append("Ensure each evidence ID is unique")
        
        # Check for date format
        for eid in found_evidence[:3]:
            if not re.search(r'\d{8}', eid):
                issues.append(f"Invalid evidence ID format: {eid}")
                recommendations.append("Evidence ID should contain date (YYYYMMDD)")
        
        score = 100 - (len(issues) * 20)
        status = "PASS" if len(issues) == 0 else "WARN"
        
        return ValidatorResult(
            validator="EvidenceValidator",
            status=status,
            score=max(0, score),
            issues=issues,
            recommendations=recommendations
        )


class PerformanceValidator:
    """Validates performance characteristics. [LOCAL_RULE_BASED]"""
    
    def validate(self, artifact: str, context: Optional[Dict[str, Any]] = None) -> ValidatorResult:
        issues = []
        recommendations = []
        context = context or {}
        
        # Check for infinite loop patterns
        has_infinite_loop = False
        
        # Simple check for while True without break
        if re.search(r'while\s+True\s*:', artifact):
            if not re.search(r'while\s+True.*?break', artifact, re.DOTALL):
                issues.append("Potential infinite loop: while True without break")
                has_infinite_loop = True
        
        # Check for recursion without base case
        function_defs = re.findall(r'def\s+(\w+).*?(?=\ndef|\Z)', artifact, re.DOTALL)
        for func in function_defs:
            if 'recursion' in func.lower() or 'fib' in func.lower():
                if 'if' not in func or 'return' not in func:
                    issues.append(f"Potential infinite recursion in {func[:20]}")
        
        # Check for unbounded operations
        if re.search(r'for\s+\w+\s+in\s+range\s*\(\s*\):', artifact):
            recommendations.append("Verify range() bounds are reasonable for production use")
        
        # Check for large data structures
        if re.search(r'list\s*=\s*\[\s*\*\s*range', artifact):
            issues.append("Large list comprehension may cause memory issues")
            recommendations.append("Use generator expression or lazy evaluation")
        
        score = 100 - (len(issues) * 25)
        status = "PASS" if len(issues) == 0 else "WARN"
        
        return ValidatorResult(
            validator="PerformanceValidator",
            status=status,
            score=max(0, score),
            issues=issues,
            recommendations=recommendations
        )


class TruthfulnessValidator:
    """Validates truthfulness and no overclaims. [LOCAL_RULE_BASED]"""
    
    def validate(self, artifact: str, context: Optional[Dict[str, Any]] = None) -> ValidatorResult:
        issues = []
        recommendations = []
        context = context or {}
        
        # Check for overclaim patterns
        overclaim_patterns = [
            (r'100%\s*(?:secure|perfect|guarantee)', "Absolute security/quality claim without evidence"),
            (r'always\s*(?:works|success|fail)', "Absolute behavior claim"),
            (r'proven\s*(?:best|fastest|most|optimal)', "Unsubstantiated superlative"),
            (r'no\s*(?:bug|error|issue|problem|exception)', "Absolute negative claim"),
            (r'guaranteed\s*(?:to\s+)?(?:work|succeed|fix)', "Guarantee without empirical validation"),
            (r'universal\s*(?:solution|fix|answer)', "Universal claim - likely overstatement"),
            (r'impossible\s*(?:to\s+)?(?:break|fail|hack)', "Absolute impossibility claim"),
            (r'never\s*(?:fails|breaks|errors)', "Absolute 'never' claim"),
        ]
        
        for pattern, description in overclaim_patterns:
            if re.search(pattern, artifact, re.IGNORECASE):
                issues.append(f"Overclaim detected: {description}")
                recommendations.append("Remove absolute claim or provide empirical evidence")
        
        # Check for testable claims
        has_claims = len(issues) > 0
        has_evidence = bool(re.search(r'ILMA-EVID-|tested|validated|verified|measured', artifact, re.IGNORECASE))
        
        if has_claims and not has_evidence:
            issues.append("Overclaims present without supporting evidence")
            recommendations.append("Add evidence IDs for verifiable claims")
        
        score = 100 - (len(issues) * 20)
        status = "PASS" if len(issues) == 0 else "WARN"
        
        return ValidatorResult(
            validator="TruthfulnessValidator",
            status=status,
            score=max(0, score),
            issues=issues,
            recommendations=recommendations
        )


class RegressionValidator:
    """Validates no regression in existing functionality. [LOCAL_RULE_BASED]"""
    
    def validate(self, artifact: str, context: Optional[Dict[str, Any]] = None) -> ValidatorResult:
        issues = []
        recommendations = []
        context = context or {}
        
        # Check for imports
        imports = re.findall(r'^import\s+\w+|^from\s+\w+\s+import', artifact, re.MULTILINE)
        
        if not imports:
            recommendations.append("No imports found - verify this is intentional")
        
        # Check for backward compatibility markers
        has_version_check = bool(re.search(r'version|__version__|compat', artifact, re.IGNORECASE))
        has_deprecated = bool(re.search(r'deprecated|deprecated|Deprecation', artifact, re.IGNORECASE))
        
        if has_deprecated:
            recommendations.append("Deprecated code detected - plan migration path")
        
        # Check for breaking changes patterns
        breaking_patterns = [
            (r'del\s+\w+', "Deletion of symbols - potential breaking change"),
            (r'raise\s+.*(?:Error|Exception)', "Raising exceptions - may break callers"),
        ]
        
        for pattern, description in breaking_patterns:
            if re.search(pattern, artifact):
                issues.append(description)
        
        score = 100 - (len(issues) * 15)
        status = "PASS" if len(issues) == 0 else "WARN"
        
        return ValidatorResult(
            validator="RegressionValidator",
            status=status,
            score=max(0, score),
            issues=issues,
            recommendations=recommendations
        )


class DocumentationValidator:
    """Validates documentation quality. [LOCAL_RULE_BASED]"""
    
    def validate(self, artifact: str, context: Optional[Dict[str, Any]] = None) -> ValidatorResult:
        issues = []
        recommendations = []
        context = context or {}
        
        # Check for README/docstring
        has_docstring = bool(re.search(r'""".*?"""', artifact, re.DOTALL))
        has_comment = '#' in artifact
        
        if not has_docstring:
            issues.append("No module-level docstring found")
            recommendations.append("Add module docstring explaining purpose")
        
        if not has_comment:
            issues.append("No comments found")
            recommendations.append("Add comments explaining non-obvious logic")
        
        # Check for function docstrings
        functions = re.findall(r'def\s+(\w+)\s*\([^)]*\):', artifact)
        if functions:
            funcs_with_docstrings = len(re.findall(r'def\s+\w+[^:]*:\s*"""', artifact))
            if funcs_with_docstrings < len(functions) * 0.5:
                issues.append(f"Only {funcs_with_docstrings}/{len(functions)} functions have docstrings")
                recommendations.append("Add docstrings to public functions")
        
        # Check for clear structure
        has_headers = bool(re.search(r'^#{1,3}\s+\w+', artifact, re.MULTILINE))
        if not has_headers and len(artifact) > 500:
            recommendations.append("Add section headers for better navigation")
        
        score = 100 - (len(issues) * 15)
        status = "PASS" if len(issues) == 0 else "WARN"
        
        return ValidatorResult(
            validator="DocumentationValidator",
            status=status,
            score=max(0, score),
            issues=issues,
            recommendations=recommendations
        )


# === SPECIALIST VALIDATOR ORCHESTRATOR ===

class SpecialistValidatorOrchestrator:
    """Orchestrates all specialist validators."""
    
    def __init__(self):
        self.validators = {
            "Architect": ArchitectValidator(),
            "QA": QAValidator(),
            "Security": SecurityValidator(),
            "Evidence": EvidenceValidator(),
            "Performance": PerformanceValidator(),
            "Truthfulness": TruthfulnessValidator(),
            "Regression": RegressionValidator(),
            "Documentation": DocumentationValidator()
        }
    
    def validate_all(
        self,
        artifact: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, ValidatorResult]:
        """Run all validators."""
        results = {}
        for name, validator in self.validators.items():
            try:
                results[name] = validator.validate(artifact, context)
            except Exception as e:
                results[name] = ValidatorResult(
                    validator=name,
                    status="FAIL",
                    score=0,
                    issues=[f"Validator error: {str(e)}"],
                    recommendations=[]
                )
        return results
    
    def get_summary(self, results: Dict[str, ValidatorResult]) -> Dict[str, Any]:
        """Summarize validation results."""
        passed = sum(1 for r in results.values() if r.status == "PASS")
        warned = sum(1 for r in results.values() if r.status == "WARN")
        failed = sum(1 for r in results.values() if r.status == "FAIL")
        
        return {
            "total": len(results),
            "passed": passed,
            "warned": warned,
            "failed": failed,
            "overall_score": sum(r.score for r in results.values()) / max(len(results), 1)
        }


# === DEMO ===

def run_demo():
    """Run specialist validators demo."""
    print("=" * 60)
    print("ILMA Specialist Validators v1.0")
    print("=" * 60)
    
    orchestrator = SpecialistValidatorOrchestrator()
    
    test_artifact = '''# Good Python module

"""Example module with proper structure."""

import json
from typing import List, Optional

def factorial(n: int) -> int:
    """Calculate factorial of n."""
    if n < 0:
        raise ValueError("Must be non-negative")
    if n <= 1:
        return 1
    return n * factorial(n - 1)

def test_factorial():
    """Test factorial function."""
    assert factorial(0) == 1
    assert factorial(5) == 120
    # Evidence: ILMA-EVID-20260510-VALID-001

# Good code with proper structure
# Always validate input
'''
    
    print("\n[Validating artifact...]")
    results = orchestrator.validate_all(test_artifact)
    
    for name, result in results.items():
        status_icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[result.status]
        print(f"\n{status_icon} {result.validator}")
        print(f"   Status: {result.status}")
        print(f"   Score: {result.score:.0f}/100")
        if result.issues:
            for issue in result.issues[:2]:
                print(f"   Issue: {issue[:60]}...")
    
    summary = orchestrator.get_summary(results)
    print("\n" + "=" * 40)
    print("SUMMARY")
    print(f"Passed: {summary['passed']}/{summary['total']}")
    print(f"Overall Score: {summary['overall_score']:.0f}/100")


if __name__ == "__main__":
    run_demo()