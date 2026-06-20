#!/usr/bin/env python3
"""
ILMA Queue Manager v1.0
=========================
Priority queue for ILMA tasks.
"""
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import heapq

WORKSPACE = Path("/root/.hermes/profiles/ilma")
QUEUE_FILE = WORKSPACE / ".queue" / "tasks.json"

class PriorityQueue:
    """Priority queue with persistence."""
    
    def __init__(self):
        self.queue = []
        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.load()
    
    def load(self):
        if QUEUE_FILE.exists():
            try:
                with open(QUEUE_FILE) as f:
                    self.queue = json.load(f)
            except ValueError:
                self.queue = []
    
    def save(self):
        with open(QUEUE_FILE, "w") as f:
            json.dump(self.queue, f, indent=2)
    
    def enqueue(self, task: Dict, priority: int = 0):
        heapq.heappush(self.queue, (priority, datetime.now().isoformat(), task))
        self.save()
    
    def dequeue(self) -> Dict:
        if self.queue:
            _, _, task = heapq.heappop(self.queue)
            self.save()
            return task
        return None
    
    def peek(self) -> Dict:
        if self.queue:
            return self.queue[0][2]
        return None
    
    def size(self) -> int:
        return len(self.queue)

if __name__ == "__main__":
    q = PriorityQueue()
    print(json.dumps({"size": q.size()}, indent=2))
