#!/usr/bin/env python3
"""Tests for ILMA Judge System"""
import unittest
import tempfile
import os
from pathlib import Path

# Add scripts to path
import sys
sys.path.insert(0, 'scripts')

from ilma_judge_system import JudgeEngine, Grade, Verdict, EvaluationResult, Checkpoint


class TestJudgeEngine(unittest.TestCase):
    """Test Judge Engine core functionality."""
    
    @classmethod
    def setUpClass(cls):
        """Create test fixtures."""
        cls.judge = JudgeEngine()
        
        # Create a simple valid Python file
        cls.valid_file = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False)
        cls.valid_file.write('''
"""Valid test file."""
import logging
from typing import Optional

def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

def process(data: str) -> Optional[str]:
    """Process data."""
    try:
        return data.upper()
    except Exception as e:
        logging.error(f"Error: {e}")
        return None
''')
        cls.valid_file.close()
        
        # Create a file with syntax error
        cls.bad_file = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False)
        cls.bad_file.write('def broken(\n    syntax error here')
        cls.bad_file.close()
        
        # Create a file with shell=True
        cls.shell_file = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False)
        cls.shell_file.write('''
import subprocess
def run_cmd(cmd):
    return subprocess.run(cmd, shell=True)
''')
        cls.shell_file.close()
    
    @classmethod
    def tearDownClass(cls):
        """Cleanup temp files."""
        for f in [cls.valid_file.name, cls.bad_file.name, cls.shell_file.name]:
            try: os.unlink(f)
            except OSError: pass
    
    def test_grade_from_score(self):
        """Test grade conversion."""
        self.assertEqual(Grade.from_score(100), Grade.S_PLUS_PLUS)
        self.assertEqual(Grade.from_score(95), Grade.S_PLUS)
        self.assertEqual(Grade.from_score(92), Grade.S_PLUS)
        self.assertEqual(Grade.from_score(88), Grade.S)
        self.assertEqual(Grade.from_score(85), Grade.S)
        self.assertEqual(Grade.from_score(78), Grade.A_PLUS)
        self.assertEqual(Grade.from_score(70), Grade.A)
        self.assertEqual(Grade.from_score(62), Grade.B_PLUS)
        self.assertEqual(Grade.from_score(55), Grade.B)
        self.assertEqual(Grade.from_score(45), Grade.C)
        self.assertEqual(Grade.from_score(20), Grade.F)
    
    def test_grade_production_ready(self):
        """Test production ready check."""
        self.assertTrue(Grade.S_PLUS_PLUS.is_production_ready())
        self.assertTrue(Grade.S_PLUS.is_production_ready())
        self.assertTrue(Grade.A_PLUS.is_production_ready())
        self.assertFalse(Grade.C.is_production_ready())
        self.assertFalse(Grade.F.is_production_ready())
    
    def test_evaluate_valid_file(self):
        """Judge a valid Python file."""
        result = self.judge.evaluate(
            solution_path=self.valid_file.name,
            task="Simple arithmetic",
            custom_checkpoints=["L1_syntax", "L1_import"]
        )
        self.assertGreater(result.raw_score, 50)
        self.assertIn(result.grade, [Grade.S_PLUS_PLUS, Grade.S_PLUS, Grade.S, Grade.A_PLUS])
    
    def test_evaluate_invalid_syntax(self):
        """Judge a file with syntax error."""
        result = self.judge.evaluate(
            solution_path=self.bad_file.name,
            task="Should fail syntax",
            custom_checkpoints=["L1_syntax"]
        )
        failed_cps = [cp for cp in result.checkpoints if cp.status == "failed"]
        self.assertGreater(len(failed_cps), 0)
    
    def test_shell_injection_detection(self):
        """Detect shell=True."""
        result = self.judge.evaluate(
            solution_path=self.shell_file.name,
            task="Detect shell injection",
            custom_checkpoints=["L3_shell_injection"]
        )
        failed_cps = [cp for cp in result.checkpoints if cp.status == "failed"]
        self.assertGreater(len(failed_cps), 0)
    
    def test_checkpoint_pass(self):
        """Test checkpoint pass/fail."""
        cp = Checkpoint(id="test", name="Test", description="test", criteria="test")
        cp.pass_checkpoint("OK", {"score": 100})
        self.assertEqual(cp.status, "passed")
        self.assertIsNotNone(cp.checked_at)
    
    def test_checkpoint_fail(self):
        """Test checkpoint fail."""
        cp = Checkpoint(id="test", name="Test", description="test", criteria="test")
        cp.fail_checkpoint("Failed", {"error": "bad"})
        self.assertEqual(cp.status, "failed")
    
    def test_evaluation_result_score(self):
        """Test score calculation."""
        result = EvaluationResult(
            id="test",
            task="test",
            solution_path="/tmp/test.py",
            submitted_at=__import__('datetime').datetime.now()
        )
        cp1 = Checkpoint(id="cp1", name="CP1", description="c", criteria="c", weight=1.0, required=True)
        cp1.pass_checkpoint("OK", {})
        cp2 = Checkpoint(id="cp2", name="CP2", description="c", criteria="c", weight=1.0, required=True)
        cp2.fail_checkpoint("FAIL", {})
        result.add_checkpoint(cp1)
        result.add_checkpoint(cp2)
        
        score = result.calculate_score()
        self.assertEqual(score, 50.0)


if __name__ == "__main__":
    unittest.main()
