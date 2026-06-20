#!/usr/bin/env python3
from __future__ import annotations
import asyncio,json,sys,pathlib
ILMA_PROFILE=pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ILMA_PROFILE)); sys.path.insert(0,str(ILMA_PROFILE/'scripts'))
from ilma_unified_pipeline import ILMAUnifiedPipeline
from ilma_short_prompt_engine import interpret_short_prompt
from ilma_nvidia_parallel_kernel import NVIDIAParallelKernel
async def main():
    pipe=ILMAUnifiedPipeline(); results=[]; r=await pipe.run('buat web'); results.append({'name':'simple_short_prompt','pass':r.get('success') and 'Interpreted task' in r.get('content','')}); r=await pipe.run('analisis data, buat visualisasi, dan deploy'); results.append({'name':'complex_decomposition','pass':r.get('success')}); tp=interpret_short_prompt('buat web',{}); results.append({'name':'spis_accuracy','pass':tp.task_type in ('medium_coding','heavy_coding')}); hs=NVIDIAParallelKernel().get_health_status(); results.append({'name':'nvidia_parallel_health','pass':'key_count' in hs}); from ilma_model_router import ILMAUnifiedRouter; router=ILMAUnifiedRouter(); results.append({'name':'paid_model_block','pass':not router.is_model_runtime_allowed('openai','gpt-4o',False)}); sot=json.load(open(ILMA_PROFILE/'ilma_model_router_data'/'PROVIDER_INTELLIGENCE_MASTER.json')); errs=[1 for p,pd in sot.get('providers',{}).items() for mid,m in pd.get('models',{}).items() if m.get('is_free') and str(m.get('billing','')).lower()=='paid']; results.append({'name':'sot_free_validation','pass':not errs}); passed=sum(1 for x in results if x['pass']); out={'total':len(results),'passed':passed,'failed':len(results)-passed,'results':results,'status':'PASS' if passed==len(results) else 'FAIL'}; print(json.dumps(out,indent=2)); return 0 if out['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(asyncio.run(main()))
