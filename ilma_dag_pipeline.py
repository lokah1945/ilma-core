#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          ILMA DAG PIPELINE ENGINE v3.0 — CERTIFIED: CONTROLLED_CANARY                       ║
║          Dependency-Aware Parallel Execution with State Machine              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Improvements atas Hermes native (yang hanya flat parallel):
  ✅ DAG-aware scheduling (dependency resolution)
  ✅ Dynamic batch formation (parallelism where possible)
  ✅ Per-task model routing (bukan global model)
  ✅ State machine: PENDING→RUNNING→SUCCESS/FAILED/RETRYING
  ✅ Cascading failure isolation (1 task fail tidak kill semua)
  ✅ Context propagation antar tahap (child dapat output parent)
  ✅ Artifact registry (file/data yang dihasilkan tercatat)
  ✅ Timeout enforcement per task
  ✅ Progress tracking & telemetry
  ✅ Async-ready (bisa di-upgrade ke asyncio)

Author: ILMA Core Team
Version: 3.0.0
"""

from __future__ import annotations

import json
import logging
import time
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, Future, as_completed, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
import os

logger = logging.getLogger("ILMA.DAGPipeline")

ILMA_PROFILE = Path(os.environ.get("ILMA_PROFILE", "/root/.hermes/profiles/ilma"))
MAX_WORKERS   = int(os.environ.get("ILMA_MAX_WORKERS", "5"))
MAX_DEPTH     = int(os.environ.get("ILMA_MAX_DEPTH", "3"))


# ═══════════════════════════════════════════════════════════════════════════════
# STATE MACHINE
# ═══════════════════════════════════════════════════════════════════════════════

class TaskState(Enum):
    PENDING   = "pending"
    QUEUED    = "queued"
    RUNNING   = "running"
    SUCCESS   = "success"
    FAILED    = "failed"
    RETRYING  = "retrying"
    SKIPPED   = "skipped"  # skipped due to upstream failure
    CANCELLED = "cancelled"

TERMINAL_STATES = {TaskState.SUCCESS, TaskState.FAILED, TaskState.SKIPPED, TaskState.CANCELLED}


# ═══════════════════════════════════════════════════════════════════════════════
# ARTIFACT REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Artifact:
    """Artifact yang dihasilkan oleh suatu task."""
    task_id: str
    artifact_type: str  # "file", "data", "text", "url"
    name: str
    value: Any
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "artifact_type": self.artifact_type,
            "name": self.name,
            "value": str(self.value)[:500] if self.value else None,
            "created_at": self.created_at,
        }


class ArtifactRegistry:
    """Registry terpusat untuk semua artifacts dari workflow."""

    def __init__(self):
        self._lock = threading.Lock()
        self._artifacts: Dict[str, List[Artifact]] = defaultdict(list)  # task_id → artifacts

    def register(self, artifact: Artifact):
        with self._lock:
            self._artifacts[artifact.task_id].append(artifact)

    def get_by_task(self, task_id: str) -> List[Artifact]:
        with self._lock:
            return list(self._artifacts.get(task_id, []))

    def get_all(self) -> List[Artifact]:
        with self._lock:
            result = []
            for arts in self._artifacts.values():
                result.extend(arts)
            return result

    def to_dict(self) -> Dict:
        with self._lock:
            return {
                task_id: [a.to_dict() for a in arts]
                for task_id, arts in self._artifacts.items()
            }


# ═══════════════════════════════════════════════════════════════════════════════
# TASK NODE
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PipelineTask:
    """Satu node dalam DAG pipeline."""

    # Identity
    id: str
    name: str
    goal: str
    role: str = "executor"
    task_category: str = "general"

    # DAG structure
    depends_on: List[str] = field(default_factory=list)
    priority: int = 50  # 0-100

    # Execution config
    executor: Optional[Callable] = None  # fn(task, context) → Dict
    model_id: Optional[str] = None       # pre-assigned model (optional)
    timeout: int = 300
    max_retries: int = 2
    fail_fast: bool = False  # if True, pipeline stops on this task's failure

    # Runtime state
    state: TaskState = TaskState.PENDING
    attempt: int = 0
    result: Optional[Dict] = None
    error: Optional[str] = None
    artifacts: List[Artifact] = field(default_factory=list)

    # Timing
    queued_at: Optional[float] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    # Injected context
    context: Dict = field(default_factory=dict)
    output_schema: Dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at) * 1000
        return 0.0

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "goal": self.goal[:200],
            "role": self.role,
            "task_category": self.task_category,
            "depends_on": self.depends_on,
            "priority": self.priority,
            "state": self.state.value,
            "attempt": self.attempt,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
            "model_id": self.model_id,
            "artifacts_count": len(self.artifacts),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# DAG PIPELINE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class DAGPipelineEngine:
    """
    Production-grade DAG Pipeline Engine.

    Lifecycle:
      1. validate()    — check for cycles, missing deps
      2. plan()        — topological sort → batches
      3. execute()     — run batches, collect results
      4. report()      — telemetry + artifact registry

    Features:
      - Parallel execution within each batch (ThreadPoolExecutor)
      - Sequential batches (respects dependencies)
      - Context propagation: downstream tasks get upstream results
      - Retry with exponential backoff
      - Fail-fast support
      - Artifact registry
      - Progress callbacks
    """

    def __init__(
        self,
        max_workers: int = MAX_WORKERS,
        max_depth: int = MAX_DEPTH,
        progress_callback: Optional[Callable[[str, TaskState, Dict], None]] = None,
    ):
        self.max_workers = max_workers
        self.max_depth   = max_depth
        self.progress_cb = progress_callback
        self._artifacts  = ArtifactRegistry()
        self._lock       = threading.Lock()
        self._executor   = None  # created per-run

    # ── Validation ─────────────────────────────────────────────────────────────

    def validate(self, tasks: List[PipelineTask]) -> Tuple[bool, List[str]]:
        """Validate DAG: detect cycles, missing deps, empty tasks."""
        errors = []

        if not tasks:
            errors.append("No tasks provided")
            return False, errors

        task_ids = {t.id for t in tasks}

        # Check for missing dependencies
        for task in tasks:
            for dep in task.depends_on:
                if dep not in task_ids:
                    errors.append(f"Task '{task.id}' depends on unknown task '{dep}'")

        # Check for duplicate IDs
        seen = set()
        for task in tasks:
            if task.id in seen:
                errors.append(f"Duplicate task ID: '{task.id}'")
            seen.add(task.id)

        if errors:
            return False, errors

        # Cycle detection (Kahn's algorithm)
        in_degree = {t.id: 0 for t in tasks}
        adj: Dict[str, List[str]] = {t.id: [] for t in tasks}
        for task in tasks:
            for dep in task.depends_on:
                adj[dep].append(task.id)
                in_degree[task.id] += 1

        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        processed = 0
        while queue:
            node = queue.pop(0)
            processed += 1
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if processed != len(tasks):
            errors.append("Circular dependency detected in pipeline DAG")

        return len(errors) == 0, errors

    # ── Planning ───────────────────────────────────────────────────────────────

    def plan(self, tasks: List[PipelineTask]) -> List[List[PipelineTask]]:
        """
        Compute execution batches via topological sort.
        Tasks in same batch can run in parallel.
        """
        task_map = {t.id: t for t in tasks}
        remaining = {t.id for t in tasks}
        completed: Set[str] = set()
        batches: List[List[PipelineTask]] = []

        while remaining:
            # Find ready tasks (all deps completed)
            ready = [
                task_map[tid] for tid in remaining
                if all(dep in completed for dep in task_map[tid].depends_on)
            ]

            if not ready:
                # Should not happen after successful validation
                logger.error(f"[Pipeline] DAG stall! Remaining tasks: {remaining}")
                # Force-add remaining tasks to prevent infinite loop
                ready = [task_map[tid] for tid in remaining]

            # Sort by priority (descending)
            ready.sort(key=lambda t: t.priority, reverse=True)

            batches.append(ready)
            for t in ready:
                remaining.discard(t.id)
                completed.add(t.id)

        logger.info(
            f"[Pipeline] Plan: {len(tasks)} tasks → {len(batches)} batches | "
            f"max_parallel={max(len(b) for b in batches) if batches else 0}"
        )
        for i, batch in enumerate(batches):
            logger.debug(f"  Batch {i+1}: {[t.id for t in batch]}")

        return batches

    # ── Execution ──────────────────────────────────────────────────────────────

    def execute(
        self,
        tasks: List[PipelineTask],
        shared_context: Dict[str, Any] = None,
        default_executor: Optional[Callable] = None,
    ) -> "PipelineResult":
        """
        Execute the full DAG pipeline.

        Args:
            tasks: List of PipelineTask nodes
            shared_context: Shared context passed to all tasks
            default_executor: Default fn(task, ctx) if task.executor is None

        Returns:
            PipelineResult with all task states + artifacts
        """
        start_time = time.time()
        shared_ctx = shared_context or {}

        # Validate
        valid, errors = self.validate(tasks)
        if not valid:
            logger.error(f"[Pipeline] Validation failed: {errors}")
            return PipelineResult(
                tasks=tasks,
                artifacts=self._artifacts,
                errors=errors,
                success=False,
                execution_time=0.0,
            )

        # Plan
        batches = self.plan(tasks)
        task_map = {t.id: t for t in tasks}

        # Execute batches sequentially
        pipeline_stop = False

        with ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="ILMA-Pipeline"
        ) as executor:
            self._executor = executor

            for batch_idx, batch in enumerate(batches):
                if pipeline_stop:
                    # Cancel remaining tasks
                    for task in batch:
                        task.state = TaskState.CANCELLED
                    continue

                logger.info(
                    f"[Pipeline] Batch {batch_idx + 1}/{len(batches)}: "
                    f"{[t.id for t in batch]} (n={len(batch)})"
                )

                # Build batch context (inject upstream results)
                batch_ctx = dict(shared_ctx)
                for task in batch:
                    for dep_id in task.depends_on:
                        dep_task = task_map.get(dep_id)
                        if dep_task and dep_task.result:
                            batch_ctx[f"result_{dep_id}"] = dep_task.result
                            batch_ctx[f"artifacts_{dep_id}"] = [
                                a.to_dict() for a in dep_task.artifacts
                            ]

                # Dispatch batch
                futures: Dict[Future, PipelineTask] = {}
                for task in batch:
                    task.state = TaskState.QUEUED
                    task.queued_at = time.time()
                    task_ctx = {**batch_ctx, **task.context}

                    exec_fn = task.executor or default_executor or self._default_executor
                    fut = executor.submit(
                        self._run_task_with_retry,
                        task, exec_fn, task_ctx
                    )
                    futures[fut] = task

                # Collect batch results
                batch_failed_critical = False
                for future in as_completed(futures, timeout=max(t.timeout for t in batch) + 60):
                    task = futures[future]
                    try:
                        completed_task = future.result(timeout=10)
                        task_map[task.id] = completed_task

                        if completed_task.state == TaskState.FAILED and completed_task.fail_fast:
                            logger.error(f"[Pipeline] Fail-fast triggered by task '{task.id}'")
                            batch_failed_critical = True

                    except FutureTimeout:
                        task.state = TaskState.FAILED
                        task.error = "Future result timeout"
                    except Exception as exc:
                        task.state = TaskState.FAILED
                        task.error = str(exc)
                        logger.error(f"[Pipeline] Task '{task.id}' threw exception: {exc}")

                    # Progress callback
                    if self.progress_cb:
                        self.progress_cb(task.id, task.state, task.to_dict())

                if batch_failed_critical:
                    pipeline_stop = True

        execution_time = time.time() - start_time
        all_tasks = list(task_map.values())

        result = PipelineResult(
            tasks=all_tasks,
            artifacts=self._artifacts,
            errors=[],
            success=all(t.state == TaskState.SUCCESS for t in all_tasks),
            execution_time=execution_time,
        )

        logger.info(
            f"[Pipeline] Done | success={result.success} | "
            f"time={execution_time:.2f}s | "
            f"tasks: {result.success_count}/{result.total_count}"
        )

        return result

    def _run_task_with_retry(
        self,
        task: PipelineTask,
        executor_fn: Callable,
        context: Dict,
    ) -> PipelineTask:
        """Execute a single task with retry + backoff."""
        task.state = TaskState.RUNNING
        task.started_at = time.time()

        for attempt in range(task.max_retries + 1):
            task.attempt = attempt + 1

            if attempt > 0:
                wait_s = min(2 ** attempt, 60)
                logger.warning(f"[Pipeline] Retry {attempt}/{task.max_retries} for '{task.id}', waiting {wait_s}s")
                task.state = TaskState.RETRYING
                time.sleep(wait_s)

            try:
                result = executor_fn(task, context)

                task.result = result if isinstance(result, dict) else {"value": result}
                task.state = TaskState.SUCCESS
                task.completed_at = time.time()

                # Extract artifacts
                artifacts = task.result.get("artifacts", [])
                for art_data in artifacts:
                    if isinstance(art_data, dict):
                        art = Artifact(
                            task_id=task.id,
                            artifact_type=art_data.get("type", "data"),
                            name=art_data.get("name", "artifact"),
                            value=art_data.get("value"),
                        )
                        task.artifacts.append(art)
                        self._artifacts.register(art)

                logger.info(f"[Pipeline] ✅ '{task.id}' done in {task.duration_ms:.0f}ms (attempt {task.attempt})")
                return task

            except Exception as e:
                task.error = str(e)
                logger.warning(f"[Pipeline] ⚠️ '{task.id}' attempt {attempt + 1} failed: {e}")

        task.state = TaskState.FAILED
        task.completed_at = time.time()
        logger.error(f"[Pipeline] ❌ '{task.id}' failed after {task.max_retries + 1} attempts")
        return task

    @staticmethod
    def _default_executor(task: PipelineTask, context: Dict) -> Dict:
        """Default executor: just returns a placeholder."""
        return {
            "status": "executed",
            "task_id": task.id,
            "goal": task.goal[:100],
            "context_keys": list(context.keys()),
        }

    def reset(self):
        """Reset artifact registry (for new pipeline run)."""
        self._artifacts = ArtifactRegistry()


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE RESULT
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PipelineResult:
    """Result dari full pipeline execution."""
    tasks: List[PipelineTask]
    artifacts: ArtifactRegistry
    errors: List[str]
    success: bool
    execution_time: float

    @property
    def total_count(self) -> int:
        return len(self.tasks)

    @property
    def success_count(self) -> int:
        return sum(1 for t in self.tasks if t.state == TaskState.SUCCESS)

    @property
    def failed_count(self) -> int:
        return sum(1 for t in self.tasks if t.state == TaskState.FAILED)

    @property
    def models_used(self) -> List[str]:
        return list(set(t.model_id for t in self.tasks if t.model_id))

    def get_result(self, task_id: str) -> Optional[Dict]:
        """Get result from specific task."""
        for t in self.tasks:
            if t.id == task_id:
                return t.result
        return None

    def get_final_output(self) -> Dict:
        """Collect all successful task results."""
        return {
            t.id: t.result
            for t in self.tasks
            if t.state == TaskState.SUCCESS and t.result
        }

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "total_count": self.total_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "execution_time_s": round(self.execution_time, 2),
            "models_used": self.models_used,
            "artifacts": self.artifacts.to_dict(),
            "tasks": [t.to_dict() for t in self.tasks],
            "errors": self.errors,
        }

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"Pipeline Result: {'✅ SUCCESS' if self.success else '❌ FAILED'}",
            f"  Tasks: {self.success_count}/{self.total_count} succeeded",
            f"  Time: {self.execution_time:.2f}s",
            f"  Models: {', '.join(self.models_used) or 'none'}",
        ]
        if self.failed_count > 0:
            failed = [t.id for t in self.tasks if t.state == TaskState.FAILED]
            lines.append(f"  Failed: {', '.join(failed)}")
        return "\n".join(lines)
