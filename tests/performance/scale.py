"""Expand ONLY the explicitly named disposable performance database."""
import asyncio
from sqlalchemy import text
from app.config import settings
from sqlalchemy.ext.asyncio import create_async_engine

# Fixture import is not an HTTP request and has its own bulk-load budget.
engine = create_async_engine(settings.database_url, connect_args={
    'timeout':3, 'command_timeout':120, 'server_settings':{'statement_timeout':'120000'}})

async def main():
    assert settings.postgres_db == 'perf' and settings.postgres_host == 'postgres'
    async with engine.begin() as conn:
        await conn.execute(text("""INSERT INTO news_items
          (source,asset_type,title,content,url,published_at,sentiment_label,sentiment_score)
          SELECT 'SYNTHETIC', CASE WHEN i%2=0 THEN 'GENERAL' ELSE 'CRYPTO' END,
          'Synthetic scaling headline '||i, 'Synthetic content', 'https://example.invalid/'||i,
          now() - (i%720)*interval '1 hour',
          CASE WHEN i%3=0 THEN 'positive' WHEN i%3=1 THEN 'negative' ELSE 'neutral' END,0.9
          FROM generate_series(10001,100000) i ON CONFLICT (url) DO NOTHING"""))
        await conn.execute(text('ANALYZE'))
        print('Synthetic news rows:', (await conn.execute(text('SELECT count(*) FROM news_items'))).scalar_one())
    await engine.dispose()
asyncio.run(main())
