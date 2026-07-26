#!/usr/bin/env python3
"""
ILMA Outbox Pattern v1.0
=========================
Outbox pattern for reliable messaging.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List

WORKSPACE = Path("/root/.hermes/profiles/ilma")
OUTBOX_DIR = WORKSPACE / ".outbox"
OUTBOX_DIR.mkdir(exist_ok=True)

class Outbox:
    """Outbox pattern for reliable messaging."""
    
    def __init__(self):
        self.outbox = []
        self.load()
    
    def load(self):
        outbox_file = OUTBOX_DIR / "messages.json"
        if outbox_file.exists():
            try:
                with open(outbox_file) as f:
                    self.outbox = json.load(f)
            except ValueError:
                self.outbox = []
    
    def save(self):
        outbox_file = OUTBOX_DIR / "messages.json"
        with open(outbox_file, "w") as f:
            json.dump(self.outbox, f, indent=2)
    
    def add(self, message: Dict):
        self.outbox.append({
            "message": message,
            "created_at": datetime.now().isoformat(),
            "sent": False
        })
        self.save()
    
    def mark_sent(self, index: int):
        if 0 <= index < len(self.outbox):
            self.outbox[index]["sent"] = True
            self.outbox[index]["sent_at"] = datetime.now().isoformat()
            self.save()
    
    def get_pending(self) -> List[Dict]:
        return [o for o in self.outbox if not o["sent"]]
    
    def size(self) -> int:
        return len(self.outbox)

if __name__ == "__main__":
    outbox = Outbox()
    print(json.dumps({"pending": len(outbox.get_pending())}, indent=2))
