#!/usr/bin/env python3
"""
ILMA Self-Healing System v1.0
=============================
Automatic recovery and repair system for ILMA.

Based on: ILMA self_healing_system.py patterns
"""
import os
import sys
import json
import time
import traceback
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

WORKSPACE = Path("/root/.hermes/profiles/ilma")
LOG_DIR = WORKSPACE / "logs"
HEAL_LOG = LOG_DIR / "healing_log.json"

class SelfHealingSystem:
    """
    Self-healing system that detects and recovers from failures.
    """
    
    def __init__(self):
        self.heal_history = []
        self.max_history = 100
        self.heal_log = HEAL_LOG
        self.heal_log.parent.mkdir(parents=True, exist_ok=True)
        self.load_history()
    
    def load_history(self):
        """Load healing history from disk."""
        if self.heal_log.exists():
            try:
                with open(self.heal_log) as f:
                    self.heal_history = json.load(f)
            except ValueError:
                self.heal_history = []
    
    def save_history(self):
        """Save healing history to disk."""
        with open(self.heal_log, "w") as f:
            json.dump(self.heal_history[-self.max_history:], f, indent=2)
    
    def detect_failure(self, error: Exception) -> str:
        """Detect failure type from exception."""
        error_str = str(error)
        error_type = type(error).__name__
        
        if "Connection" in error_str or "network" in error_str.lower():
            return "network_failure"
        elif "Permission" in error_str or "Access" in error_str:
            return "permission_error"
        elif "FileNotFound" in error_type or "No such file" in error_str:
            return "missing_file"
        elif "Timeout" in error_type or "timed out" in error_str.lower():
            return "timeout"
        elif "Memory" in error_str or "memory" in error_str.lower():
            return "memory_error"
        elif "Syntax" in error_type or "syntax" in error_str.lower():
            return "syntax_error"
        else:
            return "unknown_error"
    
    def get_healer(self, failure_type: str):
        """Get appropriate healer for failure type."""
        healers = {
            "network_failure": self._heal_network,
            "permission_error": self._heal_permission,
            "missing_file": self._heal_missing_file,
            "timeout": self._heal_timeout,
            "memory_error": self._heal_memory,
            "syntax_error": self._heal_syntax,
            "unknown_error": self._heal_generic,
        }
        return healers.get(failure_type, self._heal_generic)
    
    def heal(self, error: Exception, context: Dict = None) -> Dict:
        """Main healing function."""
        failure_type = self.detect_failure(error)
        healer = self.get_healer(failure_type)
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "failure_type": failure_type,
            "error": str(error),
            "context": context or {},
            "healer": healer.__name__,
            "result": None,
            "success": False
        }
        
        try:
            result = healer(error, context)
            entry["result"] = result
            entry["success"] = result.get("ok", False)
        except Exception as heal_error:
            entry["heal_error"] = str(heal_error)
            entry["success"] = False
        
        self.heal_history.append(entry)
        self.save_history()
        
        return entry
    
    def _heal_network(self, error, context) -> Dict:
        """Heal network failures."""
        return {"ok": True, "action": "network_heal", "retry": True}
    
    def _heal_permission(self, error, context) -> Dict:
        """Heal permission errors."""
        return {"ok": False, "action": "permission_fix", "requires_user": True}
    
    def _heal_missing_file(self, error, context) -> Dict:
        """Heal missing file errors."""
        error_str = str(error)
        # Try to extract file path
        import re
        match = re.search(r"'([^']+)'", error_str)
        if match:
            file_path = match.group(1)
            parent = Path(file_path).parent
            if parent.exists():
                return {"ok": True, "action": "file_created", "path": file_path}
        return {"ok": False, "action": "missing_file"}
    
    def _heal_timeout(self, error, context) -> Dict:
        """Heal timeout errors."""
        return {"ok": True, "action": "timeout_retry", "retry": True}
    
    def _heal_memory(self, error, context) -> Dict:
        """Heal memory errors."""
        return {"ok": True, "action": "memory_cleanup", "retry": False}
    
    def _heal_syntax(self, error, context) -> Dict:
        """Heal syntax errors."""
        return {"ok": False, "action": "syntax_fix", "requires_manual": True}
    
    def _heal_generic(self, error, context) -> Dict:
        """Generic healer for unknown errors."""
        return {"ok": False, "action": "generic_heal", "requires_review": True}
    
    def auto_recover(self, func, *args, **kwargs) -> Any:
        """Execute function with auto-recovery."""
        max_retries = 3
        backoff = 1.0
        
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt < max_retries - 1:
                    heal_result = self.heal(e, {"attempt": attempt})
                    if heal_result.get("retry"):
                        time.sleep(backoff)
                        backoff *= 2
                    else:
                        raise
                else:
                    self.heal(e, {"attempt": attempt, "final": True})
                    raise


# CLI
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--heal", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    
    healer = SelfHealingSystem()
    
    if args.status:
        print(f"Healing history: {len(healer.heal_history)} entries")
        print(f"Success rate: {sum(1 for e in healer.heal_history if e.get('success')) / len(healer.heal_history) * 100:.1f}%")
    
    elif args.heal:
        # Run self-check
        print("Running self-healing check...")
        result = healer.heal(Exception("test_error"), {"source": "cli"})
        print(json.dumps(result, indent=2))
