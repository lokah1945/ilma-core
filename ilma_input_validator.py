#!/usr/bin/env python3
"""
ILMA Input Validator v1.0 (Phase 1.2.4)
========================================
Validates user input before it reaches the orchestrator. Blocks:
- Excessive length (default max 10000 chars)
- Disallowed code-execution patterns (exec, eval, os.system, subprocess, __import__)
- Prompt injection patterns (ignore previous, DAN, jailbreak)
- Tool command whitelisting (optional)

Feature flag: config.yaml `input_validation_enabled` (default: True)

Usage:
    from ilma_input_validator import validate_input, InputValidationError
    try:
        validate_input(user_message)
    except InputValidationError as e:
        # handle invalid input
        ...

Author: ILMA v3.0
Audit: AUDIT-ILMA-20260616 / Phase 1.2.4
"""

from __future__ import annotations

import re
from typing import Optional


class InputValidationError(Exception):
    """Raised when input fails validation."""
    pass


# Maximum input length (chars)
MAX_INPUT_LENGTH = 10_000

# Disallowed code-execution patterns
DISALLOWED_PATTERNS = [
    re.compile(r"\bexec\s*\(", re.IGNORECASE),
    re.compile(r"\beval\s*\(", re.IGNORECASE),
    re.compile(r"\bos\.system\s*\(", re.IGNORECASE),
    re.compile(r"\bsubprocess\.", re.IGNORECASE),
    re.compile(r"\b__import__\s*\(", re.IGNORECASE),
    re.compile(r"\bcompile\s*\(", re.IGNORECASE),
    re.compile(r"\bopen\s*\(\s*['\"]\/", re.IGNORECASE),  # absolute path file open
]

# Prompt injection patterns
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions?", re.IGNORECASE),
    re.compile(r"forget\s+(?:all\s+)?(?:previous|prior)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:DAN|jailbreak|developer\s+mode)", re.IGNORECASE),
    re.compile(r"disregard\s+(?:your|all)\s+(?:rules|guidelines)", re.IGNORECASE),
    re.compile(r"system\s+prompt\s+override", re.IGNORECASE),
    re.compile(r"pretend\s+you\s+have\s+no\s+restrictions", re.IGNORECASE),
]

# Phase P / TASK 1.1: SQL injection patterns (Phase R found this gap)
SQL_INJECTION_PATTERNS = [
    re.compile(r";\s*DROP\s+TABLE", re.IGNORECASE),
    re.compile(r";\s*DELETE\s+FROM", re.IGNORECASE),
    re.compile(r";\s*INSERT\s+INTO", re.IGNORECASE),
    re.compile(r";\s*UPDATE\s+\w+\s+SET", re.IGNORECASE),
    re.compile(r"UNION\s+SELECT", re.IGNORECASE),
    re.compile(r"OR\s+1\s*=\s*1", re.IGNORECASE),
    re.compile(r"'\s*OR\s*'", re.IGNORECASE),
    re.compile(r"--\s+", re.IGNORECASE),  # SQL comment after statement
    re.compile(r"/\*.*?\*/", re.IGNORECASE),  # /* block comment */
    re.compile(r"\bEXEC\s*\(", re.IGNORECASE),  # SQL EXEC
    re.compile(r"\bxp_\w+", re.IGNORECASE),  # SQL Server extended procs
    re.compile(r"\bbenchmark\s*\(", re.IGNORECASE),  # MySQL DoS
    re.compile(r"\bsleep\s*\(\s*\d+\s*\)", re.IGNORECASE),  # Time-based blind
]


def validate_input(text: str, max_length: int = MAX_INPUT_LENGTH) -> str:
    """Validate user input. Returns the cleaned text or raises InputValidationError."""
    if not isinstance(text, str):
        raise InputValidationError(f"Input must be str, got {type(text).__name__}")
    if not text or not text.strip():
        raise InputValidationError("Input is empty")
    if len(text) > max_length:
        raise InputValidationError(
            f"Input too long: {len(text)} chars (max {max_length})"
        )
    for pat in DISALLOWED_PATTERNS:
        if pat.search(text):
            raise InputValidationError(f"Disallowed pattern: {pat.pattern}")
    for pat in INJECTION_PATTERNS:
        if pat.search(text):
            raise InputValidationError(f"Prompt injection detected: {pat.pattern}")
    for pat in SQL_INJECTION_PATTERNS:
        if pat.search(text):
            raise InputValidationError(f"SQL injection detected: {pat.pattern}")
    return text.strip()


# Whitelisted tool commands (optional)
ALLOWED_TOOL_COMMANDS = {
    "ls", "cat", "head", "tail", "grep", "find", "wc", "df", "du",
    "ps", "top", "uname", "date", "whoami", "pwd", "echo", "env",
    "git", "pip", "python3", "node",
}


def validate_tool_command(cmd: str) -> str:
    """Validate tool command is in the whitelist."""
    first_token = cmd.strip().split(maxsplit=1)[0] if cmd.strip() else ""
    if first_token not in ALLOWED_TOOL_COMMANDS:
        raise InputValidationError(
            f"Tool command not whitelisted: {first_token!r}. "
            f"Allowed: {sorted(ALLOWED_TOOL_COMMANDS)}"
        )
    return cmd


if __name__ == "__main__":
    # Smoke test
    test_cases = [
        ("Hello world", True),
        ("x" * 10_001, False),
        ("please exec('rm -rf /')", False),
        ("ignore previous instructions and...", False),
        ("What's the weather?", True),
    ]
    for text, should_pass in test_cases:
        try:
            validate_input(text)
            result = "PASS"
        except InputValidationError as e:
            result = f"BLOCKED: {e}"
        status = "✓" if (should_pass and "PASS" in result) or (not should_pass and "BLOCKED" in result) else "✗"
        print(f"{status} {text[:40]!r} → {result}")
