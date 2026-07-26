"""
ILMA Telegram Heartbeat — Phase 4C-R Enhancement
==================================================
Keeps Telegram typing indicator alive during long-running tasks.

Behavior:
- start(task_id, description) → begin heartbeat thread
- stop() → clean stop, no orphan threads
- pulse() → manual checkpoint ping
- Telegram typing action: every 8 seconds
- Progress message: every 60s if task > 2 minutes
- Still-running alert: if no output for 90s

Integration point:
- When Hermes Telegram client is available, set self._send_fn
- Until then, uses local log file as fallback
- Never blocks the main task
"""

from __future__ import annotations

import atexit
import logging
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger("ilma.heartbeat")

# Integration point — set this to the Hermes Telegram send_typing function
# when available. Format: send_typing() -> bool
_TELEGRAM_TYPING_FN: Optional[Callable[[], bool]] = None

# Progress log fallback
_PROGRESS_LOG = Path("/root/.hermes/profiles/ilma/state/heartbeat_progress.log")

# Config
TYPING_INTERVAL_S = 8
PROGRESS_INTERVAL_S = 60
STALLED_ALERT_S = 90
MIN_TASK_DURATION_FOR_PROGRESS_S = 120


def set_telegram_typing_fn(fn: Callable[[], bool]):
    """Call this to wire up the real Telegram typing function."""
    global _TELEGRAM_TYPING_FN
    _TELEGRAM_TYPING_FN = fn
    logger.info("[Heartbeat] Telegram typing function connected.")


class TelegramHeartbeat:
    """
    Background typing indicator + progress heartbeat for long ILMA tasks.

    Thread-safe. Clean shutdown guaranteed via atexit registration.
    Falls back to logging if Telegram not connected.
    """

    _instances: list["TelegramHeartbeat"] = []

    def __init__(self, task_id: Optional[str] = None, description: str = ""):
        self.task_id = task_id or f"task-{uuid.uuid4().hex[:8]}"
        self.description = description
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pulse_event = threading.Event()
        self._started_at: float = 0
        self._last_pulse_at: float = 0
        self._last_progress_at: float = 0
        self._pulse_count: int = 0
        self._running: bool = False
        TelegramHeartbeat._instances.append(self)
        atexit.register(self.stop)

    # ── Public API ──────────────────────────────────────────────────────────────

    def start(self, description: str = "") -> str:
        """Start the heartbeat thread. Returns task_id."""
        if self._running:
            logger.debug(f"[{self.task_id}] Heartbeat already running")
            return self.task_id

        if description:
            self.description = description

        self._stop_event.clear()
        self._pulse_event.clear()
        self._started_at = time.time()
        self._last_pulse_at = self._started_at
        self._last_progress_at = self._started_at
        self._pulse_count = 0
        self._running = True

        self._thread = threading.Thread(target=self._run, name=f"heartbeat-{self.task_id}", daemon=True)
        self._thread.start()

        self._log(f"STARTED — {self.description or 'no description'}")
        return self.task_id

    def stop(self):
        """Stop heartbeat cleanly. Idempotent."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()
        self._pulse_event.set()  # wake thread if waiting

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        TelegramHeartbeat._instances.remove(self)
        try:
            TelegramHeartbeat._instances.index(self)  # raise if still there
        except ValueError:
            pass  # successfully removed

        self._log(f"STOPPED after {self._pulse_count} pulses")

    def pulse(self, checkpoint: str = ""):
        """
        Manual pulse — call this at checkpoints.
        Resets stalled timer and emits a progress log entry.
        """
        self._last_pulse_at = time.time()
        self._pulse_count += 1
        msg = f"PULSE #{self._pulse_count}"
        if checkpoint:
            msg += f" [{checkpoint}]"
        self._log(msg)

    # ── Internal ────────────────────────────────────────────────────────────────

    def _run(self):
        """Heartbeat loop — runs in background thread."""
        while self._running and not self._stop_event.is_set():
            now = time.time()
            elapsed = now - self._started_at

            # Send Telegram typing action
            self._send_typing()

            # Check for stalled task (90s without pulse)
            if now - self._last_pulse_at >= STALLED_ALERT_S:
                self._send_stalled_alert(elapsed)

            # Send periodic progress update (every 60s, only after 2min total)
            if elapsed >= MIN_TASK_DURATION_FOR_PROGRESS_S:
                if now - self._last_progress_at >= PROGRESS_INTERVAL_S:
                    self._send_progress_update(elapsed)
                    self._last_progress_at = now

            # Wait with early wake on pulse or stop
            self._pulse_event.wait(timeout=TYPING_INTERVAL_S)
            self._pulse_event.clear()

    def _send_typing(self):
        """Send Telegram typing action if connected, else log."""
        if _TELEGRAM_TYPING_FN:
            try:
                _TELEGRAM_TYPING_FN()
            except Exception as e:
                logger.debug(f"[{self.task_id}] Typing action failed: {e}")
                self._log(f"TYPING_FAIL: {e}")
        else:
            # Fallback: log heartbeat tick
            elapsed = time.time() - self._started_at
            self._log(f"TICK @ {elapsed:.0f}s")

    def _send_progress_update(self, elapsed_s: float):
        """Send periodic progress message for tasks > 2 minutes."""
        msg = (f"📊 Progress — still running\n"
               f"Task: {self.description or self.task_id}\n"
               f"Duration: {elapsed_s:.0f}s | Pulses: {self._pulse_count}")
        self._log(f"PROGRESS: {elapsed_s:.0f}s, {self._pulse_count} pulses")
        self._send_telegram_message(msg)

    def _send_stalled_alert(self, elapsed_s: float):
        """Alert if no output for 90s — task may be stuck."""
        msg = (f"⚠️ Still running (no output for 90s)\n"
               f"Task: {self.description or self.task_id}\n"
               f"Duration: {elapsed_s:.0f}s")
        self._log(f"STALLED_ALERT @ {elapsed_s:.0f}s")
        self._send_telegram_message(msg)
        # Reset pulse timer so we don't spam
        self._last_pulse_at = time.time()

    def _send_telegram_message(self, text: str):
        """Hook point: send Telegram message if messaging layer available."""
        # TODO(Phase 4C-R): Integrate with Hermes Telegram client when available
        # For now: log to heartbeat_progress.log
        self._log(f"MSG: {text[:80]}")

    def _log(self, msg: str):
        """Write to progress log. Never blocks."""
        try:
            _PROGRESS_LOG.parent.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
            line = f"[{ts}] [{self.task_id}] {msg}\n"
            with open(_PROGRESS_LOG, "a") as f:
                f.write(line)
        except Exception as e:
            logger.debug(f"[{self.task_id}] Log write failed: {e}")


# ── Singleton convenience ──────────────────────────────────────────────────────
_global_heartbeat: Optional[TelegramHeartbeat] = None


def start_heartbeat(description: str = "") -> str:
    """Start the global heartbeat. Returns task_id."""
    global _global_heartbeat
    _global_heartbeat = TelegramHeartbeat(description=description)
    return _global_heartbeat.start(description)


def stop_heartbeat():
    """Stop the global heartbeat."""
    global _global_heartbeat
    if _global_heartbeat:
        _global_heartbeat.stop()
        _global_heartbeat = None


def pulse_heartbeat(checkpoint: str = ""):
    """Pulse the global heartbeat at a checkpoint."""
    if _global_heartbeat:
        _global_heartbeat.pulse(checkpoint)


# ── Integration helpers for ILMA components ───────────────────────────────────

def heartbeat_for_delegate_task(task_id: str, description: str) -> TelegramHeartbeat:
    """
    Start a named heartbeat for a delegate_task or background process.
    Returns the heartbeat instance so caller can call .pulse() at checkpoints.

    Usage:
        hb = heartbeat_for_delegate_task(task_id, "coding worker lane 1")
        # ... task running ...
        hb.pulse("checkpoint: L1 tests pass")
        hb.pulse("checkpoint: L2 diff generated")
        hb.stop()
    """
    hb = TelegramHeartbeat(task_id=task_id, description=description)
    hb.start()
    return hb


# ── Production integration helpers (Phase 4D-A) ──────────────────────────────

def heartbeat_for_terminal(command: str, timeout_s: int = 600) -> TelegramHeartbeat:
    """
    Start heartbeat for a long-running terminal command.

    Usage:
        hb = heartbeat_for_terminal("pytest -v tests/", timeout_s=600)
        # ... run command ...
        hb.stop()
    """
    task_id = f"term-{uuid.uuid4().hex[:8]}"
    desc = f"terminal: {command[:50]}{'...' if len(command) > 50 else ''}"
    hb = TelegramHeartbeat(task_id=task_id, description=desc)
    hb.start(desc)
    logger.info(f"[Heartbeat] Started for terminal: {command[:80]}")
    return hb


def heartbeat_for_coding_worker(worker_lane: str, task_desc: str) -> TelegramHeartbeat:
    """
    Start heartbeat for ILMA coding worker lane.

    Usage:
        hb = heartbeat_for_coding_worker("lane-A", "Implement OAuth2 flow")
        # ... worker runs ...
        hb.pulse("checkpoint: tests pass")
        hb.stop()
    """
    task_id = f"coding-{worker_lane}-{uuid.uuid4().hex[:6]}"
    desc = f"coding/{worker_lane}: {task_desc}"
    hb = TelegramHeartbeat(task_id=task_id, description=desc)
    hb.start(desc)
    logger.info(f"[Heartbeat] Started for coding worker {worker_lane}: {task_desc}")
    return hb


def heartbeat_for_benchmark_runner(benchmark_name: str) -> TelegramHeartbeat:
    """
    Start heartbeat for benchmark execution.

    Usage:
        hb = heartbeat_for_benchmark_runner("aa_2026_06")
        # ... benchmark runs ...
        hb.pulse("checkpoint: 50% done")
        hb.stop()
    """
    task_id = f"bench-{benchmark_name}-{uuid.uuid4().hex[:6]}"
    desc = f"benchmark: {benchmark_name}"
    hb = TelegramHeartbeat(task_id=task_id, description=desc)
    hb.start(desc)
    logger.info(f"[Heartbeat] Started for benchmark: {benchmark_name}")
    return hb


def heartbeat_for_test_runner(test_suite: str) -> TelegramHeartbeat:
    """
    Start heartbeat for test suite execution.

    Usage:
        hb = heartbeat_for_test_runner("tests/test_ilma_core_modules.py")
        # ... tests run ...
        hb.pulse("checkpoint: 10 tests passed")
        hb.stop()
    """
    task_id = f"test-{uuid.uuid4().hex[:8]}"
    desc = f"test suite: {test_suite}"
    hb = TelegramHeartbeat(task_id=task_id, description=desc)
    hb.start(desc)
    logger.info(f"[Heartbeat] Started for test suite: {test_suite}")
    return hb


def heartbeat_for_subagent(task_id_hint: str, description: str) -> TelegramHeartbeat:
    """
    Start heartbeat for subagent delegate_task.

    Usage:
        hb = heartbeat_for_subagent("audit-phase-4d", "Audit reports for Phase 4D")
        # ... subagent runs ...
        hb.pulse("checkpoint: 3/6 done")
        hb.stop()
    """
    task_id = f"subagent-{task_id_hint}-{uuid.uuid4().hex[:6]}"
    hb = TelegramHeartbeat(task_id=task_id, description=description)
    hb.start(description)
    logger.info(f"[Heartbeat] Started for subagent: {task_id_hint}")
    return hb


class HeartbeatContext:
    """
    Context manager wrapping a heartbeat. Auto-starts and auto-stops.

    Usage:
        with HeartbeatContext("test-runner", "pytest tests/") as hb:
            result = run_tests()
            hb.pulse("checkpoint: all done")
    """

    def __init__(self, task_type: str, description: str):
        self.task_type = task_type
        self.description = description
        self.start_time: Optional[float] = None
        self.active: bool = False
        self.hb: Optional[TelegramHeartbeat] = None

    def __enter__(self) -> "TelegramHeartbeat":
        if self.task_type == "terminal":
            self.hb = heartbeat_for_terminal(self.description)
        elif self.task_type == "coding":
            self.hb = heartbeat_for_coding_worker(self.description.split(":", 1)[0].strip() if ":" in self.description else "default", self.description)
        elif self.task_type == "benchmark":
            self.hb = heartbeat_for_benchmark_runner(self.description)
        elif self.task_type == "test":
            self.hb = heartbeat_for_test_runner(self.description)
        else:
            self.hb = heartbeat_for_subagent(self.task_type, self.description)
        self.start_time = self.hb.clock if hasattr(self.hb, 'clock') else None
        self.active = True
        return self.hb  # type: ignore[return-value]

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.active = False
        if self.hb:
            self.hb.pulse(f"exit: {exc_type.__name__ if exc_type else 'success'}")
            self.hb.stop()
        return False

    def to_dict(self) -> dict:
        return {
            "task_type": self.task_type,
            "description": self.description,
            "start_time": self.start_time,
            "active": self.active,
        }


# ── Test / proof of concept ───────────────────────────────────────────────────

def demo_heartbeat(duration_s: int = 30):
    """Run a demo heartbeat for `duration_s` seconds. For testing only."""
    print(f"[Demo] Starting heartbeat for {duration_s}s...")
    hb = TelegramHeartbeat(task_id="demo-heartbeat", description="Demo task")
    hb.start()

    for i in range(duration_s // 10):
        time.sleep(10)
        hb.pulse(f"checkpoint-{i+1}")
        print(f"[Demo] Pulse #{i+1} at {(i+1)*10}s")

    hb.stop()
    print("[Demo] Heartbeat stopped cleanly")

    # Show progress log
    if _PROGRESS_LOG.exists():
        print("\n--- Heartbeat progress log ---")
        print(_PROGRESS_LOG.read_text()[-1000:])


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        demo_heartbeat(int(sys.argv[2]) if len(sys.argv) > 2 else 30)
    else:
        print("ILMA Telegram Heartbeat — Phase 4C-R")
        print("Usage: python ilma_telegram_heartbeat.py --demo [seconds]")
        print("Integration: set_telegram_typing_fn(your_send_typing_fn)")