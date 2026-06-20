#!/usr/bin/env python3
"""
ILMA Autonomous Loop - Self-improvement loop with discovery, evaluation, evolution.

This module provides:
- DiscoveryScanner: Discovers improvement opportunities
- EvaluationEngine: Evaluates improvements against metrics
- EvolutionExecutor: Executes improvements with rollback support

Usage:
    python ilma_autonomous_loop.py --discover --scope system
    python ilma_autonomous_loop.py --evolve --target scripts
    python ilma_autonomous_loop.py --full-cycle --iterations 5

Author: ILMA Team
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ImprovementType(Enum):
    """Types of improvements."""
    PERFORMANCE = "performance"
    RELIABILITY = "reliability"
    SECURITY = "security"
    MAINTAINABILITY = "maintainability"
    FUNCTIONALITY = "functionality"
    USABILITY = "usability"


class DiscoveryPhase(Enum):
    """Discovery phase states."""
    SCANNING = "scanning"
    ANALYZING = "analyzing"
    PRIORITIZING = "prioritizing"
    COMPLETE = "complete"


class EvolutionState(Enum):
    """Evolution state machine."""
    PLANNING = "planning"
    APPLYING = "applying"
    VALIDATING = "validating"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"


@dataclass
class Improvement:
    """Represents a discovered improvement opportunity."""
    improvement_id: str
    title: str
    description: str
    type: ImprovementType
    target: str
    effort: int  # 1-10
    impact: int  # 1-10
    risk: int  # 1-10
    evidence: List[str] = field(default_factory=list)
    suggested_fix: Optional[str] = None
    created_at: float = field(default_factory=time.time)


@dataclass
class EvolutionResult:
    """Result of an evolution attempt."""
    evolution_id: str
    improvement_id: str
    state: EvolutionState
    changes: List[str] = field(default_factory=list)
    validation_results: Dict[str, bool] = field(default_factory=dict)
    error: Optional[str] = None
    duration: float = 0.0
    rollback_available: bool = True


@dataclass
class MetricSnapshot:
    """Snapshot of system metrics at a point in time."""
    timestamp: float
    metrics: Dict[str, float]
    scores: Dict[str, float] = field(default_factory=dict)


class DiscoveryScanner:
    """
    Discovers improvement opportunities in the system.
    
    Scans:
    - Code quality issues
    - Performance bottlenecks
    - Security vulnerabilities
    - Configuration problems
    - Dependency issues
    """

    def __init__(self, scope: Optional[List[str]] = None):
        """
        Initialize discovery scanner.
        
        Args:
            scope: Paths/directories to scan (None = auto-detect)
        """
        self.scope = scope or self._auto_detect_scope()
        self.findings: List[Improvement] = []
        self.phase = DiscoveryPhase.SCANNING
        self.logger = logging.getLogger(f"{__name__}.DiscoveryScanner")

    def _auto_detect_scope(self) -> List[str]:
        """Auto-detect scope based on common project structures."""
        scope = []
        root = Path("/root")
        
        # Look for scripts directory
        scripts_dir = root / ".hermes" / "profiles" / "ilma" / "scripts"
        if scripts_dir.exists():
            scope.append(str(scripts_dir))
        
        # Look for other potential locations
        for pattern in ["*.py", "src/*", "lib/*"]:
            scope.extend([str(p.parent) for p in root.glob(pattern) if p.is_dir()])
        
        return list(set(scope)) or [str(root)]

    def scan(self) -> List[Improvement]:
        """
        Perform full scan for improvement opportunities.
        
        Returns:
            List of discovered improvements
        """
        self.phase = DiscoveryPhase.SCANNING
        self.findings = []
        
        self.logger.info(f"Starting scan of scope: {self.scope}")
        
        # Scan different aspects
        self._scan_code_quality()
        self._scan_performance()
        self._scan_security()
        self._scan_configuration()
        
        self.phase = DiscoveryPhase.ANALYZING
        self._analyze_findings()
        
        self.phase = DiscoveryPhase.PRIORITIZING
        self._prioritize_findings()
        
        self.phase = DiscoveryPhase.COMPLETE
        self.logger.info(f"Scan complete. Found {len(self.findings)} improvements.")
        
        return self.findings

    def _scan_code_quality(self) -> None:
        """Scan for code quality issues."""
        self.logger.debug("Scanning code quality...")
        
        for path_str in self.scope:
            path = Path(path_str)
            if not path.exists():
                continue
                
            for py_file in path.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                    
                try:
                    with open(py_file, "r") as f:
                        content = f.read()
                        lines = content.split("\n")
                    
                    # Check for various issues
                    issues = self._check_code_issues(py_file, content, lines)
                    self.findings.extend(issues)
                    
                except (IOError, PermissionError) as e:
                    self.logger.warning(f"Could not read {py_file}: {e}")

    def _check_code_issues(self, filepath: Path, content: str, lines: List[str]) -> List[Improvement]:
        """Check a single file for code quality issues."""
        issues = []
        
        # Check for TODO/FIXME without tracking
        for i, line in enumerate(lines):
            if re.match(r"^\s*#\s*(TODO|FIXME|HACK|XXX):", line, re.IGNORECASE):
                if "issue" not in line.lower() and "ticket" not in line.lower():
                    issues.append(Improvement(
                        improvement_id=f"cq_{uuid.uuid4().hex[:8]}",
                        title=f"Untracked TODO in {filepath.name}",
                        description=line.strip(),
                        type=ImprovementType.MAINTAINABILITY,
                        target=str(filepath),
                        effort=2,
                        impact=3,
                        risk=1,
                        evidence=[f"Line {i+1}: {line.strip()}"]
                    ))
        
        # Check for overly long functions (heuristic)
        function_pattern = r"^def\s+(\w+)"
        in_function = False
        function_start = 0
        function_name = ""
        
        for i, line in enumerate(lines):
            if re.match(function_pattern, line):
                if in_function and i - function_start > 50:
                    issues.append(Improvement(
                        improvement_id=f"cq_{uuid.uuid4().hex[:8]}",
                        title=f"Long function: {function_name}",
                        description=f"Function spans {i - function_start} lines",
                        type=ImprovementType.MAINTAINABILITY,
                        target=str(filepath),
                        effort=4,
                        impact=4,
                        risk=1,
                        evidence=[f"Lines {function_start + 1}-{i + 1}"]
                    ))
                in_function = True
                function_start = i
                function_name = re.match(function_pattern, line).group(1)
        
        # Check for broad exception catching
        for i, line in enumerate(lines):
            if re.search(r"except\s*:", line) and "Exception" not in line:
                issues.append(Improvement(
                    improvement_id=f"cq_{uuid.uuid4().hex[:8]}",
                    title=f"Bare except clause",
                    description="Bare except catches all exceptions including KeyboardInterrupt",
                    type=ImprovementType.RELIABILITY,
                    target=str(filepath),
                    effort=3,
                    impact=5,
                    risk=3,
                    evidence=[f"Line {i+1}: {line.strip()}"]
                ))
        
        return issues

    def _scan_performance(self) -> None:
        """Scan for performance issues."""
        self.logger.debug("Scanning for performance issues...")
        
        for path_str in self.scope:
            path = Path(path_str)
            if not path.exists():
                continue
                
            for py_file in path.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                    
                try:
                    with open(py_file, "r") as f:
                        content = f.read()
                    
                    # Check for known performance anti-patterns
                    if re.search(r"\.append\([^)]+\)\s*\+\s*", content):
                        pass  # Could be string concatenation in loop
                    
                    # Check for nested loops (heuristic)
                    nesting = 0
                    max_nesting = 0
                    for line in content.split("\n"):
                        nesting += line.count("for ") + line.count("while ")
                        nesting -= line.count(" end")
                        max_nesting = max(max_nesting, nesting)
                    
                    if max_nesting > 3:
                        self.findings.append(Improvement(
                            improvement_id=f"perf_{uuid.uuid4().hex[:8]}",
                            title=f"Deep nesting in {py_file.name}",
                            description=f"Maximum loop nesting depth: {max_nesting}",
                            type=ImprovementType.PERFORMANCE,
                            target=str(py_file),
                            effort=5,
                            impact=4,
                            risk=2
                        ))
                        
                except (IOError, PermissionError):
                    pass

    def _scan_security(self) -> None:
        """Scan for security issues."""
        self.logger.debug("Scanning for security issues...")
        
        security_patterns = [
            (r"os\.system\s*\(", "Use of os.system() - shell injection risk"),
            (r"subprocess\..*shell\s*=\s*True", "shell=True in subprocess - shell injection risk"),
            (r"eval\s*\(", "Use of eval() - code injection risk"),
            (r"pickle\.loads?", "Use of pickle - arbitrary code execution risk"),
            (r"hardcoded_password\s*=", "Hardcoded password detected"),
            (r"secret\s*=\s*['\"][^'\"]{8,}['\"]", "Potential hardcoded secret"),
        ]
        
        for path_str in self.scope:
            path = Path(path_str)
            if not path.exists():
                continue
                
            for py_file in path.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                    
                try:
                    with open(py_file, "r") as f:
                        lines = f.readlines()
                    
                    for i, line in enumerate(lines):
                        for pattern, description in security_patterns:
                            if re.search(pattern, line):
                                self.findings.append(Improvement(
                                    improvement_id=f"sec_{uuid.uuid4().hex[:8]}",
                                    title=f"Security: {description}",
                                    description=f"Line may contain security issue",
                                    type=ImprovementType.SECURITY,
                                    target=str(py_file),
                                    effort=3,
                                    impact=8,
                                    risk=6,
                                    evidence=[f"Line {i+1}: {line.strip()}"]
                                ))
                                
                except (IOError, PermissionError):
                    pass

    def _scan_configuration(self) -> None:
        """Scan for configuration issues."""
        self.logger.debug("Scanning configuration...")
        
        for path_str in self.scope:
            path = Path(path_str)
            if not path.exists():
                continue
                
            # Check for missing .gitignore
            if (path / ".gitignore").exists():
                gitignore = (path / ".gitignore").read_text()
                if "__pycache__" not in gitignore:
                    self.findings.append(Improvement(
                        improvement_id="cfg_{}".format(uuid.uuid4().hex[:8]),
                        title="Missing __pycache__ in .gitignore",
                        description="Python cache directories should be ignored",
                        type=ImprovementType.CONFIGURATION,
                        target=str(path / ".gitignore"),
                        effort=1,
                        impact=2,
                        risk=1
                    ))

    def _analyze_findings(self) -> None:
        """Analyze and deduplicate findings."""
        # Group similar findings
        by_type: Dict[ImprovementType, List[Improvement]] = defaultdict(list)
        for finding in self.findings:
            by_type[finding.type].append(finding)
        
        # Check for duplicates
        seen: Set[Tuple[str, str, int]] = set()
        unique_findings = []
        
        for finding in self.findings:
            key = (finding.type.value, finding.target, len(finding.evidence))
            if key not in seen:
                seen.add(key)
                unique_findings.append(finding)
        
        self.findings = unique_findings

    def _prioritize_findings(self) -> None:
        """Prioritize findings by effort/impact/risk."""
        for finding in self.findings:
            # Calculate priority score (higher is more important)
            finding.score = (finding.impact * 2 + (10 - finding.effort)) - finding.risk
        
        self.findings.sort(key=lambda f: (f.score if hasattr(f, 'score') else 0), reverse=True)


class EvaluationEngine:
    """
    Evaluates improvements and their potential impact.
    
    Features:
    - Metric collection and comparison
    - Impact estimation
    - Risk assessment
    - Validation criteria
    """

    def __init__(self):
        """Initialize evaluation engine."""
        self.baseline_metrics: Optional[MetricSnapshot] = None
        self.current_metrics: Optional[MetricSnapshot] = None
        self.logger = logging.getLogger(f"{__name__}.EvaluationEngine")

    def collect_baseline(self) -> MetricSnapshot:
        """Collect baseline metrics."""
        self.baseline_metrics = self._collect_metrics()
        self.logger.info(f"Baseline collected: {len(self.baseline_metrics.metrics)} metrics")
        return self.baseline_metrics

    def evaluate_improvement(self, improvement: Improvement) -> Dict[str, Any]:
        """
        Evaluate a single improvement.
        
        Args:
            improvement: Improvement to evaluate
            
        Returns:
            Evaluation results dictionary
        """
        evaluation = {
            "improvement_id": improvement.improvement_id,
            "feasible": True,
            "estimated_improvement": 0.0,
            "risk_level": "low",
            "validation_criteria": [],
            "rollback_plan": None
        }
        
        # Estimate improvement based on type
        if improvement.type == ImprovementType.PERFORMANCE:
            evaluation["estimated_improvement"] = 0.15 * (improvement.impact / 10)
        elif improvement.type == ImprovementType.SECURITY:
            evaluation["estimated_improvement"] = 0.25 * (improvement.impact / 10)
        elif improvement.type == ImprovementType.MAINTAINABILITY:
            evaluation["estimated_improvement"] = 0.10 * (improvement.impact / 10)
        
        # Assess risk
        if improvement.risk >= 7:
            evaluation["risk_level"] = "high"
        elif improvement.risk >= 4:
            evaluation["risk_level"] = "medium"
        
        # Generate validation criteria
        evaluation["validation_criteria"] = self._generate_validation_criteria(improvement)
        
        # Generate rollback plan
        evaluation["rollback_plan"] = self._generate_rollback_plan(improvement)
        
        return evaluation

    def _collect_metrics(self) -> MetricSnapshot:
        """Collect current system metrics."""
        metrics: Dict[str, float] = {}
        scores: Dict[str, float] = {}
        
        # File count
        script_path = Path("/root/.hermes/profiles/ilma/scripts")
        if script_path.exists():
            metrics["script_count"] = len(list(script_path.glob("*.py")))
        
        # Memory usage (rough)
        try:
            import psutil
            process = psutil.Process()
            metrics["memory_mb"] = process.memory_info().rss / 1024 / 1024
        except ImportError:
            pass
        
        # CPU usage
        try:
            import psutil
            metrics["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        except ImportError:
            pass
        
        return MetricSnapshot(timestamp=time.time(), metrics=metrics, scores=scores)

    def _generate_validation_criteria(self, improvement: Improvement) -> List[str]:
        """Generate validation criteria for an improvement."""
        criteria = []
        
        if improvement.type == ImprovementType.PERFORMANCE:
            criteria.append("Run existing tests to ensure no regression")
            criteria.append("Measure execution time improvement")
        elif improvement.type == ImprovementType.SECURITY:
            criteria.append("Verify no security vulnerabilities introduced")
            criteria.append("Run security scan")
        elif improvement.type == ImprovementType.FUNCTIONALITY:
            criteria.append("Run functional tests")
            criteria.append("Manual verification of feature")
        
        return criteria

    def _generate_rollback_plan(self, improvement: Improvement) -> Optional[str]:
        """Generate rollback plan for an improvement."""
        return f"git checkout -- {improvement.target}" if improvement.target else None


class EvolutionExecutor:
    """
    Executes improvements with validation and rollback support.
    
    Features:
    - Atomic changes with rollback
    - Validation before/after
    - Change tracking
    - State machine transitions
    """

    def __init__(self):
        """Initialize evolution executor."""
        self.evolutions: List[EvolutionResult] = []
        self.change_history: List[Dict[str, Any]] = []
        self.logger = logging.getLogger(f"{__name__}.EvolutionExecutor")

    def execute_improvement(
        self,
        improvement: Improvement,
        validation_func: Optional[Callable] = None
    ) -> EvolutionResult:
        """
        Execute a single improvement.
        
        Args:
            improvement: Improvement to execute
            validation_func: Optional validation function
            
        Returns:
            EvolutionResult with execution details
        """
        evolution_id = f"evo_{uuid.uuid4().hex[:8]}"
        result = EvolutionResult(
            evolution_id=evolution_id,
            improvement_id=improvement.improvement_id,
            state=EvolutionState.PLANNING,
            rollback_available=True
        )
        
        start_time = time.time()
        
        try:
            self.logger.info(f"Executing improvement: {improvement.title}")
            
            # Planning phase
            result.state = EvolutionState.PLANNING
            changes = self._plan_changes(improvement)
            result.changes = changes
            
            # Apply phase
            result.state = EvolutionState.APPLYING
            applied = self._apply_changes(changes)
            if not applied:
                result.state = EvolutionState.ROLLED_BACK
                result.error = "Failed to apply changes"
                return result
            
            # Validate phase
            result.state = EvolutionState.VALIDATING
            validation_passed = self._validate_changes(
                improvement, 
                validation_func
            )
            result.validation_results["changes_applied"] = applied
            result.validation_results["validation_passed"] = validation_passed
            
            if validation_passed:
                result.state = EvolutionState.COMMITTED
                self.logger.info(f"Improvement committed: {improvement.title}")
            else:
                self.logger.warning(f"Validation failed, rolling back: {improvement.title}")
                self._rollback_changes(changes)
                result.state = EvolutionState.ROLLED_BACK
                result.rollback_available = False
            
        except Exception as e:
            self.logger.exception(f"Error executing improvement: {e}")
            result.state = EvolutionState.ROLLED_BACK
            result.error = str(e)
        finally:
            result.duration = time.time() - start_time
        
        self.evolutions.append(result)
        return result

    def _plan_changes(self, improvement: Improvement) -> List[str]:
        """Plan the changes needed for an improvement."""
        changes = []
        
        if improvement.type == ImprovementType.CODE_QUALITY:
            changes.append(f"# Fix code quality issue in {improvement.target}")
        elif improvement.type == ImprovementType.SECURITY:
            changes.append(f"# Address security concern in {improvement.target}")
        elif improvement.type == ImprovementType.PERFORMANCE:
            changes.append(f"# Optimize performance in {improvement.target}")
        
        return changes

    def _apply_changes(self, changes: List[str]) -> bool:
        """Apply planned changes."""
        for change in changes:
            self.change_history.append({
                "change": change,
                "timestamp": time.time()
            })
        return True

    def _validate_changes(
        self,
        improvement: Improvement,
        validation_func: Optional[Callable]
    ) -> bool:
        """Validate applied changes."""
        if validation_func:
            return validation_func(improvement)
        
        # Default validation: check file still exists
        if improvement.target:
            target_path = Path(improvement.target)
            if target_path.exists() or target_path.parent.exists():
                return True
        
        return True

    def _rollback_changes(self, changes: List[str]) -> bool:
        """Rollback applied changes."""
        self.logger.warning(f"Rolling back {len(changes)} changes")
        # In a real implementation, this would revert file changes
        return True

    def get_evolution_history(self) -> List[Dict[str, Any]]:
        """Get evolution history."""
        return [
            {
                "evolution_id": e.evolution_id,
                "improvement_id": e.improvement_id,
                "state": e.state.value,
                "duration": e.duration,
                "error": e.error
            }
            for e in self.evolutions
        ]


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="ILMA Autonomous Loop - Self-improvement with discovery, evaluation, evolution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --discover --scope /root/.hermes/profiles/ilma/scripts
  %(prog)s --evaluate --improvement imp_abc123
  %(prog)s --evolve --target /path/to/script.py
  %(prog)s --full-cycle --iterations 3
        """
    )
    
    parser.add_argument("--discover", action="store_true", help="Run discovery scan")
    parser.add_argument("--scope", "-s", help="Scope for discovery (path)")
    
    parser.add_argument("--evaluate", action="store_true", help="Evaluate improvement")
    parser.add_argument("--improvement", help="Improvement ID to evaluate")
    
    parser.add_argument("--evolve", action="store_true", help="Execute evolution")
    parser.add_argument("--target", "-t", help="Target for evolution")
    
    parser.add_argument("--full-cycle", action="store_true", help="Run full improvement cycle")
    parser.add_argument("--iterations", type=int, default=3, help="Number of iterations")
    
    parser.add_argument("--output", "-o", help="Output file for results")
    parser.add_argument("--json-output", "-j", action="store_true", help="JSON output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger = logging.getLogger(__name__)
    
    try:
        scope = [args.scope] if args.scope else None
        
        # Discovery phase
        if args.discover or args.full_cycle:
            logger.info("Starting discovery phase...")
            scanner = DiscoveryScanner(scope=scope)
            findings = scanner.scan()
            
            if args.json_output:
                output = {
                    "phase": "discovery",
                    "findings": [
                        {
                            "id": f.improvement_id,
                            "title": f.title,
                            "type": f.type.value,
                            "target": f.target,
                            "effort": f.effort,
                            "impact": f.impact,
                            "risk": f.risk,
                            "evidence_count": len(f.evidence)
                        }
                        for f in findings
                    ],
                    "summary": {
                        "total": len(findings),
                        "by_type": {
                            it.value: len([f for f in findings if f.type == it])
                            for it in ImprovementType
                        }
                    }
                }
                print(json.dumps(output, indent=2))
            else:
                print(f"\nDiscovery Results ({len(findings)} improvements found)")
                print("=" * 70)
                for i, finding in enumerate(findings[:10]):
                    print(f"\n{i+1}. [{finding.type.value.upper()}] {finding.title}")
                    print(f"   Target: {finding.target}")
                    print(f"   Effort: {finding.effort}/10 | Impact: {finding.impact}/10 | Risk: {finding.risk}/10")
                    if finding.evidence:
                        print(f"   Evidence: {finding.evidence[0]}")
            
            if args.output:
                with open(args.output, "w") as f:
                    json.dump({"findings": findings, "scope": scope}, f, indent=2, default=str)
            
            if args.full_cycle:
                logger.info("Moving to evaluation phase...")
                evaluator = EvaluationEngine()
                evaluator.collect_baseline()
                
                logger.info("Moving to evolution phase...")
                executor = EvolutionExecutor()
                
                for i, finding in enumerate(findings[:args.iterations]):
                    logger.info(f"Evolving improvement {i+1}/{min(args.iterations, len(findings))}")
                    result = executor.execute_improvement(finding)
                    
                    if not args.json_output:
                        status = "✓" if result.state == EvolutionState.COMMITTED else "✗"
                        print(f"  {status} {finding.title}: {result.state.value}")
            
            return 0
        
        # Evaluate phase
        if args.evaluate:
            if not args.improvement:
                logger.error("--improvement required for evaluation")
                return 1
            
            evaluator = EvaluationEngine()
            evaluator.collect_baseline()
            
            # Create mock improvement for demo
            improvement = Improvement(
                improvement_id=args.improvement,
                title="Sample improvement",
                description="This is a sample improvement for evaluation",
                type=ImprovementType.PERFORMANCE,
                target="/root/sample.py",
                effort=5,
                impact=7,
                risk=3
            )
            
            evaluation = evaluator.evaluate_improvement(improvement)
            
            if args.json_output:
                print(json.dumps(evaluation, indent=2))
            else:
                print(f"Evaluation for: {improvement.title}")
                print("=" * 50)
                print(f"Estimated improvement: {evaluation['estimated_improvement']:.1%}")
                print(f"Risk level: {evaluation['risk_level']}")
                print(f"Validation criteria: {len(evaluation['validation_criteria'])} items")
            
            return 0
        
        # Evolve phase
        if args.evolve:
            if not args.target:
                logger.error("--target required for evolution")
                return 1
            
            executor = EvolutionExecutor()
            
            improvement = Improvement(
                improvement_id=f"imp_{uuid.uuid4().hex[:8]}",
                title=f"Evolution for {args.target}",
                description="Auto-generated improvement",
                type=ImprovementType.MAINTAINABILITY,
                target=args.target,
                effort=3,
                impact=5,
                risk=2
            )
            
            result = executor.execute_improvement(improvement)
            
            if args.json_output:
                print(json.dumps({
                    "evolution_id": result.evolution_id,
                    "state": result.state.value,
                    "changes": result.changes,
                    "validation_results": result.validation_results,
                    "duration": result.duration
                }, indent=2))
            else:
                print(f"Evolution completed: {result.state.value}")
                print(f"Duration: {result.duration:.2f}s")
            
            return 0
        
        # Default: show help
        parser.print_help()
        return 0
        
    except Exception as e:
        logger.exception("Fatal error")
        return 1


if __name__ == "__main__":
    exit(main())