#!/usr/bin/env python3
"""
ILMA Limited Internal Auto-Learning Command Interface
======================================================
Safe command interface for owner-triggered autonomous learning.

NOT always-on. Explicit owner command required for every run.

Commands:
  START   — Trigger auto-learning session (requires explicit owner command)
  STOP    — Stop running session
  PAUSE   — Pause session (preserve queue + checkpoint)
  RESUME  — Resume from pause (reload checkpoint)
  STATUS  — Show current state (NO start, no side-effect)
  TRACE   — Show last trace
  CHECKPOINT — Show active checkpoint
  CANCEL  — Cancel pending confirmation

Version: 1.0.0
Date: 2026-05-10
"""
from __future__ import annotations

import sys
import json
import os
import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List

sys.path.insert(0, 'scripts')

from ilma_autolearning_trigger import AutoLearningTriggerParser, TriggerAction
from ilma_autolearning_session_manager import AutoLearningSessionManager, SessionState


@dataclass
class CommandResult:
    command: str
    success: bool
    state: str
    message: str
    data: dict = field(default_factory=dict)
    blocked_reason: Optional[str] = None
    requires_confirmation: bool = False


class AutoLearnCommandInterface:
    """Safe command interface for ILMA limited internal auto-learning."""

    COMMANDS = ['start', 'stop', 'pause', 'resume', 'status', 'trace', 'checkpoint', 'cancel', 'help']
    FORBIDDEN_SCOPES = [
        'dependency_install', 'production_deployment', 'destructive_delete',
        'os_build', 'external_publish', 'credential_use', 'live_api_posting',
        'risky_service_move', 'mass_rewrite'
    ]
    ALLOWED_SCOPES = [
        'registry_truth_audit', 'evidence_hardening', 'documentation_consistency',
        'runner_count_truth', 'status_semantics_validation', 'lesson_memory_reuse',
        'safe_refactor_plan', 'test_coverage_gap_scan', 'autonomous_evolution_reliability',
        'security_scope_review', 'test_expansion', 'safe_refactor', 'runner_cleanup'
    ]

    def __init__(self):
        self.parser = AutoLearningTriggerParser()
        self.session_mgr = AutoLearningSessionManager()
        self.current_session_id: Optional[str] = None
        self.last_trace_path: Optional[str] = None

    def execute(self, raw_command: str) -> CommandResult:
        """Execute a command string. Returns CommandResult with no side effects on failure."""
        cmd_lower = raw_command.strip().lower()
        tokens = cmd_lower.split()

        if not tokens:
            return CommandResult(
                command=raw_command,
                success=False,
                state="IDLE",
                message="Empty command. Use 'help' for available commands.",
                blocked_reason="invalid_command"
            )

        cmd = tokens[0]

        if cmd == 'help':
            return self._cmd_help()
        elif cmd == 'start':
            return self._cmd_start(raw_command)
        elif cmd == 'stop':
            return self._cmd_stop()
        elif cmd == 'pause':
            return self._cmd_pause()
        elif cmd == 'resume':
            return self._cmd_resume()
        elif cmd == 'status':
            return self._cmd_status()
        elif cmd == 'trace':
            return self._cmd_trace()
        elif cmd == 'checkpoint':
            return self._cmd_checkpoint()
        elif cmd == 'cancel':
            return self._cmd_cancel()
        else:
            return CommandResult(
                command=raw_command,
                success=False,
                state=self._get_current_state(),
                message=f"Unknown command: '{cmd}'. Available: {', '.join(self.COMMANDS)}",
                blocked_reason="invalid_command"
            )

    def _cmd_help(self) -> CommandResult:
        help_text = """ILMA Auto-Learning Command Interface
======================================
NOT always-on. Explicit owner command required.

Commands:
  start <command>     — Trigger auto-learning (requires explicit owner command)
                         Example: "start auto learning selama 30 menit fokus registry truth"
  stop                — Stop running session safely
  pause               — Pause session (preserve queue + checkpoint)
  resume              — Resume from pause (reload checkpoint)
  status              — Show current state (NO start, safe read-only)
  trace               — Show path and summary of last trace
  checkpoint          — Show active checkpoint summary
  cancel              — Cancel pending confirmation
  help                — Show this help

Safety Rules:
  - START requires explicit owner trigger
  - STOP works anytime
  - STATUS never starts a run
  - Invalid commands return BLOCKED_SAFE/INVALID_COMMAND (no crash)
  - Forbidden actions are BLOCKED at runtime

Allowed scopes:
  registry_truth_audit, evidence_hardening, documentation_consistency,
  runner_count_truth, status_semantics_validation, lesson_memory_reuse,
  safe_refactor_plan, test_coverage_gap_scan, autonomous_evolution_reliability,
  security_scope_review

Forbidden scopes (BLOCKED):
  dependency_install, production_deployment, destructive_delete,
  os_build, external_publish, credential_use, live_api_posting,
  risky_service_move, mass_rewrite
"""
        return CommandResult(
            command='help',
            success=True,
            state=self._get_current_state(),
            message=help_text,
            data={'commands': self.COMMANDS}
        )

    def _cmd_start(self, raw_command: str) -> CommandResult:
        """Start auto-learning session. Requires explicit owner command."""
        # Extract actual trigger command (after "start")
        trigger_cmd = raw_command.strip()
        if trigger_cmd.lower().startswith('start '):
            trigger_cmd = trigger_cmd[6:].strip()

        if not trigger_cmd:
            return CommandResult(
                command='start',
                success=False,
                state=self._get_current_state(),
                message="Start requires explicit command. Example: start auto learning selama 30 menit fokus registry truth",
                blocked_reason="missing_trigger_command"
            )

        # Parse trigger
        trigger = self.parser.parse(trigger_cmd)

        # Validate: must be a trigger
        if not trigger.is_trigger:
            return CommandResult(
                command='start',
                success=False,
                state=self._get_current_state(),
                message=f"Command is not a recognized auto-learning trigger. is_trigger=False",
                blocked_reason="not_a_trigger"
            )

        # Validate: must not be an empty command
        if trigger.action == TriggerAction.NONE:
            return CommandResult(
                command='start',
                success=False,
                state=self._get_current_state(),
                message="No valid action detected in command.",
                blocked_reason="no_action"
            )

        # Validate: forbidden scope check
        if trigger.forbidden_scope:
            # Check if any are in active scope (should not be after patch)
            active_forbidden = [f for f in trigger.forbidden_scope if f in trigger.scope]
            if active_forbidden:
                return CommandResult(
                    command='start',
                    success=False,
                    state=self._get_current_state(),
                    message=f"Command contains forbidden actions in active scope: {active_forbidden}. "
                            f"These must be removed or negated.",
                    blocked_reason="forbidden_in_active_scope"
                )

        # Validate: confirmation gate
        if trigger.requires_confirmation:
            return CommandResult(
                command='start',
                success=False,
                state=self._get_current_state(),
                message=f"Command requires explicit owner confirmation before proceeding. "
                        f"Confirmation needed for: {trigger.forbidden_scope or 'high-duration/ambiguous command'}",
                blocked_reason="requires_confirmation",
                requires_confirmation=True
            )

        # Validate: duration check
        if trigger.duration_minutes and trigger.duration_minutes > 120:
            return CommandResult(
                command='start',
                success=False,
                state=self._get_current_state(),
                message=f"Duration {trigger.duration_minutes}min exceeds 120min without re-approval. "
                        f"Max duration without re-approval is 120 minutes.",
                blocked_reason="duration_exceeds_max"
            )

        # All validations passed → create session
        try:
            session = self.session_mgr.create_session(trigger, owner_command=trigger_cmd)
            self.current_session_id = session.session_id

            return CommandResult(
                command='start',
                success=True,
                state=session.final_status,
                message=f"Session started. session_id={session.session_id}, "
                        f"duration={trigger.duration_minutes}min, "
                        f"scope={trigger.scope}, "
                        f"forbidden={trigger.forbidden_scope}",
                data={
                    'session_id': session.session_id,
                    'duration_minutes': trigger.duration_minutes,
                    'active_scope': trigger.scope,
                    'forbidden_scope': trigger.forbidden_scope,
                    'owner_command': trigger_cmd,
                    'trigger_parsed': {
                        'is_trigger': trigger.is_trigger,
                        'action': str(trigger.action),
                        'confidence': trigger.confidence,
                        'requires_confirmation': trigger.requires_confirmation
                    }
                }
            )
        except Exception as e:
            return CommandResult(
                command='start',
                success=False,
                state=self._get_current_state(),
                message=f"Failed to create session: {type(e).__name__}: {e}",
                blocked_reason="session_creation_failed"
            )

    def _cmd_stop(self) -> CommandResult:
        """Stop running session safely."""
        if not self.current_session_id:
            return CommandResult(
                command='stop',
                success=True,
                state=self._get_current_state(),
                message="No active session to stop.",
                data={'session_id': None, 'stopped': False}
            )

        try:
            self.session_mgr.stop_session(self.current_session_id)
            return CommandResult(
                command='stop',
                success=True,
                state='STOPPED',
                message=f"Session {self.current_session_id} stopped safely.",
                data={'session_id': self.current_session_id, 'stopped': True}
            )
        except Exception as e:
            return CommandResult(
                command='stop',
                success=False,
                state=self._get_current_state(),
                message=f"Stop failed: {type(e).__name__}: {e}",
                blocked_reason="stop_failed"
            )

    def _cmd_pause(self) -> CommandResult:
        """Pause session (preserve queue + checkpoint)."""
        if not self.current_session_id:
            return CommandResult(
                command='pause',
                success=True,
                state=self._get_current_state(),
                message="No active session to pause.",
                data={'session_id': None, 'paused': False}
            )

        try:
            self.session_mgr.pause_session(self.current_session_id)
            return CommandResult(
                command='pause',
                success=True,
                state='PAUSED',
                message=f"Session {self.current_session_id} paused. Queue and checkpoint preserved.",
                data={'session_id': self.current_session_id, 'paused': True}
            )
        except Exception as e:
            return CommandResult(
                command='pause',
                success=False,
                state=self._get_current_state(),
                message=f"Pause failed: {type(e).__name__}: {e}",
                blocked_reason="pause_failed"
            )

    def _cmd_resume(self) -> CommandResult:
        """Resume from pause (reload checkpoint)."""
        if not self.current_session_id:
            return CommandResult(
                command='resume',
                success=True,
                state=self._get_current_state(),
                message="No paused session to resume.",
                data={'session_id': None, 'resumed': False}
            )

        try:
            self.session_mgr.resume_session(self.current_session_id)
            return CommandResult(
                command='resume',
                success=True,
                state='RUNNING',
                message=f"Session {self.current_session_id} resumed from checkpoint.",
                data={'session_id': self.current_session_id, 'resumed': True}
            )
        except Exception as e:
            return CommandResult(
                command='resume',
                success=False,
                state=self._get_current_state(),
                message=f"Resume failed: {type(e).__name__}: {e}",
                blocked_reason="resume_failed"
            )

    def _cmd_status(self) -> CommandResult:
        """Show current state — NO start, safe read-only."""
        state = self._get_current_state()
        session_id = self.current_session_id

        status_data = {
            'state': state,
            'session_id': session_id,
            'auto_learning_always_on': False,
            'owner_triggered': True,
            'default_state': 'IDLE',
            'interface_version': '1.0.0'
        }

        if session_id:
            status_data['message'] = f"State: {state}, session_id={session_id}"
        else:
            status_data['message'] = f"State: {state}, no active session"

        return CommandResult(
            command='status',
            success=True,
            state=state,
            message=status_data['message'],
            data=status_data
        )

    def _cmd_trace(self) -> CommandResult:
        """Show path and summary of last trace."""
        trace_dir = 'evidence/evolution_traces/limited_internal'
        trace_files = []
        if os.path.isdir(trace_dir):
            trace_files = sorted([f for f in os.listdir(trace_dir) if f.endswith('.json')])

        if trace_files:
            last_trace = os.path.join(trace_dir, trace_files[-1])
            try:
                with open(last_trace) as f:
                    t = json.load(f)
                summary = {
                    'path': last_trace,
                    'session_id': t.get('session_id', 'unknown'),
                    'run_type': t.get('run_type', 'unknown'),
                    'final_verdict': t.get('final_verdict', 'unknown'),
                    'cycles_completed': t.get('cycles_completed', 0),
                    'exit_code': t.get('exit_code', -1),
                    'errors': t.get('errors', []),
                    'timestamp': t.get('start_time', 'unknown')
                }
                return CommandResult(
                    command='trace',
                    success=True,
                    state=self._get_current_state(),
                    message=f"Last trace: {last_trace}",
                    data=summary
                )
            except Exception as e:
                return CommandResult(
                    command='trace',
                    success=False,
                    state=self._get_current_state(),
                    message=f"Failed to read last trace: {e}",
                    blocked_reason="trace_read_failed"
                )
        else:
            return CommandResult(
                command='trace',
                success=True,
                state=self._get_current_state(),
                message="No traces found in evidence/evolution_traces/limited_internal/",
                data={'path': None, 'count': 0}
            )

    def _cmd_checkpoint(self) -> CommandResult:
        """Show active checkpoint summary."""
        checkpoint_dirs = [
            'evidence/evolution_traces/phase48c_close',
            'evidence/evolution_traces/phase48c',
            'evidence/evolution_traces/phase48b',
            'checkpoints'
        ]

        for d in checkpoint_dirs:
            if os.path.isdir(d):
                files = sorted(os.listdir(d), key=lambda x: os.path.getmtime(os.path.join(d, x)), reverse=True)
                if files:
                    latest = os.path.join(d, files[0])
                    try:
                        mtime = datetime.fromtimestamp(os.path.getmtime(latest))
                        size = os.path.getsize(latest)
                        return CommandResult(
                            command='checkpoint',
                            success=True,
                            state=self._get_current_state(),
                            message=f"Latest checkpoint: {latest} (mtime={mtime.isoformat()}, size={size}bytes)",
                            data={
                                'path': latest,
                                'modified': mtime.isoformat(),
                                'size_bytes': size,
                                'source_dir': d
                            }
                        )
                    except Exception as e:
                        continue

        return CommandResult(
            command='checkpoint',
            success=True,
            state=self._get_current_state(),
            message="No checkpoints found.",
            data={'path': None}
        )

    def _cmd_cancel(self) -> CommandResult:
        """Cancel pending confirmation."""
        # In this implementation, confirmation is resolved at START time.
        # Cancel just clears any pending state.
        return CommandResult(
            command='cancel',
            success=True,
            state=self._get_current_state(),
            message="No pending confirmation to cancel. Use 'status' to check current state.",
            data={'cancelled': True}
        )

    def _get_current_state(self) -> str:
        """Get current session state or IDLE."""
        if self.current_session_id:
            try:
                session = self.session_mgr.get_session(self.current_session_id)
                if session:
                    return session.final_status
            except Exception:
                pass
        return "IDLE"


def main():
    """CLI entrypoint."""
    if len(sys.argv) < 2:
        # Interactive mode or piped input
        print("ILMA Auto-Learning Command Interface")
        print("Usage: python3 ilma_autolearning_command_interface.py <command>")
        print("Commands: start, stop, pause, resume, status, trace, checkpoint, cancel, help")
        print()
        print("Example:")
        print("  python3 ilma_autolearning_command_interface.py 'start auto learning selama 30 menit fokus registry truth'")
        print("  python3 ilma_autolearning_command_interface.py 'status'")
        print("  python3 ilma_autolearning_command_interface.py 'help'")
        sys.exit(0)

    raw = ' '.join(sys.argv[1:])
    iface = AutoLearnCommandInterface()
    result = iface.execute(raw)

    print(f"Command: {result.command}")
    print(f"Success: {result.success}")
    print(f"State: {result.state}")
    print(f"Message: {result.message}")
    if result.blocked_reason:
        print(f"Blocked: {result.blocked_reason}")
    if result.requires_confirmation:
        print(f"Requires confirmation: True")
    if result.data:
        print(f"Data: {json.dumps(result.data, indent=2)}")

    sys.exit(0 if result.success else 1)


if __name__ == '__main__':
    main()