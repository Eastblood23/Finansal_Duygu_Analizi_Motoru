import asyncio
import json
import time
from pathlib import Path
import httpx
from load import run_case

async def main():
    snapshots=[]
    async with httpx.AsyncClient(base_url='http://web',timeout=120,
            limits=httpx.Limits(max_connections=100,max_keepalive_connections=100)) as client:
        async with httpx.AsyncClient(base_url='http://api:8000',timeout=120) as direct:
            task=asyncio.create_task(run_case(client,'dashboard',10,300))
            start=time.perf_counter()
            collection=None
            while not task.done():
                snapshots.append({'seconds':round(time.perf_counter()-start,2),
                    'resources':(await direct.get('/_bench/resources')).json()})
                if collection is None and time.perf_counter()-start>=60:
                    collection=asyncio.create_task(direct.post('/_bench/collect'))
                await asyncio.sleep(5)
            result=await task
            result['case']='100k_news_mixed_300s_with_collection'
            collected_response=await collection if collection else None
            if collected_response:
                collected_response.raise_for_status()
            collected=collected_response.json() if collected_response else None
            assert collected and collected.get('articles') == 40, collected
    output={'result':result,'samples':snapshots,'collection':collected}
    Path('/results/100k-soak.json').write_text(json.dumps(output,indent=2))
    print('SOAK_COLLECTION',json.dumps(collected),flush=True)
asyncio.run(main())
