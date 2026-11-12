"""Integration checks against synthetic PostgreSQL; never production records."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import httpx
from sqlalchemy import select, func, text
from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.models import NewsItem
from app.schema import INDEXES
from app.services.portfolio_service import build_portfolio_report
from app.services.sentiment_service import signed_sentiment_expression

async def main():
    assert settings.postgres_db=='perf'
    async with httpx.AsyncClient(base_url='http://web',timeout=15) as client:
        first=(await client.get('/api/sentiment/latest',params={'limit':7,'asset_type':'CRYPTO'})).json()
        last=first[-1]
        following=(await client.get('/api/sentiment/latest',params={'limit':7,'asset_type':'CRYPTO',
            'before_time':last['published_at'],'before_id':last['id']})).json()
        legacy=(await client.get('/api/sentiment/latest',params={'limit':7,'asset_type':'CRYPTO','offset':7})).json()
        assert len(first)==len(following)==7
        assert set(row['id'] for row in first).isdisjoint(row['id'] for row in following)
        assert [row['id'] for row in following]==[row['id'] for row in legacy]
        assert last['published_at']==following[0]['published_at'], 'Fixture should test a timestamp tie'
        login=await client.post('/api/auth/login',data={'username':'perf1@example.invalid','password':'performance-test-only'})
        login.raise_for_status()
        headers={'Authorization':'Bearer '+login.json()['access_token']}
        response=await client.get('/api/portfolio/report',headers=headers)
        response.raise_for_status()
        report=response.json()
        market=(await client.get('/api/market/ticker')).json()
    async with AsyncSessionLocal() as db:
        result=await db.execute(select(NewsItem.asset_type,func.avg(signed_sentiment_expression()).label('score'))
            .where(NewsItem.published_at>=datetime.now(timezone.utc)-timedelta(days=7)).group_by(NewsItem.asset_type))
        scores={row.asset_type:float(row.score) for row in result if row.score is not None}
        expected=build_portfolio_report([SimpleNamespace(symbol='USD_TRY',amount=100),SimpleNamespace(symbol='BTC',amount=.1)],market,scores)
        assert report['total_value_usd']==expected['total_value_usd']==5100
        assert abs(report['sentiment_score']-expected['sentiment_score'])<1e-9
        valid=set((await db.execute(text("SELECT c.relname FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid WHERE i.indisvalid"))).scalars())
        assert set(INDEXES).issubset(valid)
    await engine.dispose()
    print('PASS: timestamp-tie cursor pagination, legacy offset compatibility, exact cached/direct summary equivalence, valid indexes')
asyncio.run(main())
