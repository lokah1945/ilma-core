"""
ILMA CLI Capability - Terminal command execution
Provides safe command execution with streaming output
"""

import subprocess
import shlex
from typing import Tuple, Optional, List

class CLI:
    """Terminal command execution"""
    
    def run(self, command: str, timeout: int = 30, capture: bool = True) -> Tuple[int, str, str]:
        """
        Run terminal command
        Returns: (exit_code, stdout, stderr)
        """
        try:
            if capture:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                return result.returncode, result.stdout, result.stderr
            else:
                result = subprocess.run(command, shell=True, timeout=timeout)
                return result.returncode, "", ""
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return -1, "", str(e)
    
    def run_background(self, command: str) -> subprocess.Popen:
        """Run command in background"""
        return subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    
    def escape(self, text: str) -> str:
        """Escape text for shell"""
        return shlex.quote(text)

# Global instance
_cli = CLI()

def run(command: str, timeout: int = 30) -> Tuple[int, str, str]:
    return _cli.run(command, timeout)

def escape(text: str) -> str:
    return _cli.escape(text)
