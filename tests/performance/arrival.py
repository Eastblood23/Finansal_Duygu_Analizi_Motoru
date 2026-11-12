"""Fixed-rate arrivals. Report generator lag, dropped work and end-to-end latency."""
import asyncio
import json
import time
from collections import Counter
from pathlib import Path
import httpx
from load import percentile

async def case(client, rate, seconds, token):
    statuses=Counter()
    latency=[]
    lag=[]
    tasks=set()
    dropped=0
    paths=('/api/sentiment/latest?limit=50','/api/market/ticker','/api/auth/me',
           '/api/portfolio/','/api/portfolio/report','/api/correlation/BTC')
    start=time.perf_counter()
    async def request(index,scheduled):
        lag.append((time.perf_counter()-scheduled)*1000)
        try:
            response=await client.get(paths[index%len(paths)],headers={'Authorization':'Bearer '+token})
            statuses[str(response.status_code)]+=1
        except httpx.HTTPError as error:
            statuses[type(error).__name__]+=1
        latency.append((time.perf_counter()-scheduled)*1000)
    for index in range(rate*seconds):
        scheduled=start+index/rate
        await asyncio.sleep(max(0,scheduled-time.perf_counter()))
        if len(tasks)>=200:
            dropped+=1
            continue
        task=asyncio.create_task(request(index,scheduled))
        tasks.add(task)
        task.add_done_callback(tasks.discard)
    await asyncio.gather(*list(tasks))
    result={'offered_rps':rate,'duration_s':seconds,'elapsed_s':round(time.perf_counter()-start,2),
            'completed':len(latency),'dropped':dropped,'statuses':dict(statuses),
            'p95_ms':round(percentile(latency,.95),2),'p99_ms':round(percentile(latency,.99),2),
            'max_ms':round(max(latency),2),'generator_lag_p95_ms':round(percentile(lag,.95),2)}
    result['error_pct']=round(100*(sum(v for k,v in statuses.items() if k!='200')+dropped)/(rate*seconds),2)
    print(json.dumps(result),flush=True)
    return result

async def main():
    async with httpx.AsyncClient(base_url='http://web',timeout=30,
            limits=httpx.Limits(max_connections=200,max_keepalive_connections=200)) as client:
        login=await client.post('/api/auth/login',data={'username':'perf1@example.invalid','password':'performance-test-only'})
        login.raise_for_status()
        token=login.json()['access_token']
        results=[]
        for repeat in range(1,4):
            for rate in (25,50,100,200):
                result=await case(client,rate,15,token)
                result['round']=repeat
                results.append(result)
    Path('/results/fixed-arrival-100k.json').write_text(json.dumps(results,indent=2))
asyncio.run(main())
