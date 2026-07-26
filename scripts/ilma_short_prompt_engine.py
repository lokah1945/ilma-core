#!/usr/bin/env python3
from __future__ import annotations
import json,re,time,sys
from dataclasses import dataclass,asdict
from pathlib import Path
from typing import Any,Dict,List
ILMA_PROFILE=Path(__file__).resolve().parents[1]; REGISTRY=ILMA_PROFILE/'ILMA_CAPABILITY_REGISTRY.json'
@dataclass
class TaskPackage:
    original_prompt:str; expanded_task:str; task_type:str; detailed_requirements:List[str]; expected_output_format:str; required_capabilities:List[str]; suggested_models:List[str]; complexity_score:int; estimated_tokens:int; parallel_subtasks:List[Dict[str,Any]]; clarifying_questions:List[str]; confidence:float; created_at:float
    def to_dict(self): return asdict(self)
_EXP={'buat web':('Build a responsive website with semantic HTML, CSS, JavaScript, accessibility, and deployment notes.','medium_coding',['webdev','coding']),'buat api':('Design and implement a REST API with authentication, validation, rate limiting, tests, and documentation.','medium_coding',['coding']),'fix bug':('Diagnose root cause, patch code, explain fix, and provide regression tests.','medium_coding',['coding','analysis']),'analisis':('Perform structured analysis with assumptions, risks, evidence, alternatives, and recommended action.','reasoning_xhigh',['analysis']),'audit':('Run deep logic/security/consistency audit with concrete findings and remediation.','security_review',['security_review','analysis']),'riset':('Research topic, synthesize findings, compare alternatives, and provide actionable summary.','research',['research']),'deploy':('Prepare deployment plan, environment config, CI/CD checklist, rollback, and monitoring.','medium_coding',['coding','ops_self_healing'])}
def _caps(prompt):
    try: caps=json.loads(REGISTRY.read_text()).get('capabilities',[])
    except Exception: caps=[]
    out=[c['name'] for c in caps if c.get('trigger_pattern') and re.search(c['trigger_pattern'],prompt,re.I)]
    return out or ['short_prompt_mastery','analysis']
def _models(task):
    try:
        sys.path.insert(0,str(ILMA_PROFILE)); from ilma_model_router import ILMAUnifiedRouter
        r=ILMAUnifiedRouter(); res=r.route(task,n_fallbacks=5,allow_paid=False); arr=[f"{res.get('provider')}/{res.get('model_id')}"]+[f"{f.get('provider')}/{f.get('model_id')}" for f in res.get('fallback_chain',[])]
        return arr[:6]
    except Exception: return ['minimax/MiniMax-M3']
def interpret_short_prompt(prompt:str, context:Dict[str,Any]|None=None)->TaskPackage:
    raw=(prompt or '').strip(); low=raw.lower(); short=len(low.split())<=5; matched=None
    for k,v in _EXP.items():
        if k in low or low in k: matched=v; break
    if matched: expanded,task,caps=matched
    else:
        caps=_caps(low); task='medium_coding' if any(c in caps for c in ['coding','webdev']) else 'reasoning_xhigh' if 'analysis' in caps else 'general'; expanded=(f"Interpret '{raw}' into complete production-grade requirements and output.") if short else raw
    comp=2 if len(low.split())<=2 else 4 if short else min(10,max(5,len(raw)//120+4));
    if any(w in low for w in ['fullstack','deploy','architecture','audit','analisis data']): comp=max(comp,8)
    subs=[]
    if comp>7: subs=[{'id':'plan','capability':'analysis','prompt':'Create plan.'},{'id':'implement','capability':'coding','prompt':'Implement.'},{'id':'review','capability':'analysis','prompt':'Review.'}]
    return TaskPackage(raw,expanded,task,['Infer missing intent safely','Apply FREE_MODEL_ONLY routing','Return complete actionable output'],'complete_markdown_or_code_as_needed',caps,_models(task),comp,800+comp*350,subs,[] if matched else ['Ambiguous; proceeding with safe defaults.'],0.92 if matched else 0.78,time.time())
if __name__=='__main__': print(json.dumps(interpret_short_prompt(' '.join(sys.argv[1:]) or 'buat web',{}).to_dict(),indent=2,ensure_ascii=False))
