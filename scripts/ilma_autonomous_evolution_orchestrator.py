#!/usr/bin/env python3
"""
ILMA Autonomous Evolution Orchestrator v1.0
==========================================
Actor-Critic state machine with Reflexion loop.
Phase 46 - Autonomous Evolution Foundation.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ILMA paths
ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
WORKSPACE = ILMA_PROFILE
sys.path.insert(0, str(WORKSPACE))


class MissionStatus(Enum):
    INIT = "INIT"
    MEMORY_RETRIEVED = "MEMORY_RETRIEVED"
    PLANNED = "PLANNED"
    EXECUTED = "EXECUTED"
    EVALUATED = "EVALUATED"
    REFLECTING = "REFLECTING"
    REVISING = "REVISING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"
    COMPLETE = "COMPLETE"


class JudgeVerdict(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    UNKNOWN = "UNKNOWN"


class ExitReason(Enum):
    MAX_ITERATIONS = "max_iterations"
    UNSAFE_CONDITION = "unsafe_condition"
    REPEATED_FAILURE = "repeated_failure"
    DEPENDENCY_MISSING = "dependency_missing"
    AMBIGUOUS_TARGET = "ambiguous_target"
    ALL_PASSED = "all_passed"
    OWNER_ESCALATION = "owner_escalation"


@dataclass
class MissionState:
    mission_id: str = ""
    created_at: str = ""
    target: str = ""
    target_criteria: str = ""
    task_type: str = "unknown"
    max_iterations: int = 300
    checkpoint_frequency: int = 25
    iteration: int = 0
    current_status: MissionStatus = MissionStatus.INIT
    previous_status: MissionStatus = MissionStatus.INIT
    actor_plan: str = ""
    actor_artifact: str = ""
    actor_artifact_path: Optional[str] = None  # Path to written artifact
    actor_attempts: List[Dict[str, Any]] = field(default_factory=list)
    judge_result: Optional[Dict[str, Any]] = None
    judge_history: List[Dict[str, Any]] = field(default_factory=list)
    reflection_result: Optional[Dict[str, Any]] = None
    reflection_history: List[Dict[str, Any]] = field(default_factory=list)
    retrieved_lessons: List[Dict[str, Any]] = field(default_factory=list)
    stored_lesson_ids: List[str] = field(default_factory=list)
    failure_patterns: List[str] = field(default_factory=list)
    repeated_failures: int = 0
    exit_reason: ExitReason = ExitReason.MAX_ITERATIONS
    exit_message: str = ""
    evidence_ids: List[str] = field(default_factory=list)
    checkpoint_count: int = 0
    last_checkpoint_at: str = ""
    dry_run: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['current_status'] = self.current_status.value
        d['previous_status'] = self.previous_status.value
        d['exit_reason'] = self.exit_reason.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MissionState":
        """Deserialize from dict."""
        if 'current_status' in d and isinstance(d['current_status'], str):
            d['current_status'] = MissionStatus(d['current_status'])
        if 'previous_status' in d and isinstance(d['previous_status'], str):
            d['previous_status'] = MissionStatus(d['previous_status'])
        if 'exit_reason' in d and isinstance(d['exit_reason'], str):
            d['exit_reason'] = ExitReason(d['exit_reason'])
        # Remove fields not in dataclass
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in valid_fields}
        return cls(**filtered)


class AutonomousEvolutionOrchestrator:
    """Actor-Critic state machine orchestrator."""

    def __init__(
        self,
        max_iterations: int = 300,
        checkpoint_frequency: int = 25,
        dry_run: bool = False,
        memory_path: Optional[Path] = None,
        checkpoint_dir: Optional[Path] = None
    ):
        self.max_iterations = max_iterations
        self.checkpoint_frequency = checkpoint_frequency
        self.dry_run = dry_run
        self.memory_path = memory_path or (WORKSPACE / "memory" / "ilma_lessons.jsonl")
        self.checkpoint_dir = checkpoint_dir or (WORKSPACE / "memory" / "checkpoints")
        self.actor_callback: Optional[Callable] = None
        self.revision_callback: Optional[Callable] = None

    def create_mission(
        self,
        target: str,
        criteria: str = "",
        task_type: str = "unknown",
        max_iterations: Optional[int] = None
    ) -> MissionState:
        return MissionState(
            mission_id=str(uuid.uuid4())[:8],
            created_at=datetime.now().isoformat(),
            target=target,
            target_criteria=criteria,
            task_type=task_type,
            max_iterations=max_iterations or self.max_iterations,
            dry_run=self.dry_run
        )

    def run(self, state: MissionState, verbose: bool = True) -> MissionState:
        if verbose:
            print(f"[Orchestrator] Mission {state.mission_id} starting")
            print(f"  Target: {state.target[:80]}...")

        # Track status to detect when no progress is made
        status_before_step = state.current_status

        while state.iteration < state.max_iterations:
            status_before_step = state.current_status

            # Execute one step
            if state.current_status == MissionStatus.INIT:
                state = self._step_init(state, verbose)
            elif state.current_status == MissionStatus.MEMORY_RETRIEVED:
                state = self._step_plan(state, verbose)
            elif state.current_status == MissionStatus.PLANNED:
                state = self._step_execute(state, verbose)
            elif state.current_status == MissionStatus.EXECUTED:
                state = self._step_evaluate(state, verbose)
            elif state.current_status == MissionStatus.EVALUATED:
                state = self._route_evaluation(state, verbose)
            elif state.current_status == MissionStatus.REFLECTING:
                state = self._step_reflect(state, verbose)
            elif state.current_status == MissionStatus.REVISING:
                state = self._step_revise(state, verbose)
            else:
                break  # Terminal state

            state.iteration += 1

            if state.iteration % self.checkpoint_frequency == 0:
                self._checkpoint(state)

            if verbose:
                print(f"[Iteration {state.iteration}] Status: {state.current_status.value}")

            # Check if status advanced; if not and not terminal, force next step
            if state.current_status == status_before_step and state.current_status not in [
                MissionStatus.PASSED, MissionStatus.FAILED,
                MissionStatus.BLOCKED, MissionStatus.ESCALATED,
            ]:
                if verbose:
                    print(f"  [Orchestrator] Status stuck at {state.current_status.value}, forcing next step")
                # Force advance: map current status to next
                if state.current_status == MissionStatus.INIT:
                    state.current_status = MissionStatus.MEMORY_RETRIEVED
                elif state.current_status == MissionStatus.MEMORY_RETRIEVED:
                    state.current_status = MissionStatus.PLANNED
                elif state.current_status == MissionStatus.PLANNED:
                    state = self._step_execute(state, verbose)
                    state.iteration += 1
                    if verbose:
                        print(f"[Iteration {state.iteration}] Status: {state.current_status.value}")
                elif state.current_status == MissionStatus.EVALUATED:
                    # Force evaluation routing
                    state = self._route_evaluation(state, verbose)
                elif state.current_status == MissionStatus.REFLECTING:
                    state = self._step_reflect(state, verbose)
                elif state.current_status == MissionStatus.REVISING:
                    state = self._step_revise(state, verbose)

            if self._is_unsafe(state):
                state.current_status = MissionStatus.FAILED
                state.exit_reason = ExitReason.UNSAFE_CONDITION
                break

        if state.iteration >= state.max_iterations and state.current_status not in [
            MissionStatus.PASSED, MissionStatus.FAILED, MissionStatus.BLOCKED, MissionStatus.ESCALATED
        ]:
            state.current_status = MissionStatus.FAILED
            state.exit_reason = ExitReason.MAX_ITERATIONS

        if verbose:
            self._print_summary(state)

        return state

    def _step_init(self, state: MissionState, verbose: bool) -> MissionState:
        state.previous_status = state.current_status
        state.current_status = MissionStatus.MEMORY_RETRIEVED
        # Try to load lessons
        if self.memory_path.exists():
            try:
                with open(self.memory_path) as f:
                    lessons = [json.loads(line) for line in f if line.strip()]
                    state.retrieved_lessons = [{"lesson_id": l.get("lesson_id", ""), "relevance": 0.5} for l in lessons[-5:]]
                if verbose:
                    print(f"  [Memory] Found {len(state.retrieved_lessons)} past lessons")
            except ValueError:
                pass
        return state

    def _step_plan(self, state: MissionState, verbose: bool) -> MissionState:
        state.previous_status = state.current_status
        state.current_status = MissionStatus.PLANNED
        state.actor_plan = f"Plan for: {state.target[:80]}...\nSteps: Analyze, Implement, Test, Verify"
        if verbose:
            print(f"  [Actor] Plan generated")
        return state

    def _step_execute(self, state: MissionState, verbose: bool) -> MissionState:
        state.previous_status = state.current_status
        state.current_status = MissionStatus.EXECUTED

        # Use actor callback if provided
        if self.actor_callback:
            artifact = self.actor_callback(state, state.iteration, verbose=verbose)
            state.actor_artifact = artifact
        else:
            # Fallback placeholder
            state.actor_artifact = f"# Artifact: {state.target[:80]}...\n<IMPLEMENTATION>Placeholder</IMPLEMENTATION>"

        state.actor_attempts.append({"iteration": state.iteration, "artifact_length": len(state.actor_artifact)})
        if verbose:
            print(f"  [Actor] Artifact produced")
        return state

    def _step_evaluate(self, state: MissionState, verbose: bool) -> MissionState:
        state.previous_status = state.current_status
        state.current_status = MissionStatus.EVALUATED

        # Use CriticJudge for proper evaluation
        try:
            from ilma_critic_judge import CriticJudge
            judge = CriticJudge()
            jr = judge.evaluate(
                artifact=state.actor_artifact,
                target=state.target,
                criteria=f"Task type: {state.task_type}",
                task_type=state.task_type
            )
            state.judge_result = {"status": jr.status.value, "score": jr.score, "failures": []}
            if verbose:
                print(f"  [Judge] Verdict: {jr.status.value}, score={jr.score:.0f}")
        except Exception as e:
            state.judge_result = {"status": "FAIL", "score": 0, "failures": [str(e)]}
            if verbose:
                print(f"  [Judge] Error: {e}")

        return state

    def _route_evaluation(self, state: MissionState, verbose: bool) -> MissionState:
        verdict = state.judge_result.get("status", "FAIL") if state.judge_result else "FAIL"
        if verdict == "PASS":
            state.current_status = MissionStatus.PASSED
            state.exit_reason = ExitReason.ALL_PASSED
        elif verdict == "WARN":
            state.current_status = MissionStatus.PASSED
            state.exit_reason = ExitReason.ALL_PASSED
        else:
            if state.repeated_failures >= 2:
                state.current_status = MissionStatus.ESCALATED
                state.exit_reason = ExitReason.REPEATED_FAILURE
            else:
                state.current_status = MissionStatus.REFLECTING
        return state

    def _step_reflect(self, state: MissionState, verbose: bool) -> MissionState:
        state.previous_status = state.current_status
        state.current_status = MissionStatus.REVISING
        failures = state.judge_result.get("failures", []) if state.judge_result else []
        state.reflection_result = {
            "root_cause": failures[0] if failures else "unknown",
            "fix_plan": ["Add required component", "Re-evaluate"]
        }
        state.failure_patterns.append(failures[0] if failures else "unknown")
        if state.failure_patterns.count(state.failure_patterns[-1]) >= 2:
            state.repeated_failures += 1
        if verbose:
            print(f"  [Reflection] Root cause: {failures[0] if failures else 'unknown'}")
        return state

    def _step_revise(self, state: MissionState, verbose: bool) -> MissionState:
        state.previous_status = state.current_status
        state.current_status = MissionStatus.EXECUTED

        # Use default artifact producer to revise the artifact
        if state.actor_artifact_path and hasattr(state, 'actor_artifact_path'):
            # Get reflection feedback from last attempt
            reflection_feedback = ""
            if state.actor_attempts and len(state.actor_attempts) > 0:
                last_attempt = state.actor_attempts[-1]
                # Check if there was a reflection result stored
                reflection_data = getattr(state, 'reflection_data', {})
                if reflection_data:
                    reflection_feedback = reflection_data.get('root_cause', '')

            # Revise using default producer
            from ilma_default_actor_artifact_producer import DefaultArtifactProducer
            producer = DefaultArtifactProducer()
            if reflection_feedback:
                revised = producer.revise_artifact(state.actor_artifact_path, reflection_feedback)
                if revised.success and revised.artifact_path:
                    from pathlib import Path
                    state.actor_artifact = Path(revised.artifact_path).read_text()
                    state.actor_artifact_path = revised.artifact_path
                    state.evidence_id = revised.evidence_id
            else:
                # Just re-produce with revision context
                result = producer.produce_artifact(
                    target=state.target + " (revised iteration)",
                    task_class=state.task_type,
                    artifact_type="markdown_report",
                    context={"revision": True, "iteration": state.iteration},
                )
                if result.success and result.artifact_path:
                    from pathlib import Path
                    state.actor_artifact = Path(result.artifact_path).read_text()
                    state.actor_artifact_path = result.artifact_path
                    state.evidence_id = result.evidence_id
        else:
            # No path to revise, generate new artifact
            state.actor_artifact = f"# Revised Artifact: {state.target[:80]}...\n\nThis is a generated revision.\n"

        state.actor_attempts.append({"iteration": state.iteration, "type": "revision"})
        if verbose:
            print(f"  [Actor] Revision complete")
        return state

    def _is_unsafe(self, state: MissionState) -> bool:
        dangerous = ["rm -rf /", "DROP TABLE", "DELETE FROM", "format c:", "del /f /s"]
        for p in dangerous:
            if p.lower() in state.actor_artifact.lower():
                return True
        return False

    def _checkpoint(self, state: MissionState):
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        path = self.checkpoint_dir / f"mission_{state.mission_id}_iter_{state.iteration}.json"
        with open(path, 'w') as f:
            json.dump(state.to_dict(), f, indent=2)
        state.checkpoint_count += 1

    def _print_summary(self, state: MissionState):
        print()
        print("=" * 60)
        print("MISSION SUMMARY")
        print("=" * 60)
        print(f"Mission ID: {state.mission_id}")
        print(f"Final Status: {state.current_status.value}")
        print(f"Iterations: {state.iteration}")
        print(f"Exit Reason: {state.exit_reason.value}")
        print(f"Actor Attempts: {len(state.actor_attempts)}")
        print(f"Lessons Retrieved: {len(state.retrieved_lessons)}")
        print("=" * 60)

    def export_json(self, state: MissionState, path: Path) -> Path:
        with open(path, 'w') as f:
            json.dump(state.to_dict(), f, indent=2)
        return path


def run_demo():
    print("=" * 60)
    print("ILMA Autonomous Evolution Orchestrator v1.0")
    print("=" * 60)
    orchestrator = AutonomousEvolutionOrchestrator(max_iterations=5)
    mission = orchestrator.create_mission(
        target="Build factorial function with tests",
        criteria="Must handle edge cases",
        task_type="code"
    )
    result = orchestrator.run(mission, verbose=True)
    return orchestrator, result


if __name__ == "__main__":
    run_demo()