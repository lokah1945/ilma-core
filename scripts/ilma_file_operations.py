#!/usr/bin/env python3
"""
ILMA File Operations — Minimal sandboxed file operations
Phase 38E: NEEDS_SMALL_SCRIPT implementation

NOT CLAIMED:
- Network operations
- Execution of files
- Directory deletion outside sandbox
- Cross-filesystem operations
"""
import os
import re
from pathlib import Path
from typing import List, Optional

# Sandbox: only allow operations within ILMA base
BASE = "/root/.hermes/profiles/ilma"

def _sanitize_path(path: str) -> Optional[str]:
    """Ensure path is within sandbox."""
    try:
        # Resolve to absolute, check within BASE
        abs_path = os.path.abspath(os.path.join(BASE, path.lstrip('/')))
        if abs_path.startswith(BASE):
            return abs_path
        return None
    except Exception:
        return None

def safe_read(path: str) -> str:
    """
    Read file within sandbox.
    Returns content or raises ValueError.
    """
    safe_path = _sanitize_path(path)
    if not safe_path:
        raise ValueError(f"Path outside sandbox: {path}")
    if not os.path.isfile(safe_path):
        raise ValueError(f"Not a file: {path}")
    with open(safe_path, 'r') as f:
        return f.read()

def safe_write(path: str, content: str) -> bool:
    """
    Write content to file within sandbox.
    Returns True on success.
    """
    safe_path = _sanitize_path(path)
    if not safe_path:
        raise ValueError(f"Path outside sandbox: {path}")
    # Create parent dirs
    os.makedirs(os.path.dirname(safe_path), exist_ok=True)
    with open(safe_path, 'w') as f:
        f.write(content)
    return True

def safe_append(path: str, content: str) -> bool:
    """Append content to file within sandbox."""
    safe_path = _sanitize_path(path)
    if not safe_path:
        raise ValueError(f"Path outside sandbox: {path}")
    os.makedirs(os.path.dirname(safe_path), exist_ok=True)
    with open(safe_path, 'a') as f:
        f.write(content)
    return True

def safe_list_dir(path: str = ".") -> List[str]:
    """
    List directory contents within sandbox.
    Returns list of filenames.
    """
    safe_path = _sanitize_path(path) or BASE
    if not os.path.isdir(safe_path):
        raise ValueError(f"Not a directory: {path}")
    return sorted(os.listdir(safe_path))

def safe_exists(path: str) -> bool:
    """Check if path exists within sandbox."""
    safe_path = _sanitize_path(path)
    return safe_path is not None and os.path.exists(safe_path)

def safe_is_file(path: str) -> bool:
    """Check if path is a file within sandbox."""
    safe_path = _sanitize_path(path)
    return safe_path is not None and os.path.isfile(safe_path)

def safe_is_dir(path: str) -> bool:
    """Check if path is a directory within sandbox."""
    safe_path = _sanitize_path(path)
    return safe_path is not None and os.path.isdir(safe_path)

def safe_mkdir(path: str) -> bool:
    """Create directory within sandbox."""
    safe_path = _sanitize_path(path)
    if not safe_path:
        raise ValueError(f"Path outside sandbox: {path}")
    os.makedirs(safe_path, exist_ok=True)
    return True

def safe_remove(path: str) -> bool:
    """Remove file within sandbox."""
    safe_path = _sanitize_path(path)
    if not safe_path:
        raise ValueError(f"Path outside sandbox: {path}")
    if not os.path.isfile(safe_path):
        raise ValueError(f"Not a file: {path}")
    os.remove(safe_path)
    return True

def detect_path_traversal(path: str) -> bool:
    """Detect path traversal attempt."""
    return '..' in path or path.startswith('/etc') or path.startswith('/root')

def main():
    """CLI for testing."""
    import sys
    if len(sys.argv) < 2:
        print("Usage: ilma_file_operations.py <command> [args]")
        print("Commands: read <path>, write <path> <content>, list [path], exists <path>")
        sys.exit(1)
    
    cmd = sys.argv[1]
    try:
        if cmd == 'read' and len(sys.argv) >= 3:
            print(safe_read(sys.argv[2]))
        elif cmd == 'write' and len(sys.argv) >= 4:
            safe_write(sys.argv[2], sys.argv[3])
            print("OK")
        elif cmd == 'list':
            path = sys.argv[2] if len(sys.argv) >= 3 else "."
            print('\n'.join(safe_list_dir(path)))
        elif cmd == 'exists':
            print(safe_exists(sys.argv[2]))
        elif cmd == 'traversal':
            print(detect_path_traversal(sys.argv[2]))
        else:
            print("Unknown command")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()