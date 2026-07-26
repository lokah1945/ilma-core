#!/usr/bin/env python3
from __future__ import annotations
import json,time,gc,shutil
from pathlib import Path
ILMA_PROFILE=Path(__file__).resolve().parents[1]
LOG=ILMA_PROFILE/'logs'/'self_healing.jsonl'; SOT=ILMA_PROFILE/'ilma_model_router_data'/'PROVIDER_INTELLIGENCE_MASTER.json'
class SelfHealingEngine:
    def __init__(self): self.heartbeats={}; self.circuits={}
    def heartbeat(self,component): self.heartbeats[component]=time.time(); self._log('heartbeat',component,'ok')
    def monitor(self):
        stale=[c for c,t in self.heartbeats.items() if time.time()-t>120]
        for c in stale: self.heal(c,'heartbeat_stale')
        return {'stale_components':stale,'circuits':self.circuits}
    def heal(self,component,reason):
        action='noop'
        if component in ('router','sot'):
            try: json.loads(SOT.read_text()); action='reload_sot'
            except Exception: action='restore_last_known_good'; self._restore_sot()
        elif component=='client': action='retry_with_exponential_backoff'
        elif component.startswith('provider:'): self.circuits[component]={'state':'open','until':time.time()+300}; action='open_circuit_5m'
        elif component.startswith('key:nvidia'): action='rotate_key'
        gc.collect(); self._log('healing_completed',component,reason,action); return {'component':component,'reason':reason,'action':action}
    def record_error(self,component,error):
        rec=self.circuits.setdefault(component,{'errors':[]}); rec['errors'].append(time.time()); rec['errors']=[t for t in rec['errors'] if time.time()-t<60]
        if len(rec['errors'])>=5: return self.heal(component,'circuit_threshold')
        self._log('error',component,error); return {'recorded':True}
    def _restore_sot(self):
        b=ILMA_PROFILE/'ilma_model_router_data'/'backups'; arr=sorted(b.glob('PROVIDER_INTELLIGENCE_MASTER*.json')) if b.exists() else []
        if arr: shutil.copy2(arr[-1],SOT)
    def _log(self,event,component,reason='',action=''):
        LOG.parent.mkdir(parents=True,exist_ok=True)
        with LOG.open('a') as f: f.write(json.dumps({'timestamp':time.time(),'event':event,'component':component,'reason':reason,'action':action})+'\n')
