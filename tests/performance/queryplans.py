import asyncio
import json
from sqlalchemy import text
from app.config import settings
from app.database import engine

async def main():
    assert settings.postgres_db == 'perf'
    queries = {
        'latest_news': 'SELECT id,title,published_at FROM news_items ORDER BY published_at DESC LIMIT 50',
        'daily_sentiment': "SELECT date_trunc('day',published_at),avg(sentiment_score) FROM news_items WHERE asset_type='CRYPTO' AND published_at >= now()-interval '30 days' GROUP BY 1 ORDER BY 1",
        'portfolio_sentiment': "SELECT asset_type,avg(sentiment_score) FROM news_items WHERE published_at>=now()-interval '7 days' GROUP BY asset_type",
    }
    plans={}
    async with engine.connect() as conn:
        for name,query in queries.items():
            result=await conn.execute(text('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+query))
            plans[name]=result.scalar_one()
    print(json.dumps(plans))
    await engine.dispose()
asyncio.run(main())
