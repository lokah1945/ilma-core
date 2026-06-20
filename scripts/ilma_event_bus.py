#!/usr/bin/env python3
from __future__ import annotations
import asyncio, json, time
from collections import defaultdict, deque
from pathlib import Path
ILMA_PROFILE=Path(__file__).resolve().parents[1]
EVENT_LOG=ILMA_PROFILE/'logs'/'event_bus.jsonl'
class ILMAEventBus:
    def __init__(self,max_buffer=10000):
        self.subscribers=defaultdict(list); self.buffer=deque(maxlen=max_buffer); self._lock=asyncio.Lock()
    def subscribe(self,event_type,handler): self.subscribers[event_type].append(handler)
    async def publish(self,event_type,payload=None):
        event={'type':event_type,'payload':payload or {},'timestamp':time.time()}
        async with self._lock:
            self.buffer.append(event); EVENT_LOG.parent.mkdir(parents=True,exist_ok=True)
            with EVENT_LOG.open('a',encoding='utf-8') as f: f.write(json.dumps(event,ensure_ascii=False)+'\n')
        for h in self.subscribers.get(event_type,[])+self.subscribers.get('*',[]):
            try:
                r=h(event)
                if hasattr(r,'__await__'): await r
            except Exception as e:
                if event_type!='error_occurred': await self.publish('error_occurred',{'source':'event_bus','error':str(e)})
    def recent(self,n=100): return list(self.buffer)[-n:]
_global_bus=ILMAEventBus()
def get_event_bus(): return _global_bus
