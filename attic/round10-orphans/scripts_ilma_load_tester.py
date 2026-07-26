#!/usr/bin/env python3
from __future__ import annotations
import asyncio,statistics,time,json
from ilma_unified_pipeline import ILMAUnifiedPipeline
async def run_load(concurrency=100,prompt='buat web'):
    pipe=ILMAUnifiedPipeline(); lat=[]; errors=0
    async def one(i):
        nonlocal errors
        t=time.perf_counter(); r=await pipe.run(prompt,{'request_id':i}); lat.append((time.perf_counter()-t)*1000); errors+=0 if r.get('success') else 1
    await asyncio.gather(*[one(i) for i in range(concurrency)]); return {'requests':concurrency,'p50_ms':statistics.median(lat),'p95_ms':sorted(lat)[int(len(lat)*.95)-1],'error_rate':errors/max(1,concurrency),'target_simple_lt_1s':statistics.median(lat)<1000}
if __name__=='__main__': print(json.dumps(asyncio.run(run_load()),indent=2))
