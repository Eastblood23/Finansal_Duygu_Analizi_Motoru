"""Synthetic jobs, real collector/model, separate process and container."""
import asyncio
import json
import time
from datetime import datetime, timezone
from app.database import redis_client
from app.services import collector_service
from redis.exceptions import RedisError

async def main():
    async def heartbeat():
        while True:
            try:
                await redis_client.setex('collector:heartbeat',60,'ok')
            except RedisError:
                pass
            await asyncio.sleep(5)
    pulse=asyncio.create_task(heartbeat())
    try:
        while True:
            try:
                entry=await redis_client.lpop('bench:collect')
            except RedisError:
                await asyncio.sleep(1)
                continue
            if not entry:
                await asyncio.sleep(.05)
                continue
            marker=entry
            async def synthetic():
                return [{'source':'SYNTHETIC','asset_type':'GENERAL',
                    'title':'The company reported higher profits and strong revenue growth.',
                    'content':'The company reported higher profits and strong revenue growth. '*12,
                    'url':f'https://example.invalid/collect/{marker}/{i}',
                    'published_at':datetime.now(timezone.utc)} for i in range(40)]
            async def empty():
                return []
            collector_service.fetch_finnhub_news=synthetic
            collector_service.fetch_yahoo_finance_rss=empty
            collector_service.fetch_coindesk_rss=empty
            start=time.perf_counter()
            count=await collector_service.process_and_save_news()
            await redis_client.setex('bench:result:'+marker,300,json.dumps(
                {'seconds':time.perf_counter()-start,'articles':count}))
    finally:
        pulse.cancel()
        await asyncio.gather(pulse,return_exceptions=True)
asyncio.run(main())
