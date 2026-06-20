#!/usr/bin/env python3
"""
ILMA Working Buffer — In-memory ordered key-value buffer
Phase 38E: NEEDS_SMALL_SCRIPT implementation

NOT CLAIMED:
- Persistence across sessions
- Thread safety
- Large data handling
- Distributed buffer
"""
from typing import Any, Dict, List, Optional
from collections import OrderedDict

class WorkingBuffer:
    """In-memory ordered key-value buffer with FIFO/LIFO order tracking."""
    
    def __init__(self):
        self._store: OrderedDict[str, Any] = OrderedDict()
        self._order: List[str] = []  # Track insertion order
    
    def store(self, key: str, value: Any) -> bool:
        """Store value under key. Returns True."""
        if key not in self._order:
            self._order.append(key)
        self._store[key] = value
        return True
    
    def get(self, key: str) -> Optional[Any]:
        """Get value by key. Returns None if not found."""
        return self._store.get(key)
    
    def update(self, key: str, value: Any) -> bool:
        """Update existing key. Returns True if exists, False if not."""
        if key not in self._store:
            return False
        self._store[key] = value
        return True
    
    def delete(self, key: str) -> bool:
        """Delete key. Returns True if existed, False if not."""
        if key in self._store:
            del self._store[key]
            self._order.remove(key)
            return True
        return False
    
    def list_keys(self) -> List[str]:
        """List all keys in insertion order."""
        return list(self._order)
    
    def clear(self) -> bool:
        """Clear all. Returns True."""
        self._store.clear()
        self._order.clear()
        return True
    
    def order(self) -> List[str]:
        """Return insertion order."""
        return list(self._order)
    
    def count(self) -> int:
        """Return number of items."""
        return len(self._store)
    
    def has_key(self, key: str) -> bool:
        """Check if key exists."""
        return key in self._store


# Global singleton buffer
_buffer = WorkingBuffer()

def buffer_store(key: str, value: Any) -> bool:
    """Store value under key."""
    return _buffer.store(key, value)

def buffer_get(key: str) -> Optional[Any]:
    """Get value by key."""
    return _buffer.get(key)

def buffer_update(key: str, value: Any) -> bool:
    """Update existing key."""
    return _buffer.update(key, value)

def buffer_delete(key: str) -> bool:
    """Delete key."""
    return _buffer.delete(key)

def buffer_list() -> List[str]:
    """List all keys."""
    return _buffer.list_keys()

def buffer_clear() -> bool:
    """Clear all."""
    return _buffer.clear()

def buffer_order() -> List[str]:
    """Return insertion order."""
    return _buffer.order()

def buffer_count() -> int:
    """Return count."""
    return _buffer.count()

def buffer_has(key: str) -> bool:
    """Check if key exists."""
    return _buffer.has_key(key)

def new_buffer() -> WorkingBuffer:
    """Create a new isolated buffer instance."""
    return WorkingBuffer()

def main():
    """CLI for testing."""
    import sys
    if len(sys.argv) < 2:
        print("Usage: ilma_working_buffer.py <command> [args]")
        print("Commands: store <key> <value>, get <key>, list, clear, order")
        sys.exit(1)
    
    cmd = sys.argv[1]
    try:
        if cmd == 'store' and len(sys.argv) >= 4:
            result = buffer_store(sys.argv[2], sys.argv[3])
            print("OK" if result else "FAIL")
        elif cmd == 'get' and len(sys.argv) >= 3:
            val = buffer_get(sys.argv[2])
            print(val if val is not None else "NOT_FOUND")
        elif cmd == 'list':
            print('\n'.join(buffer_list()))
        elif cmd == 'clear':
            buffer_clear()
            print("OK")
        elif cmd == 'order':
            print('\n'.join(buffer_order()))
        elif cmd == 'count':
            print(buffer_count())
        else:
            print("Unknown command")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()