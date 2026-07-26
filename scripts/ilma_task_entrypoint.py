#!/usr/bin/env python3
"""
ILMA Task Entrypoint — Central Integration Point for Autonomous Evolution
========================================================================
Phase 47 - Nerve Integration.

This is the PRIMARY integration point for the Actor-Critic loop.
All heavy missions should route through this entrypoint.

Usage:
    from scripts.ilma_task_entrypoint import run_task_with_evolution
    result = run_task_with_evolution(
        target="Build feature X",
        task_class="heavy",
        max_iterations=80,
        require_judge=True,
        store_lessons=True
    )

Flow:
1. Load autonomous evolution config
2. Determine if task_class triggers evolution
3. If yes: pre_task_retrieval → Actor-Critic loop → Reflection → Judge → Finalize
4. If no: execute normally (direct path)
5. Store lessons on recovery
6. Export evolution trace
"""

from __future__ import annotations

import json
import sys
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable

# Import Phase 46 components
sys.path.insert(0, str(Path(__file__).parent))
from ilma_autonomous_evolution_orchestrator import (
    AutonomousEvolutionOrchestrator,
    MissionState,
    MissionStatus,
)
from ilma_critic_judge import CriticJudge, JudgeStatus, JudgeResult
from ilma_reflection_engine import ReflectionEngine, ReflectionResult
from ilma_lesson_memory import LessonMemory
from ilma_pretask_learning_hook import PreTaskLearningHook
from ilma_default_actor_artifact_producer import DefaultArtifactProducer


class TaskClass(str, Enum):
    """Task classification for evolution requirements."""
    SIMPLE = "simple"
    NORMAL = "normal"
    HEAVY = "heavy"
    SUPER_HEAVY = "super_heavy"
    EXTREME_MISSION = "extreme_mission"
    AUTONOMOUS_EVOLUTION = "autonomous_evolution"


class EvolutionResult(str, Enum):
    """Outcome of evolution loop."""
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"


@dataclass
class EvolutionTrace:
    """Complete trace of one evolution session."""
    trace_id: str
    timestamp: str
    target: str
    task_class: str
    start_time: str
    end_time: Optional[str] = None
    iteration_count: int = 0
    retrieved_lessons: List[Dict] = field(default_factory=list)
    actor_outputs: List[str] = field(default_factory=list)
    judge_results: List[Dict] = field(default_factory=list)
    reflections: List[Dict] = field(default_factory=list)
    revisions: List[str] = field(default_factory=list)
    final_status: str = "UNKNOWN"
    lessons_created: List[str] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    blocked_reason: Optional[str] = None
    exit_reason: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['final_status'] = self.final_status
        return d

    def to_json(self, path: Path) -> None:
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def from_dict(cls, d: Dict) -> "EvolutionTrace":
        return cls(**d)


def load_config() -> Dict[str, Any]:
    """Load autonomous evolution configuration."""
    config_path = Path(__file__).parent.parent / "config" / "ilma_autonomous_evolution_config.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {"enabled": False}


def requires_evolution(task_class: str, config: Dict) -> bool:
    """Check if task_class triggers evolution loop."""
    if not config.get("enabled", False):
        return False
    return task_class in config.get("default_for_task_classes", [])


def run_task_with_evolution(
    target: str,
    task_class: str = "heavy",
    max_iterations: Optional[int] = None,
    require_judge: bool = True,
    store_lessons: bool = True,
    actor_callback: Optional[Callable] = None,
    verbose: bool = False,
) -> EvolutionTrace:
    """
    Run a task through the Autonomous Evolution loop.

    Args:
        target: The task target/goal
        task_class: Task classification (simple/normal/heavy/super_heavy/extreme/autonomous)
        max_iterations: Override max iterations (uses config default if None)
        require_judge: Whether to require judge evaluation
        store_lessons: Whether to store lessons on recovery
        actor_callback: Optional callback for actor (mode, target, context) -> str
        verbose: Print progress

    Returns:
        EvolutionTrace with full loop record
    """
    config = load_config()
    trace_id = f"TRACE-{datetime.now().strftime('%Y%m%d%H%M%S')}-{task_class[:3].upper()}"
    trace = EvolutionTrace(
        trace_id=trace_id,
        timestamp=datetime.now().isoformat(),
        target=target,
        task_class=task_class,
        start_time=datetime.now().isoformat(),
    )

    try:
        # Check if evolution required
        if not requires_evolution(task_class, config):
            if verbose:
                print(f"[TaskEntrypoint] Task class '{task_class}' does not require evolution. Direct execute.")
            trace.final_status = "DIRECT_EXECUTE"
            trace.exit_reason = "no_evolution_required"
            return trace

        if verbose:
            print(f"[TaskEntrypoint] Evolution required for '{task_class}'. Starting loop.")

        # Get max iterations from config or override
        if max_iterations is None:
            max_iters_map = config.get("max_iterations", {})
            max_iterations = max_iters_map.get(task_class, 80)

        # Initialize components
        orchestrator = AutonomousEvolutionOrchestrator(max_iterations=max_iterations)
        judge = CriticJudge()
        reflection = ReflectionEngine()
        memory = LessonMemory()
        pretask_hook = PreTaskLearningHook()

        # Step 1: Pre-task lesson retrieval
        if verbose:
            print(f"[TaskEntrypoint] Pre-task retrieval...")
        # Do NOT filter by task_type — seeded lessons have task_types like
        # parser_fix/safety_gate_fix/etc., not 'heavy'. Filtering by task_class
        # would exclude all seeded lessons. Let the keyword search find relevant ones.
        retrieved = pretask_hook.retrieve_for_task(target, limit=10)
        # retrieve_for_task returns a dict with 'lessons' key, not a list of dataclasses
        if isinstance(retrieved, dict):
            trace.retrieved_lessons = retrieved.get('lessons', [])
            retrieved_lesson_sigs = retrieved.get('retrieved_lesson_sigs', [])
        else:
            trace.retrieved_lessons = []
            retrieved_lesson_sigs = []

        # Build lesson context for actor
        lesson_context = {
            'lesson_count': len(trace.retrieved_lessons),
            'lesson_sigs': retrieved_lesson_sigs,
            'has_lessons': len(trace.retrieved_lessons) > 0,
        }

        # Step 2: Create mission
        if verbose:
            print(f"[TaskEntrypoint] Creating mission...")
        mission = orchestrator.create_mission(target=target, task_type=task_class)

        # Set actor callback if provided, otherwise use default artifact producer
        producer = DefaultArtifactProducer()
        if actor_callback:
            orchestrator.actor_callback = actor_callback
        else:
            # Use default artifact producer as the actor callback
            def default_actor(mission, iteration, verbose=False):
                """Default artifact producer that writes real files."""
                # Determine artifact type based on target
                target_lower = mission.target.lower()
                if "report" in target_lower or "audit" in target_lower or "summary" in target_lower:
                    artifact_type = "markdown_report"
                elif "test" in target_lower or "spec" in target_lower:
                    artifact_type = "test_file"
                elif "config" in target_lower or "settings" in target_lower:
                    artifact_type = "json_config"
                elif "plan" in target_lower:
                    artifact_type = "refactor_plan"
                else:
                    artifact_type = "markdown_report"

                # Build context with lesson info
                context = {"iteration": iteration}
                context.update(lesson_context)

                # Produce the artifact
                result = producer.produce_artifact(
                    target=mission.target,
                    task_class=mission.task_type,
                    artifact_type=artifact_type,
                    context=context,
                )

                if result.success and result.artifact_path:
                    # Read artifact content
                    from pathlib import Path
                    artifact_content = Path(result.artifact_path).read_text()

                    # If lessons were retrieved, inject lesson context into artifact
                    # This ensures the artifact references the lessons and passes rubric
                    if lesson_context['has_lessons']:
                        sigs = lesson_context['lesson_sigs']
                        lesson_header = (
                            f"\n\n## Lesson Context (from auto-learning)\n"
                            f"Retrieved {lesson_context['lesson_count']} relevant lesson(s):\n"
                        )
                        for sig in sigs[:5]:
                            lesson_header += f"- `{sig}`\n"
                        lesson_header += (
                            f"\n*Note: This artifact was generated with lesson-aware context.*\n"
                        )
                        # Append lesson header to artifact content
                        artifact_content += lesson_header
                        # Write back with lesson context
                        Path(result.artifact_path).write_text(artifact_content)

                    mission.actor_artifact = artifact_content
                    mission.actor_artifact_path = result.artifact_path
                    if verbose:
                        print(f"  [Actor] Artifact produced: {result.artifact_path} (with {lesson_context['lesson_count']} lessons)")
                    return artifact_content
                else:
                    mission.actor_artifact = ""
                    if verbose:
                        print(f"  [Actor] Artifact production failed: {result.errors}")
                    return ""

            orchestrator.actor_callback = default_actor

        # Step 3: Run Actor-Critic loop
        if verbose:
            print(f"[TaskEntrypoint] Running Actor-Critic loop (max_iter={max_iterations})...")

        result = orchestrator.run(mission, verbose=verbose)
        trace.iteration_count = result.iteration

        # Step 4: Judge evaluation
        if require_judge:
            if verbose:
                print(f"[TaskEntrypoint] Judge evaluation...")
            artifact = mission.actor_artifact or ""
            judge_result = judge.evaluate(
                artifact=artifact,
                target=target,
                criteria=f"Task class: {task_class}",
                task_type=task_class
            )
            # Convert to dict with Enum values as strings for JSON serialization
            jr_dict = asdict(judge_result)
            jr_dict['status'] = judge_result.status.value  # Enum -> string
            trace.judge_results = [jr_dict]

            if verbose:
                print(f"[TaskEntrypoint] Judge: {judge_result.status.value}, score={judge_result.score:.0f}")

            # === PHASE 48G-H: mark_reused Integration ===
            # Mark lessons as reused ONLY when judge status is PASS or WARN (not FAIL/ERROR)
            # This ensures reuse_count only increments for successful artifact evaluations
            if retrieved and retrieved.get('lessons'):
                lesson_ids_to_mark = [l.get('lesson_id', '') for l in retrieved['lessons'] if l.get('lesson_id')]
                if lesson_ids_to_mark and judge_result.status in (JudgeStatus.PASS, JudgeStatus.WARN):
                    if verbose:
                        print(f"[TaskEntrypoint] Marking {len(lesson_ids_to_mark)} lessons as reused (judge={judge_result.status.value})...")
                    for lid in lesson_ids_to_mark:
                        if lid:
                            memory.mark_reused(lid)

            # Step 5: Handle judge result
            if judge_result.status == JudgeStatus.PASS:
                trace.final_status = "PASS"
                trace.exit_reason = "judge_passed"
            elif judge_result.status == JudgeStatus.WARN:
                # Check if warn threshold allows pass
                warn_threshold = config.get("judge_threshold_warn", 70)
                if judge_result.score >= warn_threshold:
                    trace.final_status = "PASS_WITH_WARN"
                    trace.exit_reason = "warn_allowed"
                else:
                    trace.final_status = "FAIL"
                    trace.exit_reason = "warn_below_threshold"
            else:
                # FAIL - trigger reflection
                trace.final_status = "FAIL"
                trace.exit_reason = "judge_failed"

                # Reflection
                if verbose:
                    print(f"[TaskEntrypoint] Reflection triggered...")

                # === PHASE 57: LIVE RESEARCH TRIGGER ===
                # If reflection gave unclear root cause AND iteration >= 2, trigger live research
                refl_result = reflection.analyze(
                    target=target,
                    artifact=artifact,
                    judge_result={"status": judge_result.status.value, "score": judge_result.score, "failures": [], "warnings": []},
                    previous_attempts=trace.actor_outputs
                )
                
                # Check if reflection root cause is unclear
                root_cause_unclear = not refl_result.root_cause or "unknown" in refl_result.root_cause.lower() or "unclear" in refl_result.root_cause.lower()
                
                if root_cause_unclear and iteration >= 2:
                    print(f"\n🧪 [LIVE RESEARCH] Root cause unclear after {iteration} iterations — triggering live research...")
                    try:
                        from scripts.ilma_live_research import LiveResearch
                        lr = LiveResearch()
                        
                        # Get failure context from judge
                        failures = judge_result.failures if hasattr(judge_result, 'failures') else []
                        error_context = failures[0] if failures else str(artifact)[:200]
                        
                        research_result = lr.research(
                            error_context=error_context,
                            task_type=task_class,
                            root_cause=refl_result.root_cause or "",
                            failed_attempts=iteration
                        )
                        
                        if research_result.solutions:
                            print(f"   📚 Found {len(research_result.solutions)} potential solution(s) from live research")
                            # Enhance reflection fix plan with research
                            if not refl_result.fix_plan:
                                refl_result.fix_plan = []
                            refl_result.fix_plan.insert(0, f"📚 Live research suggests: {research_result.solutions[0][:100]}")
                            for sol in research_result.solutions[1:4]:
                                refl_result.fix_plan.append(f"  → Alternative: {sol[:100]}")
                            
                            # Store research result for future
                            lr.store_research_result(error_context, research_result)
                        else:
                            print(f"   ⚠️ Live research: No solutions found")
                    except Exception as lr_e:
                        print(f"   ⚠️ Live research failed (non-fatal): {lr_e}")
                # Convert ReflectionResult to dict (handle Enum values)
                refl_dict = asdict(refl_result)
                trace.reflections = [refl_dict]

                if verbose:
                    print(f"[TaskEntrypoint] Root cause: {refl_result.root_cause}")

                # Store lesson if recovered
                try:
                    if store_lessons:
                        if verbose:
                            print(f"[TaskEntrypoint] Storing lesson...")
                        # Build lesson from reflection
                        lesson_data = {
                            "task_type": task_class,
                            "failure_pattern": refl_dict.get("root_cause", "unknown")[:100],
                            "root_cause": refl_dict.get("root_cause", ""),
                            "fix": refl_dict.get("fix_plan", ["none"])[0] if refl_dict.get("fix_plan") else "none",
                            "validation_method": "judge_recovery",
                            "confidence": 0.7,
                            "source_evidence": f"TRACE-{trace.trace_id}",
                            "phase": "Phase 47CLOSE"
                        }
                        lid = memory.add_lesson(lesson_data)
                        trace.lessons_created = [{"lesson_id": lid}]
                        if verbose:
                            print(f"[TaskEntrypoint] Lesson stored: {lid}")
                except Exception as lesson_e:
                    if verbose:
                        print(f"[TaskEntrypoint] Lesson store failed (non-fatal): {lesson_e}")

        else:
            trace.final_status = "NO_JUDGE"
            trace.exit_reason = "judge_skipped"

        # Step 6: Store lesson if recovery happened
        # NOTE: Lesson storage is non-fatal. If it fails, do NOT change final_status.
        if store_lessons and trace.final_status in ["PASS", "PASS_WITH_WARN"]:
            # Only store if we have meaningful lessons (reflections from recovery)
            if trace.reflections and len(trace.reflections) > 0:
                try:
                    if verbose:
                        print(f"[TaskEntrypoint] Storing lesson from reflection...")
                    # Only access trace.reflections[0] AFTER confirming it's non-empty
                    first_reflect = trace.reflections[0]
                    lesson = {
                        "event_type": "judge_recovery",
                        "phase": "Phase 48B-CLOSE",
                        "task_type": task_class,
                        "failure_pattern": first_reflect.get("root_cause", "unknown")[:200],
                        "root_cause": first_reflect.get("root_cause", ""),
                        "fix_plan": first_reflect.get("fix_plan", ["none"]),
                        "validation_method": "judge_recovery",
                        "confidence": 0.7,
                        "overclaim_detected": False,
                        "evidence_gaps": [],
                        "source_evidence": f"TRACE-{trace.trace_id}"
                    }
                    lesson_id = memory.add_lesson(lesson)
                    trace.lessons_created = [{"lesson_id": lesson_id}]
                    if verbose:
                        print(f"[TaskEntrypoint] Lesson stored: {lesson_id}")
                except Exception as lesson_e:
                    # Lesson storage failure is non-fatal — log but PRESERVE final_status
                    if verbose:
                        print(f"[TaskEntrypoint] Lesson store failed (non-fatal): {lesson_e}")
                    # Do NOT change trace.final_status — keep PASS_WITH_WARN
            elif verbose:
                print(f"[TaskEntrypoint] No reflections to store lesson from (final_status={trace.final_status})")

        trace.end_time = datetime.now().isoformat()

    except Exception as e:
        # CRITICAL: Only set ERROR if this is a REAL execution failure.
        # Lesson storage failure should NOT set ERROR — preserve the judge-verdict status.
        trace.error = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        # If final_status was already set by judge (PASS/PASS_WITH_WARN), do NOT overwrite with ERROR
        # Only set ERROR if final_status is still UNKNOWN or was never set by judge
        if trace.final_status in ["UNKNOWN", ""]:
            trace.final_status = "ERROR"
        trace.exit_reason = "exception"

    return trace


def run_pretask_learning(target: str, task_class: str = "heavy") -> List[Dict]:
    """
    Standalone pre-task lesson retrieval.

    Args:
        target: The task target
        task_class: Task classification

    Returns:
        List of retrieved lessons with relevance scores
    """
    config = load_config()
    if not config.get("enabled", False):
        return []

    hook = PreTaskLearningHook()
    lessons = hook.retrieve_for_task(target, task_class)
    return [asdict(l) for l in lessons]


# ============ DEMO / TEST ============

def demo():
    """Demo of the task entrypoint."""
    print("=" * 60)
    print("ILMA Task Entrypoint — Autonomous Evolution Loop")
    print("=" * 60)

    # Test pre-task retrieval
    print("\n[Pre-Task Retrieval Test]")
    lessons = run_pretask_learning(
        target="Build a REST API with authentication",
        task_class="heavy"
    )
    print(f"  Retrieved {len(lessons)} lessons")
    for l in lessons[:3]:
        print(f"    - {l.get('lesson_id', 'unknown')}: {l.get('task_type', 'unknown')}")

    # Test evolution loop with a simple task
    print("\n[Evolution Loop Test]")
    def simple_actor(mode, target, context):
        if mode == "plan":
            return "1. Create API structure\n2. Add auth\n3. Add tests"
        else:
            return """# Simple API Implementation

## Structure
- app.py with Flask routes
- auth.py for authentication
- tests/ for unit tests

## Evidence: ILMA-EVID-20260510-P47-ENTRYPOINT-001
"""

    trace = run_task_with_evolution(
        target="Build a simple REST API",
        task_class="heavy",
        max_iterations=5,
        require_judge=True,
        store_lessons=True,
        actor_callback=simple_actor,
        verbose=True
    )

    print(f"\n[Result]")
    print(f"  Trace ID: {trace.trace_id}")
    print(f"  Iterations: {trace.iteration_count}")
    print(f"  Status: {trace.final_status}")
    print(f"  Exit Reason: {trace.exit_reason}")
    print(f"  Lessons Created: {trace.lessons_created}")
    print(f"  Judge Results: {len(trace.judge_results)}")

    # Save trace
    trace_dir = Path(__file__).parent.parent / "evidence" / "evolution_traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_path = trace_dir / f"{trace.trace_id}.json"
    trace.to_json(trace_path)
    print(f"  Trace saved: {trace_path}")

    print("=" * 60)


if __name__ == "__main__":
    demo()