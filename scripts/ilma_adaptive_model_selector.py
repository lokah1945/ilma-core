#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ILMA_PROFILE=Path(__file__).resolve().parents[1]; SOT=ILMA_PROFILE/'ilma_model_router_data'/'PROVIDER_INTELLIGENCE_MASTER.json'; HEALTH=ILMA_PROFILE/'ilma_model_router_data'/'model_health_state.json'; BENCH=ILMA_PROFILE/'ilma_model_router_data'/'benchmark_database.json'
class AdaptiveModelSelector:
    def __init__(self): self.sot=self._load(SOT,{'providers':{}}); self.health=self._load(HEALTH,{}); self.bench=self._load(BENCH,{})
    def _load(self,p,d):
        try: return json.loads(Path(p).read_text())
        except Exception: return d
    def _score(self,p,mid,m,task_type='general'):
        if m.get('disabled') or not m.get('is_free') or m.get('is_active') is not True: return -1
        q=float(m.get('quality_score') or m.get('score') or .5); q=q if q<=1 else q/100; coding=float(m.get('coding_score') or m.get('capabilities_detail',{}).get('coding') or q); coding=coding if coding<=1 else coding/100; reasoning=float(m.get('capabilities_detail',{}).get('reasoning') or q); success=float(m.get('success_rate_1h') if m.get('success_rate_1h') is not None else m.get('success_rate_24h') or .95); lat=float(m.get('avg_latency_ms') or 1500); lat_score=max(0,min(1,1000/max(1,lat))); health=0 if m.get('consecutive_failures',0)>=5 else 1
        if task_type in ('coding','medium_coding','heavy_coding'): score=q*.20+coding*.40+success*.20+lat_score*.10+health*.10
        elif task_type=='fast_tasks': score=lat_score*.50+success*.30+q*.10+health*.10
        else: score=q*.35+reasoning*.25+success*.20+lat_score*.10+health*.10
        if float(m.get('error_rate') or 0)>.10: score-=.30
        return round(max(-1,min(1,score)),4)
    def rank_models(self,task_type='general',limit=20):
        out=[]
        for p,pd in self.sot.get('providers',{}).items():
            if pd.get('disabled'): continue
            for mid,m in pd.get('models',{}).items():
                s=self._score(p,mid,m,task_type)
                if s>=0: out.append({'provider':p,'model_id':mid,'adaptive_score':s,'real_time_score':m.get('real_time_score',s)})
        return sorted(out,key=lambda x:x['adaptive_score'],reverse=True)[:limit]
    def select(self,task_type='general'):
        r=self.rank_models(task_type,1); return r[0] if r else {'provider':'minimax','model_id':'MiniMax-M3','adaptive_score':.5}
