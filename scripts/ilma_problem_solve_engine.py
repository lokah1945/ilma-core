#!/usr/bin/env python3
"""
ILMA Problem Solving Engine
==========================
Advanced problem decomposition, solution mapping, and failure recovery.

Classes: ProblemDecomposer, SolutionMapper, FailureRecovery

Usage:
    python3 ilma_problem_solve_engine.py --decompose "complex problem description"
    python3 ilma_problem_solve_engine.py --map-solution --problem-id 12345
    python3 ilma_problem_solve_engine.py --recover --failure-id 99

Author: ILMA v5.0
Version: 1.0.0
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ProblemSolveEngine")


# =============================================================================
# ENUMS AND DATA STRUCTURES
# =============================================================================

class ProblemComplexity(Enum):
    """Problem complexity levels."""
    TRIVIAL = "trivial"       # < 5 min to solve
    SIMPLE = "simple"         # 5-15 min
    MODERATE = "moderate"     # 15-60 min
    COMPLEX = "complex"       # 1-4 hours
    VERY_COMPLEX = "very_complex"  # 4+ hours
    UNSOLVABLE = "unsolvable"  # Cannot be solved with current resources


class ProblemDomain(Enum):
    """Problem domains."""
    SOFTWARE = "software"
    INFRASTRUCTURE = "infrastructure"
    BUSINESS = "business"
    DATA = "data"
    SECURITY = "security"
    USER_EXPERIENCE = "user_experience"
    UNKNOWN = "unknown"


class SolutionStatus(Enum):
    """Solution status."""
    PROPOSED = "proposed"
    VALIDATED = "validated"
    IMPLEMENTED = "implemented"
    FAILED = "failed"
    DEPRECATED = "deprecated"


@dataclass
class Problem:
    """Problem representation."""
    id: str
    description: str
    domain: ProblemDomain
    complexity: ProblemComplexity
    constraints: List[str] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)
    sub_problems: List['Problem'] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SubProblem:
    """Decomposed sub-problem."""
    id: str
    name: str
    description: str
    priority: int
    dependencies: List[str] = field(default_factory=list)
    estimated_effort_hours: float = 1.0
    solution_approaches: List[str] = field(default_factory=list)


@dataclass
class SolutionPath:
    """Solution path representation."""
    problem_id: str
    steps: List[str]
    estimated_time_hours: float
    success_probability: float
    resources_required: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    fallback_options: List[str] = field(default_factory=list)


@dataclass
class FailureRecord:
    """Record of a failure and recovery action."""
    id: str
    failure_time: datetime
    description: str
    root_cause: Optional[str] = None
    impact_level: str = "medium"
    recovery_actions: List[str] = field(default_factory=list)
    recovery_time_minutes: float = 0
    status: str = "open"


# =============================================================================
# PROBLEM DECOMPOSER CLASS
# =============================================================================

class ProblemDecomposer:
    """
    Breaks down complex problems into manageable sub-problems.
    
    Uses hierarchical decomposition, dependency analysis, and
    complexity scoring.
    """
    
    DECOMPOSITION_PATTERNS = {
        "software": [
            "requirements",
            "architecture",
            "implementation",
            "testing",
            "deployment"
        ],
        "infrastructure": [
            "assessment",
            "planning",
            "implementation",
            "validation",
            "monitoring"
        ],
        "business": [
            "analysis",
            "strategy",
            "execution",
            "review"
        ],
        "data": [
            "collection",
            "validation",
            "processing",
            "analysis",
            "reporting"
        ],
        "security": [
            "threat_modeling",
            "mitigation",
            "implementation",
            "testing",
            "monitoring"
        ]
    }
    
    def __init__(self):
        self.problems: Dict[str, Problem] = {}
        self.sub_problems: Dict[str, List[SubProblem]] = {}
        logger.info("ProblemDecomposer initialized")
    
    def decompose(
        self,
        description: str,
        domain: ProblemDomain = ProblemDomain.UNKNOWN,
        depth: int = 3
    ) -> Problem:
        """Decompose a problem into sub-problems."""
        problem_id = f"problem_{int(time.time())}"
        
        # Analyze complexity
        complexity = self._assess_complexity(description)
        
        problem = Problem(
            id=problem_id,
            description=description,
            domain=domain,
            complexity=complexity
        )
        
        # Extract goals and constraints
        problem.goals = self._extract_goals(description)
        problem.constraints = self._extract_constraints(description)
        
        # Generate sub-problems based on domain
        if domain != ProblemDomain.UNKNOWN:
            problem.sub_problems = self._generate_sub_problems(
                description, domain, depth
            )
        
        self.problems[problem_id] = problem
        
        logger.info(f"Decomposed problem: {problem_id} ({len(problem.sub_problems)} sub-problems)")
        
        return problem
    
    def _assess_complexity(self, description: str) -> ProblemComplexity:
        """Assess problem complexity based on description."""
        complexity_score = 0
        
        # Length indicators
        if len(description) > 500:
            complexity_score += 2
        elif len(description) > 200:
            complexity_score += 1
        
        # Keywords indicating complexity
        complex_keywords = [
            "distributed", "microservices", "scalability", "performance",
            "security", "authentication", "real-time", "concurrent",
            "legacy", "monolith", "refactoring", "migration"
        ]
        
        for keyword in complex_keywords:
            if keyword.lower() in description.lower():
                complexity_score += 1
        
        # Technical terms
        tech_terms = len(re.findall(r'\b[A-Z][a-z]+[A-Z]\b|\b\w+\.\w+\b', description))
        complexity_score += min(tech_terms // 3, 3)
        
        # Number of constraints/goals mentioned
        constraint_count = len(re.findall(r'(must|should|have to|need to|require)', description, re.I))
        complexity_score += min(constraint_count // 2, 2)
        
        # Map score to complexity
        if complexity_score <= 2:
            return ProblemComplexity.TRIVIAL
        elif complexity_score <= 4:
            return ProblemComplexity.SIMPLE
        elif complexity_score <= 6:
            return ProblemComplexity.MODERATE
        elif complexity_score <= 9:
            return ProblemComplexity.COMPLEX
        else:
            return ProblemComplexity.VERY_COMPLEX
    
    def _extract_goals(self, description: str) -> List[str]:
        """Extract goals from problem description."""
        goals = []
        
        # Look for "to" patterns
        patterns = [
            r'to\s+(\w+\s+\w+)',
            r'goal:\s*([^\.]+)',
            r'want\s+(\w+\s+\w+\s+\w+)',
            r'need\s+(\w+\s+\w+\s+\w+)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, description, re.I)
            goals.extend(matches[:3])  # Limit to 3
        
        return list(set(goals))[:5]  # Dedupe and limit
    
    def _extract_constraints(self, description: str) -> List[str]:
        """Extract constraints from problem description."""
        constraints = []
        
        # Look for constraint patterns
        constraint_keywords = ["must", "cannot", "should not", "only", "must not"]
        
        sentences = description.split(".")
        for sentence in sentences:
            sentence = sentence.strip()
            if any(kw in sentence.lower() for kw in constraint_keywords):
                constraints.append(sentence)
        
        return constraints[:5]
    
    def _generate_sub_problems(
        self,
        description: str,
        domain: ProblemDomain,
        depth: int
    ) -> List[Problem]:
        """Generate sub-problems based on domain and depth."""
        sub_problems = []
        
        if domain.value not in self.DECOMPOSITION_PATTERNS:
            # Generic decomposition
            return [
                Problem(
                    id=f"sub_{i}",
                    description=f"Sub-problem {i}: {description[:100]}",
                    domain=domain,
                    complexity=self._assess_complexity(description)
                )
                for i in range(3)
            ]
        
        phases = self.DECOMPOSITION_PATTERNS[domain.value]
        
        for i, phase in enumerate(phases[:depth * 2]):
            sub = Problem(
                id=f"{self.problems.keys()[-1]}_sub_{i}",
                description=f"{phase}: {description[:50]}...",
                domain=domain,
                complexity=self._assess_complexity(description) if i == 0 else ProblemComplexity.SIMPLE
            )
            sub_problems.append(sub)
        
        return sub_problems
    
    def get_problem_tree(self, problem_id: str) -> Dict[str, Any]:
        """Get hierarchical problem tree."""
        if problem_id not in self.problems:
            return {}
        
        problem = self.problems[problem_id]
        
        tree = {
            "id": problem.id,
            "description": problem.description,
            "domain": problem.domain.value,
            "complexity": problem.complexity.value,
            "goals": problem.goals,
            "constraints": problem.constraints,
            "sub_problems": [
                {
                    "id": sp.id,
                    "description": sp.description,
                    "priority": sp.priority,
                    "estimated_hours": sp.estimated_effort_hours
                }
                for sp in problem.sub_problems
            ]
        }
        
        return tree
    
    def prioritize_sub_problems(self, problem_id: str) -> List[SubProblem]:
        """Prioritize sub-problems based on dependencies and effort."""
        if problem_id not in self.problems:
            return []
        
        problem = self.problems[problem_id]
        
        prioritized = []
        for sp in problem.sub_problems:
            priority_score = self._calculate_priority(sp)
            sp.priority = priority_score
            prioritized.append(sp)
        
        return sorted(prioritized, key=lambda x: x.priority, reverse=True)
    
    def _calculate_priority(self, sub_problem: SubProblem) -> int:
        """Calculate priority score for a sub-problem."""
        score = 10
        
        # Higher priority for fewer dependencies
        if not sub_problem.dependencies:
            score += 5
        
        # Lower priority for high effort
        if sub_problem.estimated_effort_hours > 8:
            score -= 2
        
        # Add some variance
        score += random.randint(-2, 2)
        
        return max(1, min(score, 20))
    
    def suggest_next_steps(self, problem_id: str) -> List[str]:
        """Suggest next steps for problem resolution."""
        prioritized = self.prioritize_sub_problems(problem_id)
        
        steps = []
        for i, sp in enumerate(prioritized[:5]):
            steps.append(f"Step {i+1}: {sp.name} - {sp.description[:80]}...")
        
        return steps


# =============================================================================
# SOLUTION MAPPER CLASS
# =============================================================================

class SolutionMapper:
    """
    Maps problems to solutions with multiple approaches.
    
    Evaluates solution paths, estimates success probability,
    and provides recommendations.
    """
    
    SOLUTION_TEMPLATES = {
        ProblemDomain.SOFTWARE: [
            "Modular architecture with clear separation of concerns",
            "API-first design with versioned endpoints",
            "Comprehensive testing strategy (unit, integration, e2e)",
            "CI/CD pipeline with automated quality gates",
            "Observability stack (logging, metrics, tracing)"
        ],
        ProblemDomain.INFRASTRUCTURE: [
            "Infrastructure as Code (Terraform/Pulumi)",
            "Container orchestration with Kubernetes",
            "Multi-region deployment with geo-redundancy",
            "Automated backup and disaster recovery",
            "Centralized monitoring and alerting"
        ],
        ProblemDomain.BUSINESS: [
            "Lean startup methodology with MVP",
            "Data-driven decision making",
            "Agile sprints with retrospectives",
            "Customer feedback loops",
            "KPI tracking and optimization"
        ],
        ProblemDomain.DATA: [
            "Data quality framework with validation",
            "ETL pipelines with monitoring",
            "Data catalog with lineage tracking",
            "Self-service analytics platform",
            "ML model lifecycle management"
        ],
        ProblemDomain.SECURITY: [
            "Defense in depth architecture",
            "Zero trust network model",
            "Security automation (SAST/DAST)",
            "Incident response playbooks",
            "Regular security audits and penetration testing"
        ]
    }
    
    def __init__(self):
        self.solutions: Dict[str, SolutionPath] = {}
        logger.info("SolutionMapper initialized")
    
    def map_solution(
        self,
        problem: Problem,
        max_solutions: int = 3
    ) -> List[SolutionPath]:
        """Map problem to potential solutions."""
        templates = self.SOLUTION_TEMPLATES.get(problem.domain, [
            "Analysis and planning phase",
            "Implementation phase",
            "Validation and testing phase",
            "Deployment and monitoring phase"
        ])
        
        solutions = []
        
        for i in range(min(max_solutions, len(templates))):
            solution = self._create_solution(problem, templates[i], i)
            solutions.append(solution)
            self.solutions[f"{problem.id}_sol_{i}"] = solution
        
        # Sort by success probability
        solutions.sort(key=lambda x: x.success_probability, reverse=True)
        
        logger.info(f"Mapped {len(solutions)} solutions for problem {problem.id}")
        
        return solutions
    
    def _create_solution(
        self,
        problem: Problem,
        approach: str,
        index: int
    ) -> SolutionPath:
        """Create a solution path."""
        steps = self._decompose_into_steps(approach, problem)
        
        # Calculate success probability
        base_probability = 0.7 - (index * 0.1)  # First solution is most likely
        complexity_factor = {
            ProblemComplexity.TRIVIAL: 0.15,
            ProblemComplexity.SIMPLE: 0.1,
            ProblemComplexity.MODERATE: 0.0,
            ProblemComplexity.COMPLEX: -0.1,
            ProblemComplexity.VERY_COMPLEX: -0.2,
            ProblemComplexity.UNSOLVABLE: -0.3
        }
        
        success_prob = base_probability + complexity_factor.get(problem.complexity, 0)
        success_prob = max(0.1, min(0.95, success_prob))
        
        # Estimate time
        time_estimates = {
            ProblemComplexity.TRIVIAL: 0.5,
            ProblemComplexity.SIMPLE: 2.0,
            ProblemComplexity.MODERATE: 8.0,
            ProblemComplexity.COMPLEX: 24.0,
            ProblemComplexity.VERY_COMPLEX: 80.0,
            ProblemComplexity.UNSOLVABLE: 999.0
        }
        
        estimated_hours = time_estimates.get(problem.complexity, 8.0)
        if index > 0:
            estimated_hours *= 0.8  # Alternative solutions may be faster
        
        # Identify risks
        risks = self._identify_risks(problem, approach)
        
        return SolutionPath(
            problem_id=problem.id,
            steps=steps,
            estimated_time_hours=estimated_hours,
            success_probability=success_prob,
            resources_required=self._get_required_resources(problem.domain),
            risks=risks,
            fallback_options=self._generate_fallbacks(approach)
        )
    
    def _decompose_into_steps(self, approach: str, problem: Problem) -> List[str]:
        """Decompose solution into executable steps."""
        steps = []
        
        # Add discovery step
        steps.append("Discovery: Analyze requirements and constraints")
        
        # Add approach-specific steps
        if "architecture" in approach.lower():
            steps.append("Design system architecture with component diagram")
            steps.append("Define API contracts and data models")
            steps.append("Evaluate technology stack options")
        elif "implementation" in approach.lower():
            steps.append("Set up development environment")
            steps.append("Implement core functionality")
            steps.append("Add error handling and logging")
        elif "testing" in approach.lower():
            steps.append("Define test strategy and coverage goals")
            steps.append("Implement unit tests")
            steps.append("Execute integration tests")
        else:
            steps.append(f"Execute: {approach}")
            steps.append("Validate results against requirements")
        
        # Add common finalization steps
        steps.append("Document solution and create runbook")
        steps.append("Plan for maintenance and support")
        
        return steps
    
    def _identify_risks(self, problem: Problem, approach: str) -> List[str]:
        """Identify potential risks for the solution."""
        risks = []
        
        if problem.complexity in (ProblemComplexity.COMPLEX, ProblemComplexity.VERY_COMPLEX):
            risks.append("Complexity may lead to scope creep")
            risks.append("Integration challenges with existing systems")
        
        if len(problem.constraints) > 3:
            risks.append("Constraint saturation may limit flexibility")
        
        if "legacy" in problem.description.lower():
            risks.append("Legacy system dependencies may cause delays")
        
        risks.append("Resource availability may impact timeline")
        
        return risks[:4]
    
    def _get_required_resources(self, domain: ProblemDomain) -> List[str]:
        """Get required resources for a domain."""
        resources = {
            ProblemDomain.SOFTWARE: ["Developers", "QA Engineers", "CI/CD Pipeline", "Test Environment"],
            ProblemDomain.INFRASTRUCTURE: ["DevOps Engineers", "Cloud Resources", "Monitoring Tools"],
            ProblemDomain.BUSINESS: ["Business Analysts", "Stakeholder Time", "Data Sources"],
            ProblemDomain.DATA: ["Data Engineers", "Data Warehouse", "Analytics Tools"],
            ProblemDomain.SECURITY: ["Security Engineers", "Security Tools", "Audit Support"],
            ProblemDomain.UNKNOWN: ["General Resources", "Planning Time"]
        }
        
        return resources.get(domain, ["General Resources"])
    
    def _generate_fallbacks(self, approach: str) -> List[str]:
        """Generate fallback options."""
        fallbacks = [
            "Reduce scope to core functionality",
            "Extend timeline if complexity is underestimated",
            "Prioritize quality over speed",
            "Consider outsourcing non-critical components"
        ]
        
        return fallbacks
    
    def validate_solution(self, solution: SolutionPath) -> Dict[str, Any]:
        """Validate a solution against problem constraints."""
        validation = {
            "is_valid": True,
            "warnings": [],
            "recommendations": []
        }
        
        if solution.success_probability < 0.5:
            validation["warnings"].append("Low success probability - consider alternatives")
        
        if solution.estimated_time_hours > 40:
            validation["recommendations"].append("Consider breaking into smaller phases")
        
        if len(solution.risks) > 3:
            validation["recommendations"].append("Develop detailed risk mitigation plan")
        
        return validation
    
    def compare_solutions(
        self,
        solution_a: SolutionPath,
        solution_b: SolutionPath
    ) -> Dict[str, Any]:
        """Compare two solutions."""
        comparison = {
            "solution_a_time": solution_a.estimated_time_hours,
            "solution_b_time": solution_b.estimated_time_hours,
            "time_diff": solution_a.estimated_time_hours - solution_b.estimated_time_hours,
            "solution_a_prob": solution_a.success_probability,
            "solution_b_prob": solution_b.success_probability,
            "prob_diff": solution_a.success_probability - solution_b.success_probability,
            "recommended": "A" if solution_a.success_probability > solution_b.success_probability else "B"
        }
        
        return comparison


# =============================================================================
# FAILURE RECOVERY CLASS
# =============================================================================

class FailureRecovery:
    """
    Failure analysis and recovery orchestration.
    
    Tracks failures, identifies root causes, and manages
    recovery procedures.
    """
    
    def __init__(self):
        self.failures: Dict[str, FailureRecord] = {}
        self.recovery_playbooks: Dict[str, List[str]] = {
            "timeout": [
                "Check service health endpoints",
                "Review recent deployment changes",
                "Scale up if resource constrained",
                "Implement circuit breaker"
            ],
            "crash": [
                "Capture crash dump/logs",
                "Identify last known good state",
                "Rollback if recent change detected",
                "Restart service with recovery mode"
            ],
            "data_corruption": [
                "Isolate affected data stores",
                "Restore from backup",
                "Validate data integrity",
                "Implement checksum validation"
            ],
            "security_incident": [
                "Isolate affected systems",
                "Preserve forensic evidence",
                "Reset compromised credentials",
                "Conduct security audit"
            ],
            "performance_degradation": [
                "Check resource utilization",
                "Review slow query logs",
                "Analyze recent traffic patterns",
                "Implement caching if applicable"
            ]
        }
        logger.info("FailureRecovery initialized")
    
    def record_failure(
        self,
        description: str,
        impact_level: str = "medium"
    ) -> FailureRecord:
        """Record a new failure."""
        failure_id = f"failure_{int(time.time())}"
        
        failure = FailureRecord(
            id=failure_id,
            failure_time=datetime.now(),
            description=description,
            impact_level=impact_level
        )
        
        self.failures[failure_id] = failure
        
        logger.info(f"Recorded failure: {failure_id}")
        
        return failure
    
    def analyze_root_cause(self, failure_id: str) -> Optional[str]:
        """Analyze and identify root cause of failure."""
        if failure_id not in self.failures:
            return None
        
        failure = self.failures[failure_id]
        
        # Simple keyword-based root cause detection
        description_lower = failure.description.lower()
        
        root_causes = {
            "timeout": ["timeout", "timed out", "deadline", "slow response"],
            "crash": ["crash", "segfault", "killed", "core dumped"],
            "data_corruption": ["corrupt", "invalid", "malformed", "checksum failed"],
            "security_incident": ["unauthorized", "breach", "injection", "exploit"],
            "performance_degradation": ["slow", "latency", "high cpu", "memory leak"]
        }
        
        for cause, keywords in root_causes.items():
            if any(kw in description_lower for kw in keywords):
                failure.root_cause = cause
                return cause
        
        failure.root_cause = "unknown"
        return "unknown"
    
    def suggest_recovery(self, failure_id: str) -> List[str]:
        """Suggest recovery actions for a failure."""
        if failure_id not in self.failures:
            return []
        
        failure = self.failures[failure_id]
        
        if failure.root_cause and failure.root_cause in self.recovery_playbooks:
            return self.recovery_playbooks[failure.root_cause]
        
        # Return generic recovery steps
        return [
            "Gather diagnostic information",
            "Identify recent changes",
            "Implement containment if needed",
            "Restore to known good state",
            "Verify recovery was successful"
        ]
    
    def execute_recovery(
        self,
        failure_id: str,
        recovery_action: str
    ) -> Dict[str, Any]:
        """Execute a recovery action and track results."""
        if failure_id not in self.failures:
            return {"success": False, "error": "Failure not found"}
        
        failure = self.failures[failure_id]
        
        start_time = time.time()
        
        # Simulate recovery execution
        # In production, this would actually execute the recovery
        
        success = random.random() > 0.1  # 90% success rate simulation
        
        recovery_time = (time.time() - start_time) * 60  # Convert to minutes
        
        failure.recovery_actions.append({
            "action": recovery_action,
            "timestamp": datetime.now().isoformat(),
            "success": success
        })
        
        if success:
            failure.status = "resolved"
            failure.recovery_time_minutes += recovery_time
        else:
            failure.status = "failed_recovery"
        
        return {
            "success": success,
            "failure_id": failure_id,
            "action": recovery_action,
            "recovery_time_minutes": recovery_time,
            "new_status": failure.status
        }
    
    def get_failure_summary(self) -> Dict[str, Any]:
        """Get summary of all failures."""
        if not self.failures:
            return {"total": 0, "by_status": {}, "by_impact": {}}
        
        by_status = {}
        by_impact = {}
        
        for failure in self.failures.values():
            # Count by status
            status = failure.status
            by_status[status] = by_status.get(status, 0) + 1
            
            # Count by impact
            impact = failure.impact_level
            by_impact[impact] = by_impact.get(impact, 0) + 1
        
        return {
            "total": len(self.failures),
            "by_status": by_status,
            "by_impact": by_impact,
            "open_failures": sum(1 for f in self.failures.values() if f.status == "open")
        }
    
    def create_incident_report(self, failure_id: str) -> str:
        """Create a formatted incident report."""
        if failure_id not in self.failures:
            return "Failure not found"
        
        failure = self.failures[failure_id]
        
        report = f"""
=== Incident Report ===

ID: {failure.id}
Time: {failure.failure_time.isoformat()}
Description: {failure.description}
Impact: {failure.impact_level}
Root Cause: {failure.root_cause or 'Under investigation'}
Status: {failure.status}

Recovery Actions:
"""
        
        for action in failure.recovery_actions:
            status = "✓" if action["success"] else "✗"
            report += f"  {status} {action['action']} ({action['timestamp']})\n"
        
        report += f"""
Total Recovery Time: {failure.recovery_time_minutes:.1f} minutes

=== End Report ===
"""
        
        return report
    
    def learn_from_failure(self, failure_id: str) -> Dict[str, Any]:
        """Learn from a failure to prevent future occurrences."""
        if failure_id not in self.failures:
            return {}
        
        failure = self.failures[failure_id]
        
        lessons = {
            "root_cause": failure.root_cause,
            "impact_level": failure.impact_level,
            "recovery_time": failure.recovery_time_minutes,
            "successful_actions": [
                a["action"] for a in failure.recovery_actions if a["success"]
            ],
            "failed_actions": [
                a["action"] for a in failure.recovery_actions if not a["success"]
            ],
            "recommendations": self._generate_recommendations(failure)
        }
        
        return lessons
    
    def _generate_recommendations(self, failure: FailureRecord) -> List[str]:
        """Generate recommendations based on failure."""
        recommendations = []
        
        if failure.root_cause == "timeout":
            recommendations.append("Implement circuit breaker pattern")
            recommendations.append("Add timeout handling to all external calls")
            recommendations.append("Set up alerting for timeout errors")
        
        elif failure.root_cause == "crash":
            recommendations.append("Add health checks and restart policies")
            recommendations.append("Implement graceful shutdown handling")
            recommendations.append("Set up crash monitoring and alerting")
        
        elif failure.root_cause == "data_corruption":
            recommendations.append("Implement data validation at entry points")
            recommendations.append("Add checksum validation for stored data")
            recommendations.append("Regular backup validation")
        
        elif failure.root_cause == "security_incident":
            recommendations.append("Review and strengthen authentication")
            recommendations.append("Implement input sanitization")
            recommendations.append("Schedule security audit")
        
        elif failure.root_cause == "performance_degradation":
            recommendations.append("Implement caching strategy")
            recommendations.append("Add query performance monitoring")
            recommendations.append("Set up capacity planning")
        
        return recommendations[:4]


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="ILMA Problem Solving Engine - Decomposition, solution mapping, and failure recovery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Decompose a problem
  %(prog)s --decompose "Build a distributed system that handles 10K req/s"
  
  # Map solutions
  %(prog)s --map-solution --problem-id problem_1234567890 --max-solutions 3
  
  # Record and recover from failure
  %(prog)s --record-failure "Service crashed due to OOM" --impact high
  %(prog)s --recover --failure-id failure_1234567890 --action "Restart service"
  
  # Get failure summary
  %(prog)s --failure-summary
        """
    )
    
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    # Problem decomposition options
    parser.add_argument("--decompose", help="Problem description to decompose")
    parser.add_argument("--domain", choices=["software", "infrastructure", "business", "data", "security"],
                       default="software", help="Problem domain")
    parser.add_argument("--depth", type=int, default=3, help="Decomposition depth")
    parser.add_argument("--problem-id", help="Problem ID to get tree for")
    
    # Solution mapping options
    parser.add_argument("--map-solution", action="store_true", help="Map solutions for a problem")
    parser.add_argument("--max-solutions", type=int, default=3, help="Maximum solutions to generate")
    parser.add_argument("--validate-solution", help="Validate a specific solution")
    
    # Failure recovery options
    parser.add_argument("--record-failure", help="Record a new failure")
    parser.add_argument("--recover", action="store_true", help="Execute recovery")
    parser.add_argument("--failure-id", help="Failure ID for recovery")
    parser.add_argument("--action", help="Recovery action to execute")
    parser.add_argument("--impact", choices=["low", "medium", "high", "critical"], default="medium",
                       help="Failure impact level")
    parser.add_argument("--failure-summary", action="store_true", help="Get failure summary")
    parser.add_argument("--incident-report", help="Generate incident report")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Problem Decomposition
        if args.decompose:
            decomposer = ProblemDecomposer()
            domain = ProblemDomain(args.domain)
            
            problem = decomposer.decompose(args.decompose, domain, args.depth)
            
            print(f"\n=== Problem Decomposed ===")
            print(f"ID: {problem.id}")
            print(f"Domain: {problem.domain.value}")
            print(f"Complexity: {problem.complexity.value}")
            print(f"\nGoals:")
            for goal in problem.goals:
                print(f"  - {goal}")
            print(f"\nConstraints: {len(problem.constraints)}")
            print(f"Sub-problems: {len(problem.sub_problems)}")
            
            tree = decomposer.get_problem_tree(problem.id)
            if tree.get("sub_problems"):
                print("\nSub-problems:")
                for sp in tree["sub_problems"]:
                    print(f"  - [{sp['id']}] {sp['description'][:60]}...")
            
            next_steps = decomposer.suggest_next_steps(problem.id)
            if next_steps:
                print("\nRecommended Next Steps:")
                for step in next_steps:
                    print(f"  {step}")
        
        elif args.problem_id:
            decomposer = ProblemDecomposer()
            tree = decomposer.get_problem_tree(args.problem_id)
            
            if tree:
                print(f"\n=== Problem Tree: {args.problem_id} ===")
                print(f"Description: {tree['description']}")
                print(f"Domain: {tree['domain']}")
                print(f"Complexity: {tree['complexity']}")
                print(f"\nGoals:")
                for goal in tree['goals']:
                    print(f"  - {goal}")
                print(f"\nSub-problems: {len(tree['sub_problems'])}")
            else:
                print(f"Problem not found: {args.problem_id}")
        
        # Solution Mapping
        elif args.map_solution:
            # Need to decompose first or use stored problem
            if not args.problem_id:
                print("Error: --problem-id required for solution mapping")
            else:
                decomposer = ProblemDecomposer()
                # Create a mock problem from stored if available
                # For demo, create a simple one
                problem = decomposer.decompose("Demo problem for solution mapping", 
                                               ProblemDomain.SOFTWARE)
                
                mapper = SolutionMapper()
                solutions = mapper.map_solution(problem, args.max_solutions)
                
                print(f"\n=== Solution Options ===")
                for i, sol in enumerate(solutions):
                    print(f"\nOption {i+1} (Probability: {sol.success_probability:.0%})")
                    print(f"  Estimated Time: {sol.estimated_time_hours:.1f} hours")
                    print(f"  Steps: {len(sol.steps)}")
                    print(f"  Resources: {', '.join(sol.resources_required[:2])}")
                    print(f"  Risks: {len(sol.risks)}")
                
                validation = mapper.validate_solution(solutions[0])
                if validation.get("recommendations"):
                    print("\nRecommendations:")
                    for rec in validation["recommendations"]:
                        print(f"  - {rec}")
        
        # Failure Recording
        elif args.record_failure:
            recovery = FailureRecovery()
            failure = recovery.record_failure(args.record_failure, args.impact)
            
            print(f"\n=== Failure Recorded ===")
            print(f"ID: {failure.id}")
            print(f"Time: {failure.failure_time.isoformat()}")
            print(f"Impact: {failure.impact_level}")
            
            root_cause = recovery.analyze_root_cause(failure.id)
            if root_cause:
                print(f"Root Cause: {root_cause}")
            
            recovery_actions = recovery.suggest_recovery(failure.id)
            print(f"\nSuggested Recovery Actions:")
            for action in recovery_actions:
                print(f"  - {action}")
        
        # Failure Recovery
        elif args.recover:
            if not args.failure_id or not args.action:
                parser.error("--failure-id and --action required for recovery")
            
            recovery = FailureRecovery()
            result = recovery.execute_recovery(args.failure_id, args.action)
            
            print(f"\n=== Recovery Execution ===")
            print(f"Success: {result['success']}")
            print(f"Action: {result['action']}")
            print(f"Recovery Time: {result['recovery_time_minutes']:.1f} minutes")
            print(f"New Status: {result['new_status']}")
        
        # Failure Summary
        elif args.failure_summary:
            recovery = FailureRecovery()
            summary = recovery.get_failure_summary()
            
            print(f"\n=== Failure Summary ===")
            print(f"Total Failures: {summary['total']}")
            print(f"Open: {summary.get('open_failures', 0)}")
            print("\nBy Status:")
            for status, count in summary.get('by_status', {}).items():
                print(f"  {status}: {count}")
            print("\nBy Impact:")
            for impact, count in summary.get('by_impact', {}).items():
                print(f"  {impact}: {count}")
        
        # Incident Report
        elif args.incident_report:
            recovery = FailureRecovery()
            report = recovery.create_incident_report(args.incident_report)
            print(report)
        
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