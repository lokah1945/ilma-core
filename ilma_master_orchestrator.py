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
            from ilma_model_router import route_task_simple,execute_call
            model_id,provider,reason=route_task_simple(prompt,task_type,override_model); response=execute_call(model_id,provider,prompt); return {'status':'success' if 'Error:' not in str(response) else 'error','model':model_id,'provider':provider,'reason':reason,'response':response,'policy_applied':self.policy,'tier':self.tier}
class ILMAMasterOrchestrator(ILMAMaster): pass
if __name__=='__main__': print(json.dumps(ILMAMaster().process_request(' '.join(sys.argv[1:])),indent=2,ensure_ascii=False) if len(sys.argv)>1 else "Usage: python3 ilma_master_orchestrator.py 'Your prompt'")
