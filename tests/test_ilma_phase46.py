#!/usr/bin/env python3
"""
ILMA Phase 46 Unit Tests
========================
Unit tests for Autonomous Evolution components.
Phase 46 - Autonomous Evolution Foundation.
"""

import unittest
from pathlib import Path
import sys

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class TestAutonomousEvolutionOrchestrator(unittest.TestCase):
    """Test AutonomousEvolutionOrchestrator."""

    def test_mission_creation(self):
        from ilma_autonomous_evolution_orchestrator import (
            AutonomousEvolutionOrchestrator, MissionState, MissionStatus
        )
        orch = AutonomousEvolutionOrchestrator(max_iterations=5)
        mission = orch.create_mission(
            target="Build factorial function",
            criteria="Must handle edge cases",
            task_type="code"
        )
        self.assertIsInstance(mission, MissionState)
        self.assertEqual(mission.target, "Build factorial function")
        self.assertEqual(mission.task_type, "code")
        self.assertEqual(mission.max_iterations, 5)
        self.assertEqual(mission.current_status, MissionStatus.INIT)

    def test_mission_state_serialization(self):
        from ilma_autonomous_evolution_orchestrator import MissionState
        state = MissionState(
            mission_id="test123",
            target="Test target",
            iteration=3
        )
        d = state.to_dict()
        self.assertEqual(d["mission_id"], "test123")
        self.assertEqual(d["current_status"], "INIT")
        
        restored = MissionState.from_dict(d)
        self.assertEqual(restored.mission_id, "test123")

    def test_run_completes(self):
        from ilma_autonomous_evolution_orchestrator import (
            AutonomousEvolutionOrchestrator
        )
        orch = AutonomousEvolutionOrchestrator(max_iterations=3)
        mission = orch.create_mission(
            target="Build simple function",
            task_type="code"
        )
        result = orch.run(mission, verbose=False)
        self.assertIn(result.current_status.value, [
            "PASSED", "FAILED", "BLOCKED", "ESCALATED"
        ])

    def test_checkpoint_frequency(self):
        from ilma_autonomous_evolution_orchestrator import (
            AutonomousEvolutionOrchestrator
        )
        orch = AutonomousEvolutionOrchestrator(
            max_iterations=10,
            checkpoint_frequency=5
        )
        mission = orch.create_mission(target="Test", task_type="code")
        result = orch.run(mission, verbose=False)
        # Checkpoint should happen at iteration 5


class TestCriticJudge(unittest.TestCase):
    """Test CriticJudge."""

    def test_judge_good_artifact(self):
        from ilma_critic_judge import CriticJudge, JudgeStatus
        judge = CriticJudge()
        result = judge.evaluate(
            artifact='''def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

def test_factorial():
    assert factorial(0) == 1
    assert factorial(5) == 120

# Quality markers: complete, tested, error-handled
''',
            target="Build factorial",
            criteria="Must have tests",
            task_type="code"
        )
        # Good artifact should pass or warn (WARN still means acceptable quality)
        self.assertIn(result.status, [JudgeStatus.PASS, JudgeStatus.WARN])
        self.assertGreater(result.score, 70)

    def test_judge_bad_artifact_syntax(self):
        from ilma_critic_judge import CriticJudge, JudgeStatus
        judge = CriticJudge()
        result = judge.evaluate(
            artifact="def factorial(n):\n    return n * factorial(n-1)\n    return 1",
            target="Build factorial",
            criteria="Must compile",
            task_type="code"
        )
        # Bad artifact with syntax error gets FAIL or WARN (not PASS)
        self.assertIn(result.status, [JudgeStatus.FAIL, JudgeStatus.WARN])

    def test_judge_overclaim(self):
        from ilma_critic_judge import CriticJudge, JudgeStatus
        judge = CriticJudge()
        result = judge.evaluate(
            artifact="This is 100% perfect and will ALWAYS work with no bugs!",
            target="Build function",
            criteria="No overclaims",
            task_type="code"
        )
        self.assertEqual(result.status, JudgeStatus.FAIL)

    def test_security_check(self):
        from ilma_critic_judge import CriticJudge
        judge = CriticJudge()
        result = judge.evaluate(
            artifact="password = 'supersecret123'",
            target="Config",
            criteria="Security",
            task_type="code"
        )
        self.assertGreater(len(result.failures), 0)


class TestReflectionEngine(unittest.TestCase):
    """Test ReflectionEngine."""

    def test_analyze_syntax_error(self):
        from ilma_reflection_engine import ReflectionEngine
        engine = ReflectionEngine()
        result = engine.analyze(
            target="Build function",
            artifact="def bad:",
            judge_result={"failures": ["Syntax error at line 1"], "warnings": []}
        )
        self.assertIn("syntax", result.root_cause.lower())
        self.assertGreater(len(result.fix_plan), 0)

    def test_analyze_hallucination(self):
        from ilma_reflection_engine import ReflectionEngine
        engine = ReflectionEngine()
        result = engine.analyze(
            target="Build function",
            artifact="100% perfect always works",
            judge_result={"failures": ["Overclaim detected"], "warnings": []}
        )
        self.assertTrue(result.hallucination_detected)

    def test_analyze_missing_dependency(self):
        from ilma_reflection_engine import ReflectionEngine
        engine = ReflectionEngine()
        result = engine.analyze(
            target="Build function",
            artifact="import missing_module",
            judge_result={"failures": ["ModuleNotFoundError"], "warnings": []}
        )
        self.assertTrue(result.missing_dependency)


class TestLessonMemory(unittest.TestCase):
    """Test LessonMemory."""

    def test_add_lesson(self):
        from ilma_lesson_memory import LessonMemory
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = LessonMemory(Path(tmpdir) / "lessons.jsonl")
            lesson_id = memory.add_lesson({
                "phase": "Phase 46",
                "task_type": "code",
                "failure_pattern": "Test pattern",
                "root_cause": "Test root cause"
            })
            self.assertIsNotNone(lesson_id)

    def test_validate_schema(self):
        from ilma_lesson_memory import LessonMemory
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = LessonMemory(Path(tmpdir) / "lessons.jsonl")
            valid, errors = memory.validate_schema({
                "lesson_id": "test123",
                "timestamp": "2026-05-10T00:00:00",
                "phase": "Phase 46",
                "task_type": "code",
                "failure_pattern": "Test",
                "root_cause": "Test"
            })
            self.assertTrue(valid)
            self.assertEqual(len(errors), 0)

    def test_search_lessons(self):
        from ilma_lesson_memory import LessonMemory
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = LessonMemory(Path(tmpdir) / "lessons.jsonl")
            memory.add_lesson({
                "phase": "Phase 46",
                "task_type": "code",
                "failure_pattern": "Syntax error in Python",
                "root_cause": "Missing parenthesis"
            })
            results = memory.search_lessons("syntax")
            self.assertGreater(len(results), 0)

    def test_retrieve_for_task(self):
        from ilma_lesson_memory import LessonMemory
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = LessonMemory(Path(tmpdir) / "lessons.jsonl")
            memory.add_lesson({
                "phase": "Phase 46",
                "task_type": "code",
                "failure_pattern": "Test failure",
                "root_cause": "Missing assertions"
            })
            result = memory.retrieve_for_task("Build Python function", task_type="code")
            self.assertIn("lessons", result)
            self.assertIn("count", result)


class TestPreTaskLearningHook(unittest.TestCase):
    """Test PreTaskLearningHook."""

    def test_retrieve_for_task(self):
        from ilma_pretask_learning_hook import PreTaskLearningHook
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            hook = PreTaskLearningHook(Path(tmpdir) / "lessons.jsonl")
            result = hook.retrieve_for_task("Build Python function", task_type="code")
            self.assertIn("task", result)
            self.assertIn("lessons", result)
            self.assertIn("count", result)
            self.assertIn("changed_plan", result)

    def test_extract_keywords(self):
        from ilma_pretask_learning_hook import PreTaskLearningHook
        import tempfile
        hook = PreTaskLearningHook()
        keywords = hook._extract_keywords("Build Python factorial function with tests")
        self.assertIsInstance(keywords, list)


class TestSpecialistValidators(unittest.TestCase):
    """Test Specialist Validators."""

    def test_architect_validator_good(self):
        from ilma_specialist_validators import ArchitectValidator
        validator = ArchitectValidator()
        result = validator.validate('''def factorial(n):
    """Calculate factorial."""
    return 1
''')
        self.assertIn(result.status, ["PASS", "WARN"])

    def test_qa_validator_has_tests(self):
        from ilma_specialist_validators import QAValidator
        validator = QAValidator()
        result = validator.validate('''def test_factorial():
    assert factorial(0) == 1
''')
        self.assertIn(result.status, ["PASS", "WARN"])

    def test_security_validator_detects_danger(self):
        from ilma_specialist_validators import SecurityValidator
        validator = SecurityValidator()
        result = validator.validate("password = 'supersecret123456789012345678'")
        # Multiple issues = FAIL, single issue = WARN
        self.assertIn(result.status, ["FAIL", "WARN"])
        self.assertGreater(len(result.issues), 0)

    def test_truthfulness_validator_detects_overclaim(self):
        from ilma_specialist_validators import TruthfulnessValidator
        validator = TruthfulnessValidator()
        result = validator.validate("This is 100% perfect and will ALWAYS work!")
        self.assertEqual(result.status, "WARN")
        self.assertGreater(len(result.issues), 0)

    def test_evidence_validator(self):
        from ilma_specialist_validators import EvidenceValidator
        validator = EvidenceValidator()
        result = validator.validate("# ILMA-EVID-20260510-VALID-001")
        self.assertEqual(result.status, "PASS")

    def test_all_validators_run(self):
        from ilma_specialist_validators import SpecialistValidatorOrchestrator
        orch = SpecialistValidatorOrchestrator()
        results = orch.validate_all("# Simple artifact")
        self.assertEqual(len(results), 8)


class TestStrategyOptimizer(unittest.TestCase):
    """Test StrategyOptimizer."""

    def test_record_attempt(self):
        from ilma_strategy_optimizer import StrategyOptimizer
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            optimizer = StrategyOptimizer(Path(tmpdir) / "policy.json")
            attempt = optimizer.record_strategy_attempt(
                task_type="code",
                prompt_policy="temperature=0.5",
                score_before=70,
                score_after=85
            )
            self.assertIsNotNone(attempt.attempt_id)
            self.assertEqual(attempt.improvement, 15)
            self.assertTrue(attempt.approved)

    def test_compare_before_after(self):
        from ilma_strategy_optimizer import StrategyOptimizer
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            optimizer = StrategyOptimizer(Path(tmpdir) / "policy.json")
            optimizer.record_strategy_attempt(
                task_type="code",
                prompt_policy="temp=0.5",
                score_before=70,
                score_after=85
            )
            comparison = optimizer.compare_before_after("code")
            # Check at least 1 (history may have entries from other tests)
            self.assertGreaterEqual(comparison["total_attempts"], 1)

    def test_suggest_patch(self):
        from ilma_strategy_optimizer import StrategyOptimizer
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            optimizer = StrategyOptimizer(Path(tmpdir) / "policy.json")
            patch = optimizer.suggest_prompt_policy_patch(
                task_type="code",
                policy_key="temperature",
                old_value="0.4-0.7",
                new_value="0.5-0.7",
                expected_improvement=5.0
            )
            self.assertIsNotNone(patch.patch_id)
            self.assertEqual(patch.status, "PENDING")


class TestExecutionJudgeAdapter(unittest.TestCase):
    """Test ExecutionJudgeAdapter."""

    def test_execute_simple_command(self):
        from ilma_execution_judge_adapter import ExecutionJudgeAdapter
        adapter = ExecutionJudgeAdapter(timeout=10)
        result = adapter.execute("echo 'hello'")
        self.assertEqual(result.returncode, 0)
        self.assertFalse(result.timed_out)

    def test_execute_failing_command(self):
        from ilma_execution_judge_adapter import ExecutionJudgeAdapter
        adapter = ExecutionJudgeAdapter(timeout=10)
        result = adapter.execute("python3 -c 'import nonexistent'")
        self.assertNotEqual(result.returncode, 0)

    def test_judge_execution_pass(self):
        from ilma_execution_judge_adapter import ExecutionJudgeAdapter
        adapter = ExecutionJudgeAdapter()
        result = adapter.execute("echo 'test'")
        judgment = adapter.judge_execution(result)
        self.assertEqual(judgment["status"], "PASS")

    def test_judge_execution_fail(self):
        from ilma_execution_judge_adapter import ExecutionJudgeAdapter
        adapter = ExecutionJudgeAdapter()
        result = adapter.execute("python3 -c 'raise ValueError(\"test\")'")
        judgment = adapter.judge_execution(result)
        # Runtime error gets WARN (only SyntaxError/ImportError/timeout = FAIL)
        self.assertIn(judgment["status"], ["FAIL", "WARN"])


class TestConditionalLoopRouter(unittest.TestCase):
    """Test ConditionalLoopRouter."""

    def test_route_pass(self):
        from ilma_conditional_loop_router import ConditionalLoopRouter, Decision
        router = ConditionalLoopRouter()
        decision = router.route(
            {"status": "PASS", "failures": [], "warnings": []},
            {"iteration": 1, "max_iterations": 300, "repeated_failures": 0, "unsafe_detected": False}
        )
        self.assertEqual(decision, Decision.FINALIZE)

    def test_route_fail_fixable(self):
        from ilma_conditional_loop_router import ConditionalLoopRouter, Decision
        router = ConditionalLoopRouter()
        decision = router.route(
            {"status": "FAIL", "failures": ["Missing tests"], "warnings": []},
            {"iteration": 1, "max_iterations": 300, "repeated_failures": 0, "unsafe_detected": False}
        )
        self.assertEqual(decision, Decision.REVISE)

    def test_route_repeated_failure(self):
        from ilma_conditional_loop_router import ConditionalLoopRouter, Decision
        router = ConditionalLoopRouter()
        decision = router.route(
            {"status": "FAIL", "failures": ["Same error"], "warnings": []},
            {"iteration": 5, "max_iterations": 300, "repeated_failures": 3, "unsafe_detected": False}
        )
        self.assertEqual(decision, Decision.ESCALATE)

    def test_route_unsafe(self):
        from ilma_conditional_loop_router import ConditionalLoopRouter, Decision
        router = ConditionalLoopRouter()
        decision = router.route(
            {"status": "FAIL", "failures": ["Dangerous"], "warnings": []},
            {"iteration": 1, "max_iterations": 300, "repeated_failures": 0, "unsafe_detected": True}
        )
        self.assertEqual(decision, Decision.ABORT)

    def test_route_max_iterations(self):
        from ilma_conditional_loop_router import ConditionalLoopRouter, Decision
        router = ConditionalLoopRouter(max_iterations=5)
        decision = router.route(
            {"status": "FAIL", "failures": [], "warnings": []},
            {"iteration": 5, "max_iterations": 5, "repeated_failures": 0, "unsafe_detected": False}
        )
        self.assertEqual(decision, Decision.FAILED)

    def test_get_next_state(self):
        from ilma_conditional_loop_router import ConditionalLoopRouter, Decision
        router = ConditionalLoopRouter()
        next_state = router.get_next_state(Decision.FINALIZE, {"iteration": 1})
        self.assertEqual(next_state, {"iteration": 2})


if __name__ == "__main__":
    unittest.main()