#!/usr/bin/env python3
"""
ILMA Event Sourcing Store v1.0
================================
Event sourcing implementation.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

WORKSPACE = Path("/root/.hermes/profiles/ilma")
EVENTS_DIR = WORKSPACE / ".events"
EVENTS_DIR.mkdir(exist_ok=True)

class EventStore:
    """Event sourcing store."""
    
    def __init__(self, aggregate_id: str):
        self.aggregate_id = aggregate_id
        self.events_file = EVENTS_DIR / f"{aggregate_id}.json"
        self.events = []
        self.load()
    
    def load(self):
        if self.events_file.exists():
            try:
                with open(self.events_file) as f:
                    self.events = json.load(f)
            except ValueError:
                self.events = []
    
    def save(self):
        with open(self.events_file, "w") as f:
            json.dump(self.events, f, indent=2)
    
    def append(self, event_type: str, data: Any):
        self.events.append({
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })
        self.save()
    
    def get_events(self) -> List[Dict]:
        return self.events

if __name__ == "__main__":
    store = EventStore("example")
    print(json.dumps({"events": len(store.get_events())}, indent=2))
