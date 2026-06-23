#!/usr/bin/env python3
from __future__ import annotations
import asyncio,json,time
from dataclasses import dataclass,asdict
from typing import Any,Dict,List
from pathlib import Path
from ilma_short_prompt_engine import interpret_short_prompt,TaskPackage
from ilma_event_bus import get_event_bus
from ilma_state_manager import get_state_manager
from ilma_governance_guard import GovernanceGuard
from ilma_cache_manager import ILMACacheManager
from ilma_adaptive_model_selector import AdaptiveModelSelector
@dataclass
class ExecutionPlan:
    mode:str; provider:str; model_id:str; task_package:Dict[str,Any]; subtasks:List[Dict[str,Any]]; use_nvidia_parallel:bool=False
class ILMAUnifiedPipeline:
    def __init__(self): self.bus=get_event_bus(); self.state=get_state_manager(); self.guard=GovernanceGuard(); self.cache=ILMACacheManager(); self.selector=AdaptiveModelSelector()
    async def run(self,prompt:str,context:Dict[str,Any]|None=None,**kwargs):
        start=time.perf_counter(); context=context or {}; await self.bus.publish('request_received',{'prompt_len':len(prompt)}); pre=self.guard.preflight({'prompt':prompt,**kwargs})
        if not pre.get('allowed'): self.guard.audit({'action':'blocked_request','reason':pre.get('reason')}); return {'success':False,'error':pre.get('reason')}
        tp=interpret_short_prompt(pre.get('prompt',prompt),context); await self.bus.publish('task_interpreted',tp.to_dict()); plan=self._route(tp); await self.bus.publish('model_selected',asdict(plan)); cached=self.cache.get(tp.expanded_task,f'{plan.provider}/{plan.model_id}')
        if cached is not None: return {'success':True,'content':cached,'cached':True,'plan':asdict(plan)}
        raw=await self._execute(plan); _ok=bool(raw) and all(x.get('success') for x in raw); final=self._synthesize(tp,raw); self.cache.set(tp.expanded_task,f'{plan.provider}/{plan.model_id}',final,ttl=300); lat=(time.perf_counter()-start)*1000; self.guard.audit({'action':'request_completed','provider':plan.provider,'model':plan.model_id,'latency_ms':lat,'why':'adaptive_free_selection'}); await self.state.set('last_request',{'prompt':prompt[:200],'latency_ms':lat,'success':True}); await self.bus.publish('output_generated',{'latency_ms':lat}); return {'success':_ok,'content':final,'latency_ms':lat,'plan':asdict(plan),'task_package':tp.to_dict()}
    def _route(self,tp:TaskPackage):
        c=self.selector.select(tp.task_type); subs=tp.parallel_subtasks; return ExecutionPlan('parallel' if subs else 'single',c.get('provider','minimax'),c.get('model_id','MiniMax-M3'),tp.to_dict(),subs,c.get('provider')=='nvidia' and len(subs)>=2)
    async def _execute(self,plan):
        # REAL execution via the free-only SubAgentRouter (was a facade returning
        # f"Executed via {provider}/{model}: {task}" with NO model call — fixed 2026-06-22).
        import asyncio as _a
        await self.bus.publish('execution_started',asdict(plan))
        try:
            from ilma_subagent_router import get_router
            router=get_router()
        except Exception as e:
            return [{'subtask':'main','success':False,'content':f'router unavailable: {e}'}]
        tt=(plan.task_package or {}).get('task_type') or 'general'
        if plan.mode=='parallel' and plan.subtasks:
            async def _one(s):
                r=await _a.to_thread(router.route_and_execute, message=s.get('prompt',''),
                                     task_type_or_desc=tt, allow_paid=False)
                return {'subtask':s.get('id'),'success':bool(r.get('success')),
                        'content':r.get('content') or r.get('error',''),'model':r.get('model')}
            out=list(await _a.gather(*[_one(s) for s in plan.subtasks]))
        else:
            task=(plan.task_package or {}).get('expanded_task','')
            r=await _a.to_thread(router.route_and_execute, message=task,
                                 task_type_or_desc=tt, allow_paid=False)
            out=[{'subtask':'main','success':bool(r.get('success')),
                  'content':r.get('content') or r.get('error',''),'model':r.get('model')}]
        await self.bus.publish('execution_completed',{'count':len(out)}); return out
    def _synthesize(self,tp,raw):
        body = '\n'.join('- '+r.get('content','') for r in raw)
        return '## ILMA Result\n\n**Interpreted task:** '+tp.expanded_task+'\n\n**Execution:**\n'+body+'\n\n**Validation:** free-only policy enforced; output synthesized by unified pipeline.'
def run_sync(prompt,context=None,**kwargs): return asyncio.run(ILMAUnifiedPipeline().run(prompt,context,**kwargs))
