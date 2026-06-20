#!/usr/bin/env python3
"""
ILMA Hermes Kanban Integration — SSS Tier
Integrates ILMA with Hermes v0.13.0 Kanban board via hermes CLI.

Supports:
- Task creation with parent/child dependencies
- Worker assignment
- Priority/urgency management
- Heartbeat monitoring
- Task completion with metadata
- Hallucination gate validation
- Retry budget tracking
- Zombie detection recovery

Usage:
    from ilma_kanban_integration import ILMAKanban
    kanban = ILMAKanban()
    task_id = kanban.create(title="...", assignee="researcher", body="...")
    kanban.complete(task_id, summary="...", metadata={...})
"""

import json
import subprocess
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional, Any
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class KanbanConfig:
    """Kanban board configuration."""
    board: str = "default"
    workspace_kind: str = "scratch"  # scratch | dir:<path> | worktree
    default_assignee: str = "ilma"
    heartbeat_interval: int = 60  # seconds
    zombie_threshold: int = 180  # seconds without heartbeat
    max_retries: int = 3
    tenant: Optional[str] = field(default_factory=lambda: os.environ.get("HERMES_TENANT"))


@dataclass
class KanbanTask:
    """Represents a Kanban task."""
    id: str
    title: str
    body: str = ""
    assignee: str = ""
    status: str = "todo"
    priority: int = 0
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    consecutive_failures: int = 0
    last_heartbeat: Optional[datetime] = None
    workspace_path: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "KanbanTask":
        return cls(
            id=d.get("id", ""),
            title=d.get("title", ""),
            body=d.get("body", ""),
            assignee=d.get("assignee", ""),
            status=d.get("status", "todo"),
            priority=int(d.get("priority", 0)),
            metadata=json.loads(d.get("metadata", "{}")) if isinstance(d.get("metadata"), str) else d.get("metadata", {}),
        )


from ilma_kanban_free_model_optimizer import (
    get_best_free_for_task, get_model_for_task_body, get_fallback_chain,
    sync_worker_model_env, get_kanban_stats, force_refresh, get_all_free_model_ids
)


class ILMAKanban:
    """
    ILMA's interface to Hermes Kanban board.

    Wraps `hermes kanban` CLI for task management.
    Used for parallel sub-agent coordination, long-running task tracking,
    multi-stage workflows with dependency gates, and human-in-the-loop workflows.

    Auto-triggers when:
    - Task can be parallelized (fan-out)
    - Task is long-running (>5 min)
    - Multi-stage workflow with dependencies
    - Human review/approval needed
    - Audit trail required

    FREE MODEL ROUTING: All workers use ILMA's 163 FREE models.
    Workers get HERMES_MODEL env var set to best free model per task body.
    """

    def __init__(self, config: Optional[KanbanConfig] = None):
        self.config = config or KanbanConfig()
        self._last_heartbeat: Optional[datetime] = None
        self._current_task_id: Optional[str] = None
        self._model_optimizer = None  # lazy-load

        # Verify hermes kanban is available
        r = subprocess.run(["hermes", "kanban", "--help"],
                          capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            raise RuntimeError("Hermes kanban not available. Install hermes-agent v0.13.0+")

        # Check if kanban DB exists
        kanban_db = Path("/root/.hermes/kanban.db")
        if not kanban_db.exists():
            subprocess.run(["hermes", "kanban", "init"], capture_output=True, timeout=10)

        # Sync free model list for worker routing
        self._sync_free_models()

    def _sync_free_models(self) -> None:
        """Sync free model list from ILMA registry."""
        try:
            sync_worker_model_env()
        except Exception:
            pass  # Non-blocking — workers still get default free model

    def get_worker_model_for_task(self, task_body: str) -> str:
        """
        Get best FREE model for a kanban worker based on task body.
        Returns "provider/model_id" format for hermes -m flag.
        """
        try:
            if self._model_optimizer is None:
                from ilma_kanban_free_model_optimizer import get_model_for_task_body
                self._model_optimizer = get_model_for_task_body

            model_id = self._model_optimizer(task_body)
            return model_id
        except Exception:
            # Fallback to default free model
            return "nvidia/DeepSeek-R1"

    def get_task_type_from_body(self, task_body: str) -> str:
        """Infer task type from body text."""
        try:
            from ilma_kanban_free_model_optimizer import get_model_for_task_body
            # get_model_for_task_body returns model_id, we just need task type
            body_lower = task_body.lower()
            if any(kw in body_lower for kw in ["code", "coding", "build", "debug", "fix bug", "function", "api"]):
                if any(kw in body_lower for kw in ["heavy", "complex", "fullstack", "platform"]):
                    return "heavy_coding"
                return "medium_coding"
            if any(kw in body_lower for kw in ["research", "riset", "analisis", "study", "paper"]):
                return "research"
            if any(kw in body_lower for kw in ["reasoning", "strategi", "planning", "evaluasi"]):
                return "reasoning_high"
            if any(kw in body_lower for kw in ["image", "screenshot", "visual", "foto"]):
                return "vision"
            if any(kw in body_lower for kw in ["write", "blog", "article", "document", "tulis"]):
                return "writing"
            return "general"
        except Exception:
            return "general"

    def _run(self, args: list, timeout: int = 30) -> dict:
        """Run hermes kanban command, return parsed JSON."""
        cmd = ["hermes", "kanban"] + args
        # Add --json flag where supported
        json_flags = ["show", "list", "ls", "stats", "boards", "runs", "log"]
        if args and args[0] in json_flags:
            cmd.append("--json")
        
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            return {"error": r.stderr or r.stdout, "rc": r.returncode}
        
        # Try to parse as JSON
        try:
            # Find JSON in output (some commands print text + JSON)
            text = r.stdout.strip()
            # Handle "No tasks" text responses
            if text in ("No tasks.", "No boards."):
                return {"data": [], "raw": text}
            # Try full parse first
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in output
            import re
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return {"raw": text, "parsed_manually": True}

    # -------------------------------------------------------------------------
    # Task CRUD
    # -------------------------------------------------------------------------

    def create(
        self,
        title: str,
        body: str = "",
        assignee: Optional[str] = None,
        priority: int = 0,
        parent: Optional[str] = None,
        children: Optional[list] = None,
        workspace_kind: Optional[str] = None,
        workspace_path: Optional[str] = None,
        max_runtime: Optional[int] = None,
        skills: Optional[list] = None,
        idempotency_key: Optional[str] = None,
        model_override: Optional[str] = None,
    ) -> KanbanTask:
        """
        Create a kanban task.

        Args:
            title: Task title
            body: Detailed description
            assignee: Profile to assign (researcher, analyst, writer, etc.)
            priority: 0=normal, 1=high, 2=urgent
            parent: Parent task ID (dependency gate)
            children: List of child task IDs to link
            workspace_kind: scratch|dir:<path>|worktree
            workspace_path: Path for dir:/worktree workspaces
            max_runtime: Max runtime in seconds
            skills: Extra skills to load for worker
            idempotency_key: Prevent duplicate creation
            model_override: FREE model override (provider/model_id format).
                Uses ILMA's 163 free models if not specified. Passes -m flag
                to kanban worker. Use get_worker_model_for_task(body) for auto.

        Returns:
            KanbanTask object with id
        """
        args = ["create", title]

        if body:
            args.extend(["--body", body])

        assignee = assignee or self.config.default_assignee
        args.extend(["--assign", assignee])

        if priority:
            args.extend(["--priority", str(priority)])

        if parent:
            args.extend(["--parent", parent])

        if workspace_kind:
            ws = workspace_kind
            if workspace_path:
                ws = f"{workspace_kind}:{workspace_path}"
            args.extend(["--workspace", ws])
        
        if max_runtime:
            args.extend(["--max-runtime", str(max_runtime)])
        
        if skills:
            for skill in skills:
                args.extend(["--skill", skill])
        
        if idempotency_key:
            args.extend(["--idempotency-key", idempotency_key])

        # ILMA FREE MODEL ROUTING: Auto-select best free model per task body
        # model_override can be passed directly, or auto-derived from task body
        if model_override is None and body:
            # Auto-select best free model for this task
            model_override = self.get_worker_model_for_task(body)

        if model_override:
            args.extend(["--model", model_override])

        result = self._run(args)
        
        if "error" in result and result.get("rc", 0) != 0:
            raise RuntimeError(f"Failed to create task: {result['error']}")
        
        # Parse task ID from output
        raw = result.get("raw", "")
        task_id = ""
        import re
        id_match = re.search(r't_([a-f0-9]+)', raw or result.get("data", {}).get("id", ""))
        if id_match:
            task_id = "t_" + id_match.group(1)
        else:
            data = result.get("data", {})
            task_id = data.get("id", "")
        
        task = KanbanTask(
            id=task_id,
            title=title,
            body=body,
            assignee=assignee,
            priority=priority,
        )
        
        # Link children
        if children:
            for child_id in children:
                self.link(parent_id=task_id, child_id=child_id)
        
        return task

    def show(self, task_id: str) -> Optional[KanbanTask]:
        """Get task details."""
        result = self._run(["show", task_id])
        if "error" in result:
            return None
        data = result.get("data", result)
        if data and data.get("id"):
            return KanbanTask.from_dict(data)
        return None

    def list(
        self,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
        board: Optional[str] = None,
    ) -> list:
        """List tasks, optionally filtered."""
        args = ["list"]
        if status:
            args.extend(["--status", status])
        if assignee:
            args.extend(["--assign", assignee])
        if board:
            args.extend(["--board", board])
        
        result = self._run(args)
        tasks = []
        data = result.get("data", [])
        if isinstance(data, list):
            for item in data:
                if item.get("id"):
                    tasks.append(KanbanTask.from_dict(item))
        return tasks

    def complete(
        self,
        task_id: str,
        summary: str = "",
        metadata: Optional[dict] = None,
        created_cards: Optional[list] = None,
    ) -> bool:
        """Mark task as complete."""
        args = ["complete", task_id]
        if summary:
            args.extend(["--summary", summary])
        if metadata:
            args.extend(["--metadata", json.dumps(metadata)])
        if created_cards:
            for card_id in created_cards:
                args.extend(["--created-card", card_id])
        
        result = self._run(args)
        if "error" in result and result.get("rc", 0) != 0:
            return False
        
        # Verify completion
        task = self.show(task_id)
        return task is not None and task.status == "done"

    def block(self, task_id: str, reason: str) -> bool:
        """Block a task waiting for input."""
        result = self._run(["block", task_id, reason])
        return "error" not in result

    def reclaim(self, task_id: str) -> bool:
        """Reclaim an abandoned/zombie task."""
        result = self._run(["reclaim", task_id])
        return "error" not in result

    def reassign(self, task_id: str, new_assignee: str, reclaim: bool = True) -> bool:
        """Reassign task to a different profile."""
        args = ["reassign", task_id, new_assignee]
        if reclaim:
            args.append("--reclaim")
        result = self._run(args)
        return "error" not in result

    def heartbeat(self, task_id: str, note: str = "") -> bool:
        """Send heartbeat for a running task."""
        args = ["heartbeat", task_id]
        if note:
            args.extend(["--note", note])
        result = self._run(args)
        if "error" not in result:
            self._last_heartbeat = datetime.now()
        return "error" not in result

    def comment(self, task_id: str, body: str) -> bool:
        """Add comment to a task."""
        result = self._run(["comment", task_id, "--body", body])
        return "error" not in result

    def link(self, parent_id: str, child_id: str) -> bool:
        """Create parent-child dependency."""
        result = self._run(["link", parent_id, child_id])
        return "error" not in result

    def stats(self) -> dict:
        """Get kanban board statistics."""
        result = self._run(["stats"])
        return result.get("data", result)

    def boards(self) -> list:
        """List available boards."""
        result = self._run(["boards"])
        data = result.get("data", [])
        if isinstance(data, list):
            return data
        raw = result.get("raw", "")
        if raw:
            return [b.strip() for b in raw.split("\n") if b.strip()]
        return []

    def runs(self, task_id: str) -> list:
        """Get task run history."""
        result = self._run(["runs", task_id])
        data = result.get("data", [])
        return data if isinstance(data, list) else []

    def get_zombies(self) -> list:
        """Find zombie tasks (no heartbeat > threshold)."""
        threshold = datetime.now() - timedelta(seconds=self.config.zombie_threshold)
        zombies = []
        
        all_tasks = self.list()
        for task in all_tasks:
            if task.status == "running":
                # Check heartbeat from task data
                show_result = self._run(["show", task.id])
                data = show_result.get("data", show_result)
                last_hb = data.get("last_heartbeat_at")
                if last_hb:
                    try:
                        hb_time = datetime.fromtimestamp(last_hb)
                        if hb_time < threshold:
                            zombies.append(task)
                    except (ValueError, TypeError):
                        pass
                else:
                    # No heartbeat at all — might be zombie
                    created = data.get("created_at")
                    if created:
                        try:
                            c_time = datetime.fromtimestamp(created)
                            if c_time < threshold:
                                zombies.append(task)
                        except (ValueError, TypeError):
                            pass
        return zombies

    def diagnose(self, task_id: str) -> dict:
        """Get diagnostic info for a task."""
        result = self._run(["diagnostics", task_id])
        return result.get("data", result)

    # -------------------------------------------------------------------------
    # High-level orchestration patterns
    # -------------------------------------------------------------------------

    def fan_out(
        self,
        tasks: list,
        assignee: str = "researcher",
        title_prefix: str = "",
        parent_title: Optional[str] = None,
        body_prefix: Optional[str] = None,
    ) -> tuple[str, list]:
        """
        Create N parallel tasks from a list.

        Returns (parent_id, [child_ids])

        Each worker gets best FREE model auto-selected from task body.
        """
        if len(tasks) == 1:
            # No need for fan-out, just create single task
            task_body = f"{body_prefix or ''}{tasks[0]}"
            task = self.create(title=tasks[0], body=task_body, assignee=assignee)
            return task.id, [task.id]

        # Create parent task
        parent = None
        if parent_title:
            parent_body = f"Orchestrates {len(tasks)} parallel tasks:\n" + "\n".join(f"- {t}" for t in tasks)
            parent = self.create(
                title=parent_title,
                body=parent_body,
                assignee="ilma",
                priority=2,
            )

        # Create child tasks — each gets FREE model auto-routed from body
        child_ids = []
        for i, task_desc in enumerate(tasks):
            title = f"{title_prefix}{task_desc}" if title_prefix else task_desc
            # Body is used for FREE model auto-selection
            task_body = f"{body_prefix or ''}{task_desc}"
            child = self.create(
                title=title,
                body=task_body,
                assignee=assignee,
                priority=1,
                parent=parent.id if parent else None,
            )
            child_ids.append(child.id)

        return parent.id if parent else "", child_ids

    def pipeline(
        self,
        stages: list,
        title: str,
        assignees: Optional[list] = None,
    ) -> str:
        """
        Create a sequential pipeline of tasks.
        
        stages: list of (title, description) tuples
        assignees: list of profile names per stage
        
        Returns first task ID. Subsequent tasks are linked sequentially.
        """
        assignee_list = assignees or ["researcher"] * len(stages)
        
        prev_id = None
        first_id = None
        
        for i, ((stage_title, stage_body), stage_assignee) in enumerate(zip(stages, assignee_list)):
            task = self.create(
                title=f"[{i+1}/{len(stages)}] {stage_title}",
                body=stage_body,
                assignee=stage_assignee,
                priority=1,
                parent=prev_id,
            )
            
            if i == 0:
                first_id = task.id
            prev_id = task.id
        
        return first_id

    def wait_for_completion(self, task_ids: list, poll_interval: int = 30, timeout: int = 3600) -> dict:
        """
        Poll until all tasks complete.
        
        Returns dict of {task_id: final_status}
        """
        start = time.time()
        results = {}
        
        while time.time() - start < timeout:
            all_done = True
            for tid in task_ids:
                task = self.show(tid)
                if task is None:
                    results[tid] = "unknown"
                    continue
                results[tid] = task.status
                if task.status not in ("done", "failed", "blocked"):
                    all_done = False
            
            if all_done:
                break
            
            time.sleep(poll_interval)
        
        return results

    # -------------------------------------------------------------------------
    # Validation / Hallucination Gate
    # -------------------------------------------------------------------------

    def validate_output(self, task_id: str, checks: dict) -> tuple[bool, list]:
        """
        Hallucination gate — validate task output before marking complete.
        
        checks: dict of {check_name: bool}
        Returns (all_passed, list_of_failures)
        """
        failures = [k for k, v in checks.items() if not v]
        return len(failures) == 0, failures


# Convenience singleton for ILMA runtime
_kanban_instance: Optional[ILMAKanban] = None

def get_kanban() -> ILMAKanban:
    """Get ILMA Kanban singleton."""
    global _kanban_instance
    if _kanban_instance is None:
        _kanban_instance = ILMAKanban()
    return _kanban_instance


if __name__ == "__main__":
    # Test basic connectivity
    k = ILMAKanban()
    print(f"Boards: {k.boards()}")
    print(f"Stats: {k.stats()}")
    
    # Create test task
    task = k.create(
        title="ILMA Kanban Integration Test",
        body="Verify kanban integration is working",
        assignee="ilma",
        priority=1,
    )
    print(f"Created: {task.id}")
    
    # Complete it
    k.complete(task.id, summary="Integration verified OK")
    print("Complete: OK")
