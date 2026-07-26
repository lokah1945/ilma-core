#!/usr/bin/env python3
"""
ILMA Task Orchestrator v1.0 (Phase C / TASK 5.1)
=================================================
Splits large tasks into sub-tasks, executes independent ones in parallel,
respects dependency order.

Feature flag: config.yaml `task_orchestrator_enabled` (default: False)
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from ilma_code_forge import DualHarnessCodeForge, ForgeResult

logger = logging.getLogger("ilma.task_orchestrator")


@dataclass
class SubTask:
    """A sub-task with dependencies."""
    id: str
    type: str
    spec: Dict
    depends_on: List[str] = field(default_factory=list)
    level: int = 0  # Topological level (0 = no deps)
    result: Optional[Any] = None
    error: Optional[str] = None
    duration: float = 0.0


class TaskOrchestrator:
    """Split, schedule, and execute tasks in parallel respecting deps."""

    def __init__(self, forge: Optional[DualHarnessCodeForge] = None, max_concurrent: int = 3):
        self.forge = forge or DualHarnessCodeForge()
        self.max_concurrent = max_concurrent

    def split_task(self, task_spec: Dict) -> List[SubTask]:
        """Split a large task into sub-tasks with dependencies."""
        task_type = task_spec.get("type", "code")

        if task_type == "implement_feature":
            return [
                SubTask("design_api", "design", {"id": "design_api", "title": "Design API", "type": "design"}, []),
                SubTask("impl_backend", "code", {"id": "impl_backend", "title": "Implement backend", "type": "code"}, ["design_api"]),
                SubTask("impl_frontend", "code", {"id": "impl_frontend", "title": "Implement frontend", "type": "code"}, ["design_api"]),
                SubTask("write_tests", "code", {"id": "write_tests", "title": "Write tests", "type": "code"}, ["impl_backend", "impl_frontend"]),
                SubTask("integrate", "code", {"id": "integrate", "title": "Integrate", "type": "code"}, ["write_tests"]),
            ]

        # Default: return the task as-is (no split)
        return [SubTask(task_spec.get("id", "task"), task_type, task_spec, [])]

    def _compute_levels(self, sub_tasks: List[SubTask]) -> None:
        """Topological sort: assign level = max(deps.level) + 1."""
        by_id = {t.id: t for t in sub_tasks}
        # In case of circular dep, fall back
        for t in sub_tasks:
            t.level = 0
        changed = True
        iterations = 0
        while changed and iterations < 100:
            changed = False
            iterations += 1
            for t in sub_tasks:
                max_dep = -1
                for dep_id in t.depends_on:
                    if dep_id in by_id:
                        max_dep = max(max_dep, by_id[dep_id].level)
                new_level = max_dep + 1
                if new_level > t.level:
                    t.level = new_level
                    changed = True

    async def _run_subtask(self, sub: SubTask) -> SubTask:
        """Run a sub-task through the forge."""
        start = time.time()
        try:
            logger.info(f"[Orchestrator] Running {sub.id} (level {sub.level})")
            result = self.forge.execute_task(sub.spec, num_solutions=2)
            sub.result = result
            sub.duration = time.time() - start
            logger.info(f"[Orchestrator] {sub.id} done in {sub.duration:.2f}s")
        except Exception as e:
            sub.error = str(e)
            logger.error(f"[Orchestrator] {sub.id} failed: {e}")
        return sub

    async def execute_parallel(self, sub_tasks: List[SubTask]) -> List[SubTask]:
        """Execute sub-tasks in parallel, respecting dependency levels."""
        self._compute_levels(sub_tasks)

        # Group by level
        levels = defaultdict(list)
        for t in sub_tasks:
            levels[t.level].append(t)

        max_level = max(levels.keys()) if levels else 0
        completed_ids: Set[str] = set()

        for level in range(max_level + 1):
            tasks_at_level = levels[level]
            # Skip tasks whose deps aren't satisfied
            runnable = [
                t for t in tasks_at_level
                if all(dep in completed_ids for dep in t.depends_on)
            ]
            logger.info(f"[Orchestrator] Level {level}: running {len(runnable)} task(s)")

            # Run in parallel
            coros = [self._run_subtask(t) for t in runnable]
            results = await asyncio.gather(*coros, return_exceptions=True)

            for r in results:
                if isinstance(r, Exception):
                    logger.error(f"[Orchestrator] Task exception: {r}")
                elif isinstance(r, SubTask):
                    completed_ids.add(r.id)

        return sub_tasks


if __name__ == "__main__":
    print("=== Task Orchestrator Demo ===\n")
    orch = TaskOrchestrator()

    feature_task = {
        "id": "user_profile_feature",
        "type": "implement_feature",
        "title": "User profile feature",
        "description": "Implement a user profile system",
    }

    sub_tasks = orch.split_task(feature_task)
    print(f"Split into {len(sub_tasks)} sub-tasks:")
    for t in sub_tasks:
        print(f"  [{t.level}] {t.id} (deps: {t.depends_on})")

    print()
    print("=== Executing in parallel ===")
    results = asyncio.run(orch.execute_parallel(sub_tasks))
    print()
    print("=== Results ===")
    for r in results:
        status = "OK" if r.error is None else f"ERR: {r.error}"
        print(f"  {r.id} (level {r.level}): {status} ({r.duration:.3f}s)")

    # Test with a simple task (no split)
    print()
    print("=== Simple task (no split) ===")
    simple = [{"id": "test_simple", "type": "code", "title": "Simple", "description": "x"}]
    simple_results = asyncio.run(orch.execute_parallel(simple))
    print(f"Done: {simple_results[0].id} ({simple_results[0].duration:.3f}s)")
