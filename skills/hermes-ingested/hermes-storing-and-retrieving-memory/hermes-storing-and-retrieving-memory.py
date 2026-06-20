
"""
Hermes Memory System Skill: Storing and Retrieving Memory

Auto-generated from Hermes documentation.
Source: https://example.com/docs
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class StoringandRetrievingMemoryMemorySystem:
    """
    Memory system for Storing and Retrieving Memory.
    
    python await memory.store("key", {"data": "value"}) value = await memory.retrieve("key")
    """
    
    def __init__(self, memory_dir: Path = None):
        self.memory_dir = memory_dir or Path("/root/.hermes/profiles/ilma/memory")
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.cache: Dict[str, Any] = {}
        self.max_cache_size = 1000
    
    async def store(self, key: str, value: Any, ttl: int = None) -> bool:
        """
        Store a value in memory.
        
        Args:
            key: Memory key
            value: Value to store
            ttl: Time-to-live in seconds (optional)
            
        Returns:
            True if stored successfully
        """
        try:
            memory_file = self.memory_dir / f"{key}.json"
            
            data = {
                "key": key,
                "value": value,
                "stored_at": datetime.now().isoformat(),
                "ttl": ttl
            }
            
            memory_file.write_text(json.dumps(data, indent=2))
            self.cache[key] = value
            
            return True
            
        except Exception as e:
            logger.error(f"[MEMORY] Store failed for {key}: {e}")
            return False
    
    async def retrieve(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from memory.
        
        Args:
            key: Memory key
            
        Returns:
            Stored value or None if not found
"""
        # Check cache first
        if key in self.cache:
            return self.cache[key]
        
        try:
            memory_file = self.memory_dir / f"{key}.json"
            
            if not memory_file.exists():
                return None
            
            data = json.loads(memory_file.read_text())
            
            # Check TTL if set
            if data.get("ttl"):
                stored_at = datetime.fromisoformat(data["stored_at"])
                age = (datetime.now() - stored_at).total_seconds()
                if age > data["ttl"]:
                    # Expired
                    memory_file.unlink()
                    return None
            
            return data["value"]
            
        except Exception as e:
            logger.error(f"[MEMORY] Retrieve failed for {key}: {e}")
            return None
    
    async def delete(self, key: str) -> bool:
        """Delete a key from memory."""
        try:
            if key in self.cache:
                del self.cache[key]
            
            memory_file = self.memory_dir / f"{key}.json"
            if memory_file.exists():
                memory_file.unlink()
            
            return True
        except Exception as e:
            logger.error(f"[MEMORY] Delete failed for {key}: {e}")
            return False
    
    async def search(self, pattern: str) -> List[str]:
        """
        Search for keys matching a pattern.
        
        Args:
            pattern: Search pattern (glob-style)
            
        Returns:
            List of matching keys
        """
        matches = []
        
        for f in self.memory_dir.glob(f"{pattern}*.json"):
            key = f.stem
            matches.append(key)
        
        return matches


async def execute(input_text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Execute Storing and Retrieving Memory memory system operation.
    """
    ctx = context or {}
    memory = StoringandRetrievingMemoryMemorySystem()
    
    operation = ctx.get("operation", "retrieve")
    key = ctx.get("key", "default")
    
    if operation == "store":
        value = ctx.get("value")
        await memory.store(key, value)
        return {"status": "stored", "key": key}
    elif operation == "delete":
        await memory.delete(key)
        return {"status": "deleted", "key": key}
    else:
        value = await memory.retrieve(key)
        return {"status": "retrieved", "key": key, "value": value}
