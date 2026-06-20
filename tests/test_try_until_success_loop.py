#!/usr/bin/env python3
"""
ILMA Try-Until-Success Loop Test Suite
======================================
Tests the reflexion loop's ability to recover from initial failures.

Test Cases (10 total):
1. wrong import path
2. missing evidence ID
3. poor route selection
4. duplicate lesson retrieval
5. failing test
6. inconsistent doc claim
7. stale registry status
8. performance bottleneck
9. missing output artifact
10. ambiguous user objective

For each test:
- First attempt MUST fail (inject the problem)
- Judge must reject
- Reflexion must create repair plan
- Second or later attempt must pass
- Trace must show attempts
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from typing import Tuple, List, Dict, Any
import json

# ILMA paths
ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
WORKSPACE = ILMA_PROFILE
sys.path.insert(0, str(WORKSPACE))

from fabric_archive.ilma_reflexion_loop import (
    ReflexionLoop, ReflexionSession, ReflexionPoint,
    ReflexionStatus, ErrorType
)


# === TEST HELPERS ===

def create_judge_callback(test_name: str, pass_on_retry: bool = True):
    """
    Create a judge callback that fails on first attempt but passes on retry.
    
    Args:
        test_name: Name of the test case
        pass_on_retry: If True, passes on retry; if False, stays fail
    """
    attempt_count = {"count": 0}
    
    def judge(task: str, output: str, criteria: str) -> Tuple[float, str, List[str]]:
        attempt_count["count"] += 1
        attempt = attempt_count["count"]
        
        # First attempt ALWAYS fails
        if attempt == 1:
            # Specific failure modes per test case
            if test_name == "wrong_import_path":
                return 1.5, "JUDGE: ImportError - module not found", ["IMPORT_ERROR", "STRUCTURE_ERROR"]
            elif test_name == "missing_evidence_id":
                return 2.0, "JUDGE: Evidence ID not found in ledger", ["MISSING_EVIDENCE", "INCOMPLETE_OUTPUT"]
            elif test_name == "poor_route_selection":
                return 1.0, "JUDGE: Wrong model selected for task", ["WRONG_APPROACH", "ROUTE_ERROR"]
            elif test_name == "duplicate_lesson_retrieval":
                return 1.5, "JUDGE: Duplicate lesson returned", ["DUPLICATE_LESSON", "LOGICAL_FLAW"]
            elif test_name == "failing_test":
                return 1.0, "JUDGE: Test FAILED - assertion error", ["TEST_FAILED", "ASSERTION_ERROR"]
            elif test_name == "inconsistent_doc_claim":
                return 1.5, "JUDGE: Document claims differ from actual", ["INCONSISTENT_DOC", "HALUCINATION"]
            elif test_name == "stale_registry_status":
                return 1.5, "JUDGE: Registry shows old status", ["STALE_STATUS", "MISSING_HANDLING"]
            elif test_name == "performance_bottleneck":
                return 1.0, "JUDGE: Execution timeout exceeded", ["PERFORMANCE_ISSUE", "TIMEOUT"]
            elif test_name == "missing_output_artifact":
                return 1.5, "JUDGE: Expected artifact not produced", ["MISSING_ARTIFACT", "INCOMPLETE_OUTPUT"]
            elif test_name == "ambiguous_user_objective":
                return 1.0, "JUDGE: Cannot determine user intent", ["AMBIGUOUS_OBJECTIVE", "MISSING_HANDLING"]
            else:
                return 1.5, f"JUDGE: Test {test_name} failed", ["GENERIC_ERROR"]
        
        # Subsequent attempts
        if pass_on_retry:
            return 4.5, f"JUDGE: Test {test_name} PASSED after fix", []
        else:
            return 1.5, f"JUDGE: Test {test_name} still failing", ["STILL_FAILING"]
    
    return judge


def create_actor_callback(test_name: str):
    """
    Create an actor callback that:
    - First attempt: produces faulty output
    - Subsequent: produces corrected output
    """
    attempt_count = {"count": 0}
    
    def actor(task: str, context: Dict) -> str:
        attempt_count["count"] += 1
        attempt = attempt_count["count"]
        
        if attempt == 1:
            # First attempt - produce faulty output
            if test_name == "wrong_import_path":
                return """<SCRATCHPAD>
Attempting to import modules...
</SCRATCHPAD>
<SOLUTION>
import nonexistent_module  # Wrong import path
from missing.package import something
</SOLUTION>"""
            elif test_name == "missing_evidence_id":
                return """<SCRATCHPAD>
Checking evidence ledger...
</SCRATCHPAD>
<SOLUTION>
Evidence ID: E9999 not found in ledger
Using placeholder: NULL
</SOLUTION>"""
            elif test_name == "poor_route_selection":
                return """<SCRATCHPAD>
Selecting model for task...
</SCRATCHPAD>
<SOLUTION>
Model selected: gpt-3.5-turbo (wrong for coding task)
Should use: deepseek-coder-v2
</SOLUTION>"""
            elif test_name == "duplicate_lesson_retrieval":
                return """<SCRATCHPAD>
Retrieving lessons...
</SCRATCHPAD>
<SOLUTION>
Lessons: [Lesson(id=1), Lesson(id=1), Lesson(id=1)]
Found 3 duplicates!
</SOLUTION>"""
            elif test_name == "failing_test":
                return """<SCRATCHPAD>
Running tests...
</SCRATCHPAD>
<SOLUTION>
def test_add():
    assert 1 + 1 == 3  # Wrong assertion
</SOLUTION>"""
            elif test_name == "inconsistent_doc_claim":
                return """<SCRATCHPAD>
Reviewing documentation...
</SCRATCHPAD>
<SOLUTION>
Doc claims: "System supports 10,000 TPS"
Actual: System supports 1,000 TPS
INCONSISTENT!
</SOLUTION>"""
            elif test_name == "stale_registry_status":
                return """<SCRATCHPAD>
Checking registry...
</SCRATCHPAD>
<SOLUTION>
Capability 'test_cap' status: ACTIVE (stale - actually DEPRECATED)
Last update: 2026-01-01
</SOLUTION>"""
            elif test_name == "performance_bottleneck":
                return """<SCRATCHPAD>
Executing query...
</SCRATCHPAD>
<SOLUTION>
Query took: 30 seconds
Bottleneck: O(n^3) algorithm detected
Need optimization.
</SOLUTION>"""
            elif test_name == "missing_output_artifact":
                return """<SCRATCHPAD>
Producing output...
</SCRATCHPAD>
<SOLUTION>
Expected file: output.json
Status: NOT_FOUND
</SOLUTION>"""
            elif test_name == "ambiguous_user_objective":
                return """<SCRATCHPAD>
Interpreting request...
</SCRATCHPAD>
<SOLUTION>
User said: "make it better"
Cannot determine specific objective.
Need clarification.
</SOLUTION>"""
            else:
                return "<SOLUTION>First attempt - faulty</SOLUTION>"
        
        # Second attempt - produce fixed output
        else:
            return f"""<SCRATCHPAD>
REVISION: Incorporating judge feedback for {test_name}
</SCRATCHPAD>
<SOLUTION>
FIXED: The issue has been resolved.
- Used correct approach
- All criteria met
- Test would pass now
</SOLUTION>
<REFLECTION>
Successfully addressed the feedback from previous attempt.
The solution now satisfies all target criteria.
</REFLECTION>"""
    
    return actor


# Module-level results storage (survives across test methods)
TEST_RESULTS = []

# === TEST CLASSES ===

class TestTryUntilSuccessLoop(unittest.TestCase):
    """Test the try-until-success reflexion loop."""
    
    def setUp(self):
        """Set up test fixtures."""
        pass
    
    def run_test_case(self, test_name: str, description: str, pass_on_retry: bool = True) -> Dict:
        """
        Run a single test case through the reflexion loop.
        
        Returns:
            Dict with test results including:
            - first_attempt_failed: bool
            - judge_rejected: bool
            - reflexion_generated_plan: bool
            - subsequent_attempt_passed: bool
            - attempts_count: int
        """
        print(f"\n{'='*60}")
        print(f"TEST: {test_name}")
        print(f"Description: {description}")
        print('='*60)
        
        # Create reflexion loop with mock callbacks
        reflexion = ReflexionLoop(
            actor_callback=create_actor_callback(test_name),
            judge_callback=create_judge_callback(test_name, pass_on_retry),
            max_revisions=3,
            judge_threshold=4.0
        )
        
        # Run full reflexion
        task = f"Task for {test_name}: Fix the injected problem"
        criteria = f"Must resolve {test_name} and pass all checks"
        
        session = reflexion.run_full_reflexion(
            task=task,
            target_criteria=criteria,
            verbose=True
        )
        
        # Analyze results
        result = {
            "test_name": test_name,
            "description": description,
            "pass_on_retry": pass_on_retry,
            "session_id": session.session_id,
            "attempts_count": session.current_round,
            "final_status": session.final_status.value,
            "final_score": session.final_score,
            "first_attempt_failed": session.points[0].score < 4.0 if session.points else False,
            "judge_rejected_first": session.points[0].score < 4.0 if session.points else False,
            "reflexion_generated_plan": len(session.points) > 1,
            "subsequent_passed": session.final_status == ReflexionStatus.PASS,
            "points": [p.to_dict() for p in session.points]
        }
        
        # Print summary
        print(f"\n📊 RESULTS:")
        print(f"  Attempts: {result['attempts_count']}")
        print(f"  Final Status: {result['final_status']}")
        print(f"  Final Score: {result['final_score']}")
        print(f"  First Attempt Failed: {result['first_attempt_failed']}")
        print(f"  Subsequent Passed: {result['subsequent_passed']}")
        
        return result
    
    # === TEST CASE 1: WRONG IMPORT PATH ===
    
    def test_01_wrong_import_path(self):
        """Test Case 1: Wrong import path."""
        result = self.run_test_case(
            test_name="wrong_import_path",
            description="First attempt uses invalid import path. Judge rejects. Reflexion fixes."
        )
        
        self.assertTrue(result["first_attempt_failed"], "First attempt must fail")
        self.assertTrue(result["reflexion_generated_plan"], "Reflexion must generate repair plan")
        self.assertTrue(result["subsequent_passed"], "Subsequent attempt must pass")
        
        TEST_RESULTS.append(result)
        print(f"✅ TEST PASSED: First failed → Reflexion → Second passed")
    
    # === TEST CASE 2: MISSING EVIDENCE ID ===
    
    def test_02_missing_evidence_id(self):
        """Test Case 2: Missing evidence ID."""
        result = self.run_test_case(
            test_name="missing_evidence_id",
            description="First attempt references non-existent evidence ID."
        )
        
        self.assertTrue(result["first_attempt_failed"])
        self.assertTrue(result["reflexion_generated_plan"])
        self.assertTrue(result["subsequent_passed"])
        
        TEST_RESULTS.append(result)
        print(f"✅ TEST PASSED: First failed → Reflexion → Second passed")
    
    # === TEST CASE 3: POOR ROUTE SELECTION ===
    
    def test_03_poor_route_selection(self):
        """Test Case 3: Poor route selection."""
        result = self.run_test_case(
            test_name="poor_route_selection",
            description="First attempt selects wrong model for task."
        )
        
        self.assertTrue(result["first_attempt_failed"])
        self.assertTrue(result["reflexion_generated_plan"])
        self.assertTrue(result["subsequent_passed"])
        
        TEST_RESULTS.append(result)
        print(f"✅ TEST PASSED: First failed → Reflexion → Second passed")
    
    # === TEST CASE 4: DUPLICATE LESSON RETRIEVAL ===
    
    def test_04_duplicate_lesson_retrieval(self):
        """Test Case 4: Duplicate lesson retrieval."""
        result = self.run_test_case(
            test_name="duplicate_lesson_retrieval",
            description="First attempt returns duplicate lessons instead of unique."
        )
        
        self.assertTrue(result["first_attempt_failed"])
        self.assertTrue(result["reflexion_generated_plan"])
        self.assertTrue(result["subsequent_passed"])
        
        TEST_RESULTS.append(result)
        print(f"✅ TEST PASSED: First failed → Reflexion → Second passed")
    
    # === TEST CASE 5: FAILING TEST ===
    
    def test_05_failing_test(self):
        """Test Case 5: Failing test."""
        result = self.run_test_case(
            test_name="failing_test",
            description="First attempt contains failing unit test with wrong assertion."
        )
        
        self.assertTrue(result["first_attempt_failed"])
        self.assertTrue(result["reflexion_generated_plan"])
        self.assertTrue(result["subsequent_passed"])
        
        TEST_RESULTS.append(result)
        print(f"✅ TEST PASSED: First failed → Reflexion → Second passed")
    
    # === TEST CASE 6: INCONSISTENT DOC CLAIM ===
    
    def test_06_inconsistent_doc_claim(self):
        """Test Case 6: Inconsistent doc claim."""
        result = self.run_test_case(
            test_name="inconsistent_doc_claim",
            description="First attempt makes claims inconsistent with documentation."
        )
        
        self.assertTrue(result["first_attempt_failed"])
        self.assertTrue(result["reflexion_generated_plan"])
        self.assertTrue(result["subsequent_passed"])
        
        TEST_RESULTS.append(result)
        print(f"✅ TEST PASSED: First failed → Reflexion → Second passed")
    
    # === TEST CASE 7: STALE REGISTRY STATUS ===
    
    def test_07_stale_registry_status(self):
        """Test Case 7: Stale registry status."""
        result = self.run_test_case(
            test_name="stale_registry_status",
            description="First attempt uses outdated registry status information."
        )
        
        self.assertTrue(result["first_attempt_failed"])
        self.assertTrue(result["reflexion_generated_plan"])
        self.assertTrue(result["subsequent_passed"])
        
        TEST_RESULTS.append(result)
        print(f"✅ TEST PASSED: First failed → Reflexion → Second passed")
    
    # === TEST CASE 8: PERFORMANCE BOTTLENECK ===
    
    def test_08_performance_bottleneck(self):
        """Test Case 8: Performance bottleneck."""
        result = self.run_test_case(
            test_name="performance_bottleneck",
            description="First attempt has unoptimized code causing timeout."
        )
        
        self.assertTrue(result["first_attempt_failed"])
        self.assertTrue(result["reflexion_generated_plan"])
        self.assertTrue(result["subsequent_passed"])
        
        TEST_RESULTS.append(result)
        print(f"✅ TEST PASSED: First failed → Reflexion → Second passed")
    
    # === TEST CASE 9: MISSING OUTPUT ARTIFACT ===
    
    def test_09_missing_output_artifact(self):
        """Test Case 9: Missing output artifact."""
        result = self.run_test_case(
            test_name="missing_output_artifact",
            description="First attempt fails to produce expected output file."
        )
        
        self.assertTrue(result["first_attempt_failed"])
        self.assertTrue(result["reflexion_generated_plan"])
        self.assertTrue(result["subsequent_passed"])
        
        TEST_RESULTS.append(result)
        print(f"✅ TEST PASSED: First failed → Reflexion → Second passed")
    
    # === TEST CASE 10: AMBIGUOUS USER OBJECTIVE ===
    
    def test_10_ambiguous_user_objective(self):
        """Test Case 10: Ambiguous user objective."""
        result = self.run_test_case(
            test_name="ambiguous_user_objective",
            description="First attempt cannot determine user intent from vague request."
        )
        
        self.assertTrue(result["first_attempt_failed"])
        self.assertTrue(result["reflexion_generated_plan"])
        self.assertTrue(result["subsequent_passed"])
        
        TEST_RESULTS.append(result)
        print(f"✅ TEST PASSED: First failed → Reflexion → Second passed")
    
    # === TEST CASE: RECOVERY FAILURE ===
    
    def test_11_recovery_failure(self):
        """Test Case 11: Even after reflexion, recovery fails."""
        result = self.run_test_case(
            test_name="generic_error",
            description="First attempt fails and subsequent attempts also fail.",
            pass_on_retry=False  # Will always fail
        )
        
        self.assertTrue(result["first_attempt_failed"])
        self.assertFalse(result["subsequent_passed"], "Should NOT pass even after retry")
        
        TEST_RESULTS.append(result)
        print(f"✅ TEST PASSED: First failed → Still failing after reflexion (expected)")
    
    # === FINAL VERIFICATION ===
    
    def test_final_summary(self):
        """Print final test summary."""
        global TEST_RESULTS
        print("\n" + "=" * 80)
        print("FINAL TEST SUMMARY")
        print("=" * 80)
        print(f"\nTotal test cases run: {len(TEST_RESULTS)}")
        
        passed = sum(1 for r in TEST_RESULTS if r["subsequent_passed"])
        failed = len(TEST_RESULTS) - passed
        
        print(f"Successful recoveries: {passed}")
        print(f"Failed recoveries: {failed}")
        
        total = len(TEST_RESULTS)
        success_rate = (passed / total * 100) if total > 0 else 0
        print(f"Success rate: {success_rate:.1f}%")
        
        print("\nDetailed Results:")
        for r in TEST_RESULTS:
            status = "✅ PASS" if r["subsequent_passed"] else "❌ FAIL"
            print(f"  {status} | {r['test_name']}: {r['attempts_count']} attempts, score={r['final_score']}")
        
        print("\n" + "=" * 80)
        
        # Assert all passed (except the recovery failure test)
        recovery_failures = sum(1 for r in TEST_RESULTS if not r["pass_on_retry"])
        expected_passes = len(TEST_RESULTS) - recovery_failures
        
        self.assertEqual(passed, expected_passes, f"Expected {expected_passes} passes, got {passed}")
        print(f"\n✅ ALL {expected_passes} RECOVERY TESTS PASSED!")


# === RUN TESTS ===

if __name__ == "__main__":
    print("=" * 80)
    print("ILMA TRY-UNTIL-SUCCESS LOOP TEST SUITE")
    print("Phase 53H - Reflexion Loop Recovery Testing")
    print("=" * 80)
    print("\nThis test suite validates the reflexion loop's ability to:")
    print("1. Fail on first attempt (injected problems)")
    print("2. Have judge reject the output")
    print("3. Generate a repair plan via reflexion")
    print("4. Succeed on subsequent attempt")
    
    # Run tests
    unittest.main(verbosity=2, exit=False)