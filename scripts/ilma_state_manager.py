#!/usr/bin/env python3
from __future__ import annotations
import asyncio,json,time
from pathlib import Path
ILMA_PROFILE=Path(__file__).resolve().parents[1]; STATE_FILE=ILMA_PROFILE/'ilma_model_router_data'/'unity_state.json'
class ILMAStateManager:
    def __init__(self): self._lock=asyncio.Lock(); self.state=self._load()
    def _load(self):
        try: return json.loads(STATE_FILE.read_text())
        except Exception: return {'current_requests':{},'active_models':{},'provider_health':{},'key_rotation':{},'sot_version':None,'conversation_memory':{},'learned_patterns':{},'updated_at':time.time()}
    async def set(self,path,value):
        async with self._lock:
            cur=self.state
            for p in path.split('.')[:-1]: cur=cur.setdefault(p,{})
            cur[path.split('.')[-1]]=value; self.state['updated_at']=time.time(); self._save()
    async def get(self,path,default=None):
        cur=self.state
        for p in path.split('.'):
            if not isinstance(cur,dict) or p not in cur: return default
            cur=cur[p]
        return cur
    def _save(self): STATE_FILE.parent.mkdir(parents=True,exist_ok=True); tmp=STATE_FILE.with_suffix('.tmp'); tmp.write_text(json.dumps(self.state,indent=2,ensure_ascii=False)); tmp.replace(STATE_FILE)
    def snapshot(self): return dict(self.state)
_global_state=ILMAStateManager()
def get_state_manager(): return _global_state
