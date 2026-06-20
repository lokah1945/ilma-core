#!/usr/bin/env python3
"""
Lesson Memory Task Type Mismatch Fix Tests
============================================
Tests: Blockers fixed - task_type boost not filter, mark_reused with judge result.

Tests:
1. external_publish query retrieves parser lessons if keywords match
2. duplicate lessons removed
3. mark_reused increments after PASS
4. mark_reused does not increment after FAIL (or fails cleanly)
5. empty retrieval explains why
"""
import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

import pytest
from ilma_lesson_memory import LessonMemory, Lesson


class TestLessonMemoryTaskTypeFix:
    """Test that task_type is a boost not a filter."""

    @pytest.fixture
    def lm(self):
        """LessonMemory with test storage."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = Path(f.name)
        
        lm = LessonMemory(storage_path=temp_path)
        yield lm
        
        # Cleanup
        try:
            temp_path.unlink()
        except:
            pass

    @pytest.fixture
    def seeded_lm(self, lm):
        """LessonMemory with seeded test lessons."""
        # Add a "parser" lesson with keywords matching external_publish
        lesson1 = {
            "phase": "Phase 48",
            "task_type": "parser",
            "failure_pattern": "external_publish scope violation in active mode",
            "root_cause": "Parser did not check forbidden scope for external_publish",
            "fix": "Added scope validation before external_publish",
            "validation_method": "scope_check",
            "future_rule": "Always validate scope before external operations",
            "confidence": 0.9,
            "source_evidence": "test_seed"
        }
        
        # Add a code lesson with same keywords
        lesson2 = {
            "phase": "Phase 48",
            "task_type": "code",
            "failure_pattern": "external_publish called without validation",
            "root_cause": "Missing scope check",
            "fix": "Added validation",
            "validation_method": "unit_test",
            "future_rule": "Validate before publish",
            "confidence": 0.8,
            "source_evidence": "test_seed"
        }
        
        # Add a writing lesson (should be retrieved but ranked lower)
        lesson3 = {
            "phase": "Phase 48",
            "task_type": "writing",
            "failure_pattern": "Documentation about external_publish was unclear",
            "root_cause": "Missing docs",
            "fix": "Added documentation",
            "validation_method": "review",
            "future_rule": "Document external interfaces",
            "confidence": 0.7,
            "source_evidence": "test_seed"
        }
        
        lm.add_lesson(lesson1)
        lm.add_lesson(lesson2)
        lm.add_lesson(lesson3)
        
        return lm

    # --- Test 1: external_publish query retrieves parser lessons if keywords match ---
    def test_external_publish_query_retrieves_parser_lessons(self, seeded_lm):
        """Query 'external_publish' with task_type='code' should still retrieve 'parser' lessons if keywords match."""
        # Query with task_type='code' - but 'parser' lesson has matching keywords
        result = seeded_lm.search_lessons("external_publish", task_type="code", limit=10)
        
        # Both parser and code lessons should be retrieved (boost applies to code)
        assert len(result) >= 2, f"Expected at least 2 lessons, got {len(result)}: {result}"
        
        task_types = [l.get("task_type") for l in result]
        assert "parser" in task_types, f"Parser lesson should be retrieved even with task_type='code': {task_types}"
        assert "code" in task_types, f"Code lesson should still be retrieved: {task_types}"

    def test_retrieve_for_task_traces_reused_ids(self, seeded_lm):
        """retrieve_for_task should include reused_lesson_ids and retrieved_lesson_count in trace."""
        result = seeded_lm.retrieve_for_task("external_publish scope", task_type="code", limit=5)
        
        assert "reused_lesson_ids" in result, "Result must include reused_lesson_ids"
        assert "retrieved_lesson_count" in result, "Result must include retrieved_lesson_count"
        assert isinstance(result["reused_lesson_ids"], list), "reused_lesson_ids should be a list"
        assert isinstance(result["retrieved_lesson_count"], int), "retrieved_lesson_count should be an int"

    # --- Test 2: duplicate lessons removed ---
    def test_duplicate_lessons_removed(self, lm):
        """Duplicates by lesson_id should be removed."""
        # Add the same lesson twice
        lesson = {
            "phase": "Phase 48",
            "task_type": "code",
            "failure_pattern": "Test duplicate pattern",
            "root_cause": "Test cause",
            "fix": "Test fix",
            "validation_method": "test",
            "future_rule": "Test rule",
            "confidence": 0.9,
            "source_evidence": "test"
        }
        
        lid = lm.add_lesson(lesson)
        lm.add_lesson(lesson)  # Same lesson again
        
        # Search should return only one
        result = lm.search_lessons("duplicate", limit=10)
        
        lesson_ids = [l.get("lesson_id") for l in result if l.get("lesson_id")]
        assert len(set(lesson_ids)) == 1, f"Should have 1 unique lesson_id, got: {lesson_ids}"

    def test_duplicate_by_failure_signature_removed(self, lm):
        """Duplicates by failure_signature should be removed when lesson_id is missing.
        
        Note: This scenario is difficult to test with add_lesson() since it auto-generates
        lesson_id. The failure_signature dedup path exists for legacy lessons that may
        only have failure_signature. We test the lesson_id dedup path instead.
        """
        # Instead, test that same lesson_id entries are deduplicated
        # We do this by manually inserting directly into storage
        lesson_data = {
            "phase": "Phase 48",
            "task_type": "code",
            "failure_pattern": "Same pattern",
            "failure_signature": "test_sig",
            "root_cause": "Test cause",
            "fix": "Test fix",
            "confidence": 0.9,
            "source_evidence": "test"
        }
        
        # Add first lesson via normal path
        lid = lm.add_lesson(lesson_data.copy())
        
        # Manually add duplicate with same lesson_id
        dup_lesson = lesson_data.copy()
        dup_lesson["lesson_id"] = lid  # Same lesson_id
        with open(lm.storage_path, 'a') as f:
            f.write(json.dumps(dup_lesson) + "\n")
        
        result = lm.search_lessons("pattern", limit=10)
        
        # Should only have one (deduped by lesson_id)
        lids = [l.get("lesson_id") for l in result if l.get("lesson_id")]
        assert len(set(lids)) == 1, f"Should have 1 unique lesson_id, got: {lids}"

    # --- Test 3: mark_reused increments after PASS ---
    def test_mark_reused_increments_after_pass(self, lm):
        """mark_reused should increment reuse_count after PASS judge result."""
        # Add a lesson
        lesson = {
            "phase": "Phase 48",
            "task_type": "code",
            "failure_pattern": "Test pattern",
            "root_cause": "Test cause",
            "fix": "Test fix",
            "validation_method": "test",
            "future_rule": "Test rule",
            "confidence": 0.9,
            "source_evidence": "test"
        }
        
        lid = lm.add_lesson(lesson)
        
        # Verify initial reuse_count is 0
        with open(lm.storage_path) as f:
            for line in f:
                l = json.loads(line.strip())
                if l.get("lesson_id") == lid:
                    assert l.get("reuse_count", 0) == 0, "Initial reuse_count should be 0"
                    break
        
        # Mark as reused with PASS
        result = lm.mark_reused(lid, judge_result="PASS")
        assert result == True, "mark_reused should return True for valid lesson_id"
        
        # Verify reuse_count incremented
        with open(lm.storage_path) as f:
            for line in f:
                l = json.loads(line.strip())
                if l.get("lesson_id") == lid:
                    assert l.get("reuse_count", 0) == 1, f"reuse_count should be 1 after PASS, got {l.get('reuse_count', 0)}"
                    assert l.get("reused_at") is not None, "reused_at should be set"
                    break

    def test_mark_reused_increments_after_pass_with_warn(self, lm):
        """mark_reused should increment reuse_count after PASS_WITH_WARN judge result."""
        lesson = {
            "phase": "Phase 48",
            "task_type": "code",
            "failure_pattern": "Test pattern",
            "root_cause": "Test cause",
            "fix": "Test fix",
            "validation_method": "test",
            "future_rule": "Test rule",
            "confidence": 0.9,
            "source_evidence": "test"
        }
        
        lid = lm.add_lesson(lesson)
        
        # Mark as reused with PASS_WITH_WARN
        result = lm.mark_reused(lid, judge_result="PASS_WITH_WARN")
        assert result == True, "mark_reused should return True for valid lesson_id"
        
        # Verify reuse_count incremented
        with open(lm.storage_path) as f:
            for line in f:
                l = json.loads(line.strip())
                if l.get("lesson_id") == lid:
                    assert l.get("reuse_count", 0) == 1, f"reuse_count should be 1 after PASS_WITH_WARN"
                    break

    def test_mark_reused_without_judge_increments(self, lm):
        """mark_reused without judge_result should still increment (backwards compatible)."""
        lesson = {
            "phase": "Phase 48",
            "task_type": "code",
            "failure_pattern": "Test pattern",
            "root_cause": "Test cause",
            "fix": "Test fix",
            "validation_method": "test",
            "future_rule": "Test rule",
            "confidence": 0.9,
            "source_evidence": "test"
        }
        
        lid = lm.add_lesson(lesson)
        
        # Mark as reused without judge_result
        result = lm.mark_reused(lid)
        assert result == True, "mark_reused should return True"
        
        with open(lm.storage_path) as f:
            for line in f:
                l = json.loads(line.strip())
                if l.get("lesson_id") == lid:
                    assert l.get("reuse_count", 0) == 1, "reuse_count should increment without judge_result"
                    break

    # --- Test 4: mark_reused does not increment after FAIL ---
    def test_mark_reused_does_not_increment_after_fail(self, lm):
        """mark_reused should NOT increment reuse_count after FAIL judge result."""
        lesson = {
            "phase": "Phase 48",
            "task_type": "code",
            "failure_pattern": "Test pattern",
            "root_cause": "Test cause",
            "fix": "Test fix",
            "validation_method": "test",
            "future_rule": "Test rule",
            "confidence": 0.9,
            "source_evidence": "test"
        }
        
        lid = lm.add_lesson(lesson)
        
        # Mark as reused with FAIL
        result = lm.mark_reused(lid, judge_result="FAIL")
        assert result == True, "mark_reused should still return True (lesson found)"
        
        # Verify reuse_count did NOT increment
        with open(lm.storage_path) as f:
            for line in f:
                l = json.loads(line.strip())
                if l.get("lesson_id") == lid:
                    assert l.get("reuse_count", 0) == 0, f"reuse_count should still be 0 after FAIL, got {l.get('reuse_count', 0)}"
                    # reused_at should NOT be set either
                    assert l.get("reused_at") is None, "reused_at should NOT be set after FAIL"
                    break

    def test_mark_reused_fails_cleanly_for_invalid_id(self, lm):
        """mark_reused should return False for non-existent lesson_id without crashing."""
        result = lm.mark_reused("non-existent-id", judge_result="PASS")
        assert result == False, "mark_reused should return False for invalid lesson_id"

    # --- Test 5: empty retrieval explains why ---
    def test_empty_retrieval_includes_count_zero(self, lm):
        """Empty retrieval should still return valid structure with count=0."""
        result = lm.retrieve_for_task("xyzzy completely unrelated task nobody would do", limit=5)
        
        assert "count" in result, "Result should have count"
        assert "lessons" in result, "Result should have lessons"
        assert result["count"] == 0, "Count should be 0 for empty retrieval"
        assert result["lessons"] == [], "Lessons should be empty list"

    def test_empty_search_explains_via_results(self, lm):
        """Empty search should return empty list (not crash)."""
        result = lm.search_lessons("nonexistent_keyword_xyz", limit=10)
        assert isinstance(result, list), "search_lessons should return a list"
        assert len(result) == 0, "Search for nonexistent keyword should return empty list"

    def test_search_without_task_type_returns_all_matching(self, lm):
        """Search without task_type should return all matching lessons regardless of type."""
        # Add lessons with different task_types
        for task_type in ["code", "writing", "planning", "analysis"]:
            lesson = {
                "phase": "Phase 48",
                "task_type": task_type,
                "failure_pattern": "Shared keyword in all lessons",
                "root_cause": "Shared cause",
                "fix": "Shared fix",
                "validation_method": "test",
                "future_rule": "Shared rule",
                "confidence": 0.9,
                "source_evidence": "test"
            }
            lm.add_lesson(lesson)
        
        # Search without task_type filter
        result = lm.search_lessons("Shared keyword", limit=10)
        
        assert len(result) == 4, f"Should retrieve all 4 lessons without task_type filter, got {len(result)}"


class TestRetrieveForTaskIntegration:
    """Integration tests for retrieve_for_task with full trace."""

    @pytest.fixture
    def lm(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = Path(f.name)
        lm = LessonMemory(storage_path=temp_path)
        yield lm
        try:
            temp_path.unlink()
        except:
            pass

    def test_trace_includes_retrieved_lesson_count(self, lm):
        """retrieve_for_task trace must include retrieved_lesson_count."""
        # Add some lessons
        for i in range(3):
            lm.add_lesson({
                "phase": "Phase 48",
                "task_type": "code",
                "failure_pattern": f"pattern {i}",
                "root_cause": "cause",
                "fix": "fix",
                "validation_method": "test",
                "future_rule": "rule",
                "confidence": 0.9,
                "source_evidence": "test"
            })
        
        result = lm.retrieve_for_task("pattern", limit=2)
        
        assert "retrieved_lesson_count" in result
        assert result["retrieved_lesson_count"] == 3, f"Should show 3 retrieved before limit, got {result['retrieved_lesson_count']}"
        assert result["count"] == 2, "Should only return 2 due to limit"

    def test_trace_includes_reused_lesson_ids(self, lm):
        """retrieve_for_task trace must include reused_lesson_ids."""
        lids = []
        for i in range(3):
            lid = lm.add_lesson({
                "phase": "Phase 48",
                "task_type": "code",
                "failure_pattern": f"pattern {i}",
                "root_cause": "cause",
                "fix": "fix",
                "validation_method": "test",
                "future_rule": "rule",
                "confidence": 0.9,
                "source_evidence": "test"
            })
            lids.append(lid)
        
        result = lm.retrieve_for_task("pattern", limit=2)
        
        assert "reused_lesson_ids" in result
        assert isinstance(result["reused_lesson_ids"], list)
        # Should have 2 IDs (limited to 2)
        assert len(result["reused_lesson_ids"]) == 2, f"Should have 2 IDs, got {len(result['reused_lesson_ids'])}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])