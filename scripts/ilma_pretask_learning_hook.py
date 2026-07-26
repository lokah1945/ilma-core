#!/usr/bin/env python3
"""
ILMA Pre-Task Learning Hook v2.0
=================================
Retrieves relevant lessons BEFORE task execution.
Key fix v2.0: Uses LessonMemory.search_lessons() directly (not custom scoring)
and prioritizes lessons with proper failure_signature over old-schema lessons.

Storage: memory/ilma_lessons.jsonl (JSONL, stdlib)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

WORKSPACE = Path("/root/.hermes/profiles/ilma")


class PreTaskLearningHook:
    """Hook that retrieves relevant past lessons before task execution."""

    def __init__(self, memory_path: Optional[Path] = None):
        self.memory_path = memory_path or (WORKSPACE / "memory" / "ilma_lessons.jsonl")

    def retrieve_for_task(
        self,
        task: str,
        task_type: Optional[str] = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Retrieve relevant lessons for a task.

        Returns:
        {
            "task": "...",
            "task_type": "...",
            "lessons": [...],  # Each lesson is a dict
            "count": N,
            "changed_plan": bool,
            "planning_hints": [...]
        }
        """
        # Keyword-based retrieval using LessonMemory
        lessons = self._retrieve_by_keywords(task, task_type, limit)

        # Generate planning hints
        hints = self._generate_hints(lessons)

        # Determine if plan changed
        changed_plan = len(lessons) > 0

        return {
            "task": task,
            "task_type": task_type,
            "lessons": lessons,
            "count": len(lessons),
            "changed_plan": changed_plan,
            "planning_hints": hints,
            "retrieved_lesson_ids": [l.get("lesson_id", "") for l in lessons],
            "retrieved_lesson_sigs": [l.get("failure_signature", "") for l in lessons],
        }

    def _retrieve_by_keywords(
        self,
        task: str,
        task_type: Optional[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Retrieve lessons by keyword matching. Fresh read per call."""
        from ilma_lesson_memory import LessonMemory
        lm = LessonMemory()  # Fresh instance, fresh file read

        # Extract keywords from task
        keywords = self._extract_keywords(task)

        all_relevant = []

        for keyword in keywords:
            results = lm.search_lessons(keyword, task_type=task_type, limit=3)
            for result in results:
                if result not in all_relevant:
                    all_relevant.append(result)

        # Sort by relevance first, then by confidence
        all_relevant.sort(key=lambda x: (
            x.get("relevance", 0),
            x.get("confidence", 0)
        ), reverse=True)

        # PRIORITY: lessons with failure_signature come FIRST
        # Old harness tests wrote lessons without failure_signature — those go last
        has_sig = [l for l in all_relevant if l.get("failure_signature") and l.get("failure_signature") != "N/A"]
        no_sig = [l for l in all_relevant if not l.get("failure_signature") or l.get("failure_signature") == "N/A"]
        all_relevant = has_sig + no_sig

        return all_relevant[:limit]

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from task text."""
        import re
        # Split on common separators
        words = re.split(r'[\s,;.\-_/]+', text.lower())
        # Filter: length >= 3, not common stop words
        stop_words = {
            'the', 'and', 'for', 'with', 'from', 'this', 'that', 'were',
            'been', 'have', 'has', 'had', 'will', 'would', 'could', 'should',
            'about', 'into', 'through', 'during', 'before', 'after', 'above',
            'below', 'between', 'under', 'again', 'further', 'then', 'once',
            'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each',
            'few', 'more', 'most', 'other', 'some', 'such', 'only', 'same',
            'just', 'also', 'very', 'check', 'verify', 'test', 'lesson',
            'review', 'retrieve', 'ensure', 'make', 'must', 'fokus', 'focus'
        }
        keywords = [w for w in words if len(w) >= 3 and w not in stop_words]
        # Also add composite phrases from text
        composites = []
        text_lower = text.lower()
        for phrase in ['external_publish', 'create_session', 'PASS_WITH_WARN', 'status_label',
                        'negative_scope', 'artifact_producer', 'owner_command', 'API_mismatch',
                        'scope_parser', 'confirmation_gate']:
            if phrase in text_lower:
                composites.append(phrase)
        keywords.extend(composites)
        # Deduplicate
        seen = set()
        result = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                result.append(kw)
        return result

    def _generate_hints(self, lessons: List[Dict[str, Any]]) -> List[str]:
        """Generate planning hints from lessons."""
        hints = []
        for lesson in lessons:
            rule = lesson.get("reusable_rule", "") or lesson.get("future_rule", "")
            if rule:
                hints.append(f"Remember: {rule[:100]}")
            fix = lesson.get("fix_strategy", "") or lesson.get("fix", "")
            if fix and len(hints) < 3:
                hints.append(f"Fix: {fix[:100]}")
        return hints[:3]

    def log_retrieval(
        self,
        task: str,
        retrieval_result: Dict[str, Any],
        plan_changed: bool
    ) -> str:
        """Log retrieval event for audit."""
        log_entry = {
            "event": "pretask_retrieval",
            "task": task[:100],
            "lessons_retrieved": retrieval_result.get("count", 0),
            "lesson_ids": retrieval_result.get("retrieved_lesson_ids", []),
            "plan_changed": plan_changed,
            "hints_generated": len(retrieval_result.get("planning_hints", []))
        }

        log_path = WORKSPACE / "memory" / "pretask_retrieval_log.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(log_path, 'a') as f:
            f.write(json.dumps(log_entry) + "\n")

        return f"Logged retrieval of {log_entry['lessons_retrieved']} lessons"


def run_demo():
    """Run pre-task hook demo."""
    print("=" * 60)
    print("ILMA Pre-Task Learning Hook Demo")
    print("=" * 60)
    hook = PreTaskLearningHook()

    test_tasks = [
        "external_publish scope parser bug fix",
        "create_session owner_command API mismatch",
        "PASS_WITH_WARN status label bug",
        "artifact producer empty artifact",
        "random irrelevant task",
    ]

    for task in test_tasks:
        print(f"\n>>> Task: {task}")
        result = hook.retrieve_for_task(task)
        print(f"  Retrieved: {result['count']} lessons")
        print(f"  Changed plan: {result['changed_plan']}")
        print(f"  Hints: {result['planning_hints']}")
        for lesson in result['lessons'][:2]:
            print(f"  - {lesson.get('failure_signature', 'N/A')}: {lesson.get('failure_pattern', 'N/A')[:50]}")


if __name__ == '__main__':
    run_demo()