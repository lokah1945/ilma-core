#!/usr/bin/env python3
"""
ILMA Phase 49-F: Tool/Skill Selector

Selects the right tools, skills, and scripts for a given task.
This is the "muscles" of ILMA — executes what the brain decides.

Rules:
- coding → compiler/tests/static analysis first
- research → source/evidence workflow
- document → doc/artifact workflow
- slides/pdf/spreadsheet → proper artifact workflow
- internal ILMA → registry/evidence/runner/judge workflow
- unsafe task → refuse or safety route
- unavailable tool → fallback
- never hallucinate unavailable tools

Owner: Bos (Huda Choirul Anam)
Safety: Owner-triggered only, no always-on
"""

import sys
import json
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))


class ToolSkillSelector:
    """
    Selects tools/skills/scripts based on task_class and workflow.
    
    Safety rules:
    - Never return unavailable tools as available
    - If tool requires permission and not granted, mark as BLOCKED
    - Fallback to safer options if primary unavailable
    - Never hallucinate capabilities
    """
    
    def __init__(self):
        self._load_policy()
    
    def _load_policy(self):
        """Load tool/skill selection policy."""
        policy_path = Path(__file__).parent.parent / "config" / "ilma_tool_skill_selection_policy.json"
        if policy_path.exists():
            with open(policy_path) as f:
                self.policy = json.load(f)
        else:
            self.policy = self._default_policy()
        self.rules = self.policy.get("selection_rules", {})
    
    def _default_policy(self):
        """Fallback policy if config missing."""
        return {
            "selection_rules": {
                "if_coding_task": {
                    "primary_tools": ["terminal", "file", "search"],
                    "primary_skills": ["ilma-python-patterns", "ilma-testing"],
                    "execution_order": ["terminal:py_compile", "file:read", "file:write", "terminal:test"],
                    "fallback": "decline_or_template"
                },
                "if_unsafe_task": {
                    "primary_tools": [],
                    "primary_skills": [],
                    "execution_order": [],
                    "fallback": "safety_explanation_no_execution"
                }
            }
        }
    
    def _map_task_class_to_policy_key(self, task_class, workflow_type):
        """Map task_class to policy key like 'if_coding_task'."""
        # Handle TaskClass enum or string
        if hasattr(task_class, 'value'):
            tc_lower = task_class.value.lower()  # e.g., "audit"
        else:
            tc_lower = str(task_class).lower()
        
        # Map TaskClass to policy key
        mapping = {
            "code": "if_coding_task",
            "write": "if_document_task",
            "research": "if_research_task",
            "audit": "if_audit_task",
            "plan": "if_document_task",
            "internal": "if_internal_ilma_task",
            "simple": "if_document_task",
            "slides": "if_slides_pdf_task",
            "pdf": "if_slides_pdf_task",
            "spreadsheet": "if_slides_pdf_task",
            "unsafe": "if_unsafe_task",
        }
        
        # Check workflow_type for special cases
        if workflow_type == "auto_learning":
            return "if_internal_ilma_task"
        if workflow_type == "internal_audit":
            return "if_audit_task"
        if workflow_type in ["slides", "pdf", "spreadsheet"]:
            return "if_slides_pdf_task"
        if workflow_type in ["coding", "debugging", "refactor", "testing"]:
            return "if_coding_task"
        if workflow_type in ["writing", "longform", "document_artifact"]:
            return "if_document_task"
        if workflow_type in ["research"]:
            return "if_research_task"
        if workflow_type in ["security_review", "evidence_workflow"]:
            return "if_audit_task"
        if workflow_type in ["mission_loop", "multi_mission"]:
            return "if_internal_ilma_task"
        
        # Fall back to task_class mapping
        return mapping.get(tc_lower, "if_document_task")
    
    def select(self, task_class, workflow_type, safety_class="normal"):
        """
        Select tools, skills, and execution order.
        
        Args:
            task_class: TaskClass enum or string
            workflow_type: workflow type string
            safety_class: "normal", "elevated", "restricted"
        
        Returns:
            dict with tools, skills, execution_order, fallback, warnings
        """
        # Normalize task_class
        if hasattr(task_class, 'value'):
            tc = task_class.value.lower()
        else:
            tc = str(task_class).lower()
        
        # Safety check first
        if safety_class == "restricted":
            return self._restricted_selection(tc, workflow_type)
        
        # Get policy key for this task
        policy_key = self._map_task_class_to_policy_key(tc, workflow_type)
        rule = self.rules.get(policy_key, self.rules.get("if_document_task", {}))
        
        # Build selection
        result = {
            "task_class": tc,
            "workflow_type": workflow_type,
            "safety_class": safety_class,
            "tools": rule.get("primary_tools", []),
            "skills": rule.get("primary_skills", []),
            "scripts": self._get_scripts_for_workflow(workflow_type),
            "execution_order": rule.get("execution_order", ["file:read", "file:write"]),
            "fallback": rule.get("fallback", "limited_audit"),
            "warnings": [],
            "claim_boundary": "normal_task"
        }
        
        # Add workflow-specific tweaks
        result = self._apply_workflow_tweaks(result, workflow_type)
        
        # Check for blocked/unavailable tools
        result = self._check_tool_availability(result)
        
        return result
    
    def _restricted_selection(self, task_class, workflow_type):
        """Restricted mode — limited tools only."""
        return {
            "task_class": task_class,
            "workflow_type": workflow_type,
            "safety_class": "restricted",
            "tools": ["file"],
            "skills": [],
            "scripts": [],
            "execution_order": ["file:read"],
            "fallback": "abort_and_report",
            "warnings": [
                "Restricted mode — limited tools available",
                "Some capabilities may not work"
            ],
            "claim_boundary": "restricted_task"
        }
    
    def _get_scripts_for_workflow(self, workflow_type):
        """Map workflow to scripts."""
        workflow_scripts = {
            "auto_learning": ["ilma_phase49i_realtime_gate.py"],
            "internal_audit": [],
            "evidence_workflow": [],
            "security_review": [],
            "mission_loop": [],
            "multi_mission": [],
            "testing": [],
            "coding": [],
            "refactor": [],
        }
        return workflow_scripts.get(workflow_type, [])
    
    def _apply_workflow_tweaks(self, result, workflow_type):
        """Apply workflow-specific adjustments."""
        tweaks = {
            "auto_learning": {
                "warnings": ["Owner-triggered only — not always-on"]
            },
            "security_review": {
                "warnings": ["High-safety — extra verification required"]
            }
        }
        
        if workflow_type in tweaks:
            result["warnings"].extend(tweaks[workflow_type]["warnings"])
        
        return result
    
    def _check_tool_availability(self, result):
        """Check if tools are actually available."""
        available_tools = self._get_available_tools()
        blocked_tools = []
        
        for tool in result.get("tools", []):
            if tool not in available_tools:
                blocked_tools.append(tool)
        
        if blocked_tools:
            result["warnings"].append(f"Tools not available: {blocked_tools}")
            result["tools"] = [t for t in result["tools"] if t in available_tools]
            if not result["tools"]:
                result["tools"] = ["file"]
                result["warnings"].append("Using file-only fallback")
        
        return result
    
    def _get_available_tools(self):
        """Check which tools are actually available."""
        # Hermes native tools — always available in this context
        return ["file", "search", "terminal", "web", "browser"]
    
    def validate_selection(self, selection):
        """
        Validate selection for safety and correctness.
        
        Returns: (valid, errors, warnings)
        """
        errors = []
        warnings = list(selection.get("warnings", []))
        
        # Check for forbidden tools
        forbidden = ["credential_use", "unsafe_network", "shell_injection"]
        for tool in selection.get("tools", []):
            if tool in forbidden:
                errors.append(f"Forbidden tool detected: {tool}")
        
        # Check for empty selection
        if not selection.get("tools") and not selection.get("skills"):
            warnings.append("No tools or skills selected — may not produce output")
        
        # Check for unsafe execution order
        if "terminal:exec" in selection.get("execution_order", []):
            warnings.append("Terminal execution — ensure shell safety")
        
        return (len(errors) == 0, errors, warnings)


def demo():
    """Demo the tool/skill selector."""
    selector = ToolSkillSelector()
    
    print("=== ILMA Tool/Skill Selector Demo ===\n")
    
    test_cases = [
        ("code", "coding", "normal"),
        ("write", "writing", "normal"),
        ("research", "research", "normal"),
        ("internal", "auto_learning", "normal"),
        ("audit", "internal_audit", "normal"),
        ("unsafe", "simple_answer", "restricted"),
    ]
    
    for task_class, workflow, safety in test_cases:
        result = selector.select(task_class, workflow, safety)
        print(f"Task: {task_class} | Workflow: {workflow} | Safety: {safety}")
        print(f"  Tools: {result['tools']}")
        print(f"  Skills: {result['skills']}")
        print(f"  Exec: {result['execution_order']}")
        print(f"  Fallback: {result['fallback']}")
        print(f"  Boundary: {result['claim_boundary']}")
        if result['warnings']:
            print(f"  ⚠️  {result['warnings']}")
        print()
        
        # Validate
        valid, errors, warns = selector.validate_selection(result)
        print(f"  Valid: {valid}")
        if errors:
            print(f"  ❌ Errors: {errors}")
        if warns:
            print(f"  ⚠️  Warnings: {warns}")
        print()


if __name__ == "__main__":
    demo()