#!/usr/bin/env python3
from __future__ import annotations
import asyncio,json,time,itertools,urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List,Dict,Optional
ILMA_PROFILE=Path(__file__).resolve().parents[1]; HEALTH=ILMA_PROFILE/'ilma_model_router_data'/'nvidia_key_health.json'; CRED=Path('/root/credential/api_key.json')
@dataclass
class NVIDIARequest: model_id:str; messages:List[Dict[str,str]]; max_tokens:int=1024; temperature:float=0.7; timeout:int=60
@dataclass
class NVIDIAResponse: success:bool; content:str; model_id:str; key_index:int; latency_ms:float; error:Optional[str]=None
class NVIDIAParallelKernel:
    def __init__(self): self.keys=self._load_keys(); self._rr=itertools.count(); self.health=self._load_health()
    def _load_keys(self):
        try:
            raw=json.loads(CRED.read_text()).get('nvidia',{}); keys=raw.get('keys',[]) if isinstance(raw,dict) else raw if isinstance(raw,list) else []
            return [k for k in keys if isinstance(k,str) and len(k)>10][:3]
        except Exception: return []
    def _load_health(self):
        try: return json.loads(HEALTH.read_text())
        except Exception: return {'keys':{},'updated_at':time.time()}
    def _save_health(self): HEALTH.parent.mkdir(parents=True,exist_ok=True); tmp=HEALTH.with_suffix('.tmp'); tmp.write_text(json.dumps(self.health,indent=2)); tmp.replace(HEALTH)
    def rotate_key(self): return next(self._rr)%max(1,len(self.keys))
    def _mark(self,idx,success,lat,error=''):
        rec=self.health.setdefault('keys',{}).setdefault(str(idx),{'request_count':0,'error_count':0,'avg_latency_ms':0,'last_used':None}); rec['request_count']+=1; rec['last_used']=time.time()
        if success: rec['avg_latency_ms']=rec.get('avg_latency_ms',0)*0.8+lat*0.2
        else: rec['error_count']+=1; rec['last_error']=error
        rec['error_rate']=rec['error_count']/max(1,rec['request_count']); self.health['updated_at']=time.time(); self._save_health()
    async def _execute_one(self,req,key_index=None):
        if not self.keys: return NVIDIAResponse(False,'',req.model_id,-1,0,'no_nvidia_keys')
        start=time.perf_counter(); first=(self.rotate_key() if key_index is None else key_index)%len(self.keys); attempts=list(range(len(self.keys))); attempts=attempts[first:]+attempts[:first]; last=''
        for idx in attempts:
            try:
                payload=json.dumps({'model':req.model_id,'messages':req.messages,'max_tokens':req.max_tokens,'temperature':req.temperature}).encode()
                def post():
                    r=urllib.request.Request('https://integrate.api.nvidia.com/v1/chat/completions',data=payload,headers={'Authorization':f'Bearer {self.keys[idx]}','Content-Type':'application/json'})
                    with urllib.request.urlopen(r,timeout=req.timeout) as resp: return json.loads(resp.read())
                data=await asyncio.to_thread(post); content=data.get('choices',[{}])[0].get('message',{}).get('content',''); lat=(time.perf_counter()-start)*1000; self._mark(idx,True,lat); return NVIDIAResponse(True,content,req.model_id,idx,lat)
            except Exception as e:
                last=str(e)[:300]; self._mark(idx,False,0,last)
                if '429' not in last and 'rate' not in last.lower(): break
        return NVIDIAResponse(False,'',req.model_id,-1,(time.perf_counter()-start)*1000,last)
    async def execute_parallel(self,requests): return await asyncio.gather(*[self._execute_one(r,i%max(1,len(self.keys))) for i,r in enumerate(requests)])
    def get_health_status(self): self.health['key_count']=len(self.keys); return self.health
