#!/usr/bin/env python3
"""
ILMA Intelligence Core v1.0
===========================
Layer 6 of ILMA 7-Layer Architecture.
Deep task analysis, 4W1H decomposition, verification engine.

Based on: ILMA ILMA_intelligence_core.py patterns
"""
import re
import time
import json
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# === 4W1H Analysis ===
@dataclass
class FourWOneH:
    what: str = ""
    why: str = ""
    who: str = ""
    when: str = ""
    where: str = ""
    how: str = ""


class FourWOneHAnalyzer:
    """Analyze task using 4W1H framework."""
    
    WHAT_PATTERNS = [
        r"(?:apa|what|membuat|create|bikin|kerjakan)",
        r"(?:apa yang|what.*yang)",
    ]
    
    WHY_PATTERNS = [
        r"(?:mengapa|why|untuk apa|untuk apa|maksud|tujuan)",
        r"(?:kenapa|for what)",
    ]
    
    WHO_PATTERNS = [
        r"(?:siapa|who|untuk siapa|for whom)",
    ]
    
    WHEN_PATTERNS = [
        r"(?:kapan|when|sebelum|sesudah|deadline)",
    ]
    
    WHERE_PATTERNS = [
        r"(?:where|diman|dimana|di mana|lokasi)",
    ]
    
    HOW_PATTERNS = [
        r"(?:bagaimana|how|cara|gimana)",
    ]
    
    def analyze(self, task: str) -> FourWOneH:
        """Perform 4W1H analysis on task."""
        result = FourWOneH()
        task_lower = task.lower()
        
        # Extract WHAT
        for pattern in self.WHAT_PATTERNS:
            match = re.search(pattern, task_lower)
            if match:
                result.what = task
                break
        
        # Extract WHY
        for pattern in self.WHY_PATTERNS:
            if re.search(pattern, task_lower):
                result.why = "User has specific goal to achieve"
                break
        
        # Extract WHO
        for pattern in self.WHO_PATTERNS:
            if re.search(pattern, task_lower):
                result.who = "User/Bos"
                break
        
        # Extract WHEN
        for pattern in self.WHEN_PATTERNS:
            if re.search(pattern, task_lower):
                result.when = "ASAP"
                break
        
        # Extract WHERE
        for pattern in self.WHERE_PATTERNS:
            if re.search(pattern, task_lower):
                result.where = "Current workspace"
                break
        
        # Extract HOW
        for pattern in self.HOW_PATTERNS:
            if re.search(pattern, task_lower):
                result.how = "Via ILMA capabilities"
                break
        
        return result
    
    def to_dict(self, analysis: FourWOneH) -> Dict:
        """Convert to dictionary."""
        return {
            "what": analysis.what,
            "why": analysis.why,
            "who": analysis.who,
            "when": analysis.when,
            "where": analysis.where,
            "how": analysis.how
        }


# === Task Analysis ===
class TaskAnalysis:
    """Deep task analysis component."""
    
    def __init__(self):
        self.analyzer = FourWOneHAnalyzer()
    
    def analyze(self, task: str) -> Dict:
        """Perform comprehensive task analysis."""
        start = time.time()
        
        # 4W1H analysis
        four_w_one_h = self.analyzer.analyze(task)
        
        # Complexity assessment
        complexity = self.assess_complexity(task)
        
        # Risk assessment
        risks = self.assess_risks(task)
        
        # Resource estimation
        resources = self.estimate_resources(task)
        
        analysis = {
            "task": task,
            "four_w_one_h": self.analyzer.to_dict(four_w_one_h),
            "complexity": complexity,
            "risks": risks,
            "resources": resources,
            "timestamp": datetime.now().isoformat(),
            "analysis_time_ms": int((time.time() - start) * 1000)
        }
        
        return analysis
    
    def assess_complexity(self, task: str) -> str:
        """Assess task complexity."""
        task_lower = task.lower()
        
        # High complexity indicators
        high_complex = ["architecture", "system", "database", "security", "complex"]
        medium_complex = ["api", "integration", "workflow", "design"]
        
        if any(w in task_lower for w in high_complex):
            return "high"
        elif any(w in task_lower for w in medium_complex):
            return "medium"
        return "low"
    
    def assess_risks(self, task: str) -> List[str]:
        """Identify potential risks."""
        risks = []
        task_lower = task.lower()
        
        if "delete" in task_lower or "remove" in task_lower:
            risks.append("data_loss_risk")
        if "database" in task_lower:
            risks.append("db_migration_risk")
        if "security" in task_lower:
            risks.append("security_risk")
        if "deploy" in task_lower:
            risks.append("deployment_risk")
        
        return risks
    
    def estimate_resources(self, task: str) -> Dict:
        """Estimate required resources."""
        complexity = self.assess_complexity(task)
        
        resource_map = {
            "high": {"time_min": 30, "tools": ["terminal", "file", "browser"], "agents": 1},
            "medium": {"time_min": 15, "tools": ["terminal", "file"], "agents": 1},
            "low": {"time_min": 5, "tools": ["terminal"], "agents": 0}
        }
        
        return resource_map.get(complexity, resource_map["low"])


# === Resource Manager ===
class ResourceManager:
    """Manages resource allocation for tasks."""
    
    def __init__(self):
        self.available_memory_mb = 2048
        self.available_cpu_percent = 80
    
    def check_availability(self, required: Dict) -> bool:
        """Check if resources are available."""
        time_min = required.get("time_min", 5)
        
        # Simple check - assume available if < 60 min
        return time_min < 60
    
    def allocate(self, task_id: str, resources: Dict) -> bool:
        """Allocate resources for task."""
        return True
    
    def release(self, task_id: str):
        """Release resources after task."""
        pass


# === Verification Engine ===
class VerificationEngine:
    """Verify task completion and quality."""
    
    def verify(self, task: str, result: Any, expected: Any = None) -> Dict:
        """Verify task result."""
        verification = {
            "task": task,
            "result": str(result)[:200],
            "passed": False,
            "quality_score": 0.0,
            "issues": [],
            "timestamp": datetime.now().isoformat()
        }
        
        # Basic checks
        if result is None:
            verification["issues"].append("Result is None")
        elif isinstance(result, dict) and "error" in result:
            verification["issues"].append(f"Error in result: {result['error']}")
        else:
            verification["passed"] = True
            verification["quality_score"] = 1.0
        
        # Expected comparison if provided
        if expected and result != expected:
            verification["issues"].append("Result differs from expected")
            verification["quality_score"] = 0.5
        
        return verification
    
    def validate_output(self, output: Any, rules: List[str]) -> Dict:
        """Validate output against rules."""
        validation = {
            "passed": True,
            "failed_rules": [],
            "timestamp": datetime.now().isoformat()
        }
        
        for rule in rules:
            if not self._check_rule(output, rule):
                validation["passed"] = False
                validation["failed_rules"].append(rule)
        
        return validation
    
    def _check_rule(self, output: Any, rule: str) -> bool:
        """Check single rule."""
        # Simplified rule checking
        if rule == "not_none":
            return output is not None
        if rule == "is_dict":
            return isinstance(output, dict)
        if rule == "is_list":
            return isinstance(output, list)
        return True


# === Main Intelligence Core ===
class ILMAIntelligenceCore:
    """Main intelligence core combining all components."""
    
    def __init__(self):
        self.task_analysis = TaskAnalysis()
        self.resource_manager = ResourceManager()
        self.verification_engine = VerificationEngine()
    
    def analyze(self, task: str) -> Dict:
        """Full task analysis."""
        return self.task_analysis.analyze(task)
    
    def verify(self, task: str, result: Any) -> Dict:
        """Verify task result."""
        return self.verification_engine.verify(task, result)
    
    def plan(self, task: str) -> Dict:
        """Plan task execution."""
        analysis = self.analyze(task)
        
        return {
            "task": task,
            "analysis": analysis,
            "execution_plan": {
                "steps": self._generate_steps(analysis),
                "estimated_time": analysis["resources"]["time_min"],
                "tools_needed": analysis["resources"]["tools"]
            }
        }
    
    def _generate_steps(self, analysis: Dict) -> List[str]:
        """Generate execution steps from analysis."""
        complexity = analysis["complexity"]
        
        if complexity == "high":
            return [
                "1. Deep analysis and planning",
                "2. Resource preparation",
                "3. Step-by-step implementation",
                "4. Continuous verification",
                "5. Final validation"
            ]
        elif complexity == "medium":
            return [
                "1. Quick analysis",
                "2. Implementation",
                "3. Verification"
            ]
        else:
            return [
                "1. Direct execution",
                "2. Quick check"
            ]


# === CLI ===
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: ilma_intelligence_core.py --analyze 'task'")
        sys.exit(1)
    
    command = sys.argv[1]
    task = " ".join(sys.argv[2:])
    
    core = ILMAIntelligenceCore()
    
    if command == "--analyze":
        result = core.analyze(task)
    elif command == "--plan":
        result = core.plan(task)
    else:
        result = core.analyze(task)
    
    print(json.dumps(result, indent=2))
