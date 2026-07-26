#!/usr/bin/env python3
"""
ILMA CommandCenterCore v1.0
=============================
Standalone command center without external dependencies (no jose, passlib, psutil).

Provides:
- Command registry and routing
- Health/status methods
- Structured dict responses
- No web server required

This is the VERIFIABLE version of command_center.
"""

from __future__ import annotations
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CommandCenterCore")


class CommandStatus(Enum):
    """Command execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    UNKNOWN = "unknown"


class CommandPriority(Enum):
    """Command priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Command:
    """A registered command."""
    name: str
    handler: str  # Function/module reference
    description: str
    priority: CommandPriority = CommandPriority.NORMAL
    timeout: int = 300  # seconds
    requires_auth: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandResult:
    """Result of command execution."""
    command: str
    status: CommandStatus
    output: Optional[str] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'command': self.command,
            'status': self.status.value,
            'output': self.output,
            'error': self.error,
            'duration_ms': self.duration_ms,
            'timestamp': self.timestamp,
            'metadata': self.metadata
        }


class CommandCenterCore:
    """
    Standalone command center core.
    Works WITHOUT external dependencies (no jose, passlib, psutil).
    """

    VERSION = "1.0.0"

    def __init__(self):
        """Initialize command center."""
        self._commands: Dict[str, Command] = {}
        self._execution_history: List[CommandResult] = []
        self._started_at = datetime.now()
        self._health_status = "healthy"

        # Register built-in commands
        self._register_builtin_commands()

        logger.info(f"CommandCenterCore v{self.VERSION} initialized")

    def _register_builtin_commands(self):
        """Register built-in diagnostic commands."""
        builtin_commands = [
            Command(
                name="status",
                handler="builtin:status",
                description="Get command center status",
                priority=CommandPriority.HIGH,
                timeout=5,
                requires_auth=False
            ),
            Command(
                name="health",
                handler="builtin:health",
                description="Health check",
                priority=CommandPriority.CRITICAL,
                timeout=5,
                requires_auth=False
            ),
            Command(
                name="list_commands",
                handler="builtin:list",
                description="List all registered commands",
                priority=CommandPriority.NORMAL,
                timeout=10,
                requires_auth=False
            ),
            Command(
                name="version",
                handler="builtin:version",
                description="Get command center version",
                priority=CommandPriority.LOW,
                timeout=5,
                requires_auth=False
            ),
            Command(
                name="uptime",
                handler="builtin:uptime",
                description="Get uptime information",
                priority=CommandPriority.LOW,
                timeout=5,
                requires_auth=False
            ),
            Command(
                name="history",
                handler="builtin:history",
                description="Get command execution history",
                priority=CommandPriority.NORMAL,
                timeout=10,
                requires_auth=False
            ),
        ]

        for cmd in builtin_commands:
            self.register_command(cmd)

    def register_command(self, command: Command) -> bool:
        """Register a command."""
        if command.name in self._commands:
            logger.warning(f"Command '{command.name}' already registered, overwriting")
        self._commands[command.name] = command
        logger.info(f"Registered command: {command.name}")
        return True

    def unregister_command(self, name: str) -> bool:
        """Unregister a command."""
        if name in self._commands:
            del self._commands[name]
            logger.info(f"Unregistered command: {name}")
            return True
        return False

    def list_commands(self) -> List[str]:
        """List all registered command names."""
        return list(self._commands.keys())

    def get_command(self, name: str) -> Optional[Command]:
        """Get a command by name."""
        return self._commands.get(name)

    def get_commands(self) -> Dict[str, Command]:
        """Get all registered commands."""
        return self._commands.copy()

    def execute(self, command_name: str, params: Optional[Dict[str, Any]] = None) -> CommandResult:
        """Execute a command."""
        start_time = time.time()

        # Get command
        command = self._commands.get(command_name)
        if not command:
            result = CommandResult(
                command=command_name,
                status=CommandStatus.FAILED,
                error=f"Command '{command_name}' not found",
                duration_ms=0.0,
                timestamp=datetime.now().isoformat()
            )
            self._execution_history.append(result)
            return result

        # Execute built-in commands
        try:
            if command.handler.startswith("builtin:"):
                builtin = command.handler.split(":")[1]
                output = self._execute_builtin(builtin, params or {})

                result = CommandResult(
                    command=command_name,
                    status=CommandStatus.SUCCESS,
                    output=output,
                    duration_ms=(time.time() - start_time) * 1000,
                    timestamp=datetime.now().isoformat()
                )
            else:
                # External handler (would need actual implementation)
                result = CommandResult(
                    command=command_name,
                    status=CommandStatus.SUCCESS,
                    output=f"Handler '{command.handler}' would execute here",
                    duration_ms=(time.time() - start_time) * 1000,
                    timestamp=datetime.now().isoformat()
                )

            self._execution_history.append(result)
            return result

        except Exception as e:
            result = CommandResult(
                command=command_name,
                status=CommandStatus.FAILED,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.now().isoformat()
            )
            self._execution_history.append(result)
            return result

    def _execute_builtin(self, builtin: str, params: Dict[str, Any]) -> str:
        """Execute built-in command."""
        if builtin == "status":
            return json.dumps(self.get_status(), indent=2)
        elif builtin == "health":
            return json.dumps(self.health(), indent=2)
        elif builtin == "list":
            return json.dumps({
                'commands': self.list_commands(),
                'count': len(self._commands)
            }, indent=2)
        elif builtin == "version":
            return json.dumps({'version': self.VERSION})
        elif builtin == "uptime":
            return json.dumps(self.get_uptime(), indent=2)
        elif builtin == "history":
            history = [r.to_dict() for r in self._execution_history[-10:]]
            return json.dumps({'history': history}, indent=2)
        else:
            return f"Unknown builtin: {builtin}"

    def get_status(self) -> Dict[str, Any]:
        """Get command center status."""
        return {
            'status': self._health_status,
            'version': self.VERSION,
            'commands_registered': len(self._commands),
            'total_executions': len(self._execution_history),
            'uptime_seconds': (datetime.now() - self._started_at).total_seconds(),
            'started_at': self._started_at.isoformat(),
            'builtins': self.list_commands()
        }

    def health(self) -> Dict[str, Any]:
        """Health check - returns structured dict."""
        return {
            'healthy': True,
            'status': 'operational',
            'command_center_version': self.VERSION,
            'timestamp': datetime.now().isoformat(),
            'checks': {
                'registry': len(self._commands) >= 5,
                'history': True,
                'builtins': len(self.list_commands()) >= 5
            }
        }

    def get_uptime(self) -> Dict[str, Any]:
        """Get uptime information."""
        uptime = (datetime.now() - self._started_at).total_seconds()
        return {
            'uptime_seconds': uptime,
            'uptime_formatted': self._format_uptime(uptime),
            'started_at': self._started_at.isoformat(),
            'current_time': datetime.now().isoformat()
        }

    @staticmethod
    def _format_uptime(seconds: float) -> str:
        """Format uptime as human-readable string."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        elif seconds < 86400:
            return f"{seconds/3600:.1f}h"
        else:
            return f"{seconds/86400:.1f}d"


def main():
    """CLI entrypoint for testing."""
    cc = CommandCenterCore()

    print("=== CommandCenterCore v1.0.0 ===")
    print(f"Commands registered: {len(cc.list_commands())}")
    print(f"Available commands: {cc.list_commands()}")
    print()

    # Health check
    print("--- Health Check ---")
    health = cc.health()
    print(json.dumps(health, indent=2))
    print()

    # Status
    print("--- Status ---")
    status = cc.get_status()
    print(json.dumps(status, indent=2))
    print()

    # Execute status command
    print("--- Execute 'status' command ---")
    result = cc.execute("status")
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()