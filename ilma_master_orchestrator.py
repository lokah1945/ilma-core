#!/usr/bin/env python3
from __future__ import annotations
import json,sys,asyncio
from typing import Optional,Dict,Any
class ILMAMaster:
    def __init__(self): self.system_name='Hermes Agent Profile ILMA'; self.policy='STRICT_FREE_ONLY'; self.tier='SSS+++'
    async def process_request_async(self,prompt:str,task_type:Optional[str]=None,override_model:Optional[str]=None,context:Optional[Dict[str,Any]]=None):
        from scripts.ilma_unified_pipeline import ILMAUnifiedPipeline
        ctx=context or {}; 
        if task_type: ctx['task_type_hint']=task_type
        if override_model: ctx['requested_override']=override_model
        result=await ILMAUnifiedPipeline().run(prompt,ctx,model_override=override_model)
        return {'status':'success' if result.get('success') else 'error','policy_applied':self.policy,'tier':self.tier,**result}
    def process_request(self,prompt:str,task_type:Optional[str]=None,override_model:Optional[str]=None,context:Optional[Dict[str,Any]]=None):
        try: return asyncio.run(self.process_request_async(prompt,task_type,override_model,context))
        except RuntimeError:
            # sync fallback — UNIFIED on the self-healing SubAgentRouter (no ProviderKernel
            # bypass; 2026-06-23): re-routes past failed models + correct circuit breaker.
            from ilma_subagent_router import get_router
            r=get_router().route_and_execute(message=prompt,task_type_or_desc=task_type or prompt[:80],allow_paid=False)
            return {'status':'success' if r.get('success') else 'error','model':r.get('model',''),'provider':(r.get('decision') or {}).get('provider',''),'reason':'subagent_router_self_heal','response':r.get('content') or r.get('error',''),'policy_applied':self.policy,'tier':self.tier}
class ILMAMasterOrchestrator(ILMAMaster): pass
if __name__=='__main__': print(json.dumps(ILMAMaster().process_request(' '.join(sys.argv[1:])),indent=2,ensure_ascii=False) if len(sys.argv)>1 else "Usage: python3 ilma_master_orchestrator.py 'Your prompt'")
