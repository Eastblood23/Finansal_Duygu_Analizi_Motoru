"""Isolated benchmark only: synthetic data, no external APIs, no production writes."""
import asyncio
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import uvicorn
from sqlalchemy import text

started = time.perf_counter()
from app.services import market_service, chatbot_service

async def market():
    return {symbol: {"symbol": symbol, "price": price, "available": True,
        "history": [{"timestamp": int(time.time()) - i * 86400, "price": price} for i in range(30)]}
        for symbol, price in {"USD_TRY": 40, "BTC": 50000, "GOLD": 3000, "BIST100": 12000}.items()}

async def ticker(symbol, yahoo_symbol):
    return (await market())[symbol]

async def chat(user_id, message, db):
    await asyncio.sleep(0.2)
    return "Synthetic provider response."

market_service._fetch_all_market_data = market
market_service.fetch_ticker_data = ticker
chatbot_service.generate_chat_response = chat

from app import main
from app.database import engine, AsyncSessionLocal
from app.auth import get_password_hash
from app.database import redis_client
from app.limiter import limiter

limiter.enabled = False  # Measure capacity independently of per-IP quotas.

async def seed():
    hashed = get_password_hash("performance-test-only")
    async with engine.begin() as conn:
        if (await conn.execute(text("SELECT count(*) FROM news_items"))).scalar_one() == 0:
            await conn.execute(text("""INSERT INTO users (email, hashed_password, first_name, last_name)
              SELECT 'perf' || i || '@example.invalid', :hashed, 'Synthetic', 'User'
              FROM generate_series(1,100) i"""), {"hashed": hashed})
            await conn.execute(text("""INSERT INTO portfolio_items (user_id,symbol,amount)
              SELECT id,'USD_TRY',100 FROM users UNION ALL SELECT id,'BTC',0.1 FROM users"""))
            await conn.execute(text("""INSERT INTO news_items (source,asset_type,title,content,url,published_at,sentiment_label,sentiment_score)
              SELECT 'SYNTHETIC', CASE WHEN i%2=0 THEN 'GENERAL' ELSE 'CRYPTO' END,
              'Synthetic financial headline '||i, 'Synthetic content', 'https://example.invalid/'||i,
              now() - (i%720)*interval '1 hour',
              CASE WHEN i%3=0 THEN 'positive' WHEN i%3=1 THEN 'negative' ELSE 'neutral' END, 0.9
              FROM generate_series(1,10000) i"""))
            await conn.execute(text('ANALYZE'))
    print(f'BENCH_READY_SECONDS={time.perf_counter()-started:.3f}', flush=True)

async def noop():
    pass



@main.app.get('/_bench/resources')
async def resources():
    result = {}
    for name in ('memory.current', 'memory.peak', 'memory.max', 'cpu.stat'):
        path = Path('/sys/fs/cgroup') / name
        if path.exists():
            result[name] = path.read_text().strip()
    return result

@main.app.post('/_bench/collect')
async def collect():
    marker = uuid4().hex
    await redis_client.rpush('bench:collect', marker)
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        result = await redis_client.get('bench:result:' + marker)
        if result is not None:
            import json
            return json.loads(result)
        await asyncio.sleep(.05)
    raise TimeoutError('Benchmark worker did not finish')

from contextlib import asynccontextmanager
production_lifespan = main.lifespan
@asynccontextmanager
async def benchmark_lifespan(app):
    async with production_lifespan(app):
        await seed()
        yield
main.app.router.lifespan_context = benchmark_lifespan

if __name__ == '__main__':
    uvicorn.run(main.app, host='0.0.0.0', port=8000, access_log=False,
                proxy_headers=True, forwarded_allow_ips='*')
