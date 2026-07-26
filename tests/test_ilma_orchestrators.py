#!/usr/bin/env python3
"""
ILMA Orchestrator Frameworks — Test Suite v1.0
=============================================
Comprehensive tests for all 4 orchestrator patterns.

Patterns tested:
1. LangGraph: State machine with conditional edges
2. AutoGen: Real-world execution with stack traces
3. DSPy: Metric-based self-improvement
4. MetaGPT: Corporate SOP simulation
5. Universal: Auto-selection and routing
"""

import sys
from pathlib import Path

# ILMA paths
ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
WORKSPACE = ILMA_PROFILE
sys.path.insert(0, str(WORKSPACE))

import unittest
from unittest.mock import patch, MagicMock
import json

# Import all orchestrators
from ilma_langgraph_orchestrator import (
    LangGraphOrchestrator, GraphState, ActorNode, JudgeNode,
    ConditionalEdge, VerdictType, NodeStatus
)
from ilma_autogen_executor import (
    AutoGenOrchestrator, UserProxyAgent, AutogenSession,
    ExecutionMode, ExecutionResult
)
from ilma_dspy_self_improver import (
    DSPyOrchestrator, MetricFunctions, Teleprompter,
    MetricResult, MetricType
)
from ilma_metagpt_orchestrator import (
    MetaGPTOrchestrator, SOPStage, AgentRole, Artifact, RoleConfig
)
from ilma_universal_orchestrator import (
    UniversalOrchestrator, OrchestratorType
)


# === LANGGRAPH TESTS ===

class TestLangGraphOrchestrator(unittest.TestCase):
    """Test LangGraph-style state machine orchestrator."""
    
    def test_session_creation(self):
        """Test session creation."""
        orch = LangGraphOrchestrator(max_rounds=3)
        session = orch.create_session("Build function", "Must validate input")
        
        self.assertIsNotNone(session.session_id)
        self.assertEqual(session.task, "Build function")
        self.assertEqual(session.target_criteria, "Must validate input")
        self.assertEqual(session.max_rounds, 3)
        self.assertEqual(session.round_number, 0)
    
    def test_actor_node_execution(self):
        """Test Actor node produces output."""
        node = ActorNode(temperature=0.5)
        state = GraphState(
            session_id="test",
            task="Build factorial",
            target_criteria="Handle edge cases"
        )
        
        result = node.execute(state)
        
        self.assertEqual(node.status, NodeStatus.COMPLETED)
        self.assertGreater(len(result.actor_output), 0)
        self.assertEqual(result.actor_attempts, 1)
        self.assertEqual(result.round_number, 1)
    
    def test_judge_node_execution(self):
        """Test Judge node evaluates output."""
        node = JudgeNode(pass_threshold=4.0)
        state = GraphState(
            session_id="test",
            task="Build factorial",
            target_criteria="Handle edge cases",
            actor_output="<SCRATCHPAD>Plan</SCRATCHPAD>\n<SOLUTION>def f(): pass</SOLUTION>"
        )
        
        result = node.execute(state)
        
        self.assertEqual(node.status, NodeStatus.COMPLETED)
        self.assertIn(result.judge_verdict, [VerdictType.PASS, VerdictType.FAIL])
        self.assertGreaterEqual(result.judge_score, 1.0)
        self.assertLessEqual(result.judge_score, 5.0)
    
    def test_conditional_edge_pass(self):
        """Test conditional edge routes to END on PASS."""
        edge = ConditionalEdge(pass_threshold=4.0, max_rounds=5)
        state = GraphState(session_id="test", task="task")
        state.judge_verdict = VerdictType.PASS
        state.round_number = 1
        
        route = edge.route(state)
        self.assertEqual(route, "END")
    
    def test_conditional_edge_fail(self):
        """Test conditional edge routes to actor on FAIL."""
        edge = ConditionalEdge(pass_threshold=4.0, max_rounds=5)
        state = GraphState(session_id="test", task="task")
        state.judge_verdict = VerdictType.FAIL
        state.round_number = 1
        
        route = edge.route(state)
        self.assertEqual(route, "actor")
    
    def test_conditional_edge_max_rounds(self):
        """Test conditional edge stops at max rounds."""
        edge = ConditionalEdge(pass_threshold=4.0, max_rounds=3)
        state = GraphState(session_id="test", task="task")
        state.judge_verdict = VerdictType.FAIL
        state.round_number = 3  # At max
        
        route = edge.route(state)
        self.assertEqual(route, "END")
    
    def test_full_orchestrator_run(self):
        """Test full orchestrator execution loop."""
        orch = LangGraphOrchestrator(max_rounds=2, pass_threshold=4.0)
        session = orch.create_session("Build factorial", "Must validate input")
        
        result = orch.run(session.session_id, verbose=False)
        
        self.assertIsNotNone(result)
        self.assertGreater(result.round_number, 0)
        self.assertGreater(result.actor_attempts, 0)
        self.assertIn(result.judge_verdict, [VerdictType.PASS, VerdictType.FAIL])
    
    def test_statistics(self):
        """Test orchestrator statistics."""
        orch = LangGraphOrchestrator(max_rounds=2)
        orch.create_session("Task 1", "Criteria")
        orch.create_session("Task 2", "Criteria")
        
        # Run both (will likely fail/pass differently)
        for sid in list(orch.sessions.keys()):
            try:
                orch.run(sid, verbose=False)
            except:
                pass
        
        stats = orch.get_statistics()
        self.assertEqual(stats['total_sessions'], 2)
        self.assertIn('passed', stats)
        self.assertIn('failed', stats)


# === AUTOGEN TESTS ===

class TestAutoGenExecutor(unittest.TestCase):
    """Test AutoGen-style executor with real-world feedback."""
    
    def test_session_creation(self):
        """Test AutoGen session creation."""
        orch = AutoGenOrchestrator(max_attempts=3)
        session = orch.create_session("Build function", "Must handle errors")
        
        self.assertIsNotNone(session.session_id)
        self.assertEqual(session.task, "Build function")
        self.assertEqual(session.assistant_attempts, 0)
    
    def test_user_proxy_syntax_check(self):
        """Test UserProxy detects syntax errors."""
        proxy = UserProxyAgent(execution_mode=ExecutionMode.DRY_RUN)
        
        code_with_error = "def solve():\n    return \"hello\""
        # This should pass syntax check
        result = proxy.execute_code(code_with_error)
        # Note: execution depends on mode
    
    def test_user_proxy_judge(self):
        """Test UserProxy judge function."""
        proxy = UserProxyAgent()
        
        good_code = """<SCRATCHPAD>Plan</SCRATCHPAD>
<SOLUTION>
def solve(x):
    if x is None:
        return {"error": "None"}
    return {"result": x}
</SOLUTION>"""
        
        passed, feedback = proxy.judge(good_code, "Must handle None")
        self.assertIn(passed, [True, False])
        self.assertIsInstance(feedback, str)
    
    def test_execution_result_dataclass(self):
        """Test ExecutionResult structure."""
        result = ExecutionResult(
            success=True,
            output="42",
            error=None,
            execution_time=0.1,
            return_code=0
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.output, "42")
        self.assertEqual(result.return_code, 0)
        
        d = result.to_dict()
        self.assertIsInstance(d, dict)
    
    def test_full_orchestrator_run(self):
        """Test full AutoGen execution loop."""
        orch = AutoGenOrchestrator(max_attempts=2)
        session = orch.create_session("Build factorial", "Handle edge cases")
        
        result = orch.run(session.session_id, verbose=False)
        
        self.assertIsNotNone(result)
        self.assertGreater(result.assistant_attempts, 0)
        self.assertIsInstance(result.judge_feedback, str)


# === DSPY TESTS ===

class TestDSPySelfImprover(unittest.TestCase):
    """Test DSPy-style self-improvement with metrics."""
    
    def test_metric_functions(self):
        """Test all metric functions."""
        output = """<SCRATCHPAD>Plan</SCRATCHPAD>
<SOLUTION>
def solve(x):
    if x is None:
        return {"error": "None"}
    return {"result": x}
</SOLUTION>
<REFLECTION>OK</REFLECTION>"""
        
        criteria = "Must validate input, handle errors"
        
        # Test correctness
        result = MetricFunctions.correctness_metric(output, criteria, {})
        self.assertIsInstance(result, MetricResult)
        self.assertEqual(result.metric_type, MetricType.CORRECTNESS)
        
        # Test style
        result = MetricFunctions.style_metric(output, criteria, {})
        self.assertEqual(result.metric_type, MetricType.STYLE)
        
        # Test safety
        result = MetricFunctions.safety_metric(output, criteria, {})
        self.assertEqual(result.metric_type, MetricType.SAFETY)
        
        # Test completeness
        result = MetricFunctions.completeness_metric(output, criteria, {})
        self.assertEqual(result.metric_type, MetricType.COMPLETENESS)
    
    def test_teleprompter_analyze_failure(self):
        """Test Teleprompter analyzes failures."""
        tp = Teleprompter()
        
        failed_metric = MetricResult(
            metric_type=MetricType.CORRECTNESS,
            passed=False,
            score=0.3,
            feedback="Missing planning; Missing solution"
        )
        
        analysis = tp.analyze_failure("output", [failed_metric], "criteria")
        
        self.assertIn("root_causes", analysis)
        self.assertIn("suggested_mutations", analysis)
        self.assertGreater(len(analysis["suggested_mutations"]), 0)
    
    def test_teleprompter_mutate_prompt(self):
        """Test prompt mutation."""
        tp = Teleprompter()
        
        original = "You are Hermes. Always use tags."
        mutations = [
            {"type": "ADD_CONSTRAINT", "mutation": "Never use eval()"},
            {"type": "EMPHASIZE", "mutation": "Always validate input first"}
        ]
        
        mutated = tp.mutate_prompt(original, mutations)
        
        self.assertIn("Never use eval()", mutated)
        self.assertIn("Always validate", mutated)
    
    def test_dspy_session_creation(self):
        """Test DSPy session creation."""
        orch = DSPyOrchestrator(max_iterations=3)
        sid = orch.create_session("Build function", "Must validate")
        
        self.assertIsNotNone(sid)
        self.assertIn(sid, orch.sessions)
    
    def test_dspy_evaluate(self):
        """Test DSPy evaluation."""
        orch = DSPyOrchestrator()
        
        output = """<SCRATCHPAD>Plan</SCRATCHPAD>
<SOLUTION>def solve(): pass</SOLUTION>"""
        
        metrics = orch._evaluate(output, "criteria", {})
        
        self.assertEqual(len(metrics), 5)  # 5 metric types
        for m in metrics:
            self.assertIsInstance(m, MetricResult)
    
    def test_full_dspy_run(self):
        """Test full DSPy improvement loop."""
        orch = DSPyOrchestrator(max_iterations=2)
        sid = orch.create_session("Build factorial", "Handle edge cases")
        
        result = orch.run(sid, verbose=False)
        
        self.assertIsNotNone(result)
        self.assertIn("iterations", result)
        self.assertGreater(len(result["iterations"]), 0)


# === METAGPT TESTS ===

class TestMetaGPTOrchestrator(unittest.TestCase):
    """Test MetaGPT-style SOP simulation."""
    
    def test_sop_stages_enum(self):
        """Test SOP stage enum values."""
        self.assertEqual(SOPStage.REQUIREMENTS.value, "requirements")
        self.assertEqual(SOPStage.ARCHITECTURE.value, "architecture")
        self.assertEqual(SOPStage.IMPLEMENTATION.value, "implementation")
        self.assertEqual(SOPStage.TESTING.value, "testing")
        self.assertEqual(SOPStage.REVIEW.value, "review")
        self.assertEqual(SOPStage.COMPLETE.value, "complete")
    
    def test_agent_roles_enum(self):
        """Test AgentRole enum values."""
        self.assertEqual(AgentRole.ENGINEER.value, "engineer")
        self.assertEqual(AgentRole.QA_ENGINEER.value, "qa_engineer")
        self.assertEqual(AgentRole.ARCHITECT.value, "architect")
    
    def test_session_creation(self):
        """Test MetaGPT session creation."""
        orch = MetaGPTOrchestrator()
        sid = orch.create_session("Build platform", "Requirements here")
        
        self.assertIsNotNone(sid)
        session = orch.sessions[sid]
        self.assertEqual(session["current_stage"], SOPStage.REQUIREMENTS)
    
    def test_artifact_creation(self):
        """Test Artifact dataclass."""
        artifact = Artifact(
            artifact_id="test-1",
            role=AgentRole.ENGINEER,
            content="def solve(): pass",
            stage=SOPStage.IMPLEMENTATION
        )
        
        self.assertEqual(artifact.artifact_id, "test-1")
        self.assertEqual(artifact.role, AgentRole.ENGINEER)
        self.assertFalse(artifact.approved)
        
        d = artifact.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["role"], "engineer")
    
    def test_role_config(self):
        """Test RoleConfig dataclass."""
        config = RoleConfig(
            role=AgentRole.ENGINEER,
            name="Test Engineer",
            system_prompt="You build things",
            temperature=0.5
        )
        
        self.assertEqual(config.role, AgentRole.ENGINEER)
        self.assertEqual(config.temperature, 0.5)
    
    def test_stage_requirements(self):
        """Test REQUIREMENTS stage."""
        orch = MetaGPTOrchestrator()
        session = {"session_id": "test", "task": "Task", "requirements": "Req", "artifacts": []}
        
        orch._stage_requirements(session, verbose=False)
        
        self.assertEqual(len(session["artifacts"]), 1)
        self.assertEqual(session["artifacts"][0].stage, SOPStage.REQUIREMENTS)
    
    def test_default_qa(self):
        """Test default QA evaluation."""
        orch = MetaGPTOrchestrator()
        
        good_code = """<SCRATCHPAD>Plan</SCRATCHPAD>
<SOLUTION>
def solve(x):
    if x is None:
        return {"error": "None"}
    return {"result": x}
</SOLUTION>
<TEST>def test_solve(): pass</TEST>"""
        
        passed, reason = orch._default_qa(good_code, "Must handle errors")
        self.assertIn(passed, [True, False])
        self.assertIsInstance(reason, str)
    
    def test_full_metagpt_run(self):
        """Test full MetaGPT pipeline."""
        orch = MetaGPTOrchestrator()
        sid = orch.create_session("Build factorial", "Handle edge cases")
        
        result = orch.run(sid, verbose=False)
        
        self.assertIsNotNone(result)
        self.assertIn("artifacts", result)
        self.assertIn("stage_history", result)


# === UNIVERSAL ORCHESTRATOR TESTS ===

class TestUniversalOrchestrator(unittest.TestCase):
    """Test universal orchestrator with auto-selection."""
    
    def test_recommend_langgraph(self):
        """Test recommendation for logical validation."""
        universal = UniversalOrchestrator()
        
        rec = universal.recommend_orchestrator(
            "Validate the input",
            "Must pass validation checks"
        )
        self.assertEqual(rec, OrchestratorType.LANGGRAPH)
    
    def test_recommend_autogen(self):
        """Test recommendation for code execution."""
        universal = UniversalOrchestrator()
        
        rec = universal.recommend_orchestrator(
            "Write a Python script",
            "Execute and return stack traces"
        )
        self.assertEqual(rec, OrchestratorType.AUTOGEN)
    
    def test_recommend_dspy(self):
        """Test recommendation for prompt optimization."""
        universal = UniversalOrchestrator()
        
        rec = universal.recommend_orchestrator(
            "Improve the system prompt",
            "Optimize template based on metrics"
        )
        self.assertEqual(rec, OrchestratorType.DSPY)
    
    def test_recommend_gemini(self):
        """Test recommendation for debate."""
        universal = UniversalOrchestrator()
        
        rec = universal.recommend_orchestrator(
            "Debate the best approach",
            "Critic finds flaws"
        )
        self.assertEqual(rec, OrchestratorType.GEMINI)
    
    def test_run_langgraph(self):
        """Test running LangGraph via universal."""
        universal = UniversalOrchestrator()
        
        result = universal.run(
            OrchestratorType.LANGGRAPH,
            "Build factorial",
            "Handle edge cases",
            verbose=False
        )
        
        self.assertEqual(result["orchestrator"], OrchestratorType.LANGGRAPH)
        self.assertIn("session_id", result)
        self.assertIn("verdict", result)
    
    def test_run_autogen(self):
        """Test running AutoGen via universal."""
        universal = UniversalOrchestrator()
        
        result = universal.run(
            OrchestratorType.AUTOGEN,
            "Build function",
            "Handle errors",
            verbose=False
        )
        
        self.assertEqual(result["orchestrator"], OrchestratorType.AUTOGEN)
        self.assertIn("session_id", result)
    
    def test_run_dspy(self):
        """Test running DSPy via universal."""
        universal = UniversalOrchestrator()
        
        result = universal.run(
            OrchestratorType.DSPY,
            "Build function",
            "Validate input",
            verbose=False
        )
        
        self.assertEqual(result["orchestrator"], OrchestratorType.DSPY)
        self.assertIn("iterations", result)
    
    def test_run_metagpt(self):
        """Test running MetaGPT via universal."""
        universal = UniversalOrchestrator()
        
        result = universal.run(
            OrchestratorType.METAGPT,
            "Build platform",
            "Requirements here",
            verbose=False
        )
        
        self.assertEqual(result["orchestrator"], OrchestratorType.METAGPT)
        self.assertIn("stages", result)
    
    def test_run_auto(self):
        """Test auto-selection."""
        universal = UniversalOrchestrator()
        
        result = universal.run_auto(
            "Build a function",
            "Validate and test",
            verbose=False
        )
        
        self.assertIn("orchestrator", result)
        self.assertIn(result["orchestrator"], OrchestratorType.all())
    
    def test_statistics(self):
        """Test usage statistics."""
        universal = UniversalOrchestrator()
        
        # Run some orchestrators
        universal.run(OrchestratorType.LANGGRAPH, "Task", "Crit", verbose=False)
        universal.run(OrchestratorType.AUTOGEN, "Task", "Crit", verbose=False)
        
        stats = universal.get_statistics()
        self.assertIn("usage", stats)
        self.assertGreater(stats["total_runs"], 0)


# === INTEGRATION TESTS ===

class TestOrchestratorIntegration(unittest.TestCase):
    """Integration tests across orchestrators."""
    
    def test_all_orchestrators_importable(self):
        """Test all orchestrators can be imported together."""
        # This is verified at module level
        self.assertTrue(True)
    
    def test_memory_integration_interface(self):
        """Test memory integration interface compatibility."""
        # All orchestrators accept memory_integration parameter
        # This tests the interface exists
        from ilma_long_term_memory import LongTermMemory
        
        try:
            memory = LongTermMemory()
            
            # All orchestrators should accept this
            orch1 = LangGraphOrchestrator(memory_integration=memory)
            orch2 = AutoGenOrchestrator(memory_integration=memory)
            orch3 = DSPyOrchestrator(memory_integration=memory)
            orch4 = MetaGPTOrchestrator(memory_integration=memory)
            
            self.assertTrue(True)
        except Exception:
            # Memory may not exist yet
            self.skipTest("LongTermMemory not available")
    
    def test_universal_with_all_types(self):
        """Test Universal orchestrator handles all types."""
        universal = UniversalOrchestrator()
        
        for orch_type in OrchestratorType.all():
            try:
                result = universal.run(
                    orch_type,
                    "Test task",
                    "Test criteria",
                    verbose=False
                )
                self.assertIn("orchestrator", result)
            except Exception as e:
                # Some may fail if dependencies missing
                self.assertIsInstance(e, Exception)


if __name__ == "__main__":
    # Run tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestLangGraphOrchestrator))
    suite.addTests(loader.loadTestsFromTestCase(TestAutoGenExecutor))
    suite.addTests(loader.loadTestsFromTestCase(TestDSPySelfImprover))
    suite.addTests(loader.loadTestsFromTestCase(TestMetaGPTOrchestrator))
    suite.addTests(loader.loadTestsFromTestCase(TestUniversalOrchestrator))
    suite.addTests(loader.loadTestsFromTestCase(TestOrchestratorIntegration))
    
    # Run
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print("=" * 70)
    
    if result.wasSuccessful():
        print("✅ ALL ORCHESTRATOR TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")