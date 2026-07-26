#!/usr/bin/env python3
"""
ILMA Auto-Learning Session Manager v1.0
=======================================
Phase 48A — User-Triggered Auto-Learning Control

Manages auto-learning sessions with:
- State machine: IDLE → ARMED → RUNNING → PAUSED → COMPLETED/STOPPED/BLOCKED/FAILED_SAFE
- Duration enforcement
- Scope enforcement
- Checkpoint system
- Stop/Pause/Resume control
- Export session report
"""

from __future__ import annotations

import json
import uuid
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum

from ilma_autolearning_trigger import TriggerResult, TriggerAction, parse_trigger


# ============================================================================
# CONSTANTS
# ============================================================================

SESSION_STATE_FILE = "memory/ilma_autolearning_session.json"
SESSION_LOG_DIR = "evidence/autolearning_sessions/"
MAX_DURATION_MINUTES = 120
DEFAULT_CHECKPOINT_INTERVAL = 10  # minutes


# ============================================================================
# ENUMS
# ============================================================================

class SessionState(Enum):
    IDLE = "IDLE"
    ARMED = "ARMED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    BLOCKED = "BLOCKED"
    FAILED_SAFE = "FAILED_SAFE"


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class Checkpoint:
    checkpoint_id: str
    timestamp: str
    elapsed_minutes: float
    actions_taken: int
    current_scope: List[str]
    state: str
    notes: str = ""


@dataclass
class SessionData:
    session_id: str
    owner_command: str
    duration_minutes: int
    scope: List[str]
    start_time: Optional[str] = None
    deadline: Optional[str] = None
    checkpoints: List[Dict] = field(default_factory=list)
    actions_taken: List[str] = field(default_factory=list)
    blocked_actions: List[Dict] = field(default_factory=list)
    lessons_created: List[str] = field(default_factory=list)
    files_changed: List[str] = field(default_factory=list)
    tests_run: int = 0
    final_status: str = "IDLE"
    stop_reason: str = ""
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# SESSION MANAGER CLASS
# ============================================================================

class AutoLearningSessionManager:
    """
    Manages auto-learning sessions with full lifecycle control.

    State transitions:
    IDLE → ARMED (trigger parsed, awaiting start)
    ARMED → RUNNING (explicit start)
    RUNNING → PAUSED (owner pause)
    RUNNING → COMPLETED (duration expired)
    RUNNING → STOPPED (owner stop)
    RUNNING → BLOCKED (forbidden action)
    RUNNING → FAILED_SAFE (unrecoverable error)
    PAUSED → RUNNING (owner resume)
    PAUSED → STOPPED (owner stop from pause)
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._session: Optional[SessionData] = None
        self._state = SessionState.IDLE
        self._timer_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._checkpoint_count = 0
        self._on_checkpoint: Optional[Callable] = None
        self._on_complete: Optional[Callable] = None

        # Ensure directories exist
        Path(SESSION_LOG_DIR).mkdir(parents=True, exist_ok=True)
        Path("memory").mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------------

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def session_id(self) -> Optional[str]:
        return self._session.session_id if self._session else None

    @property
    def is_active(self) -> bool:
        return self._state in [SessionState.ARMED, SessionState.RUNNING, SessionState.PAUSED]

    @property
    def remaining_minutes(self) -> Optional[float]:
        if self._session and self._session.deadline:
            deadline = datetime.fromisoformat(self._session.deadline)
            remaining = (deadline - datetime.now()).total_seconds() / 60
            return max(0, remaining)
        return None

    # ------------------------------------------------------------------------
    # Session Lifecycle
    # ------------------------------------------------------------------------

    def create_session(self, trigger: TriggerResult, owner_command: str | None = None) -> SessionData:
        """Create a new session from parsed trigger.

        Args:
            trigger: Parsed TriggerResult from the trigger parser
            owner_command: Optional explicit owner command string. If not provided,
                           defaults to trigger.raw_command.

        Returns:
            SessionData with session_id assigned and state set to ARMED.
        """
        session_id = str(uuid.uuid4())[:8]
        start_time = datetime.now().isoformat()
        deadline = datetime.now() + timedelta(minutes=trigger.duration_minutes)

        # Use explicit owner_command if provided, otherwise fall back to raw_command
        effective_command = owner_command if owner_command is not None else trigger.raw_command

        session = SessionData(
            session_id=session_id,
            owner_command=effective_command,
            duration_minutes=trigger.duration_minutes,
            scope=trigger.scope if trigger.scope else ["test_expansion", "evidence_improvement"],
            start_time=start_time,
            deadline=deadline.isoformat(),
        )

        self._session = session
        self._state = SessionState.ARMED

        self._persist_session()
        return session

    def start_session(self) -> bool:
        """Start the armed session. Returns True if started."""
        if self._state != SessionState.ARMED:
            return False

        self._state = SessionState.RUNNING
        self._session.start_time = datetime.now().isoformat()
        self._session.deadline = (datetime.now() + timedelta(minutes=self._session.duration_minutes)).isoformat()
        self._session.final_status = "RUNNING"

        self._stop_event.clear()
        self._start_timer()
        self._persist_session()
        return True

    def pause_session(self) -> bool:
        """Pause the running session."""
        if self._state != SessionState.RUNNING:
            return False

        self._state = SessionState.PAUSED
        self._session.final_status = "PAUSED"
        self._stop_event.set()
        self._add_checkpoint("Session paused by owner")
        self._persist_session()
        return True

    def resume_session(self) -> bool:
        """Resume a paused session."""
        if self._state != SessionState.PAUSED:
            return False

        self._state = SessionState.RUNNING
        self._session.final_status = "RUNNING"
        self._stop_event.clear()

        # Recalculate deadline from pause point
        remaining = self.remaining_minutes
        if remaining and remaining > 0:
            self._session.deadline = (datetime.now() + timedelta(minutes=remaining)).isoformat()

        self._add_checkpoint("Session resumed by owner")
        self._persist_session()
        self._start_timer()
        return True

    def stop_session(self, reason: str = "owner_command") -> bool:
        """Stop the session. Always honored."""
        if self._state not in [SessionState.RUNNING, SessionState.PAUSED, SessionState.ARMED]:
            return False

        self._state = SessionState.STOPPED
        self._session.final_status = "STOPPED"
        self._session.stop_reason = reason
        self._stop_event.set()

        self._add_checkpoint(f"Session stopped: {reason}")
        self._persist_session()
        return True

    def block_session(self, reason: str, blocked_action: str) -> bool:
        """Block session due to forbidden action."""
        if self._state != SessionState.RUNNING:
            return False

        self._state = SessionState.BLOCKED
        self._session.final_status = "BLOCKED"
        self._session.stop_reason = f"blocked: {reason}"
        self._session.blocked_actions.append({
            "action": blocked_action,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        })
        self._stop_event.set()
        self._add_checkpoint(f"Session blocked: {reason}")
        self._persist_session()
        return True

    def fail_safe(self, error: str) -> bool:
        """Fail safely due to unrecoverable error."""
        self._state = SessionState.FAILED_SAFE
        if self._session:
            self._session.final_status = "FAILED_SAFE"
            self._session.error_message = str(error)[:500]
            self._session.stop_reason = "unrecoverable_error"
        self._stop_event.set()
        self._persist_session()
        return True

    # ------------------------------------------------------------------------
    # Timer / Duration Enforcement
    # ------------------------------------------------------------------------

    def _start_timer(self):
        """Start the duration timer thread."""
        if self._timer_thread and self._timer_thread.is_alive():
            self._timer_thread.join(timeout=1)

        self._timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self._timer_thread.start()

    def _timer_loop(self):
        """Timer loop that enforces duration and checkpoints."""
        checkpoint_interval = DEFAULT_CHECKPOINT_INTERVAL * 60  # seconds
        last_checkpoint = time.time()

        while not self._stop_event.is_set():
            if self._stop_event.wait(timeout=1):
                break  # Stop event was set

            # Check duration
            if self.remaining_minutes is not None and self.remaining_minutes <= 0:
                self._state = SessionState.COMPLETED
                self._session.final_status = "COMPLETED"
                self._session.stop_reason = "duration_expired"
                self._add_checkpoint("Duration expired — session complete")
                self._persist_session()
                if self._on_complete:
                    self._on_complete(self._session)
                break

            # Checkpoint
            if time.time() - last_checkpoint >= checkpoint_interval:
                self._add_checkpoint("Scheduled checkpoint")
                self._persist_session()
                if self._on_checkpoint:
                    self._on_checkpoint(self._session)
                last_checkpoint = time.time()

    # ------------------------------------------------------------------------
    # Scope and Action Enforcement
    # ------------------------------------------------------------------------

    def can_perform_action(self, action: str, scope: List[str]) -> tuple[bool, Optional[str]]:
        """
        Check if an action is allowed within current scope.

        Returns (allowed, block_reason)
        """
        if self._state != SessionState.RUNNING:
            return False, "session_not_running"

        # Check scope
        allowed_scopes = self._session.scope if self._session else []

        # Default scopes are always allowed
        DEFAULT_SCOPES = [
            "test_expansion", "evidence_improvement", "registry_truth_audit",
            "documentation_consistency", "safe_refactor", "runner_cleanup",
            "lesson_memory_improvement", "code_quality_improvement",
            "artifact_production", "trace_validation"
        ]

        if not allowed_scopes:
            allowed_scopes = DEFAULT_SCOPES

        # Check if action falls within scope
        action_scope = self._classify_action(action)
        if action_scope and action_scope not in allowed_scopes and action_scope not in DEFAULT_SCOPES:
            return False, f"scope_exceeded: {action_scope} not in {allowed_scopes}"

        # Check forbidden actions
        FORBIDDEN = [
            "dependency_install", "production_deployment", "destructive_delete",
            "os_build", "external_publish", "social_media_post",
            "irreversible_migration", "credential_use", "key_rotation",
            "database_migration", "network_reconfiguration", "security_bypass",
        ]
        if action_scope in FORBIDDEN:
            return False, f"forbidden_action: {action_scope}"

        return True, None

    def _classify_action(self, action: str) -> Optional[str]:
        """Classify an action into scope category."""
        action_lower = action.lower()

        if "install" in action_lower and ("pip" in action_lower or "package" in action_lower or "dependency" in action_lower):
            return "dependency_install"
        if "deploy" in action_lower or "production" in action_lower:
            return "production_deployment"
        if "delete" in action_lower or "remove" in action_lower:
            return "destructive_delete"
        if "build" in action_lower or "os" in action_lower or "kernel" in action_lower:
            return "os_build"
        if "test" in action_lower or "coverage" in action_lower:
            return "test_expansion"
        if "refactor" in action_lower:
            return "safe_refactor"
        if "lesson" in action_lower or "memory" in action_lower:
            return "lesson_memory_improvement"
        if "evidence" in action_lower or "audit" in action_lower:
            return "evidence_improvement"
        if "registry" in action_lower:
            return "registry_truth_audit"
        if "doc" in action_lower or "readme" in action_lower:
            return "documentation_consistency"
        if "runner" in action_lower:
            return "runner_cleanup"

        return "artifact_production"  # Default

    def record_action(self, action: str, details: str = ""):
        """Record an action taken during the session."""
        if self._session:
            self._session.actions_taken.append({
                "action": action,
                "details": details,
                "timestamp": datetime.now().isoformat(),
            })

    def record_blocked(self, action: str, reason: str):
        """Record a blocked action."""
        if self._session:
            self._session.blocked_actions.append({
                "action": action,
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
            })

    # ------------------------------------------------------------------------
    # Checkpoint
    # ------------------------------------------------------------------------

    def checkpoint_session(self, notes: str = ""):
        """Manual checkpoint."""
        self._add_checkpoint(notes)
        self._persist_session()

    def _add_checkpoint(self, notes: str = ""):
        """Add a checkpoint to the session."""
        if not self._session:
            return

        self._checkpoint_count += 1
        elapsed = 0
        if self._session.start_time:
            start = datetime.fromisoformat(self._session.start_time)
            elapsed = (datetime.now() - start).total_seconds() / 60

        cp = Checkpoint(
            checkpoint_id=f"CP-{self._checkpoint_count:03d}",
            timestamp=datetime.now().isoformat(),
            elapsed_minutes=round(elapsed, 2),
            actions_taken=len(self._session.actions_taken),
            current_scope=self._session.scope,
            state=self._state.value,
            notes=notes,
        )
        self._session.checkpoints.append(asdict(cp))

    # ------------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------------

    def _persist_session(self):
        """Save session state to disk."""
        if not self._session:
            return

        data = self._session.to_dict()
        data["state"] = self._state.value

        with open(SESSION_STATE_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    def load_session(self) -> Optional[SessionData]:
        """Load session from disk."""
        if not Path(SESSION_STATE_FILE).exists():
            return None

        try:
            with open(SESSION_STATE_FILE) as f:
                data = json.load(f)

            self._session = SessionData(**data)
            self._state = SessionState(data.get("state", "IDLE"))
            return self._session
        except Exception:
            return None

    def clear_session(self):
        """Clear session state."""
        self._session = None
        self._state = SessionState.IDLE
        self._checkpoint_count = 0
        if Path(SESSION_STATE_FILE).exists():
            Path(SESSION_STATE_FILE).unlink()

    # ------------------------------------------------------------------------
    # Report Export
    # ------------------------------------------------------------------------

    def export_report(self) -> Optional[Dict[str, Any]]:
        """Export session report as dict."""
        if not self._session:
            return None

        report = self._session.to_dict()
        report["state"] = self._state.value
        report["remaining_minutes"] = self.remaining_minutes

        # Save to log file
        log_path = Path(SESSION_LOG_DIR) / f"session_{self._session.session_id}_{self._state.value}.json"
        with open(log_path, 'w') as f:
            json.dump(report, f, indent=2)

        return report

    # ------------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------------

    def set_on_checkpoint(self, callback: Callable):
        """Set callback for checkpoint events."""
        self._on_checkpoint = callback

    def set_on_complete(self, callback: Callable):
        """Set callback for session completion."""
        self._on_complete = callback


# ============================================================================
# STANDALONE FUNCTIONS
# ============================================================================

def create_session_from_command(command: str) -> tuple[SessionData, TriggerResult]:
    """Parse command and create session."""
    trigger = parse_trigger(command)
    if not trigger.is_trigger:
        return None, trigger
    if trigger.action != TriggerAction.START:
        return None, trigger

    manager = AutoLearningSessionManager()
    return manager.create_session(trigger), trigger


# ============================================================================
# MAIN / DEMO
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("ILMA Auto-Learning Session Manager — Test")
    print("=" * 60)

    manager = AutoLearningSessionManager()
    manager.clear_session()

    print("\n[TEST 1] Create session from trigger")
    trigger = parse_trigger("auto learning selama 5 menit fokus test expansion")
    session = manager.create_session(trigger)
    print(f"  session_id: {session.session_id}")
    print(f"  state: {manager.state.value}")
    print(f"  duration: {session.duration_minutes} min")
    print(f"  scope: {session.scope}")

    print("\n[TEST 2] Start session")
    manager.start_session()
    print(f"  state: {manager.state.value}")
    print(f"  start_time: {session.start_time}")
    print(f"  deadline: {session.deadline}")

    print("\n[TEST 3] Record action")
    manager.record_action("test_expansion", "Added 3 new tests for phase48a")
    print(f"  actions: {len(session.actions_taken)}")

    print("\n[TEST 4] Check scope enforcement")
    allowed, reason = manager.can_perform_action("run pytest", scope=["test_expansion"])
    print(f"  allowed: {allowed}")
    allowed2, reason2 = manager.can_perform_action("pip install newpackage", scope=["test_expansion"])
    print(f"  install blocked: {not allowed2}, reason: {reason2}")

    print("\n[TEST 5] Checkpoint")
    manager.checkpoint_session("Test checkpoint")
    print(f"  checkpoints: {len(session.checkpoints)}")

    print("\n[TEST 6] Export report")
    report = manager.export_report()
    print(f"  report saved, state: {report.get('state')}")

    print("\n[TEST 7] Stop session")
    manager.stop_session("test complete")
    print(f"  state: {manager.state.value}")
    print(f"  final_status: {session.final_status}")
    print(f"  stop_reason: {session.stop_reason}")

    print("\n[TEST 8] Clear session")
    manager.clear_session()
    print(f"  state: {manager.state.value}")
    print(f"  session: {manager.session_id}")

    print("\n" + "=" * 60)
    print("Session Manager test complete")
    print("=" * 60)