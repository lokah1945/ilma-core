#!/usr/bin/env python3
"""
ILMA Reflection Engine v1.0
============================
Converts judge failure into actionable fix plan.
Phase 46 - Autonomous Evolution Foundation.

Input:
- target
- actor output
- judge result
- previous attempts

Output:
- root_cause
- failed_assumption
- fix_plan
- files_to_change
- tests_to_run
- lesson_candidate
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ILMA paths
ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
WORKSPACE = ILMA_PROFILE


@dataclass
class ReflectionResult:
    """Reflection analysis result."""
    root_cause: str
    failed_assumption: str
    fix_plan: List[str]
    files_to_change: List[str]
    tests_to_run: List[str]
    lesson_candidate: Dict[str, Any]
    hallucination_detected: bool = False
    repeated_failure: bool = False
    missing_dependency: bool = False
    unclear_target: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ReflectionEngine:
    """
    Reflection engine - converts failure to fix plan.
    
    Analyzes:
    - Hallucination/overclaim detection
    - Test failure analysis
    - Missing dependency classification
    - Unclear target classification
    - Repeated failure detection
    """

    def __init__(self):
        self.failure_patterns: List[str] = []

    def analyze(
        self,
        target: str,
        artifact: str,
        judge_result: Dict[str, Any],
        previous_attempts: List[Dict[str, Any]] = None
    ) -> ReflectionResult:
        """
        Analyze failure and produce fix plan.
        """
        previous_attempts = previous_attempts or []
        failures = judge_result.get("failures", [])
        warnings = judge_result.get("warnings", [])
        
        # Detect failure types
        hallucination = self._detect_hallucination(artifact)
        missing_dep = self._detect_missing_dependency(failures, artifact)
        unclear = self._detect_unclear_target(target, failures)
        repeated = self._detect_repeated_failure(failures, previous_attempts)
        
        # Determine root cause
        root_cause = self._determine_root_cause(
            failures, hallucination, missing_dep, unclear
        )
        
        # Determine failed assumption
        failed_assumption = self._determine_failed_assumption(
            failures, root_cause
        )
        
        # Generate fix plan
        fix_plan = self._generate_fix_plan(
            failures, root_cause, hallucination, missing_dep, unclear
        )
        
        # Identify files to change
        files_to_change = self._identify_files(artifact, failures)
        
        # Identify tests to run
        tests_to_run = self._identify_tests(failures)
        
        # Create lesson candidate
        lesson_candidate = self._create_lesson_candidate(
            root_cause, failed_assumption, fix_plan, failures
        )
        
        return ReflectionResult(
            root_cause=root_cause,
            failed_assumption=failed_assumption,
            fix_plan=fix_plan,
            files_to_change=files_to_change,
            tests_to_run=tests_to_run,
            lesson_candidate=lesson_candidate,
            hallucination_detected=hallucination,
            repeated_failure=repeated,
            missing_dependency=missing_dep,
            unclear_target=unclear
        )

    def _detect_hallucination(self, artifact: str) -> bool:
        """Detect hallucination or overclaim."""
        # Look for overclaim patterns
        overclaim_patterns = [
            r'100%.*?(?:secure|perfect|guarantee)',
            r'always.*?(?:works|success)',
            r'proven.*?(?:best|fastest)',
            r'no.*?(?:bug|error|problem)',
            r'guaranteed.*?(?:to work|success)',
            r'universal.*?(?:solution|fix)',
        ]
        
        for pattern in overclaim_patterns:
            if re.search(pattern, artifact, re.IGNORECASE):
                return True
        
        return False

    def _detect_missing_dependency(self, failures: List[str], artifact: str) -> bool:
        """Detect missing dependency."""
        dep_patterns = [
            'ModuleNotFoundError',
            'ImportError',
            'No module named',
            'undefined.*not.*defined',
            'cannot import',
            'dependency',
            'requirement',
        ]
        
        for failure in failures:
            for pattern in dep_patterns:
                if pattern.lower() in failure.lower():
                    return True
        
        return False

    def _detect_unclear_target(self, target: str, failures: List[str]) -> bool:
        """Detect unclear target."""
        # If no clear failures but still failing, target might be unclear
        vague_indicators = [
            'unclear',
            'ambiguous',
            'not specific',
            'missing requirement',
            'incomplete specification',
        ]
        
        for failure in failures:
            for indicator in vague_indicators:
                if indicator in failure.lower():
                    return True
        
        return False

    def _detect_repeated_failure(
        self,
        failures: List[str],
        previous_attempts: List[Dict[str, Any]]
    ) -> bool:
        """Detect if same failure pattern repeats."""
        if len(previous_attempts) < 1:
            return False
        
        # Get current failure signature
        current_sig = self._failure_signature(failures)
        
        # Check previous attempts
        for attempt in previous_attempts[:-1]:  # Exclude current
            if 'judge_result' in attempt:
                prev_failures = attempt['judge_result'].get('failures', [])
                prev_sig = self._failure_signature(prev_failures)
                if current_sig == prev_sig:
                    return True
        
        return False

    def _failure_signature(self, failures: List[str]) -> str:
        """Generate signature for failure pattern."""
        if not failures:
            return "no_failures"
        # Normalize
        sig_parts = []
        for f in failures:
            # Remove numbers and specific values
            normalized = re.sub(r'\d+', 'N', f)
            normalized = re.sub(r'["\'].*?["\']', 'X', normalized)
            sig_parts.append(normalized[:30])
        sig_parts.sort()
        return '|'.join(sig_parts)

    def _determine_root_cause(
        self,
        failures: List[str],
        hallucination: bool,
        missing_dep: bool,
        unclear: bool
    ) -> str:
        """Determine root cause of failure."""
        if hallucination:
            return "Hallucination: Artifact contains overclaims without evidence"
        
        if missing_dep:
            return "Missing dependency: Required module or resource not available"
        
        if unclear:
            return "Unclear target: Requirements not specific enough"
        
        if not failures:
            return "Unknown: No clear failure detected"
        
        # Analyze failure types
        failure_text = ' '.join(failures).lower()
        
        if 'syntax' in failure_text:
            return "Syntax error: Code does not parse"
        
        if 'test' in failure_text:
            return "Test failure: Code does not pass required tests"
        
        if 'security' in failure_text:
            return "Security issue: Dangerous pattern detected"
        
        if 'error' in failure_text or 'exception' in failure_text:
            return "Runtime error: Code throws exception"
        
        if 'implement' in failure_text or 'missing' in failure_text:
            return "Incomplete implementation: Required component missing"
        
        return f"Validation failure: {'; '.join(failures[:2])}"

    def _determine_failed_assumption(
        self,
        failures: List[str],
        root_cause: str
    ) -> str:
        """Determine what assumption failed."""
        if 'syntax' in root_cause.lower():
            return "Assumed code would parse correctly"
        
        if 'test' in root_cause.lower():
            return "Assumed implementation would satisfy test cases"
        
        if 'security' in root_cause.lower():
            return "Assumed code patterns were safe"
        
        if 'runtime' in root_cause.lower():
            return "Assumed all input cases were handled"
        
        if 'missing' in root_cause.lower() or 'implement' in root_cause.lower():
            return "Assumed all requirements were addressed"
        
        if 'hallucination' in root_cause.lower():
            return "Made claims without sufficient evidence"
        
        return "Assumed implementation met all criteria"

    def _generate_fix_plan(
        self,
        failures: List[str],
        root_cause: str,
        hallucination: bool,
        missing_dep: bool,
        unclear: bool
    ) -> List[str]:
        """Generate step-by-step fix plan."""
        plan = []
        
        if hallucination:
            plan.append("Remove all absolute claims (100%, always, guaranteed, never)")
            plan.append("Add evidence IDs for any verifiable claims")
            plan.append("Add appropriate hedging language (e.g., 'typically', 'should')")
        
        if missing_dep:
            plan.append("Identify missing dependency from error message")
            plan.append("Check if dependency is in requirements.txt")
            plan.append("If stdlib: Import correct module")
            plan.append("If external: Document as new dependency")
        
        if unclear:
            plan.append("Break down target into specific, measurable requirements")
            plan.append("Define success criteria explicitly")
            plan.append("Identify any ambiguous terms and clarify")
        
        # General fixes based on failures
        for failure in failures:
            failure_lower = failure.lower()
            
            if 'syntax' in failure_lower:
                plan.append("Fix syntax error - check line number in error")
            
            if 'test' in failure_lower:
                plan.append("Run tests to identify specific failures")
                plan.append("Fix failing test cases or add missing tests")
            
            if 'security' in failure_lower:
                plan.append(f"Address security issue: {failure}")
                plan.append("Remove dangerous pattern or add proper sanitization")
            
            if 'error' in failure_lower or 'exception' in failure_lower:
                plan.append("Add try-except block to handle exception")
                plan.append("Validate input to prevent exception")
            
            if 'implement' in failure_lower or 'missing' in failure_lower:
                plan.append("Implement missing component")
            
            if 'evidence' in failure_lower:
                plan.append("Add evidence IDs or supporting documentation")
        
        # Default
        if not plan:
            plan.append("Review failure messages carefully")
            plan.append("Make targeted fixes based on specific errors")
            plan.append("Re-run judge after each fix")
        
        # === PHASE 57: LIVE RESEARCH TRIGGER ===
        # If fix plan is weak (≤2 steps) AND root cause is unclear/unknown,
        # trigger live research to find external solutions
        if len(plan) <= 2 and root_cause and ("unknown" in root_cause.lower() or "unclear" in root_cause.lower()):
            plan = self._enhance_with_live_research(plan, failures, root_cause)
        
        return plan[:10]  # Limit to 10 steps

    def _enhance_with_live_research(self, plan: List[str], failures: List[str], root_cause: str) -> List[str]:
        """Enhance fix plan with live research results."""
        try:
            from scripts.ilma_live_research import LiveResearch
            
            error_context = failures[0] if failures else root_cause
            lr = LiveResearch()
            
            # Check if research is warranted
            should, reason = lr.should_research(
                failed_attempts=2,  # At least 2 failed attempts
                root_cause=root_cause,
                has_lesson_memory=False
            )
            
            if should:
                print(f"\n🧪 [LIVE RESEARCH] Triggered: {reason}")
                
                result = lr.research(
                    error_context=error_context,
                    task_type="code",
                    root_cause=root_cause,
                    failed_attempts=2
                )
                
                if result.solutions:
                    # Add top solutions to fix plan
                    plan.append(f"📚 Live research found {len(result.solutions)} potential solution(s)")
                    for sol in result.solutions[:3]:
                        plan.append(f"  → {sol[:150]}")
                    
                    # Store for future use
                    lr.store_research_result(error_context, result)
                    
                    # Add new knowledge to plan
                    if result.papers:
                        plan.append(f"  📄 Relevant papers: {len(result.papers)}")
                        for p in result.papers[:2]:
                            plan.append(f"     • {p.get('title', 'Unknown')[:100]}")
                else:
                    plan.append("⚠️ Live research: No solutions found online")
                    plan.append("  → Consider manual debugging or asking for help")
            else:
                plan.append(f"No live research needed: {reason}")
                
        except ImportError:
            plan.append("⚠️ Live research module not available (ilma_live_research.py missing)")
        except Exception as e:
            plan.append(f"⚠️ Live research failed: {str(e)[:80]}")
        
        return plan

    def _identify_files(self, artifact: str, failures: List[str]) -> List[str]:
        """Identify which files need to change."""
        files = []
        
        # Look for file paths in artifact
        path_patterns = [
            r'([/\w]+\.py)',
            r'([/\w]+\.json)',
            r'([/\w]+\.md)',
            r'file[:\s]+([/\w]+\.\w+)',
        ]
        
        for pattern in path_patterns:
            matches = re.findall(pattern, artifact)
            files.extend(matches)
        
        # Dedupe
        return list(set(files))[:5]

    def _identify_tests(self, failures: List[str]) -> List[str]:
        """Identify which tests to run."""
        tests = []
        
        failure_text = ' '.join(failures).lower()
        
        if 'syntax' in failure_text:
            tests.append("Compile check")
        
        if 'test' in failure_text:
            tests.append("pytest")
            tests.append("Unit tests")
        
        if 'security' in failure_text:
            tests.append("Security scan")
        
        if 'error' in failure_text or 'exception' in failure_text:
            tests.append("Runtime test")
        
        return list(set(tests))[:5]

    def _create_lesson_candidate(
        self,
        root_cause: str,
        failed_assumption: str,
        fix_plan: List[str],
        failures: List[str]
    ) -> Dict[str, Any]:
        """Create lesson candidate for memory storage."""
        return {
            "lesson_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "phase": "Phase 46",
            "task_type": "unknown",
            "failure_pattern": root_cause,
            "root_cause": root_cause,
            "failed_assumption": failed_assumption,
            "fix": '; '.join(fix_plan[:3]),
            "validation_method": "judge_evaluation",
            "future_rule": f"When encountering: {failures[0] if failures else 'unknown'}, consider: {root_cause}",
            "confidence": 0.8,
            "source_evidence": "reflection_engine"
        }


def run_demo():
    """Run reflection demo."""
    print("=" * 60)
    print("ILMA Reflection Engine v1.0")
    print("=" * 60)
    
    engine = ReflectionEngine()
    
    test_cases = [
        {
            "name": "Syntax error",
            "target": "Build factorial",
            "artifact": "def factorial(n):\n    return n * factorial(n-1)\n    return 1",
            "judge_result": {"failures": ["Syntax error at line 2"], "warnings": []}
        },
        {
            "name": "Overclaim",
            "target": "Build factorial",
            "artifact": "This is 100% perfect and will ALWAYS work with no bugs!",
            "judge_result": {"failures": ["Overclaim: absolute security claim"], "warnings": []}
        },
        {
            "name": "Missing test",
            "target": "Build factorial",
            "artifact": "def factorial(n):\n    return 1",
            "judge_result": {"failures": ["Test failed: factorial(5) != 120"], "warnings": ["Missing edge case tests"]}
        }
    ]
    
    for tc in test_cases:
        print(f"\n[{tc['name']}]")
        result = engine.analyze(tc["target"], tc["artifact"], tc["judge_result"])
        print(f"  Root cause: {result.root_cause[:60]}...")
        print(f"  Failed assumption: {result.failed_assumption[:60]}...")
        print(f"  Fix plan ({len(result.fix_plan)} steps):")
        for step in result.fix_plan[:3]:
            print(f"    - {step[:60]}...")
        if result.lesson_candidate:
            print(f"  Lesson ID: {result.lesson_candidate.get('lesson_id', 'N/A')[:8]}...")


if __name__ == "__main__":
    run_demo()