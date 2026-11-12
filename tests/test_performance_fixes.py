import asyncio
import subprocess
import sys
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from app.services import cache_service, market_service, news_summary_service
from app.database import redis_client
from app.middleware import RequestDeadlineMiddleware
from app.config import settings


class CacheTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.marker = 'fix-test-' + uuid4().hex

    async def asyncTearDown(self):
        keys = [key async for key in redis_client.scan_iter(match='*'+self.marker+'*')]
        if keys:
            await redis_client.delete(*keys)
        await redis_client.aclose()

    async def test_concurrent_cache_misses_fill_once(self):
        async def create():
            await asyncio.sleep(.02)
            return {'price': 123}
        loader = AsyncMock(side_effect=create)
        values = await asyncio.gather(*(cache_service.cached_json(self.marker, loader) for _ in range(20)))
        self.assertEqual(values, [{'price':123}]*20)
        self.assertEqual(loader.await_count, 1)
        self.assertNotIn(self.marker, cache_service._locks)

    async def test_failed_fill_releases_lock_and_next_attempt_succeeds(self):
        loader = AsyncMock(side_effect=[ValueError('synthetic failure'), {'ok':True}])
        with self.assertRaises(ValueError):
            await cache_service.cached_json(self.marker, loader)
        self.assertEqual(await cache_service.cached_json(self.marker, loader), {'ok':True})
        self.assertFalse(await redis_client.exists(self.marker+':fill'))

    async def test_portfolio_summary_is_cached_and_generation_changes_invalidate_it(self):
        db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
            all=lambda:[SimpleNamespace(asset_type='GENERAL',score=-.8)])))
        with patch.object(news_summary_service,'generation',new=AsyncMock(return_value=self.marker)):
            self.assertEqual(await news_summary_service.portfolio_sentiments(db),{'GENERAL':-.8})
            self.assertEqual(await news_summary_service.portfolio_sentiments(db),{'GENERAL':-.8})
        self.assertEqual(db.execute.await_count,1)
        with patch.object(news_summary_service,'generation',new=AsyncMock(return_value=self.marker+'-next')):
            await news_summary_service.portfolio_sentiments(db)
        self.assertEqual(db.execute.await_count,2)

    async def test_market_consumers_share_one_fill(self):
        key=self.marker+':market'
        original=cache_service.cached_json
        async def isolated_cache(ignored,factory,ttl):
            return await original(key,factory,ttl)
        with patch.object(market_service,'cached_json',side_effect=isolated_cache), \
             patch.object(market_service,'_fetch_all_market_data',new=AsyncMock(return_value={'BTC':{'price':1}})) as fetch:
            await asyncio.gather(*(market_service.get_all_market_data() for _ in range(10)))
            self.assertEqual(fetch.await_count,1)


class IsolationAndDeadlineTests(unittest.IsolatedAsyncioTestCase):
    async def test_api_import_does_not_load_model_or_collector(self):
        result=await asyncio.create_subprocess_exec(sys.executable,'-c',
            "import app.main,sys; assert 'torch' not in sys.modules; assert 'app.services.collector_service' not in sys.modules",
            stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        _,error=await result.communicate()
        self.assertEqual(result.returncode,0,error.decode())

    async def test_http_deadline_does_not_wait_for_driver_cancellation(self):
        release=asyncio.Event()
        async def stuck(scope,receive,send):
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                await release.wait()
                raise
        app=RequestDeadlineMiddleware(stuck)
        with patch.object(settings,'request_timeout_seconds',.03):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                start=time.perf_counter()
                try:
                    response=await client.get('/api/sentiment/latest')
                    self.assertEqual(response.status_code,503)
                    self.assertLess(time.perf_counter()-start,.5)
                finally:
                    release.set()
                    await asyncio.sleep(.01)


if __name__=='__main__':
    unittest.main()
