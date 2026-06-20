#!/usr/bin/env python3
"""
ILMA Code Analyst
================
Static analysis, code quality scoring, and pattern detection.

Classes: StaticAnalyzer, QualityScorer, PatternDetector

Usage:
    python3 ilma_code_analyst.py --analyze /path/to/file.py
    python3 ilma_code_analyst.py --score /path/to/project
    python3 ilma_code_analyst.py --detect-patterns /path/to/file.py

Author: ILMA v5.0
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import logging
import os
import re
import sys
import tokenize
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CodeAnalyst")


# =============================================================================
# ENUMS AND DATA STRUCTURES
# =============================================================================

class IssueSeverity(Enum):
    """Issue severity levels."""
    BLOCKER = "blocker"
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


class CodeSmell(Enum):
    """Code smell types."""
    LONG_METHOD = "long_method"
    LARGE_CLASS = "large_class"
    DUPLICATE_CODE = "duplicate_code"
    DEAD_CODE = "dead_code"
    SPAGHETTI_CODE = "spaghetti_code"
    GOD_CLASS = "god_class"
    FEATURE_ENVY = "feature_envy"
    DATA_CLASS = "data_class"
    COMPLEX_CONDITIONAL = "complex_conditional"
    NESTED_DEPTH = "nested_depth"


@dataclass
class CodeIssue:
    """Code issue representation."""
    line: int
    column: Optional[int]
    severity: IssueSeverity
    category: str
    message: str
    code_snippet: Optional[str] = None
    suggestion: Optional[str] = None
    rule_id: Optional[str] = None


@dataclass
class QualityMetrics:
    """Code quality metrics."""
    maintainability_index: float
    halstead_volume: float
    cyclomatic_complexity: float
    lines_of_code: int
    lines_of_comments: int
    comment_ratio: float
    cognitive_complexity: float


@dataclass
class PatternMatch:
    """Pattern match result."""
    pattern_id: str
    pattern_name: str
    line: int
    matched_text: str
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# STATIC ANALYZER CLASS
# =============================================================================

class StaticAnalyzer:
    """
    Static code analysis with support for Python and other languages.
    
    Performs syntax checking, style analysis, and best practices validation.
    """
    
    PYTHON_RULES = {
        "S001": {
            "name": "Line too long",
            "severity": IssueSeverity.MINOR,
            "pattern": r".{121,}",
            "message": "Line exceeds 120 characters"
        },
        "S002": {
            "name": "Missing docstring",
            "severity": IssueSeverity.INFO,
            "pattern": r"^class\s+\w+|^def\s+\w+",
            "message": "Class/function should have a docstring"
        },
        "S003": {
            "name": "Trailing whitespace",
            "severity": IssueSeverity.MINOR,
            "pattern": r"[ \t]+$",
            "message": "Trailing whitespace detected"
        },
        "S004": {
            "name": "TODO/FIXME comment",
            "severity": IssueSeverity.INFO,
            "pattern": r"#\s*(TODO|FIXME|HACK|XXX)",
            "message": "Unresolved TODO/FIXME comment"
        },
        "S005": {
            "name": "Hardcoded password",
            "severity": IssueSeverity.CRITICAL,
            "pattern": r"password\s*=\s*['\"][^'\"]+['\"]",
            "message": "Hardcoded password detected"
        }
    }
    
    def __init__(self):
        self.issues: List[CodeIssue] = []
        self.current_file: Optional[str] = None
        logger.info("StaticAnalyzer initialized")
    
    def analyze_file(self, filepath: str) -> List[CodeIssue]:
        """Analyze a file for issues."""
        self.issues = []
        self.current_file = filepath
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Determine language and analyze
            if filepath.endswith(".py"):
                self._analyze_python(content, filepath)
            else:
                self._analyze_generic(content)
            
            logger.info(f"Analysis complete: {len(self.issues)} issues in {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to analyze {filepath}: {e}")
        
        return self.issues
    
    def _analyze_python(self, content: str, filepath: str) -> None:
        """Analyze Python source code."""
        lines = content.split("\n")
        
        # Check each line against rules
        for i, line in enumerate(lines, 1):
            for rule_id, rule in self.PYTHON_RULES.items():
                if re.search(rule["pattern"], line):
                    self.issues.append(CodeIssue(
                        line=i,
                        column=None,
                        severity=rule["severity"],
                        category="style",
                        message=rule["message"],
                        rule_id=rule_id
                    ))
        
        # AST-based analysis
        try:
            tree = ast.parse(content)
            self._analyze_ast(tree, content, lines)
        except SyntaxError as e:
            self.issues.append(CodeIssue(
                line=e.lineno or 0,
                column=e.offset,
                severity=IssueSeverity.BLOCKER,
                category="syntax",
                message=f"Syntax error: {e.msg}"
            ))
    
    def _analyze_ast(self, tree: ast.AST, content: str, lines: List[str]) -> None:
        """Perform AST-based analysis."""
        
        # Check for long functions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_lines = node.end_lineno - node.lineno + 1 if hasattr(node, 'end_lineno') else 0
                
                if func_lines > 50:
                    self.issues.append(CodeIssue(
                        line=node.lineno,
                        column=None,
                        severity=IssueSeverity.MAJOR,
                        category="design",
                        message=f"Function '{node.name}' has {func_lines} lines (exceeds 50)",
                        suggestion="Consider breaking into smaller functions"
                    ))
                
                # Check for high cyclomatic complexity
                complexity = self._calculate_cyclomatic_complexity(node)
                if complexity > 10:
                    self.issues.append(CodeIssue(
                        line=node.lineno,
                        column=None,
                        severity=IssueSeverity.MAJOR,
                        category="complexity",
                        message=f"Function '{node.name}' has cyclomatic complexity of {complexity} (exceeds 10)",
                        suggestion="Consider simplifying the function logic"
                    ))
        
        # Check for large classes
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_lines = node.end_lineno - node.lineno + 1 if hasattr(node, 'end_lineno') else 0
                
                if class_lines > 300:
                    self.issues.append(CodeIssue(
                        line=node.lineno,
                        column=None,
                        severity=IssueSeverity.MAJOR,
                        category="design",
                        message=f"Class '{node.name}' has {class_lines} lines (exceeds 300)",
                        suggestion="Consider splitting into smaller classes"
                    ))
                
                # Count methods
                methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                if len(methods) > 20:
                    self.issues.append(CodeIssue(
                        line=node.lineno,
                        column=None,
                        severity=IssueSeverity.MAJOR,
                        category="design",
                        message=f"Class '{node.name}' has {len(methods)} methods (exceeds 20)",
                        suggestion="Consider splitting class responsibilities"
                    ))
    
    def _calculate_cyclomatic_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity of a function."""
        complexity = 1
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += sum(1 for _ in child.values)
        
        return complexity
    
    def _analyze_generic(self, content: str) -> None:
        """Generic line-by-line analysis for non-Python files."""
        lines = content.split("\n")
        
        for i, line in enumerate(lines, 1):
            # Check for long lines
            if len(line) > 120:
                self.issues.append(CodeIssue(
                    line=i,
                    column=None,
                    severity=IssueSeverity.MINOR,
                    category="style",
                    message=f"Line exceeds 120 characters ({len(line)} chars)"
                ))
            
            # Check for trailing whitespace
            if line.rstrip() != line:
                self.issues.append(CodeIssue(
                    line=i,
                    column=None,
                    severity=IssueSeverity.INFO,
                    category="style",
                    message="Trailing whitespace"
                ))
    
    def analyze_project(self, project_path: str) -> Dict[str, Any]:
        """Analyze an entire project."""
        project_path = Path(project_path)
        
        all_issues = []
        file_count = 0
        
        for filepath in project_path.rglob("*.py"):
            # Skip test files and virtual environments
            if any(part in filepath.parts for part in ["test_", "venv", "__pycache__", ".venv"]):
                continue
            
            issues = self.analyze_file(str(filepath))
            for issue in issues:
                issue.file = str(filepath.relative_to(project_path))
            all_issues.extend(issues)
            file_count += 1
        
        return {
            "files_analyzed": file_count,
            "total_issues": len(all_issues),
            "issues_by_severity": self._count_by_severity(all_issues),
            "issues_by_category": self._count_by_category(all_issues),
            "issues": all_issues
        }
    
    def _count_by_severity(self, issues: List[CodeIssue]) -> Dict[str, int]:
        """Count issues by severity."""
        counts = {}
        for issue in issues:
            severity = issue.severity.value
            counts[severity] = counts.get(severity, 0) + 1
        return counts
    
    def _count_by_category(self, issues: List[CodeIssue]) -> Dict[str, int]:
        """Count issues by category."""
        counts = {}
        for issue in issues:
            counts[issue.category] = counts.get(issue.category, 0) + 1
        return counts


# =============================================================================
# QUALITY SCORER CLASS
# =============================================================================

class QualityScorer:
    """
    Code quality scoring based on multiple metrics.
    
    Calculates maintainability index, technical debt,
    and overall code quality scores.
    """
    
    def __init__(self):
        self.metrics_history: List[QualityMetrics] = []
        logger.info("QualityScorer initialized")
    
    def score_file(self, filepath: str) -> Tuple[float, QualityMetrics]:
        """Score a single file."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            metrics = self._calculate_metrics(content, filepath)
            score = self._calculate_maintainability_index(metrics)
            
            self.metrics_history.append(metrics)
            
            return score, metrics
            
        except Exception as e:
            logger.error(f"Failed to score {filepath}: {e}")
            return 0.0, QualityMetrics(0, 0, 0, 0, 0, 0, 0, 0)
    
    def score_project(self, project_path: str) -> Dict[str, Any]:
        """Score an entire project."""
        project_path = Path(project_path)
        
        scores = []
        total_lines = 0
        total_comments = 0
        total_complexity = 0
        
        file_count = 0
        
        for filepath in project_path.rglob("*.py"):
            if any(part in filepath.parts for part in ["test_", "venv", "__pycache__"]):
                continue
            
            try:
                score, metrics = self.score_file(str(filepath))
                scores.append(score)
                total_lines += metrics.lines_of_code
                total_comments += metrics.lines_of_comments
                total_complexity += metrics.cyclomatic_complexity
                file_count += 1
            except Exception:
                continue
        
        avg_score = sum(scores) / len(scores) if scores else 0
        
        # Quality grades
        grades = {
            (90, 100): "A",
            (80, 90): "B",
            (70, 80): "C",
            (60, 70): "D",
            (0, 60): "F"
        }
        
        grade = "F"
        for (low, high), letter in grades.items():
            if low <= avg_score < high:
                grade = letter
                break
        
        return {
            "files_analyzed": file_count,
            "average_score": avg_score,
            "grade": grade,
            "total_lines": total_lines,
            "total_comments": total_comments,
            "average_comment_ratio": total_comments / total_lines if total_lines > 0 else 0,
            "total_complexity": total_complexity,
            "score_distribution": self._get_score_distribution(scores)
        }
    
    def _calculate_metrics(self, content: str, filepath: str) -> QualityMetrics:
        """Calculate quality metrics for content."""
        lines = content.split("\n")
        
        # Count lines
        loc = len([l for l in lines if l.strip()])
        comments = len([l for l in lines if l.strip().startswith("#")])
        comment_ratio = comments / loc if loc > 0 else 0
        
        # Calculate complexity
        try:
            tree = ast.parse(content)
            complexity = self._calculate_project_complexity(tree)
        except Exception:
            complexity = 0
        
        # Halstead volume (simplified)
        halstead = self._calculate_halstead(content)
        
        # Cognitive complexity (simplified)
        cognitive = self._calculate_cognitive_complexity(content)
        
        return QualityMetrics(
            maintainability_index=0,  # Calculated separately
            halstead_volume=halstead,
            cyclomatic_complexity=complexity,
            lines_of_code=loc,
            lines_of_comments=comments,
            comment_ratio=comment_ratio,
            cognitive_complexity=cognitive
        )
    
    def _calculate_project_complexity(self, tree: ast.AST) -> float:
        """Calculate average cyclomatic complexity."""
        total = 0
        count = 0
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                complexity = self._count_control_flow(node)
                total += complexity
                count += 1
        
        return total / count if count > 0 else 0
    
    def _count_control_flow(self, node: ast.AST) -> int:
        """Count control flow statements."""
        complexity = 1
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += sum(1 for _ in child.values)
        
        return complexity
    
    def _calculate_halstead(self, content: str) -> float:
        """Calculate Halstead volume (simplified)."""
        words = re.findall(r'\b[a-zA-Z_]\w*\b', content)
        unique_words = set(words)
        
        n1 = len(words)
        n2 = len(unique_words)
        
        if n2 == 0:
            return 0
        
        N = n1 * (n2 ** 0.5)  # Simplified volume
        
        return N
    
    def _calculate_cognitive_complexity(self, content: str) -> float:
        """Calculate cognitive complexity."""
        complexity = 0
        
        for line in content.split("\n"):
            stripped = line.strip()
            
            # Nesting increases complexity
            indent = len(line) - len(line.lstrip())
            complexity += indent // 4
            
            # Control structures
            if any(kw in stripped for kw in ["if ", "for ", "while ", "except"]):
                complexity += 1
            
            # Logical operators
            if " and " in stripped or " or " in stripped:
                complexity += 1
        
        return complexity / 100  # Normalize
    
    def _calculate_maintainability_index(self, metrics: QualityMetrics) -> float:
        """Calculate maintainability index (0-100)."""
        # Simplified formula based on Halstead and cyclomatic complexity
        volume_factor = max(0, 100 - metrics.halstead_volume / 100)
        complexity_factor = max(0, 100 - metrics.cyclomatic_complexity * 5)
        comment_factor = metrics.comment_ratio * 100
        
        index = (volume_factor * 0.3 + complexity_factor * 0.3 + comment_factor * 0.4)
        
        return min(100, max(0, index))
    
    def _get_score_distribution(self, scores: List[float]) -> Dict[str, int]:
        """Get score distribution."""
        distribution = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        
        for score in scores:
            if score >= 90:
                distribution["A"] += 1
            elif score >= 80:
                distribution["B"] += 1
            elif score >= 70:
                distribution["C"] += 1
            elif score >= 60:
                distribution["D"] += 1
            else:
                distribution["F"] += 1
        
        return distribution
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics collected."""
        if not self.metrics_history:
            return {}
        
        return {
            "files_scored": len(self.metrics_history),
            "avg_maintainability": sum(m.maintainability_index for m in self.metrics_history) / len(self.metrics_history),
            "avg_complexity": sum(m.cyclomatic_complexity for m in self.metrics_history) / len(self.metrics_history),
            "avg_comment_ratio": sum(m.comment_ratio for m in self.metrics_history) / len(self.metrics_history)
        }


# =============================================================================
# PATTERN DETECTOR CLASS
# =============================================================================

class PatternDetector:
    """
    Code pattern detection with support for architectural and design patterns.
    
    Detects anti-patterns, design patterns, and code structure issues.
    """
    
    PATTERNS = {
        "singleton": {
            "name": "Singleton Pattern",
            "severity": IssueSeverity.INFO,
            "description": "Single instance pattern detected",
            "rules": [
                {"type": "class", "check": lambda c: "_instance" in str(ast.dump(c)) or "__new__" in str(ast.dump(c))}
            ]
        },
        "factory": {
            "name": "Factory Pattern",
            "severity": IssueSeverity.INFO,
            "description": "Factory pattern detected",
            "rules": [
                {"type": "method", "check": lambda f: f.name.startswith("create") or f.name.startswith("factory")}
            ]
        },
        "observer": {
            "name": "Observer Pattern",
            "severity": IssueSeverity.INFO,
            "description": "Observer/event pattern detected",
            "rules": [
                {"type": "method", "check": lambda f: "notify" in f.name.lower() or "subscribe" in f.name.lower()}
            ]
        },
        "decorator": {
            "name": "Decorator Pattern",
            "severity": IssueSeverity.INFO,
            "description": "Decorator pattern detected",
            "rules": [
                {"type": "class", "check": lambda c: any(isinstance(n, ast.FunctionDef) and n.name == c.name for n in ast.walk(c))}
            ]
        },
        "anti_singleton": {
            "name": "Anti-Singleton",
            "severity": IssueSeverity.MAJOR,
            "description": "Class should not be a singleton",
            "rules": [
                {"type": "class", "check": lambda c: len([n for n in ast.walk(c) if isinstance(n, ast.FunctionDef)]) > 15}
            ]
        },
        "feature_envy": {
            "name": "Feature Envy",
            "severity": IssueSeverity.MAJOR,
            "description": "Method accesses data of another class more than its own",
            "rules": []
        },
        "god_class": {
            "name": "God Class",
            "severity": IssueSeverity.CRITICAL,
            "description": "Class trying to do too much",
            "rules": [
                {"type": "class", "check": lambda c: len([n for n in ast.walk(c) if isinstance(n, ast.FunctionDef)]) > 15}
            ]
        },
        "data_class": {
            "name": "Data Class",
            "severity": IssueSeverity.MINOR,
            "description": "Class with only data and no behavior",
            "rules": []
        }
    }
    
    def __init__(self):
        self.detected_patterns: List[PatternMatch] = []
        logger.info("PatternDetector initialized")
    
    def detect_patterns(self, filepath: str) -> List[PatternMatch]:
        """Detect patterns in a file."""
        self.detected_patterns = []
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    self._check_class_patterns(node, content)
                
                elif isinstance(node, ast.FunctionDef):
                    self._check_function_patterns(node, content)
            
            logger.info(f"Pattern detection complete: {len(self.detected_patterns)} patterns in {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to detect patterns in {filepath}: {e}")
        
        return self.detected_patterns
    
    def _check_class_patterns(self, node: ast.ClassDef, content: str) -> None:
        """Check for class-level patterns."""
        class_dump = str(ast.dump(node))
        
        # Check singleton
        if "_instance" in class_dump or "__new__" in class_dump:
            self.detected_patterns.append(PatternMatch(
                pattern_id="singleton",
                pattern_name="Singleton Pattern",
                line=node.lineno,
                matched_text=node.name,
                confidence=0.8,
                metadata={"class": node.name}
            ))
        
        # Check god class
        methods = [n for n in ast.walk(node) if isinstance(n, ast.FunctionDef)]
        if len(methods) > 15:
            self.detected_patterns.append(PatternMatch(
                pattern_id="god_class",
                pattern_name="God Class",
                line=node.lineno,
                matched_text=node.name,
                confidence=0.9,
                metadata={"class": node.name, "method_count": len(methods)}
            ))
        
        # Check data class
        has_properties = len(node.body) > 0
        has_methods = any(isinstance(n, ast.FunctionDef) and n.name not in ["__init__", "__str__"] 
                        for n in node.body)
        
        if has_properties and not has_methods:
            self.detected_patterns.append(PatternMatch(
                pattern_id="data_class",
                pattern_name="Data Class",
                line=node.lineno,
                matched_text=node.name,
                confidence=0.7,
                metadata={"class": node.name}
            ))
    
    def _check_function_patterns(self, node: ast.FunctionDef, content: str) -> None:
        """Check for function-level patterns."""
        # Check for long functions
        func_lines = node.end_lineno - node.lineno + 1 if hasattr(node, 'end_lineno') else 0
        
        if func_lines > 100:
            self.detected_patterns.append(PatternMatch(
                pattern_id="long_method",
                pattern_name="Long Method",
                line=node.lineno,
                matched_text=node.name,
                confidence=0.8,
                metadata={"function": node.name, "lines": func_lines}
            ))
        
        # Check for complex conditionals
        has_nested = self._check_nesting_depth(node) > 4
        
        if has_nested:
            self.detected_patterns.append(PatternMatch(
                pattern_id="nested_depth",
                pattern_name="Deep Nesting",
                line=node.lineno,
                matched_text=node.name,
                confidence=0.7,
                metadata={"function": node.name, "depth": self._check_nesting_depth(node)}
            ))
    
    def _check_nesting_depth(self, node: ast.AST) -> int:
        """Calculate nesting depth of a node."""
        max_depth = 0
        
        class DepthChecker(ast.NodeVisitor):
            def __init__(self):
                self.current_depth = 0
                self.max_depth = 0
            
            def visit_If(self, node):
                self.current_depth += 1
                self.max_depth = max(self.max_depth, self.current_depth)
                self.generic_visit(node)
                self.current_depth -= 1
            
            def visit_For(self, node):
                self.current_depth += 1
                self.max_depth = max(self.max_depth, self.current_depth)
                self.generic_visit(node)
                self.current_depth -= 1
            
            def visit_While(self, node):
                self.current_depth += 1
                self.max_depth = max(self.max_depth, self.current_depth)
                self.generic_visit(node)
                self.current_depth -= 1
        
        checker = DepthChecker()
        checker.visit(node)
        return checker.max_depth
    
    def detect_in_project(self, project_path: str) -> Dict[str, Any]:
        """Detect patterns across a project."""
        project_path = Path(project_path)
        
        all_patterns = []
        pattern_counts = {}
        
        for filepath in project_path.rglob("*.py"):
            if any(part in filepath.parts for part in ["test_", "venv", "__pycache__"]):
                continue
            
            patterns = self.detect_patterns(str(filepath))
            
            for pattern in patterns:
                pattern.file = str(filepath.relative_to(project_path))
            
            all_patterns.extend(patterns)
            
            # Count by pattern type
            for pattern in patterns:
                pattern_counts[pattern.pattern_id] = pattern_counts.get(pattern.pattern_id, 0) + 1
        
        return {
            "files_scanned": sum(1 for _ in project_path.rglob("*.py")),
            "patterns_detected": len(all_patterns),
            "pattern_counts": pattern_counts,
            "patterns": all_patterns
        }
    
    def get_anti_patterns(self) -> List[PatternMatch]:
        """Get detected anti-patterns."""
        anti_patterns = ["god_class", "long_method", "nested_depth", "data_class"]
        return [p for p in self.detected_patterns if p.pattern_id in anti_patterns]


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="ILMA Code Analyst - Static analysis, quality scoring, and pattern detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a file
  %(prog)s --analyze /path/to/file.py
  
  # Analyze a project
  %(prog)s --analyze-project /path/to/project
  
  # Score a file
  %(prog)s --score /path/to/file.py
  
  # Score a project
  %(prog)s --score-project /path/to/project
  
  # Detect patterns
  %(prog)s --detect-patterns /path/to/file.py
  
  # Full report
  %(prog)s --full-report /path/to/project
        """
    )
    
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    # Analysis options
    parser.add_argument("--analyze", metavar="FILE", help="Analyze a file")
    parser.add_argument("--analyze-project", metavar="PROJECT", help="Analyze a project")
    
    # Scoring options
    parser.add_argument("--score", metavar="FILE", help="Score a file")
    parser.add_argument("--score-project", metavar="PROJECT", help="Score a project")
    
    # Pattern detection options
    parser.add_argument("--detect-patterns", metavar="FILE", help="Detect patterns in a file")
    parser.add_argument("--detect-in-project", metavar="PROJECT", help="Detect patterns in project")
    
    # Reporting options
    parser.add_argument("--full-report", metavar="PROJECT", help="Generate full analysis report")
    parser.add_argument("--output", "-o", help="Output file for report (JSON format)")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # File Analysis
        if args.analyze:
            analyzer = StaticAnalyzer()
            issues = analyzer.analyze_file(args.analyze)
            
            print(f"\n=== Analysis: {args.analyze} ===")
            print(f"Issues found: {len(issues)}")
            
            if issues:
                print("\nIssues by Severity:")
                severity_counts = {}
                for issue in issues:
                    severity_counts[issue.severity.value] = severity_counts.get(issue.severity.value, 0) + 1
                
                for severity in ["blocker", "critical", "major", "minor", "info"]:
                    count = severity_counts.get(severity, 0)
                    if count > 0:
                        print(f"  {severity.upper()}: {count}")
                
                print("\nFirst 10 Issues:")
                for issue in issues[:10]:
                    print(f"  [{issue.severity.value.upper()}] Line {issue.line}: {issue.message}")
        
        # Project Analysis
        elif args.analyze_project:
            analyzer = StaticAnalyzer()
            result = analyzer.analyze_project(args.analyze_project)
            
            print(f"\n=== Project Analysis: {args.analyze_project} ===")
            print(f"Files analyzed: {result['files_analyzed']}")
            print(f"Total issues: {result['total_issues']}")
            
            print("\nIssues by Severity:")
            for severity, count in result['issues_by_severity'].items():
                print(f"  {severity.upper()}: {count}")
            
            print("\nIssues by Category:")
            for category, count in result['issues_by_category'].items():
                print(f"  {category}: {count}")
        
        # File Scoring
        elif args.score:
            scorer = QualityScorer()
            score, metrics = scorer.score_file(args.score)
            
            print(f"\n=== Quality Score: {args.score} ===")
            print(f"Score: {score:.1f}/100")
            print(f"Lines of Code: {metrics.lines_of_code}")
            print(f"Lines of Comments: {metrics.lines_of_comments}")
            print(f"Comment Ratio: {metrics.comment_ratio:.1%}")
            print(f"Cyclomatic Complexity: {metrics.cyclomatic_complexity:.2f}")
        
        # Project Scoring
        elif args.score_project:
            scorer = QualityScorer()
            result = scorer.score_project(args.score_project)
            
            print(f"\n=== Project Quality Score: {args.score_project} ===")
            print(f"Files analyzed: {result['files_analyzed']}")
            print(f"Average Score: {result['average_score']:.1f}/100")
            print(f"Grade: {result['grade']}")
            print(f"Total Lines: {result['total_lines']:,}")
            print(f"Comment Ratio: {result['average_comment_ratio']:.1%}")
            
            print("\nScore Distribution:")
            for grade, count in result['score_distribution'].items():
                bar = "█" * count + "░" * max(0, 10 - count)
                print(f"  {grade}: {bar} ({count})")
        
        # Pattern Detection - File
        elif args.detect_patterns:
            detector = PatternDetector()
            patterns = detector.detect_patterns(args.detect_patterns)
            
            print(f"\n=== Pattern Detection: {args.detect_patterns} ===")
            print(f"Patterns found: {len(patterns)}")
            
            if patterns:
                anti_patterns = detector.get_anti_patterns()
                if anti_patterns:
                    print(f"\nAnti-Patterns: {len(anti_patterns)}")
                    for ap in anti_patterns[:5]:
                        print(f"  [{ap.severity.value.upper()}] {ap.pattern_name} at line {ap.line}")
                        print(f"    {ap.matched_text}")
                
                print("\nAll Patterns:")
                for p in patterns[:10]:
                    print(f"  {p.pattern_name} ({p.confidence:.0%}) - {p.matched_text}")
        
        # Pattern Detection - Project
        elif args.detect_in_project:
            detector = PatternDetector()
            result = detector.detect_in_project(args.detect_in_project)
            
            print(f"\n=== Pattern Detection: {args.detect_in_project} ===")
            print(f"Files scanned: {result['files_scanned']}")
            print(f"Patterns detected: {result['patterns_detected']}")
            
            print("\nPattern Counts:")
            for pattern_id, count in result['pattern_counts'].items():
                print(f"  {pattern_id}: {count}")
        
        # Full Report
        elif args.full_report:
            analyzer = StaticAnalyzer()
            scorer = QualityScorer()
            detector = PatternDetector()
            
            # Analyze
            analysis_result = analyzer.analyze_project(args.full_report)
            score_result = scorer.score_project(args.full_report)
            pattern_result = detector.detect_in_project(args.full_report)
            
            report = {
                "project": args.full_report,
                "generated_at": datetime.now().isoformat(),
                "analysis": {
                    "files_analyzed": analysis_result["files_analyzed"],
                    "total_issues": analysis_result["total_issues"],
                    "issues_by_severity": analysis_result["issues_by_severity"],
                    "issues_by_category": analysis_result["issues_by_category"]
                },
                "quality_score": {
                    "average_score": score_result["average_score"],
                    "grade": score_result["grade"],
                    "score_distribution": score_result["score_distribution"]
                },
                "patterns": {
                    "patterns_detected": pattern_result["patterns_detected"],
                    "pattern_counts": pattern_result["pattern_counts"]
                }
            }
            
            if args.output:
                with open(args.output, "w") as f:
                    json.dump(report, f, indent=2)
                print(f"\nReport saved to: {args.output}")
            else:
                print("\n=== Full Report ===")
                print(json.dumps(report, indent=2))
        
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()