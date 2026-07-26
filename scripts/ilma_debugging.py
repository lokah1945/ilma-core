#!/usr/bin/env python3
"""
ILMA Debugging — Minimal error pattern detection and diagnosis
Phase 38E: NEEDS_SMALL_SCRIPT implementation

NOT CLAIMED:
- Full debugging runtime
- Interactive debugger
- Memory profiling
- Breakpoint handling
"""
import re
import traceback
from typing import Dict, Optional, List
from dataclasses import dataclass

@dataclass
class Diagnosis:
    error_type: str
    error_message: str
    likely_cause: str
    suggested_fix: str
    confidence: float  # 0.0 - 1.0

# Known error patterns
ERROR_PATTERNS = [
    {
        'pattern': r"FileNotFoundError: \[Errno 2\] No such file or directory: '([^']+)'",
        'type': 'FileNotFoundError',
        'cause': 'File or directory does not exist',
        'fix': 'Check file path, create parent directories, verify file exists'
    },
    {
        'pattern': r"ModuleNotFoundError: No module named '([^']+)'",
        'type': 'ModuleNotFoundError',
        'cause': 'Python module not installed or not in path',
        'fix': 'Install with: pip install {module} or check PYTHONPATH'
    },
    {
        'pattern': r"SyntaxError: ([^']+)$",
        'type': 'SyntaxError',
        'cause': 'Invalid Python syntax',
        'fix': 'Check syntax: parentheses, colons, indentation, keywords'
    },
    {
        'pattern': r"IndentationError: ([^']+)$",
        'type': 'IndentationError',
        'cause': 'Incorrect indentation',
        'fix': 'Use consistent spaces (4 recommended) or tabs, check mix'
    },
    {
        'pattern': r"TypeError: ([^']+)$",
        'type': 'TypeError',
        'cause': 'Wrong type used in operation',
        'fix': 'Check argument types, convert if needed, verify method signatures'
    },
    {
        'pattern': r"ValueError: ([^']+)$",
        'type': 'ValueError',
        'cause': 'Invalid value provided',
        'fix': 'Check value range, format, constraints'
    },
    {
        'pattern': r"KeyError: '([^']+)'",
        'type': 'KeyError',
        'cause': 'Dictionary key not found',
        'fix': 'Check if key exists, use .get() with default, add key first'
    },
    {
        'pattern': r"IndexError: list index out of range",
        'type': 'IndexError',
        'cause': 'List index exceeds length',
        'fix': 'Check list length before indexing, use len() to validate'
    },
    {
        'pattern': r"AttributeError: '([^']+)' object has no attribute '([^']+)'",
        'type': 'AttributeError',
        'cause': 'Object missing attribute',
        'fix': 'Check attribute name, verify object type, import correct module'
    },
    {
        'pattern': r"PermissionError: \[Errno 13\] Permission denied: '([^']+)'",
        'type': 'PermissionError',
        'cause': 'No permission to access file/directory',
        'fix': 'Check file permissions, run with correct user, chmod/chown'
    },
    {
        'pattern': r"ImportError: ([^']+)$",
        'type': 'ImportError',
        'cause': 'Module import failed',
        'fix': 'Check module name, install dependencies, verify path'
    },
    {
        'pattern': r"ConnectionError|Timeout|HTTPError|URL error",
        'type': 'NetworkError',
        'cause': 'Network connection issue',
        'fix': 'Check internet connection, URL validity, firewall, timeout'
    },
]

def detect_pattern(text: str, pattern: str) -> bool:
    """Check if text matches regex pattern."""
    try:
        return bool(re.search(pattern, text, re.IGNORECASE))
    except Exception:
        return False

def diagnose_error(error_text: str) -> Diagnosis:
    """Diagnose error from text and return structured diagnosis."""
    error_text = str(error_text)
    
    for entry in ERROR_PATTERNS:
        match = re.search(entry['pattern'], error_text, re.IGNORECASE)
        if match:
            cause = entry['cause']
            fix = entry['fix']
            
            # Substitute placeholders
            if '{module}' in fix and match.groups():
                fix = fix.replace('{module}', match.group(1))
            
            return Diagnosis(
                error_type=entry['type'],
                error_message=error_text[:200],
                likely_cause=cause,
                suggested_fix=fix,
                confidence=0.9
            )
    
    # Unknown error
    return Diagnosis(
        error_type='UnknownError',
        error_message=error_text[:200],
        likely_cause='Unknown or complex error',
        suggested_fix='Review error message, search online, check recent changes',
        confidence=0.3
    )

def suggest_fix(error_type: str) -> str:
    """Get suggested fix for known error type."""
    for entry in ERROR_PATTERNS:
        if entry['type'].lower() == error_type.lower():
            return entry['fix']
    return "Review error message, search online, check recent changes"

def parse_traceback(tb_text: str) -> Dict[str, any]:
    """Parse Python traceback and extract info."""
    result = {
        'type': None,
        'message': None,
        'file': None,
        'line': None,
        'function': None
    }
    
    # Extract error type and message
    match = re.search(r'(\w+Error): (.+)', tb_text)
    if match:
        result['type'] = match.group(1)
        result['message'] = match.group(2)
    
    # Extract file and line
    file_match = re.search(r'File "([^"]+)", line (\d+)', tb_text)
    if file_match:
        result['file'] = file_match.group(1)
        result['line'] = int(file_match.group(2))
    
    # Extract function
    func_match = re.search(r'in (\w+)\(', tb_text)
    if func_match:
        result['function'] = func_match.group(1)
    
    return result

def explain_python_error(error_text: str) -> str:
    """Explain Python error in human-readable format."""
    diag = diagnose_error(error_text)
    return f"""
Error Type: {diag.error_type}
Likely Cause: {diag.likely_cause}
Suggested Fix: {diag.suggested_fix}
Confidence: {diag.confidence:.0%}
"""

def main():
    """CLI for testing."""
    import sys
    if len(sys.argv) < 2:
        print("Usage: ilma_debugging.py <command> [args]")
        print("Commands: diagnose <text>, fix <error_type>, pattern <text> <pattern>")
        sys.exit(1)
    
    cmd = sys.argv[1]
    try:
        if cmd == 'diagnose' and len(sys.argv) >= 3:
            diag = diagnose_error(sys.argv[2])
            print(f"Type: {diag.error_type}")
            print(f"Cause: {diag.likely_cause}")
            print(f"Fix: {diag.suggested_fix}")
            print(f"Confidence: {diag.confidence:.0%}")
        elif cmd == 'fix' and len(sys.argv) >= 3:
            print(suggest_fix(sys.argv[2]))
        elif cmd == 'pattern' and len(sys.argv) >= 4:
            result = detect_pattern(sys.argv[2], sys.argv[3])
            print("MATCH" if result else "NO_MATCH")
        else:
            print("Unknown command")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()