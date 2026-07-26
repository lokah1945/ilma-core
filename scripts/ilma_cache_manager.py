#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,time
from pathlib import Path
ILMA_PROFILE=Path(__file__).resolve().parents[1]; CACHE_FILE=ILMA_PROFILE/'ilma_model_router_data'/'response_cache.json'
class ILMACacheManager:
    def __init__(self):
        try: self.cache=json.loads(CACHE_FILE.read_text())
        except Exception: self.cache={}
    def key(self,prompt,model_id,params=None): return hashlib.sha256(json.dumps({'p':prompt,'m':model_id,'x':params or {}},sort_keys=True).encode()).hexdigest()
    def get(self,prompt,model_id,params=None):
        r=self.cache.get(self.key(prompt,model_id,params)); return None if not r or r.get('expires_at',0)<time.time() else r.get('value')
    def set(self,prompt,model_id,value,params=None,ttl=300): self.cache[self.key(prompt,model_id,params)]={'value':value,'expires_at':time.time()+ttl,'created_at':time.time()}; self.save()
    def save(self): CACHE_FILE.parent.mkdir(parents=True,exist_ok=True); tmp=CACHE_FILE.with_suffix('.tmp'); tmp.write_text(json.dumps(self.cache,indent=2,ensure_ascii=False)); tmp.replace(CACHE_FILE)
