import asyncio
import json
from pathlib import Path
import argparse
import httpx
from load import run_case

async def main(profile, scale=False):
    results=[]
    async with httpx.AsyncClient(base_url='http://web', timeout=60,
            limits=httpx.Limits(max_connections=150,max_keepalive_connections=150)) as client:
        for kind in (('portfolio','correlation','db_news') if scale else ('dashboard','chat_stub')):
            for concurrency in (1,10,30):
                results.append(await run_case(client,kind,concurrency,8))
        if not scale:
            results.append(await run_case(client,'warm_news',100,8))
    Path('/results',profile+'-extra.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--profile',required=True)
    parser.add_argument('--scale',action='store_true')
    args=parser.parse_args()
    asyncio.run(main(args.profile,args.scale))
