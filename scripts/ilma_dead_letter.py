#!/usr/bin/env python3
"""
ILMA Dead Letter Queue v1.0
============================
Dead letter queue for failed messages.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

WORKSPACE = Path("/root/.hermes/profiles/ilma")
DLQ_DIR = WORKSPACE / ".dlq"
DLQ_DIR.mkdir(exist_ok=True)

class DeadLetterQueue:
    """Handle failed messages."""
    
    def __init__(self):
        self.queue = []
        self.load()
    
    def load(self):
        dlq_file = DLQ_DIR / "messages.json"
        if dlq_file.exists():
            try:
                with open(dlq_file) as f:
                    self.queue = json.load(f)
            except ValueError:
                self.queue = []
    
    def save(self):
        dlq_file = DLQ_DIR / "messages.json"
        with open(dlq_file, "w") as f:
            json.dump(self.queue, f, indent=2)
    
    def add(self, message: Dict, error: str):
        self.queue.append({
            "message": message,
            "error": error,
            "failed_at": datetime.now().isoformat()
        })
        self.save()
    
    def retry(self, index: int) -> Dict:
        if 0 <= index < len(self.queue):
            msg = self.queue.pop(index)
            self.save()
            return msg["message"]
        return None
    
    def get_all(self) -> List[Dict]:
        return self.queue
    
    def size(self) -> int:
        return len(self.queue)

if __name__ == "__main__":
    dlq = DeadLetterQueue()
    print(json.dumps({"size": dlq.size()}, indent=2))
