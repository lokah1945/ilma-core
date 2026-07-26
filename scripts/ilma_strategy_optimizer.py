#!/usr/bin/env python3
"""
ILMA Strategy Optimizer v1.0
=============================
DSPy-inspired local prompt/policy optimizer.
Phase 46 - Autonomous Evolution Foundation.

NOTE: This is LOCAL and HONEST - not actual DSPy.
Functions:
- record_strategy_attempt()
- compare_before_after()
- suggest_prompt_policy_patch()
- approve_policy_patch()
- reject_policy_patch()

Rules:
- No automatic system prompt mutation without validation.
- Any prompt policy change must include before/after score.
- Rollback path required.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ILMA paths
ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
WORKSPACE = ILMA_PROFILE


@dataclass
class StrategyAttempt:
    """Record of a strategy attempt."""
    attempt_id: str
    task_type: str
    prompt_policy: str
    score_before: float
    score_after: float
    improvement: float
    evidence_id: str
    timestamp: str
    approved: bool = False
    notes: str = ""


@dataclass
class PolicyPatch:
    """Proposed policy change."""
    patch_id: str
    task_type: str
    policy_key: str
    old_value: str
    new_value: str
    expected_improvement: float
    rollback_path: str
    evidence_id: str
    created_at: str
    status: str = "PENDING"  # PENDING, APPROVED, REJECTED


class StrategyOptimizer:
    """
    Local strategy/prompt policy optimizer.
    
    NOT actual DSPy - this is a local record-keeping system
    for tracking strategy mutations and their effects.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or (WORKSPACE / "config" / "ilma_strategy_policy.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load or init
        self.policy = self._load_policy()
        self.attempts: List[StrategyAttempt] = []
        self.patches: List[PolicyPatch] = []
        
        # Load history
        self._load_history()

    def _load_policy(self) -> Dict[str, Any]:
        """Load current policy."""
        if self.storage_path.exists():
            try:
                return json.loads(self.storage_path.read_text())
            except ValueError:
                pass
        
        return self._default_policy()

    def _default_policy(self) -> Dict[str, Any]:
        """Default policy."""
        return {
            "version": "1.0",
            "updated_at": "",
            "task_policies": {
                "code": {
                    "temperature": "0.4-0.7",
                    "approach": "incremental",
                    "test_before_submit": True
                },
                "writing": {
                    "temperature": "0.5-0.8",
                    "approach": "outline_first",
                    "evidence_required": True
                },
                "planning": {
                    "temperature": "0.3-0.6",
                    "approach": "structured",
                    "milestones_required": True
                },
                "analysis": {
                    "temperature": "0.2-0.5",
                    "approach": "evidence_first",
                    "sources_required": True
                }
            },
            "meta": {
                "auto_mutation_enabled": False,
                "approval_required": True,
                "rollback_available": True
            }
        }

    def _load_history(self):
        """Load attempt history."""
        history_path = WORKSPACE / "memory" / "strategy_history.jsonl"
        if history_path.exists():
            try:
                with open(history_path) as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            if "patch_id" in data:
                                self.patches.append(PolicyPatch(**data))
                            else:
                                self.attempts.append(StrategyAttempt(**data))
            except Exception:
                pass

    def _save_policy(self):
        """Save policy."""
        self.policy["updated_at"] = datetime.now().isoformat()
        with open(self.storage_path, 'w') as f:
            json.dump(self.policy, f, indent=2)

    def record_strategy_attempt(
        self,
        task_type: str,
        prompt_policy: str,
        score_before: float,
        score_after: float,
        evidence_id: str = "",
        notes: str = ""
    ) -> StrategyAttempt:
        """
        Record a strategy attempt with before/after scores.
        """
        attempt_id = str(uuid.uuid4())[:8]
        
        attempt = StrategyAttempt(
            attempt_id=attempt_id,
            task_type=task_type,
            prompt_policy=prompt_policy,
            score_before=score_before,
            score_after=score_after,
            improvement=score_after - score_before,
            evidence_id=evidence_id or f"STRAT-{datetime.now().strftime('%Y%m%d')}-{attempt_id}",
            timestamp=datetime.now().isoformat(),
            notes=notes
        )
        
        # Auto-approve if improvement is positive
        attempt.approved = attempt.improvement > 0
        
        # Save to history
        history_path = WORKSPACE / "memory" / "strategy_history.jsonl"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(history_path, 'a') as f:
            f.write(json.dumps(attempt.__dict__) + "\n")
        
        self.attempts.append(attempt)
        
        return attempt

    def compare_before_after(
        self,
        task_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compare before/after scores for attempts.
        """
        attempts = self.attempts
        if task_type:
            attempts = [a for a in attempts if a.task_type == task_type]
        
        if not attempts:
            return {
                "task_type": task_type,
                "total_attempts": 0,
                "improvements": [],
                "average_improvement": 0,
                "conclusion": "No data yet"
            }
        
        improvements = [a.improvement for a in attempts]
        positive = sum(1 for i in improvements if i > 0)
        negative = sum(1 for i in improvements if i < 0)
        
        return {
            "task_type": task_type,
            "total_attempts": len(attempts),
            "average_improvement": sum(improvements) / len(improvements),
            "max_improvement": max(improvements) if improvements else 0,
            "min_improvement": min(improvements) if improvements else 0,
            "positive_count": positive,
            "negative_count": negative,
            "improvement_rate": positive / max(len(improvements), 1),
            "attempts": [
                {
                    "id": a.attempt_id,
                    "score_before": a.score_before,
                    "score_after": a.score_after,
                    "improvement": a.improvement,
                    "approved": a.approved
                }
                for a in attempts[-10:]  # Last 10
            ]
        }

    def suggest_prompt_policy_patch(
        self,
        task_type: str,
        policy_key: str,
        old_value: str,
        new_value: str,
        expected_improvement: float,
        reason: str = ""
    ) -> PolicyPatch:
        """
        Suggest a policy patch.
        
        NOTE: This does NOT auto-apply. Requires approval.
        """
        patch_id = str(uuid.uuid4())[:8]
        
        patch = PolicyPatch(
            patch_id=patch_id,
            task_type=task_type,
            policy_key=policy_key,
            old_value=old_value,
            new_value=new_value,
            expected_improvement=expected_improvement,
            rollback_path=f"Revert {policy_key} to '{old_value}'",
            evidence_id=f"PATCH-{datetime.now().strftime('%Y%m%d')}-{patch_id}",
            created_at=datetime.now().isoformat(),
            status="PENDING"
        )
        
        # Save
        history_path = WORKSPACE / "memory" / "strategy_history.jsonl"
        with open(history_path, 'a') as f:
            f.write(json.dumps(patch.__dict__) + "\n")
        
        self.patches.append(patch)
        
        return patch

    def approve_policy_patch(self, patch_id: str) -> bool:
        """
        Approve and apply a policy patch.
        
        Returns True if successful.
        """
        patch = next((p for p in self.patches if p.patch_id == patch_id), None)
        if not patch:
            return False
        
        if patch.status != "PENDING":
            return False
        
        # Apply
        task_policies = self.policy.get("task_policies", {})
        if patch.task_type in task_policies:
            task_policies[patch.task_type][patch.policy_key] = patch.new_value
            self._save_policy()
        
        patch.status = "APPROVED"
        
        # Update history
        self._update_patch_history(patch)
        
        return True

    def reject_policy_patch(self, patch_id: str, reason: str = "") -> bool:
        """
        Reject a policy patch.
        """
        patch = next((p for p in self.patches if p.patch_id == patch_id), None)
        if not patch:
            return False
        
        patch.status = "REJECTED"
        patch.notes = reason
        
        self._update_patch_history(patch)
        
        return True

    def _update_patch_history(self, patch: PolicyPatch):
        """Update patch in history."""
        history_path = WORKSPACE / "memory" / "strategy_history.jsonl"
        
        # Read all
        lines = []
        with open(history_path) as f:
            lines = [json.loads(line) for line in f if line.strip()]
        
        # Update
        for i, line in enumerate(lines):
            if line.get("patch_id") == patch.patch_id:
                lines[i] = patch.__dict__
                break
        
        # Write
        with open(history_path, 'w') as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")

    def get_policy(self, task_type: Optional[str] = None) -> Dict[str, Any]:
        """Get current policy."""
        if task_type:
            return self.policy.get("task_policies", {}).get(task_type, {})
        return self.policy

    def get_pending_patches(self) -> List[Dict[str, Any]]:
        """Get pending patches."""
        return [p.__dict__ for p in self.patches if p.status == "PENDING"]


# === DEMO ===

def run_demo():
    """Run strategy optimizer demo."""
    print("=" * 60)
    print("ILMA Strategy Optimizer v1.0")
    print("=" * 60)
    
    optimizer = StrategyOptimizer()
    
    # Get current policy
    print("\n[Current Policy]")
    policy = optimizer.get_policy("code")
    print(f"  Code task temperature: {policy.get('temperature', 'N/A')}")
    
    # Record attempts
    print("\n[Recording attempts...]")
    
    attempt1 = optimizer.record_strategy_attempt(
        task_type="code",
        prompt_policy="temperature=0.5",
        score_before=70,
        score_after=85,
        notes="Lower temp improved code quality"
    )
    print(f"  Attempt 1: +{attempt1.improvement:.0f} (approved: {attempt1.approved})")
    
    attempt2 = optimizer.record_strategy_attempt(
        task_type="code",
        prompt_policy="temperature=0.3",
        score_before=85,
        score_after=80,
        notes="Too low temp reduced creativity"
    )
    print(f"  Attempt 2: {attempt2.improvement:.0f} (approved: {attempt2.approved})")
    
    # Compare
    print("\n[Comparison]")
    comparison = optimizer.compare_before_after("code")
    print(f"  Total attempts: {comparison['total_attempts']}")
    print(f"  Average improvement: {comparison['average_improvement']:.1f}")
    print(f"  Improvement rate: {comparison['improvement_rate']:.0%}")
    
    # Suggest patch
    print("\n[Suggesting patch...]")
    patch = optimizer.suggest_prompt_policy_patch(
        task_type="code",
        policy_key="temperature",
        old_value="0.4-0.7",
        new_value="0.5-0.7",
        expected_improvement=5.0,
        reason="Tighten lower bound for consistency"
    )
    print(f"  Patch {patch.patch_id}: {patch.policy_key} {patch.old_value} → {patch.new_value}")
    print(f"  Expected improvement: +{patch.expected_improvement:.0f}")
    print(f"  Status: {patch.status}")
    
    # Pending patches
    print("\n[Pending Patches]")
    pending = optimizer.get_pending_patches()
    for p in pending:
        print(f"  - {p['patch_id']}: {p['policy_key']} ({p['status']})")
    
    return optimizer


if __name__ == "__main__":
    run_demo()