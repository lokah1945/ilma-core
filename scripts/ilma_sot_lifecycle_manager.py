#!/usr/bin/env python3
from __future__ import annotations
import json,time,tempfile,os
from pathlib import Path
ILMA_PROFILE=Path(__file__).resolve().parents[1]
DATA=ILMA_PROFILE/'ilma_model_router_data'; SOT=DATA/'PROVIDER_INTELLIGENCE_MASTER.json'; CHANGELOG=DATA/'sot_changelog.jsonl'; ENDPOINTS=DATA/'provider_endpoints.json'
class SOTLifecycleManager:
    def __init__(self): self.sot=self._load(SOT,{'providers':{}}); self.endpoints=self._load(ENDPOINTS,{'providers':{}})
    def _load(self,p,d):
        try: return json.loads(Path(p).read_text())
        except Exception: return d
    def _save(self):
        fd,tmp=tempfile.mkstemp(prefix='.'+SOT.name+'.',suffix='.tmp',dir=str(SOT.parent))
        with os.fdopen(fd,'w') as f: json.dump(self.sot,f,indent=2,ensure_ascii=False)
        os.replace(tmp,SOT)
    def log(self,action,model_id,reason):
        CHANGELOG.parent.mkdir(parents=True,exist_ok=True)
        with CHANGELOG.open('a') as f: f.write(json.dumps({'timestamp':time.time(),'action':action,'model_id':model_id,'reason':reason})+'\n')
    def discover_once(self):
        now=time.time(); providers=self.sot.get('providers',{})
        for p,pd in providers.items(): pd.setdefault('provider_info',{})['last_lifecycle_seen']=now
        self.sot['_sot_lifecycle']={'last_discovery':now,'discovery_interval_sec':1800,'auto_enrichment_enabled':True,'auto_deprecation_enabled':True,'provider_health_check_enabled':True,'next_scheduled_discovery':now+1800}
        self._save(); return {'providers_checked':len(providers)}
    def provider_health_snapshot(self): return {p:{'status':'active' if not pd.get('disabled') else 'down','last_updated':time.time()} for p,pd in self.sot.get('providers',{}).items()}
if __name__=='__main__': print(json.dumps(SOTLifecycleManager().discover_once(),indent=2))
