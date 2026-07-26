#!/usr/bin/env python3
"""
ILMA Lesson Memory Store v1.0
==============================
Persistent lesson storage for autonomous evolution.
Phase 46 - Autonomous Evolution Foundation.

Storage: JSONL (local, stdlib-first)
Schema validation: Built-in
Vector DB: Adapter designed but NOT implemented (not claimed)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ILMA paths
ILMA_PROFILE = Path("/root/.hermes/profiles/ilma")
WORKSPACE = ILMA_PROFILE


# === SCHEMA ===

LESSON_SCHEMA = {
    "lesson_id": "string (UUID)",
    "timestamp": "ISO8601 datetime",
    "phase": "string (e.g., 'Phase 46')",
    "task_type": "string (code|writing|planning|analysis)",
    "failure_pattern": "string (what went wrong)",
    "root_cause": "string (why it went wrong)",
    "fix": "string (how it was fixed)",
    "validation_method": "string (what test caught it)",
    "future_rule": "string (how to prevent)",
    "confidence": "float (0.0-1.0)",
    "source_evidence": "string (evidence ID or source)"
}

REQUIRED_FIELDS = ["lesson_id", "timestamp", "phase", "task_type", "failure_pattern", "root_cause"]


@dataclass
class Lesson:
    """Lesson data structure."""
    lesson_id: str
    timestamp: str
    phase: str
    task_type: str
    failure_pattern: str
    root_cause: str
    fix: str = ""
    validation_method: str = ""
    future_rule: str = ""
    confidence: float = 0.5
    source_evidence: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Lesson":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class LessonMemory:
    """
    Lesson memory store with JSONL backend.
    
    Features:
    - add_lesson()
    - search_lessons()
    - retrieve_for_task()
    - mark_reused()
    - export_lessons()
    - validate_schema()
    
    Note: Vector DB adapter designed but NOT implemented.
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or (WORKSPACE / "memory" / "ilma_lessons.jsonl")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Ensure file exists
        if not self.storage_path.exists():
            self.storage_path.write_text("")
        
        # Stats
        self._stats = {
            "total_lessons": 0,
            "by_task_type": {},
            "by_phase": {}
        }
        self._refresh_stats()

    def _refresh_stats(self):
        """Refresh statistics."""
        try:
            lessons = self._read_all()
            self._stats["total_lessons"] = len(lessons)
            self._stats["by_task_type"] = {}
            self._stats["by_phase"] = {}
            for lesson in lessons:
                tt = lesson.get("task_type", "unknown")
                ph = lesson.get("phase", "unknown")
                self._stats["by_task_type"][tt] = self._stats["by_task_type"].get(tt, 0) + 1
                self._stats["by_phase"][ph] = self._stats["by_phase"].get(ph, 0) + 1
        except RequestException:
            pass

    def _read_all(self) -> List[Dict[str, Any]]:
        """Read all lessons from storage."""
        lessons = []
        try:
            with open(self.storage_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        lessons.append(json.loads(line))
        except FileNotFoundError:
            pass
        return lessons

    def _append(self, lesson: Dict[str, Any]):
        """Append lesson to storage."""
        with open(self.storage_path, 'a') as f:
            f.write(json.dumps(lesson, ensure_ascii=False) + "\n")

    def add_lesson(
        self,
        lesson_data: Dict[str, Any],
        validate: bool = True
    ) -> str:
        """
        Add a new lesson.
        
        Args:
            lesson_data: Lesson data dict
            validate: Whether to validate schema
            
        Returns:
            lesson_id
        """
        # Auto-fill required fields before validation
        if "lesson_id" not in lesson_data:
            lesson_data["lesson_id"] = str(uuid.uuid4())
        
        if "timestamp" not in lesson_data:
            lesson_data["timestamp"] = datetime.now().isoformat()
        
        # Validate (after auto-fill so it passes)
        if validate:
            is_valid, errors = self.validate_schema(lesson_data)
            if not is_valid:
                raise ValueError(f"Invalid lesson schema: {errors}")
        
        # Append
        self._append(lesson_data)
        self._refresh_stats()
        
        return lesson_data["lesson_id"]

    def validate_schema(self, lesson: Dict[str, Any]) -> tuple:
        """
        Validate lesson against schema.
        
        Returns:
            (is_valid, errors)
        """
        errors = []
        
        # Check required fields
        for field in REQUIRED_FIELDS:
            if field not in lesson or not lesson[field]:
                errors.append(f"Missing required field: {field}")
        
        # Check types
        if "confidence" in lesson:
            try:
                conf = float(lesson["confidence"])
                if not (0.0 <= conf <= 1.0):
                    errors.append("confidence must be 0.0-1.0")
            except (ValueError, TypeError):
                errors.append("confidence must be a number")
        
        # Check timestamp format
        if "timestamp" in lesson:
            try:
                datetime.fromisoformat(lesson["timestamp"].replace('Z', '+00:00'))
            except Exception:
                errors.append("timestamp must be ISO8601 format")
        
        return len(errors) == 0, errors

    def search_lessons(
        self,
        query: str,
        task_type: Optional[str] = None,
        phase: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search lessons by text match.
        
        Primary retrieval by semantic/keyword match.
        Secondary boost by task_type (NOT hard filter).
        Never exclude all lessons unless owner explicitly requests via task_type=None.
        
        Simple keyword search, NOT vector similarity.
        For vector search, use vector DB adapter (not implemented).
        """
        results = []
        query_lower = query.lower()
        
        for lesson in self._read_all():
            # === PHASE 48G-G: task_type is BOOST not FILTER ===
            # Skip ONLY if phase filter is set and doesn't match (phase is explicit filter)
            if phase and lesson.get("phase") != phase:
                continue
            
            # Simple keyword match (PRIMARY retrieval criteria)
            search_text = ' '.join([
                lesson.get("failure_pattern", ""),
                lesson.get("root_cause", ""),
                lesson.get("fix", ""),
                lesson.get("future_rule", "")
            ]).lower()
            
            if query_lower in search_text:
                # Calculate simple relevance
                relevance = search_text.count(query_lower) / max(len(search_text.split()), 1)
                
                # Task type boost (SECONDARY - not filter)
                # Boost factor: 1.5x for matching task_type, 1.0x otherwise
                boost = 1.5 if task_type and lesson.get("task_type") == task_type else 1.0
                
                results.append({
                    **lesson,
                    "relevance": min(relevance * 10 * boost, 2.0)  # Normalize with boost
                })
        
        # Sort by relevance (boosted scores already incorporated)
        results.sort(key=lambda x: x.get("relevance", 0), reverse=True)

        # === PHASE 48G-G: Deduplication ===
        # Same lesson_id → keep first occurrence (preserve order)
        # NOTE: lessons use "lesson_id" field (not "id")
        seen_ids = set()
        deduped = []
        for r in results:
            lid = r.get("lesson_id", "")
            # Use "N/A" or empty as sentinel — deduplicate only real IDs
            if lid and lid not in ("N/A", ""):
                if lid not in seen_ids:
                    seen_ids.add(lid)
                    deduped.append(r)
            else:
                # No real id — include but deduplicate by failure_signature
                sig = r.get("failure_signature", "")
                if sig and sig not in ("N/A", ""):
                    if sig not in seen_ids:
                        seen_ids.add(sig)
                        deduped.append(r)
                else:
                    # Neither id nor sig — include (legacy lesson)
                    deduped.append(r)

        return deduped[:limit]

    def retrieve_for_task(
        self,
        task: str,
        task_type: Optional[str] = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Retrieve relevant lessons for a task.

        Uses keyword matching, NOT vector similarity.
        Primary retrieval by semantic/keyword match, secondary boost by task_type.
        
        Trace includes:
        - retrieved_lesson_count: total lessons retrieved before limit
        - reused_lesson_ids: list of lesson IDs returned
        """
        # Search by failure patterns
        relevant_lessons = []
        
        # Extract keywords from task
        keywords = self._extract_keywords(task)
        
        for keyword in keywords:
            lessons = self.search_lessons(keyword, task_type=task_type, limit=3)
            for lesson in lessons:
                if lesson not in relevant_lessons:
                    lesson["matched_keyword"] = keyword
                    relevant_lessons.append(lesson)
        
        # Sort by confidence and relevance
        relevant_lessons.sort(
            key=lambda x: (x.get("confidence", 0), x.get("relevance", 0)),
            reverse=True
        )
        
        # Deduplicate by lesson_id (final dedup pass)
        seen_ids = set()
        deduped = []
        for lesson in relevant_lessons:
            lid = lesson.get("lesson_id", "")
            if lid and lid not in ("N/A", ""):
                if lid not in seen_ids:
                    seen_ids.add(lid)
                    deduped.append(lesson)
            else:
                deduped.append(lesson)
        
        final_lessons = deduped[:limit]
        
        return {
            "task": task,
            "task_type": task_type,
            "lessons": final_lessons,
            "count": len(final_lessons),
            "retrieved_lesson_count": len(relevant_lessons),  # Before limit
            "reused_lesson_ids": [l.get("lesson_id", "") for l in final_lessons if l.get("lesson_id")]
        }

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        # Simple extraction
        words = text.lower().split()
        
        # Remove common words
        stop_words = {
            'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
            'build', 'create', 'make', 'implement'
        }
        
        keywords = [w for w in words if w not in stop_words and len(w) > 3]
        
        # Return top 5
        return list(set(keywords))[:5]

    def mark_reused(self, lesson_id: str, judge_result: Optional[str] = None) -> bool:
        """
        Mark a lesson as reused (for tracking).
        
        Args:
            lesson_id: The lesson ID to mark
            judge_result: Optional judge result ("PASS", "PASS_WITH_WARN", "FAIL")
                         If provided, only increments reuse_count for PASS or PASS_WITH_WARN.
        
        Returns:
            True if lesson was found and marked, False otherwise.
            
        Note:
            reuse_count only increments for PASS or PASS_WITH_WARN.
            reused_at is only set if count was incremented (i.e., lesson was successfully reused).
        """
        lessons = self._read_all()
        found = False
        
        # Determine if we should increment
        should_increment = True
        if judge_result is not None:
            allowed_results = {"PASS", "PASS_WITH_WARN"}
            if judge_result not in allowed_results:
                # Don't increment for FAIL or other results
                should_increment = False
        
        for lesson in lessons:
            if lesson.get("lesson_id") == lesson_id:
                if should_increment:
                    lesson["reused_at"] = datetime.now().isoformat()
                    lesson["reuse_count"] = lesson.get("reuse_count", 0) + 1
                found = True
        
        # Rewrite storage
        with open(self.storage_path, 'w') as f:
            for lesson in lessons:
                f.write(json.dumps(lesson, ensure_ascii=False) + "\n")
        
        return found

    def export_lessons(
        self,
        output_path: Path,
        task_type: Optional[str] = None,
        phase: Optional[str] = None
    ) -> int:
        """
        Export lessons to file.
        
        Returns:
            Number of lessons exported
        """
        lessons = self._read_all()
        
        # Filter
        if task_type:
            lessons = [l for l in lessons if l.get("task_type") == task_type]
        if phase:
            lessons = [l for l in lessons if l.get("phase") == phase]
        
        # Export
        with open(output_path, 'w') as f:
            json.dump(lessons, f, indent=2)
        
        return len(lessons)

    def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            **self._stats,
            "storage_path": str(self.storage_path),
            "storage_exists": self.storage_path.exists()
        }

    def clear_all(self):
        """Clear all lessons (dangerous!)."""
        self.storage_path.write_text("")
        self._refresh_stats()


# === SCHEMA CONFIG ===

def get_lesson_schema() -> Dict[str, str]:
    """Return lesson schema for reference."""
    return LESSON_SCHEMA


def create_schema_config():
    """Create schema config file."""
    schema_path = WORKSPACE / "config" / "ilma_lesson_schema.json"
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(schema_path, 'w') as f:
        json.dump({
            "schema_version": "1.0",
            "schema": LESSON_SCHEMA,
            "required_fields": REQUIRED_FIELDS,
            "note": "Vector DB adapter designed but NOT implemented"
        }, f, indent=2)
    
    return schema_path


# === DEMO ===

def run_demo():
    """Run lesson memory demo."""
    print("=" * 60)
    print("ILMA Lesson Memory Store v1.0")
    print("=" * 60)
    
    # Create memory
    memory = LessonMemory()
    
    # Add lessons
    print("\n[Adding lessons...]")
    
    lesson1 = {
        "phase": "Phase 46",
        "task_type": "code",
        "failure_pattern": "Syntax error in Python code",
        "root_cause": "Missing parenthesis in function definition",
        "fix": "Added closing parenthesis",
        "validation_method": "compile_check",
        "future_rule": "Always verify syntax before claiming implementation complete",
        "confidence": 0.9,
        "source_evidence": "demo"
    }
    
    lesson2 = {
        "phase": "Phase 46",
        "task_type": "code",
        "failure_pattern": "Security issue - eval() usage",
        "root_cause": "Used eval() for parsing user input",
        "fix": "Replaced with ast.literal_eval()",
        "validation_method": "security_check",
        "future_rule": "Never use eval() on untrusted input",
        "confidence": 0.95,
        "source_evidence": "demo"
    }
    
    lesson3 = {
        "phase": "Phase 46",
        "task_type": "writing",
        "failure_pattern": "Overclaim in documentation",
        "root_cause": "Claimed '100% perfect' without evidence",
        "fix": "Removed absolute claims, added hedging",
        "validation_method": "truthfulness_check",
        "future_rule": "Never claim 100% without empirical evidence",
        "confidence": 0.85,
        "source_evidence": "demo"
    }
    
    for lesson in [lesson1, lesson2, lesson3]:
        lid = memory.add_lesson(lesson)
        print(f"  Added: {lid[:8]}... ({lesson['task_type']})")
    
    # Search
    print("\n[Searching 'error'...]")
    results = memory.search_lessons("error")
    for r in results[:3]:
        print(f"  - {r['failure_pattern'][:50]}... (relevance: {r.get('relevance', 0):.2f})")
    
    # Retrieve for task
    print("\n[Retrieving for 'Build Python function'...]")
    result = memory.retrieve_for_task("Build Python function", task_type="code")
    print(f"  Found {result['count']} relevant lessons")
    
    # Stats
    print("\n[Statistics]")
    stats = memory.get_statistics()
    print(f"  Total lessons: {stats['total_lessons']}")
    print(f"  By task type: {stats['by_task_type']}")
    print(f"  Storage: {stats['storage_path']}")
    
    # Schema
    print("\n[Schema validation]")
    valid, errors = memory.validate_schema(lesson1)
    print(f"  Valid: {valid}")
    if errors:
        print(f"  Errors: {errors}")
    
    return memory


if __name__ == "__main__":
    run_demo()