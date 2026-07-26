#!/usr/bin/env python3
"""
ILMA Auto-Learning Trigger Parser v1.0
======================================
Phase 48A — User-Triggered Auto-Learning Control

Parses natural language commands to detect auto-learning activation/deactivation.
Always returns NONE unless trigger is explicitly detected.

Supported languages: Indonesian (primary), English

Detection rules:
- Must contain activation keyword (auto learning, autonomous learning, self improvement, optimasi otomatis, dll)
- STOP/PAUSE/RESUME never start a run (they control state)
- STATUS never starts a run
- Ambiguous commands return NONE
- Duration > 120 requires re-approval
- Forbidden scope requires confirmation
"""

from __future__ import annotations

import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

# ============================================================================
# CONSTANTS
# ============================================================================

MAX_DURATION_WITHOUT_REAPPROVAL = 120  # minutes

# Indonesian activation patterns
ID_ACTIVATION_PATTERNS = [
    r'\bauto\s*learning\b',
    r'\bautonomous\s*learning\b',
    r'\bself\s*improvement\b',
    r'\boptimasi\s*otomatis\b',
    r'\bself[- ]*optimasi\b',
    r'\bpelatihan\s*otomatis\b',
    r'\bbelajar\s*otomatis\b',
    r'\bpembelajaran\s*otomatis\b',
]

# English activation patterns
EN_ACTIVATION_PATTERNS = [
    r'\brun\s+autonomous\s+learning\b',
    r'\bstart\s+auto\s*learning\b',
    r'\bstart\s+autonomous\s+optimization\b',
    r'\brun\s+self[- ]*improvement\b',
    r'\bexecute\s+auto\s*learning\b',
    r'\btrigger\s+autonomous\s+learning\b',
    r'\bstart\s+self[- ]*optimization\b',
]

# STOP patterns
STOP_PATTERNS = [
    r'\bstop\b',
    r'\bhentikan\b',
    r'\bberhenti\b',
    r'\bkill\b',
    r'\bcancel\b',
    r'\bmatikan\b',
]

# PAUSE patterns
PAUSE_PATTERNS = [
    r'\bpause\b',
    r'\bjeda\b',
    r'\bpaused?\b',
    r'\bpause\b',
]

# RESUME patterns
RESUME_PATTERNS = [
    r'\bresume\b',
    r'\blanjutkan\b',
    r'\bteruskan\b',
    r'\bcontinue\b',
]

# STATUS patterns
STATUS_PATTERNS = [
    r'\bstatus\b',
    r'\breport\b',
    r'\bprogress\b',
    r'\bstate\b',
    r'\bapa\s*status\b',
    r'\bcek\s*status\b',
    r'\bhow\s+is\s+it\s+going\b',
]

# Duration patterns (Indonesian)
ID_DURATION_PATTERNS = [
    (r'(\d+)\s*menit\b', 1),
    (r'(\d+)\s*mnt\b', 1),
    (r'(\d+)\s*m\b', 1),
    (r'(\d+)\s*jam\b', 60),
    (r'(\d+)\s*j\b', 60),
    (r'([2-9])\s*jam\b', 60),
    (r'(\d+)\s*hour', 60),
    (r'(\d+)\s*hours?', 60),
]

# Scope patterns
SCOPE_PATTERNS = [
    # Allowed scopes
    (r'\btest\s*(expand|coverage|improvement|expansion)\b', 'test_expansion'),
    (r'\b(registry|evidence)\s*(truth\s*)?audit\b', 'registry_truth_audit'),
    (r'\bdocumentation\s*(consistency|improvement|update)\b', 'documentation_consistency'),
    (r'\b(safe\s*)?refactor(ing)?\b', 'safe_refactor'),
    (r'\blesson\s*(memory|improvement|audit)\b', 'lesson_memory_improvement'),
    (r'\brunner\s*(cleanup|improvement|audit)\b', 'runner_cleanup'),
    (r'\bcode\s*quality\b', 'code_quality_improvement'),
    (r'\bartifact\s*(production|improvement)\b', 'artifact_production'),
    (r'\btrace\s*(validation|audit)\b', 'trace_validation'),
    (r'\bevidence\s*(improvement|audit)\b', 'evidence_improvement'),
    (r'\bself[- ]?improvement\b', 'self_improvement'),
    # Forbidden scopes (require_confirmation)
    (r'\binstall\s*(dependencies?|packages?|deps)\b', 'dependency_install'),
    (r'\bdeploy\s*(production|staging)\b', 'production_deployment'),
    (r'\bdelete\s*(old|files?|code)\b', 'destructive_delete'),
    (r'\bbuild\s*(os|system|kernel)\b', 'os_build'),
    (r'\bpublish\b', 'external_publish'),
    (r'\bsocial\s*media\b', 'social_media_post'),
    (r'\bmigrate\b', 'irreversible_migration'),
    (r'\brotat(e|ing)?\s*keys?\b', 'key_rotation'),
    (r'\bcredential\b', 'credential_use'),
]


# ============================================================================
# DATACLASSES
# ============================================================================

class TriggerAction(Enum):
    NONE = "NONE"
    START = "START"
    STOP = "STOP"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    STATUS = "STATUS"


@dataclass
class TriggerResult:
    is_trigger: bool = False
    action: TriggerAction = TriggerAction.NONE
    duration_minutes: Optional[int] = None
    scope: List[str] = field(default_factory=list)
    forbidden_scope: List[str] = field(default_factory=list)  # NEW: explicitly forbidden
    requires_confirmation: bool = False
    safety_notes: List[str] = field(default_factory=list)
    confidence: float = 0.0
    raw_command: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_trigger": self.is_trigger,
            "action": self.action.value,
            "duration_minutes": self.duration_minutes,
            "scope": self.scope,
            "forbidden_scope": self.forbidden_scope,
            "requires_confirmation": self.requires_confirmation,
            "safety_notes": self.safety_notes,
            "confidence": self.confidence,
            "raw_command": self.raw_command,
        }


# ============================================================================
# PARSER CLASS
# ============================================================================

class AutoLearningTriggerParser:
    """
    Parses natural language commands to detect auto-learning triggers.

    Rules:
    1. STOP always honored (never starts a run)
    2. PAUSE/RESUME never starts a run
    3. STATUS never starts a run
    4. Ambiguous commands return NONE
    5. Duration > 120 requires confirmation
    6. Forbidden scope requires confirmation
    """

    def __init__(self):
        self._id_activation_re = [
            re.compile(p, re.IGNORECASE) for p in ID_ACTIVATION_PATTERNS
        ]
        self._en_activation_re = [
            re.compile(p, re.IGNORECASE) for p in EN_ACTIVATION_PATTERNS
        ]

    def parse(self, command: str) -> TriggerResult:
        """
        Parse a natural language command.

        Args:
            command: The command string to parse

        Returns:
            TriggerResult with parsed information
        """
        cmd = command.strip()
        result = TriggerResult(raw_command=cmd)

        if not cmd:
            return result

        # Check for control commands first (they override activation)
        # NOTE: Control commands (STOP/PAUSE/RESUME/STATUS) never start a run.
        # If command has activation + control, control wins (user controlling session).
        has_activation = self._has_activation(cmd)
        has_stop = self._is_stop_command(cmd)
        has_pause = self._is_pause_command(cmd)
        has_resume = self._is_resume_command(cmd)
        has_status = self._is_status_command(cmd)

        if has_stop:
            result.is_trigger = True
            result.action = TriggerAction.STOP
            result.confidence = 1.0
            return result

        if has_pause:
            result.is_trigger = True
            result.action = TriggerAction.PAUSE
            result.confidence = 1.0
            return result

        if has_resume:
            result.is_trigger = True
            result.action = TriggerAction.RESUME
            result.confidence = 1.0
            return result

        # STATUS never starts a run
        if has_status:
            result.is_trigger = True
            result.action = TriggerAction.STATUS
            result.confidence = 1.0
            return result

        # Check for activation
        if not self._has_activation(cmd):
            return result  # is_trigger=False, action=NONE

        # This is an activation command
        result.is_trigger = True
        result.action = TriggerAction.START
        result.confidence = 0.7

        # Extract duration
        duration = self._extract_duration(cmd)
        result.duration_minutes = duration

        if duration is None:
            result.safety_notes.append(
                "No duration specified. Using default 30 minutes. "
                "Session will be marked as assumed_default."
            )
            result.duration_minutes = 30
            result.safety_notes.append("assumed_default_duration")
            result.confidence = 0.6
        elif duration > MAX_DURATION_WITHOUT_REAPPROVAL:
            result.requires_confirmation = True
            result.safety_notes.append(
                f"Duration {duration} minutes exceeds 120-minute re-approval threshold. "
                "Owner confirmation required."
            )
            result.confidence = 0.8

        # Extract scope (active + forbidden)
        active_scope, forbidden_scope = self._extract_scope(cmd)
        result.scope = active_scope
        result.forbidden_scope = forbidden_scope

        # Check for forbidden scopes that appear in active scope (non-negative)
        # forbidden_scope from negative patterns is already in result.forbidden_scope
        # These are additional items that appeared without negation
        legacy_forbidden = self._check_forbidden_scope(active_scope)
        if legacy_forbidden:
            all_forbidden = list(set(legacy_forbidden + forbidden_scope))
            result.safety_notes.append(
                f"Forbidden action(s) in command: {all_forbidden}. "
                "These are in NEGATIVE context (jangan/don't/no) so session can proceed, "
                "but these actions are blocked at runtime regardless."
            )
            result.confidence = 0.9

        # Check if there are any forbidden items (from either negative or positive context)
        # that would require confirmation
        all_forbidden_items = list(set(legacy_forbidden + forbidden_scope))
        if all_forbidden_items:
            # At least one forbidden action detected
            # If it appeared in positive context (not in forbidden_scope from negation),
            # then requires_confirmation must be True
            positive_forbidden = [f for f in all_forbidden_items if f not in forbidden_scope]
            if positive_forbidden:
                result.requires_confirmation = True

        # Ambiguity check
        if result.confidence < 0.7:
            result.safety_notes.append(
                "Command is ambiguous. Requires explicit owner confirmation."
            )

        return result

    def _has_activation(self, cmd: str) -> bool:
        """Check if command contains activation keyword."""
        for re_pattern in self._id_activation_re + self._en_activation_re:
            if re_pattern.search(cmd):
                return True
        return False

    def _is_stop_command(self, cmd: str) -> bool:
        for pattern in STOP_PATTERNS:
            if re.search(pattern, cmd, re.IGNORECASE):
                return True
        return False

    def _is_pause_command(self, cmd: str) -> bool:
        for pattern in PAUSE_PATTERNS:
            if re.search(pattern, cmd, re.IGNORECASE):
                return True
        return False

    def _is_resume_command(self, cmd: str) -> bool:
        for pattern in RESUME_PATTERNS:
            if re.search(pattern, cmd, re.IGNORECASE):
                return True
        return False

    def _is_status_command(self, cmd: str) -> bool:
        for pattern in STATUS_PATTERNS:
            if re.search(pattern, cmd, re.IGNORECASE):
                return True
        return False

    def _extract_duration(self, cmd: str) -> Optional[int]:
        """Extract duration in minutes from command."""
        for pattern, multiplier in ID_DURATION_PATTERNS:
            match = re.search(pattern, cmd, re.IGNORECASE)
            if match:
                value = int(match.group(1))
                return value * multiplier

        # Also check English patterns
        en_duration = re.search(r'(\d+)\s*minute', cmd, re.IGNORECASE)
        if en_duration:
            return int(en_duration.group(1))

        en_hour = re.search(r'(\d+)\s*hour', cmd, re.IGNORECASE)
        if en_hour:
            return int(en_hour.group(1)) * 60

        return None

    def _extract_scope(self, cmd: str) -> tuple[List[str], List[str]]:
        """Extract scope keywords from command.

        Handles negative patterns (jangan, don't, no, etc.) to classify
        forbidden vs. allowed scope.

        Returns:
            Tuple of (active_scope, forbidden_scope)
        """
        # Negative patterns — words that negate the next action
        NEGATIVE_PATTERNS = [
            r'\bjangan\b', r'\bjanganlah\b',
            r"\bdon't\b", r"\bdo\s*not\b", r"\bdoesn't\b",
            r"\bno\b", r"\bnot\b",
            r"\btidak\b", r"\btidaklah\b",
            r"\bwithout\b",
            r"\bavoid\b", r"\bprevent\b",
            r"\bforbidden\b", r"\bblocked\b",
            r"\bstop\b", r"\bhentikan\b",
            r"\bdisallow\b", r"\bdeny\b",
        ]
        # Compile negative patterns once
        neg_re = [re.compile(p, re.IGNORECASE) for p in NEGATIVE_PATTERNS]

        # Extract all matched scope items with their positions
        matches = []  # [(scope_name, match_start, match_end)]
        for pattern, scope_name in SCOPE_PATTERNS:
            for m in re.finditer(pattern, cmd, re.IGNORECASE):
                matches.append((scope_name, m.start(), m.end()))

        # Sort by position
        matches.sort(key=lambda x: x[1])

        # For each match, check if preceded by a negative word
        active_scope = []
        forbidden_scope = []
        checked_positions = set()

        for scope_name, start, end in matches:
            # Check 20 chars before this match for a negative word
            prefix = cmd[max(0, start-20):start].lower()
            is_negative = any(n.search(prefix) for n in neg_re)

            if is_negative:
                if scope_name not in forbidden_scope:
                    forbidden_scope.append(scope_name)
            else:
                if scope_name not in active_scope:
                    active_scope.append(scope_name)

        return active_scope, forbidden_scope

    def _check_forbidden_scope(self, scopes: List[str]) -> List[str]:
        """Check if any scope is forbidden."""
        FORBIDDEN_SCOPES = [
            "dependency_install",
            "production_deployment",
            "destructive_delete",
            "os_build",
            "external_publish",
            "social_media_post",
            "irreversible_migration",
            "credential_use",
            "key_rotation",
            "database_migration",
            "network_reconfiguration",
            "security_bypass",
        ]
        return [s for s in scopes if s in FORBIDDEN_SCOPES]


# ============================================================================
# STANDALONE FUNCTIONS
# ============================================================================

def parse_trigger(command: str) -> TriggerResult:
    """Standalone function to parse trigger command."""
    parser = AutoLearningTriggerParser()
    return parser.parse(command)


# ============================================================================
# MAIN / DEMO
# ============================================================================

if __name__ == "__main__":
    parser = AutoLearningTriggerParser()

    test_cases = [
        # START triggers
        ("auto learning selama 120 menit", True, "START", 120, []),
        ("auto learning selama 2 jam", True, "START", 120, []),
        ("jalankan autonomous learning 60 menit", True, "START", 60, []),
        ("optimasi otomatis selama 2 jam", True, "START", 120, []),
        ("self improvement 45 menit fokus test coverage", True, "START", 45, ["test_expansion", "self_improvement"]),
        ("run autonomous learning for 30 minutes", True, "START", 30, []),
        ("auto learning 5 menit", True, "START", 5, []),
        # No duration → default 30
        ("auto learning fokus registry audit", True, "START", 30, ["registry_truth_audit"]),
        # STOP
        ("stop auto learning", True, "STOP", None, []),
        ("hentikan autonomous learning", True, "STOP", None, []),
        # PAUSE
        ("pause auto learning", True, "PAUSE", None, []),
        ("jeda auto learning", True, "PAUSE", None, []),
        # RESUME
        ("resume auto learning", True, "RESUME", None, []),
        ("lanjutkan session", True, "RESUME", None, []),
        # STATUS (no start)
        ("apa status auto learning?", True, "STATUS", None, []),
        ("check status", True, "STATUS", None, []),
        # Forbidden scope
        ("auto learning 30 menit install dependencies", True, "START", 30, ["dependency_install"]),
        ("auto learning 30 menit deploy production", True, "START", 30, ["production_deployment"]),
        # Ambiguous
        ("apa kabar?", False, "NONE", None, []),
        ("optimasi saja", False, "NONE", None, []),
        # Too long duration
        ("auto learning selama 180 menit", True, "START", 180, []),
    ]

    print("=" * 70)
    print("ILMA Auto-Learning Trigger Parser — Test Results")
    print("=" * 70)

    passed = 0
    failed = 0

    for cmd, exp_trigger, exp_action, exp_duration, exp_scope in test_cases:
        result = parser.parse(cmd)

        ok = (
            result.is_trigger == exp_trigger
            and result.action.value == exp_action
            and result.duration_minutes == exp_duration
            and set(result.scope) == set(exp_scope)
        )

        status = "✅" if ok else "❌"
        if ok:
            passed += 1
        else:
            failed += 1

        print(f"\n{status} Command: {cmd}")
        print(f"   is_trigger={result.is_trigger} action={result.action.value} "
              f"duration={result.duration_minutes} scope={result.scope}")
        if not ok:
            print(f"   EXPECTED: is_trigger={exp_trigger} action={exp_action} "
                  f"duration={exp_duration} scope={exp_scope}")
            if result.requires_confirmation:
                print(f"   ⚠️  requires_confirmation={result.requires_confirmation} safety_notes={result.safety_notes}")

    print(f"\n{'=' * 70}")
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)