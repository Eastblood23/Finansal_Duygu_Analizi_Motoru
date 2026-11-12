import argparse
import asyncio
import json
import math
import time
from collections import Counter
from pathlib import Path

import httpx

def percentile(values, quantile):
    return sorted(values)[max(0, math.ceil(len(values)*quantile)-1)] if values else None

async def run_case(client, kind, concurrency, seconds):
    latencies, statuses = [], Counter()
    sequence = 0
    token = None
    if kind in ('dashboard', 'portfolio', 'chat_stub'):
        login = await client.post('/api/auth/login', data={
            'username':'perf1@example.invalid', 'password':'performance-test-only'})
        login.raise_for_status()
        token = login.json()['access_token']
    deadline = time.perf_counter() + seconds
    async def worker():
        nonlocal sequence
        while time.perf_counter() < deadline:
            sequence += 1
            index = sequence
            start = time.perf_counter()
            try:
                if kind == 'login':
                    response = await client.post('/api/auth/login', data={'username':'perf1@example.invalid','password':'performance-test-only'})
                elif kind == 'portfolio':
                    response = await client.get('/api/portfolio/report', headers={'Authorization': 'Bearer '+token})
                elif kind == 'correlation':
                    response = await client.get('/api/correlation/BTC')
                elif kind == 'db_news':
                    response = await client.get(f'/api/sentiment/latest?limit=50&offset={100000+index}')
                    # Empty pages are not cached: real SQL OFFSET scan, no cache mutation.
                elif kind == 'static':
                    response = await client.get('/')
                elif kind == 'dashboard':
                    paths = ('/api/sentiment/latest?limit=50', '/api/market/ticker',
                        '/api/auth/me', '/api/portfolio/', '/api/portfolio/report', '/api/correlation/BTC')
                    response = await client.get(paths[index % len(paths)], headers={'Authorization': 'Bearer '+token})
                elif kind == 'chat_stub':
                    response = await client.post('/api/chatbot/chat', json={'message':'Synthetic question'},
                        headers={'Authorization': 'Bearer '+token})
                else:
                    response = await client.get('/api/sentiment/latest?limit=50')
                statuses[str(response.status_code)] += 1
            except httpx.HTTPError as error:
                statuses[type(error).__name__] += 1
            latencies.append((time.perf_counter()-start)*1000)
    begin = time.perf_counter()
    await asyncio.gather(*(worker() for _ in range(concurrency)))
    elapsed = time.perf_counter()-begin
    errors = sum(count for status,count in statuses.items() if status != '200')
    result = {'case':kind, 'concurrency':concurrency, 'elapsed_s':round(elapsed,2),
        'requests':len(latencies),'rps':round(len(latencies)/elapsed,2),
        'p50_ms':round(percentile(latencies,.5),2),'p95_ms':round(percentile(latencies,.95),2),
        'p99_ms':round(percentile(latencies,.99),2),'max_ms':round(max(latencies),2),
        'error_pct':round(100*errors/len(latencies),2), 'statuses':dict(statuses)}
    print(json.dumps(result), flush=True)
    return result

async def main(args):
    async with httpx.AsyncClient(base_url='http://web', timeout=60,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=100)) as client:
        await client.get('/api/sentiment/latest?limit=50')
        async with httpx.AsyncClient(base_url='http://api:8000', timeout=120) as direct:
            results = []
            resources = []
            stop = asyncio.Event()
            async def monitor():
                while not stop.is_set():
                    try:
                        data = (await direct.get('/_bench/resources')).json()
                        data['at'] = time.time()
                        resources.append(data)
                    except httpx.HTTPError:
                        pass
                    await asyncio.sleep(1)
            task = asyncio.create_task(monitor())
            try:
                for kind in ('static','warm_news','db_news','portfolio','login','correlation'):
                    for concurrency in (1,10,30):
                        results.append(await run_case(client,kind,concurrency,args.seconds))
                # A complete 40-article NLP collection cycle overlapping ordinary API requests.
                collection = asyncio.create_task(direct.post('/_bench/collect'))
                overlap = await run_case(client,'warm_news',10,15)
                overlap['case'] = 'news_during_40_article_collection'
                results.append(overlap)
                collected_response = await collection
                collected_response.raise_for_status()
                collection_result = collected_response.json()
                assert collection_result.get('articles') == 40, collection_result
                print('COLLECTION', json.dumps(collection_result), flush=True)
                results.append(await run_case(client,'warm_news',10,args.soak))
                results[-1]['case'] = 'news_soak'
            finally:
                stop.set()
                await task
            output = {'profile':args.profile,'results':results,'resources':resources,
                      'collection':collection_result,
                      'limitations':['closed-loop concurrency, not real browser users',
                        'same Docker host, no network WAN/TLS', 'external providers stubbed; no paid requests',
                        'rate limiter disabled only in isolated benchmark',
                        '10000 synthetic news, 100 users; one API worker',
                        'CPU/RAM quotas apply to API only; postgres 1 CPU/768MiB, web .5 CPU/128MiB, redis .5 CPU/128MiB']}
            Path('/results').mkdir(exist_ok=True)
            Path('/results',args.profile+'.json').write_text(json.dumps(output,indent=2))

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--profile',required=True)
    parser.add_argument('--seconds',type=float,default=6)
    parser.add_argument('--soak',type=float,default=45)
    asyncio.run(main(parser.parse_args()))
