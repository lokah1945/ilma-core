#!/usr/bin/env python3
"""
ILMA WAL Protocol Automation
============================
Write-Ahead Logging for context preservation in ILMA runtime.

This module implements the WAL (Write-Ahead Logging) protocol for ILMA,
providing persistent logging of critical information before responses
are generated. This ensures context preservation and recovery.

Author: ILMA Runtime System
Version: 1.0.0
"""

import argparse
import logging
import os
import sys
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading
import atexit
import hashlib

# Configuration
# Use explicit path to avoid Path.home() expansion issues
PROFILE_PATH = Path("/root/.hermes/profiles/ilma")
LEARNINGS_PATH = PROFILE_PATH / ".learnings"
WAL_LOG_PATH = LEARNINGS_PATH / "wal_log.md"
WAL_STATE_PATH = LEARNINGS_PATH / "wal_state.json"
CONTEXT_DANGER_THRESHOLD = 0.60  # 60% context usage triggers warning
BUFFER_FLUSH_THRESHOLD = 100  # Number of entries before auto-flush


class WALEntryType(Enum):
    """Types of entries that can be logged to WAL."""
    CORRECTION = "correction"
    PROPER_NOUN = "proper_noun"
    PREFERENCE = "preference"
    DECISION = "decision"
    CONTEXT_SNAPSHOT = "context_snapshot"
    ERROR_RECOVERY = "error_recovery"
    SYSTEM_STATE = "system_state"
    USER_FEEDBACK = "user_feedback"
    LEARNING = "learning"


@dataclass
class WALEntry:
    """Represents a single WAL entry."""
    timestamp: str
    type: str
    content: str
    session_id: Optional[str] = None
    confidence: float = 1.0
    tags: List[str] = field(default_factory=list)
    checksum: Optional[str] = None
    parent_entry_id: Optional[str] = None
    
    def __post_init__(self):
        """Generate checksum after initialization."""
        if self.checksum is None:
            self.checksum = self._generate_checksum()
    
    def _generate_checksum(self) -> str:
        """Generate SHA256 checksum for integrity verification."""
        content = f"{self.timestamp}|{self.type}|{self.content}|{self.session_id or ''}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary."""
        return asdict(self)
    
    def to_markdown(self) -> str:
        """Convert entry to markdown format for WAL log."""
        tags_str = ", ".join(self.tags) if self.tags else "none"
        return f"""## WAL Entry [{self.type.upper()}]

- **Timestamp**: {self.timestamp}
- **Type**: {self.type}
- **Session**: {self.session_id or "global"}
- **Confidence**: {self.confidence:.2f}
- **Tags**: {tags_str}
- **Checksum**: `{self.checksum}`

### Content

{self.content}

---
"""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WALEntry':
        """Create entry from dictionary."""
        return cls(**data)


class WALBuffer:
    """In-memory buffer for WAL entries before flushing."""
    
    def __init__(self, max_size: int = BUFFER_FLUSH_THRESHOLD):
        self.entries: List[WALEntry] = []
        self.max_size = max_size
        self._lock = threading.RLock()
        self.dirty = False
    
    def add(self, entry: WALEntry) -> None:
        """Add entry to buffer."""
        with self._lock:
            self.entries.append(entry)
            self.dirty = True
            if len(self.entries) >= self.max_size:
                self.flush()
    
    def flush(self) -> int:
        """Flush buffer to disk and return number of entries written."""
        with self._lock:
            if not self.entries:
                return 0
            
            count = len(self.entries)
            try:
                self._write_to_log()
                self.entries.clear()
                self.dirty = False
                return count
            except Exception as e:
                logging.error(f"Failed to flush WAL buffer: {e}")
                raise
    
    def _write_to_log(self) -> None:
        """Write buffered entries to WAL log file."""
        LEARNINGS_PATH.mkdir(parents=True, exist_ok=True)
        
        with open(WAL_LOG_PATH, 'a', encoding='utf-8') as f:
            for entry in self.entries:
                f.write(entry.to_markdown())
        
        # Update WAL state
        self._update_state()
    
    def _update_state(self) -> None:
        """Update WAL state file with current statistics."""
        state = {
            "last_flush": datetime.now().isoformat(),
            "entries_buffered": len(self.entries),
            "total_entries": self._get_total_entries() + len(self.entries)
        }
        
        with open(WAL_STATE_PATH, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
    
    def _get_total_entries(self) -> int:
        """Get total entries in WAL log."""
        if not WAL_LOG_PATH.exists():
            return 0
        
        try:
            with open(WAL_LOG_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
                return content.count("## WAL Entry")
        except Exception:
            return 0
    
    def size(self) -> int:
        """Get current buffer size."""
        with self._lock:
            return len(self.entries)
    
    def is_dirty(self) -> bool:
        """Check if buffer has unflushed entries."""
        return self.dirty


class ContextMonitor:
    """Monitor context usage and detect danger zones."""
    
    def __init__(self, danger_threshold: float = CONTEXT_DANGER_THRESHOLD):
        self.danger_threshold = danger_threshold
        self.session_context_sizes: Dict[str, List[int]] = {}
        self._lock = threading.Lock()
    
    def track_response(self, session_id: str, response_size: int) -> None:
        """Track response size for a session."""
        with self._lock:
            if session_id not in self.session_context_sizes:
                self.session_context_sizes[session_id] = []
            self.session_context_sizes[session_id].append(response_size)
    
    def get_context_usage(self, session_id: str, max_context: int = 200000) -> float:
        """
        Calculate approximate context usage for a session.
        
        Args:
            session_id: The session identifier
            max_context: Maximum context window size (default 200k chars)
        
        Returns:
            Float between 0.0 and 1.0 representing usage
        """
        with self._lock:
            if session_id not in self.session_context_sizes:
                return 0.0
            
            total = sum(self.session_context_sizes[session_id])
            return min(total / max_context, 1.0)
    
    def is_in_danger_zone(self, session_id: str, max_context: int = 200000) -> bool:
        """Check if session is in danger zone (>= 60% context usage)."""
        return self.get_context_usage(session_id, max_context) >= self.danger_threshold
    
    def get_warning_level(self, session_id: str, max_context: int = 200000) -> str:
        """Get warning level based on context usage."""
        usage = self.get_context_usage(session_id, max_context)
        
        if usage >= 0.90:
            return "CRITICAL"
        elif usage >= 0.75:
            return "HIGH"
        elif usage >= self.danger_threshold:
            return "WARNING"
        elif usage >= 0.40:
            return "MODERATE"
        else:
            return "NORMAL"
    
    def get_statistics(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get context monitoring statistics."""
        with self._lock:
            if session_id:
                sizes = self.session_context_sizes.get(session_id, [])
                total = sum(sizes)
                count = len(sizes)
                return {
                    "session_id": session_id,
                    "total_responses": count,
                    "total_chars": total,
                    "avg_response_size": total / count if count > 0 else 0,
                    "context_usage": self.get_context_usage(session_id),
                    "danger_zone": self.is_in_danger_zone(session_id)
                }
            else:
                stats = {}
                for sid in self.session_context_sizes:
                    stats[sid] = self.get_statistics(sid)
                return stats


class WALAutomation:
    """
    Main WAL Protocol Automation class.
    
    Provides Write-Ahead Logging for ILMA context preservation,
    with automatic flushing, context monitoring, and integrity verification.
    """
    
    def __init__(
        self,
        wal_log_path: Path = WAL_LOG_PATH,
        danger_threshold: float = CONTEXT_DANGER_THRESHOLD,
        auto_flush: bool = True
    ):
        self.wal_log_path = wal_log_path
        self.buffer = WALBuffer()
        self.context_monitor = ContextMonitor(danger_threshold)
        self.auto_flush = auto_flush
        self.session_id: Optional[str] = None
        self._setup_logging()
        self._register_exit_handler()
        
        # Ensure directories exist
        LEARNINGS_PATH.mkdir(parents=True, exist_ok=True)
    
    def _setup_logging(self) -> None:
        """Configure logging for WAL automation."""
        self.logger = logging.getLogger("ilma.wal")
        self.logger.setLevel(logging.DEBUG)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - WAL - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            
            # Also log to file
            log_dir = PROFILE_PATH / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_dir / "wal_automation.log")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def _register_exit_handler(self) -> None:
        """Register exit handler to flush buffer on shutdown."""
        atexit.register(self._cleanup)
    
    def _cleanup(self) -> None:
        """Cleanup handler for graceful shutdown."""
        if self.buffer.is_dirty():
            self.logger.info("Flushing WAL buffer on shutdown...")
            try:
                self.flush()
            except Exception as e:
                self.logger.error(f"Error flushing on shutdown: {e}")
    
    def set_session(self, session_id: str) -> None:
        """Set the current session ID."""
        self.session_id = session_id
        self.logger.debug(f"Session ID set to: {session_id}")
    
    def log_wal_entry(
        self,
        entry_type: Union[WALEntryType, str],
        content: str,
        session_id: Optional[str] = None,
        confidence: float = 1.0,
        tags: Optional[List[str]] = None
    ) -> WALEntry:
        """
        Log a WAL entry BEFORE responding.
        
        This is the primary interface for logging entries to the WAL.
        Entries are buffered in memory and flushed to disk periodically.
        
        Args:
            entry_type: Type of entry (from WALEntryType enum or string)
            content: The content to log
            session_id: Optional session identifier
            confidence: Confidence score (0.0 to 1.0)
            tags: Optional list of tags
        
        Returns:
            The created WALEntry object
        """
        if isinstance(entry_type, str):
            try:
                entry_type = WALEntryType(entry_type.lower())
            except ValueError:
                entry_type = WALEntryType.LEARNING
        
        session = session_id or self.session_id or "global"
        
        entry = WALEntry(
            timestamp=datetime.now().isoformat(),
            type=entry_type.value,
            content=content,
            session_id=session,
            confidence=confidence,
            tags=tags or [],
            parent_entry_id=None
        )
        
        self.logger.info(f"Logging WAL entry: {entry_type.value} [{session}]")
        self.buffer.add(entry)
        
        # Auto-check danger zone after logging
        if self.auto_flush and entry_type in [
            WALEntryType.CONTEXT_SNAPSHOT,
            WALEntryType.SYSTEM_STATE
        ]:
            self._check_and_warn_danger_zone(session)
        
        return entry
    
    def log_correction(self, original: str, corrected: str, reason: str) -> WALEntry:
        """Log a correction entry."""
        content = f"""**Original**: {original}

**Corrected**: {corrected}

**Reason**: {reason}"""
        return self.log_wal_entry(WALEntryType.CORRECTION, content)
    
    def log_proper_noun(self, noun: str, context: str) -> WALEntry:
        """Log a proper noun (name, place, etc.)."""
        content = f"""**Noun**: {noun}

**Context**: {context}"""
        return self.log_wal_entry(WALEntryType.PROPER_NOUN, content)
    
    def log_preference(self, preference: str, reason: Optional[str] = None) -> WALEntry:
        """Log a user preference."""
        content = f"""**Preference**: {preference}"""
        if reason:
            content += f"\n\n**Reason**: {reason}"
        return self.log_wal_entry(WALEntryType.PREFERENCE, content)
    
    def log_decision(self, decision: str, alternatives: List[str], chosen: str) -> WALEntry:
        """Log a decision made during processing."""
        content = f"""**Decision**: {decision}

**Alternatives considered**:
"""
        for alt in alternatives:
            marker = " [CHOSEN]" if alt == chosen else ""
            content += f"- {alt}{marker}\n"
        
        return self.log_wal_entry(WALEntryType.DECISION, content)
    
    def flush(self) -> int:
        """
        Flush the WAL buffer to permanent storage.
        
        Returns:
            Number of entries flushed
        """
        self.logger.info("Flushing WAL buffer to disk...")
        count = self.buffer.flush()
        self.logger.info(f"Flushed {count} entries to {self.wal_log_path}")
        return count
    
    def check_danger_zone(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Check if context usage is in the danger zone (~60%).
        
        Args:
            session_id: Optional session ID to check
        
        Returns:
            Dictionary with danger zone status and statistics
        """
        session = session_id or self.session_id or "global"
        
        in_danger = self.context_monitor.is_in_danger_zone(session)
        usage = self.context_monitor.get_context_usage(session)
        level = self.context_monitor.get_warning_level(session)
        stats = self.context_monitor.get_statistics(session)
        
        result = {
            "session_id": session,
            "in_danger_zone": in_danger,
            "context_usage": usage,
            "warning_level": level,
            "threshold": self.context_monitor.danger_threshold,
            "recommendation": self._get_recommendation(level)
        }
        
        if in_danger:
            self.logger.warning(
                f"DANGER ZONE: Session {session} at {usage:.1%} context usage "
                f"(threshold: {self.context_monitor.danger_threshold:.0%})"
            )
        
        return result
    
    def _check_and_warn_danger_zone(self, session_id: str) -> None:
        """Internal check for danger zone with auto-logging."""
        result = self.check_danger_zone(session_id)
        if result["in_danger_zone"]:
            self.log_wal_entry(
                WALEntryType.CONTEXT_SNAPSHOT,
                f"Danger zone warning: {result['context_usage']:.1%} context usage. "
                f"Recommendation: {result['recommendation']}",
                session_id=session_id,
                tags=["auto", "danger_zone_warning"]
            )
    
    def _get_recommendation(self, level: str) -> str:
        """Get recommendation based on warning level."""
        recommendations = {
            "CRITICAL": "Immediately flush WAL and compact context. Consider ending session.",
            "HIGH": "Flush WAL buffer and summarize context. Reduce verbosity.",
            "WARNING": "Consider flushing WAL and taking context snapshot.",
            "MODERATE": "Normal operation. Continue monitoring.",
            "NORMAL": "Context usage healthy. No action required."
        }
        return recommendations.get(level, "Unknown level")
    
    def get_wal_statistics(self) -> Dict[str, Any]:
        """Get overall WAL statistics."""
        total_entries = 0
        entries_by_type: Dict[str, int] = {}
        
        if self.wal_log_path.exists():
            try:
                with open(self.wal_log_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    total_entries = content.count("## WAL Entry")
                    
                    for entry_type in WALEntryType:
                        count = content.count(f"- **Type**: {entry_type.value}")
                        if count > 0:
                            entries_by_type[entry_type.value] = count
            except Exception as e:
                self.logger.error(f"Error reading WAL log: {e}")
        
        return {
            "total_entries": total_entries,
            "entries_by_type": entries_by_type,
            "buffered_entries": self.buffer.size(),
            "buffer_dirty": self.buffer.is_dirty(),
            "wal_log_path": str(self.wal_log_path),
            "last_modified": (
                datetime.fromtimestamp(self.wal_log_path.stat().st_mtime).isoformat()
                if self.wal_log_path.exists() else None
            )
        }
    
    def init_wal(self) -> bool:
        """
        Initialize the WAL log file.
        
        Returns:
            True if initialization successful
        """
        try:
            LEARNINGS_PATH.mkdir(parents=True, exist_ok=True)
            
            if not self.wal_log_path.exists():
                # Create new WAL log with header
                header = f"""# ILMA Write-Ahead Log (WAL)
=====================================

**Created**: {datetime.now().isoformat()}
**Version**: 1.0.0
**Purpose**: Context preservation and recovery logging

---

"""
                with open(self.wal_log_path, 'w', encoding='utf-8') as f:
                    f.write(header)
                
                self.logger.info(f"Initialized new WAL log at {self.wal_log_path}")
            else:
                self.logger.info(f"WAL log already exists at {self.wal_log_path}")
            
            # Initialize state file
            if not WAL_STATE_PATH.exists():
                initial_state = {
                    "created": datetime.now().isoformat(),
                    "last_flush": None,
                    "entries_buffered": 0,
                    "total_entries": 0
                }
                with open(WAL_STATE_PATH, 'w', encoding='utf-8') as f:
                    json.dump(initial_state, f, indent=2)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize WAL: {e}")
            return False


def create_cli_parser() -> argparse.ArgumentParser:
    """Create command-line interface parser."""
    parser = argparse.ArgumentParser(
        prog="ilma_wal_automation.py",
        description="ILMA WAL Protocol Automation - Write-Ahead Logging for context preservation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --init                    Initialize WAL log
  %(prog)s --log "correction text" --type correction
                                       Log a correction entry
  %(prog)s --flush                   Flush buffer to disk
  %(prog)s --check                   Check danger zone status
  %(prog)s --stats                   Show WAL statistics
  %(prog)s --session SESSION_ID      Set session ID
        """
    )
    
    parser.add_argument(
        "--init", "-i",
        action="store_true",
        help="Initialize WAL log"
    )
    
    parser.add_argument(
        "--log", "-l",
        type=str,
        help="Content to log"
    )
    
    parser.add_argument(
        "--type", "-t",
        type=str,
        default="learning",
        choices=[e.value for e in WALEntryType],
        help="Type of WAL entry (default: learning)"
    )
    
    parser.add_argument(
        "--flush", "-f",
        action="store_true",
        help="Flush buffer to permanent storage"
    )
    
    parser.add_argument(
        "--check", "-c",
        action="store_true",
        help="Check danger zone status"
    )
    
    parser.add_argument(
        "--stats", "-s",
        action="store_true",
        help="Show WAL statistics"
    )
    
    parser.add_argument(
        "--session", "-S",
        type=str,
        help="Set session ID"
    )
    
    parser.add_argument(
        "--confidence", "-C",
        type=float,
        default=1.0,
        help="Confidence score (0.0 to 1.0, default: 1.0)"
    )
    
    parser.add_argument(
        "--tags",
        type=str,
        help="Comma-separated tags"
    )
    
    parser.add_argument(
        "--proper-noun",
        type=str,
        help="Log a proper noun"
    )
    
    parser.add_argument(
        "--preference",
        type=str,
        help="Log a preference"
    )
    
    parser.add_argument(
        "--decision",
        type=str,
        help="Log a decision"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    return parser


def main() -> int:
    """Main entry point for CLI."""
    parser = create_cli_parser()
    args = parser.parse_args()
    
    # Setup logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create WAL automation instance
    wal = WALAutomation()
    
    # Set session if provided
    if args.session:
        wal.set_session(args.session)
    
    # Handle --init
    if args.init:
        if wal.init_wal():
            print("WAL log initialized successfully.")
            return 0
        else:
            print("Failed to initialize WAL log.", file=sys.stderr)
            return 1
    
    # Handle --log
    if args.log:
        tags = [t.strip() for t in args.tags.split(",")] if args.tags else None
        entry = wal.log_wal_entry(
            args.type,
            args.log,
            confidence=args.confidence,
            tags=tags
        )
        print(f"Logged entry: {entry.checksum}")
        return 0
    
    # Handle --proper-noun
    if args.proper_noun:
        entry = wal.log_proper_noun(args.proper_noun, args.log or "")
        print(f"Logged proper noun: {entry.checksum}")
        return 0
    
    # Handle --preference
    if args.preference:
        entry = wal.log_preference(args.preference, args.log)
        print(f"Logged preference: {entry.checksum}")
        return 0
    
    # Handle --decision
    if args.decision and args.log:
        try:
            alternatives = args.log.split("|")
            entry = wal.log_decision(args.decision, alternatives, alternatives[0])
            print(f"Logged decision: {entry.checksum}")
            return 0
        except Exception as e:
            print(f"Error logging decision: {e}", file=sys.stderr)
            return 1
    
    # Handle --flush
    if args.flush:
        count = wal.flush()
        print(f"Flushed {count} entries to disk.")
        return 0
    
    # Handle --check
    if args.check:
        result = wal.check_danger_zone()
        print(f"\nDanger Zone Check for session: {result['session_id']}")
        print(f"  Context Usage: {result['context_usage']:.1%}")
        print(f"  Warning Level: {result['warning_level']}")
        print(f"  In Danger Zone: {result['in_danger_zone']}")
        print(f"  Threshold: {result['threshold']:.0%}")
        print(f"  Recommendation: {result['recommendation']}")
        return 0
    
    # Handle --stats
    if args.stats:
        stats = wal.get_wal_statistics()
        print("\nWAL Statistics:")
        print(f"  Total Entries: {stats['total_entries']}")
        print(f"  Buffered: {stats['buffered_entries']}")
        print(f"  Buffer Dirty: {stats['buffer_dirty']}")
        print(f"  Log Path: {stats['wal_log_path']}")
        print(f"  Last Modified: {stats['last_modified']}")
        if stats['entries_by_type']:
            print("  Entries by Type:")
            for etype, count in stats['entries_by_type'].items():
                print(f"    {etype}: {count}")
        return 0
    
    # No action specified, show help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
