#!/usr/bin/env python3
"""
ILMA FILE OPERATIONS CAPABILITY
==============================
File read/write/edit operations as a capability.
"""

import os
import shutil
from pathlib import Path

class FileOps:
    """File operations capability for ILMA."""
    
    def __init__(self, base_path=None):
        self.base_path = Path(base_path) if base_path else Path.home()
    
    def read(self, path):
        """Read a file."""
        path = Path(path)
        if not path.exists():
            return {"error": f"File not found: {path}"}
        
        try:
            content = path.read_text()
            return {
                "success": True,
                "path": str(path),
                "content": content,
                "size": len(content)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def write(self, path, content):
        """Write content to a file."""
        path = Path(path)
        
        try:
            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            return {
                "success": True,
                "path": str(path),
                "size": len(content)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def copy(self, src, dst):
        """Copy a file."""
        src = Path(src)
        dst = Path(dst)
        
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            return {
                "success": True,
                "src": str(src),
                "dst": str(dst)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def move(self, src, dst):
        """Move a file."""
        src = Path(src)
        dst = Path(dst)
        
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return {
                "success": True,
                "src": str(src),
                "dst": str(dst)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def delete(self, path):
        """Delete a file."""
        path = Path(path)
        
        try:
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
            return {"success": True, "path": str(path)}
        except Exception as e:
            return {"error": str(e)}
    
    def list_dir(self, path="."):
        """List directory contents."""
        path = Path(path)
        
        try:
            items = []
            for item in path.iterdir():
                items.append({
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0
                })
            return {
                "success": True,
                "path": str(path),
                "items": items,
                "count": len(items)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def exists(self, path):
        """Check if path exists."""
        return Path(path).exists()
    
    def search(self, path, pattern):
        """Search for files matching pattern."""
        path = Path(path)
        
        try:
            matches = list(path.rglob(pattern))
            return {
                "success": True,
                "pattern": pattern,
                "matches": [str(m) for m in matches],
                "count": len(matches)
            }
        except Exception as e:
            return {"error": str(e)}

# Singleton instance
_file_ops = None

def get_file_ops():
    global _file_ops
    if _file_ops is None:
        _file_ops = FileOps()
    return _file_ops

def execute(task):
    """Execute file operation from task string."""
    ops = get_file_ops()
    
    task_lower = task.lower()
    
    if task_lower.startswith('read '):
        path = task[5:].strip()
        return ops.read(path)
    elif task_lower.startswith('write '):
        parts = task[6:].split(' ', 1)
        if len(parts) == 2:
            return ops.write(parts[0], parts[1])
        return {"error": "Usage: write <path> <content>"}
    elif task_lower.startswith('list '):
        path = task[5:].strip()
        return ops.list_dir(path)
    elif task_lower.startswith('search '):
        parts = task[7:].split(' ', 1)
        if len(parts) == 2:
            return ops.search(parts[0], parts[1])
        return {"error": "Usage: search <path> <pattern>"}
    elif task_lower.startswith('delete '):
        path = task[7:].strip()
        return ops.delete(path)
    elif task_lower.startswith('copy '):
        parts = task[5:].split(' ', 1)
        if len(parts) == 2:
            dst_parts = parts[1].split(' ', 1)
            if len(dst_parts) == 2:
                return ops.copy(parts[0], dst_parts[0])
        return {"error": "Usage: copy <src> <dst>"}
    else:
        return ops.list_dir(task if task else '.')

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = execute(' '.join(sys.argv[1:]))
        print(result)
    else:
        print("FileOps capability loaded")
        print("Usage: read <path>, write <path> <content>, list <path>, search <path> <pattern>")
