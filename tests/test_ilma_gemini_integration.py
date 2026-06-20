#!/usr/bin/env python3
"""
Test suite for ILMA Gemini Integration modules.
Run with: python3 tests/test_ilma_gemini_integration.py
"""

import sys
import unittest
from pathlib import Path

# Add ILMA to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestActorCriticCore(unittest.TestCase):
    """Test Actor-Critic Core module."""
    
    def test_import(self):
        from ilma_actor_critic_core import ActorCriticCore, AgentRole, VerdictLevel
        self.assertIsNotNone(ActorCriticCore)
    
    def test_create_session(self):
        from ilma_actor_critic_core import ActorCriticCore
        core = ActorCriticCore(max_rounds=2)
        session = core.create_session("Task", "Criteria")
        self.assertIsNotNone(session.session_id)
        self.assertEqual(session.task, "Task")
    
    def test_run_debate(self):
        from ilma_actor_critic_core import ActorCriticCore
        core = ActorCriticCore(max_rounds=2, judge_threshold=4.0)
        session = core.run_debate("Build API", "Must validate", verbose=False)
        self.assertIsNotNone(session.session_id)
        self.assertGreaterEqual(len(session.rounds), 1)


class TestReflexionLoop(unittest.TestCase):
    """Test Reflexion Loop module."""
    
    def test_import(self):
        from fabric_archive.ilma_reflexion_loop import ReflexionLoop, ReflexionStatus
        self.assertIsNotNone(ReflexionLoop)
    
    def test_create_session(self):
        from fabric_archive.ilma_reflexion_loop import ReflexionLoop
        reflexion = ReflexionLoop(max_revisions=2)
        session = reflexion.create_session("Task", "Criteria")
        self.assertIsNotNone(session.session_id)
    
    def test_run_full_reflexion(self):
        from fabric_archive.ilma_reflexion_loop import ReflexionLoop
        reflexion = ReflexionLoop(max_revisions=2, judge_threshold=4.0)
        session = reflexion.run_full_reflexion("Build endpoint", "Must handle errors", verbose=False)
        self.assertIsNotNone(session.session_id)
        self.assertGreaterEqual(session.current_round, 1)


class TestMAETriplet(unittest.TestCase):
    """Test MAE Triplet module."""
    
    def test_import(self):
        from fabric_archive.ilma_mae_triplet import MAETriplet, MAEAgentRole
        self.assertIsNotNone(MAETriplet)
    
    def test_create_session(self):
        from fabric_archive.ilma_mae_triplet import MAETriplet
        mae = MAETriplet(max_cycles=2)
        session = mae.create_session("Build auth system")
        self.assertIsNotNone(session.session_id)
    
    def test_run_full_evolution(self):
        from fabric_archive.ilma_mae_triplet import MAETriplet
        mae = MAETriplet(max_cycles=2, difficulty_threshold=0.5)
        session = mae.run_full_evolution("Build auth system", verbose=False)
        self.assertIsNotNone(session.session_id)


class TestTrajectoryEvolution(unittest.TestCase):
    """Test Trajectory Evolution module."""
    # ilma_trajectory_evolution not available - module was never created
    @unittest.skip("Module ilma_trajectory_evolution not available")
    def test_import(self):
        from ilma_trajectory_evolution import TrajectoryEvolution, EvolutionType
        self.assertIsNotNone(TrajectoryEvolution)
    
    @unittest.skip("Module ilma_trajectory_evolution not available")
    def test_create_trajectory(self):
        from ilma_trajectory_evolution import TrajectoryEvolution
        engine = TrajectoryEvolution()
        traj = engine.create_trajectory("Build API", [
            {"action": "Step 1", "reasoning": "Because...", "is_failure": False},
        ])
        self.assertIsNotNone(traj.trajectory_id)
        self.assertEqual(len(traj.steps), 1)
    
    @unittest.skip("Module ilma_trajectory_evolution not available")
    def test_revise(self):
        from ilma_trajectory_evolution import TrajectoryEvolution
        engine = TrajectoryEvolution()
        traj = engine.create_trajectory("Build API", [
            {"action": "Step 1", "reasoning": "OK", "is_failure": False},
            {"action": "Step 2", "reasoning": "Failed", "is_failure": True, "failure_reason": "ERROR"},
        ])
        result = engine.revise(traj.trajectory_id, 1)
        self.assertIsNotNone(result.evolved_trajectory)
        self.assertEqual(result.evolution_type.value, "revision")
    
    @unittest.skip("Module ilma_trajectory_evolution not available")
    def test_refine(self):
        from ilma_trajectory_evolution import TrajectoryEvolution
        engine = TrajectoryEvolution()
        traj = engine.create_trajectory("Build API", [
            {"action": "Step 1", "reasoning": "OK", "is_failure": False},
            {"action": "Step 1", "reasoning": "Duplicate", "is_failure": False},
        ])
        result = engine.refine(traj.trajectory_id)
        self.assertLessEqual(len(result.evolved_trajectory.steps), len(traj.steps))


class TestRCRPattern(unittest.TestCase):
    """Test RCR Pattern module."""
    
    def test_import(self):
        from fabric_archive.ilma_rcr_pattern import RCRPattern, RCRSession
        self.assertIsNotNone(RCRPattern)
    
    def test_create_session(self):
        from fabric_archive.ilma_rcr_pattern import RCRPattern
        rcr = RCRPattern(max_turns=3)
        session = rcr.create_session("Task", "Target")
        self.assertIsNotNone(session.session_id)
    
    def test_run_full_debate(self):
        from fabric_archive.ilma_rcr_pattern import RCRPattern
        rcr = RCRPattern(max_turns=3)
        session = rcr.run_full_debate("Build function", "Must handle nulls", verbose=False)
        self.assertIsNotNone(session.session_id)
        self.assertGreaterEqual(session.current_turn, 1)


class TestLongTermMemory(unittest.TestCase):
    """Test Long-Term Memory module."""
    # ilma_long_term_memory not available - module was never created
    @unittest.skip("Module ilma_long_term_memory not available")
    def test_import(self):
        from ilma_long_term_memory import LongTermMemory, Lesson
        self.assertIsNotNone(LongTermMemory)

    @unittest.skip("Module ilma_long_term_memory not available")
    def test_extract_lesson(self):
        from ilma_long_term_memory import LongTermMemory
        memory = LongTermMemory()  # Uses temp path
        lesson = memory.extract_lesson(
            category="test",
            task_pattern="API task",
            problem="Problem description",
            solution="Solution applied",
            success=True
        )
        self.assertIsNotNone(lesson.lesson_id)
        self.assertEqual(lesson.category, "test")

    @unittest.skip("Module ilma_long_term_memory not available")
    def test_retrieve(self):
        from ilma_long_term_memory import LongTermMemory
        memory = LongTermMemory()
        memory.extract_lesson("test", "API validation", "Problem", "Solution", success=True)
        result = memory.retrieve("API validation")
        self.assertGreaterEqual(result.total_count, 1)

    @unittest.skip("Module ilma_long_term_memory not available")
    def test_statistics(self):
        from ilma_long_term_memory import LongTermMemory
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            memory = LongTermMemory(Path(tmpdir) / "test_mem")
            memory.extract_lesson("test", "task1", "p1", "s1", success=True)
            memory.extract_lesson("test", "task2", "p2", "s2", success=True)
            stats = memory.get_statistics()
            self.assertEqual(stats["total_lessons"], 2)


class TestGeminiIntegration(unittest.TestCase):
    """Test unified Gemini Integration Core."""
    # ilma_gemini_integration not available - module was never created
    @unittest.skip("Module ilma_gemini_integration not available")
    def test_import(self):
        from ilma_gemini_integration import GeminiIntegrationCore
        self.assertIsNotNone(GeminiIntegrationCore)

    @unittest.skip("Module ilma_gemini_integration not available")
    def test_all_components_initialized(self):
        from ilma_gemini_integration import GeminiIntegrationCore
        core = GeminiIntegrationCore()
        self.assertIsNotNone(core.actor_critic)
        self.assertIsNotNone(core.reflexion)
        self.assertIsNotNone(core.mae)
        self.assertIsNotNone(core.trajectory)
        self.assertIsNotNone(core.rcr)
        self.assertIsNotNone(core.memory)

    @unittest.skip("Module ilma_gemini_integration not available")
    def test_run_all_patterns(self):
        from ilma_gemini_integration import GeminiIntegrationCore
        core = GeminiIntegrationCore(
            max_actor_critic_rounds=1,
            max_reflexion_revisions=1,
            max_mae_cycles=1,
            max_rcr_turns=1
        )
        
        # Actor-Critic
        ac = core.run_actor_critic("Task", "Criteria", verbose=False)
        self.assertIsNotNone(ac)
        
        # Reflexion
        rx = core.run_reflexion("Task", "Criteria", verbose=False)
        self.assertIsNotNone(rx)
        
        # MAE
        mae = core.run_mae("Goal", max_cycles=1, verbose=False)
        self.assertIsNotNone(mae)
        
        # RCR
        rcr = core.run_rcr_debate("Task", "Target", verbose=False)
        self.assertIsNotNone(rcr)
    
    @unittest.skip("Module ilma_gemini_integration not available")
    def test_memory_integration(self):
        from ilma_gemini_integration import GeminiIntegrationCore
        core = GeminiIntegrationCore()
        
        # Store and retrieve
        lesson = core.store_lesson("test", "task", "problem", "solution", success=True)
        result = core.retrieve_lessons("task")
        
        self.assertIsNotNone(lesson)
        self.assertGreaterEqual(result.total_count, 1)
    
    @unittest.skip("Module ilma_gemini_integration not available")
    def test_statistics(self):
        from ilma_gemini_integration import GeminiIntegrationCore
        core = GeminiIntegrationCore(
            max_actor_critic_rounds=1,
            max_reflexion_revisions=1,
            max_rcr_turns=1
        )
        core.run_actor_critic("Task", "Criteria", verbose=False)
        core.run_reflexion("Task", "Criteria", verbose=False)
        core.run_rcr_debate("Task", "Target", verbose=False)
        core.store_lesson("test", "task", "p", "s", success=True)
        
        stats = core.get_all_statistics()
        self.assertIn("version", stats)
        self.assertGreater(stats["memory"]["total_lessons"], 0)


class TestPartnerWrappers(unittest.TestCase):
    """Test partner agent wrappers."""
    
    def test_import(self):
        from ilma_partner_wrappers import PrometheusJudgeWrapper, DeepSeekCriticWrapper
        self.assertIsNotNone(PrometheusJudgeWrapper)
        self.assertIsNotNone(DeepSeekCriticWrapper)
    
    def test_prometheus_evaluate(self):
        from ilma_partner_wrappers import PrometheusJudgeWrapper
        judge = PrometheusJudgeWrapper()
        score, feedback = judge.evaluate("<SOLUTION>def f(): pass</SOLUTION>", "Basic function")
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 1.0)
        self.assertLessEqual(score, 5.0)
        self.assertIsInstance(feedback, str)
    
    def test_deepseek_critique(self):
        from ilma_partner_wrappers import DeepSeekCriticWrapper
        critic = DeepSeekCriticWrapper()
        flaws, feedback = critic.critique("<SOLUTION>def f(): pass</SOLUTION>", "Build function")
        self.assertIsInstance(flaws, list)
        self.assertIsInstance(feedback, str)
    
    def test_statistics(self):
        from ilma_partner_wrappers import PrometheusJudgeWrapper, DeepSeekCriticWrapper
        judge = PrometheusJudgeWrapper()
        critic = DeepSeekCriticWrapper()
        
        judge.evaluate("<SOLUTION>test</SOLUTION>", "criteria")
        critic.critique("<SOLUTION>test</SOLUTION>", "task")
        
        self.assertEqual(judge.get_statistics()["eval_count"], 1)
        self.assertEqual(critic.get_statistics()["critique_count"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)