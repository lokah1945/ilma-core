#!/usr/bin/env python3
from __future__ import annotations
import json,time,tempfile,os
from ilma_adaptive_model_selector import AdaptiveModelSelector,SOT,ILMA_PROFILE
HIST=ILMA_PROFILE/'ilma_model_router_data'/'score_history.jsonl'
def update_scores():
    sel=AdaptiveModelSelector(); data=sel.sot; n=0
    for p,pd in data.get('providers',{}).items():
        for mid,m in pd.get('models',{}).items():
            sc=sel._score(p,mid,m,'general')
            m['real_time_score']=sc
            m.setdefault('success_rate_1h',1.0 if m.get('is_free') else 0.0)
            m.setdefault('success_rate_24h',m['success_rate_1h'])
            m.setdefault('avg_latency_ms',m.get('avg_latency_ms') or 1500)
            m.setdefault('last_benchmarked',m.get('benchmark_updated'))
            m.setdefault('consecutive_failures',0); m.setdefault('consecutive_successes',0)
            m['predictive_score']=max(0,sc); n+=1
    data['_realtime_scorer']={'last_run':time.time(),'models_updated':n,'interval_sec':300}
    fd,tmp=tempfile.mkstemp(prefix='.'+SOT.name+'.',suffix='.tmp',dir=str(SOT.parent))
    with os.fdopen(fd,'w') as f: json.dump(data,f,indent=2,ensure_ascii=False)
    os.replace(tmp,SOT)
    HIST.parent.mkdir(parents=True,exist_ok=True)
    with HIST.open('a') as f: f.write(json.dumps({'timestamp':time.time(),'models_updated':n})+'\n')
    return {'models_updated':n}
if __name__=='__main__': print(json.dumps(update_scores(),indent=2))
