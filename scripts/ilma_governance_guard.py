#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,re,time
from pathlib import Path
ILMA_PROFILE=Path(__file__).resolve().parents[1]
AUDIT=ILMA_PROFILE/'ilma_model_router_data'/'audit_trail.jsonl'
RATE={}
BLOCK_PAT=re.compile(r'\b(illegal weapon|credential theft|exfiltrate|malware deployment)\b',re.I)
PII_PAT=re.compile(r'([\w.+-]+@[\w-]+\.[\w.-]+)|(\b\d{13,19}\b)')
class GovernanceGuard:
    def __init__(self): self.user_limit=100
    def mask_pii(self,text): return PII_PAT.sub('[MASKED_PII]',text or '')
    def preflight(self,request):
        prompt=request.get('prompt','') or ''
        if request.get('allow_paid') is True and not request.get('explicit_admin_paid_approval'): return {'allowed':False,'reason':'allow_paid requires explicit_admin_paid_approval'}
        if BLOCK_PAT.search(prompt): return {'allowed':False,'reason':'blocked harmful request pattern'}
        key=(request.get('user','default'),int(time.time()//60)); RATE[key]=RATE.get(key,0)+1
        if RATE[key]>self.user_limit: return {'allowed':False,'reason':'user rate limit exceeded'}
        return {'allowed':True,'prompt':self.mask_pii(prompt)}
    def audit(self,action):
        AUDIT.parent.mkdir(parents=True,exist_ok=True); prev='0'*64
        if AUDIT.exists():
            try: prev=json.loads(AUDIT.read_text().strip().splitlines()[-1]).get('hash',prev)
            except Exception: pass
        rec={'timestamp':time.time(),'prev_hash':prev,**action}
        rec['hash']=hashlib.sha256((prev+json.dumps(action,sort_keys=True,default=str)).encode()).hexdigest()
        with AUDIT.open('a',encoding='utf-8') as f: f.write(json.dumps(rec,ensure_ascii=False)+'\n')
        return rec['hash']
