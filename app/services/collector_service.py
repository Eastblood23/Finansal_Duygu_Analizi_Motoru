import asyncio
import logging
import httpx
from datetime import datetime
from time import mktime
import feedparser
from bs4 import BeautifulSoup

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import NewsItem
from app.services.nlp_service import analyze_sentiment
logger = logging.getLogger(__name__)



def clean_html(raw_html):
    if not raw_html: return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=" ", strip=True)

async def fetch_finnhub_news():
    """Finnhub API üzerinden genel piyasa haberlerini çeker"""
    if not settings.finnhub_api_key or settings.finnhub_api_key == "your_finnhub_key_here":
        return []
        
    url = f"https://finnhub.io/api/v1/news?category=general&token={settings.finnhub_api_key}"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            results = []
            for item in data[:15]:
                headline = item.get('headline', '')
                summary = item.get('summary', '')
                url = item.get('url')
                if not url: continue
                dt = datetime.fromtimestamp(item.get('datetime', datetime.now().timestamp()))
                results.append({
                    "source": "FINNHUB",
                    "asset_type": "GENERAL",
                    "title": headline,
                    "content": f"{headline}. {summary}",
                    "url": url,
                    "published_at": dt
                })
            return results
        except Exception as e:
            logger.warning("Finnhub fetch failed: %s", type(e).__name__)
            return []

async def fetch_yahoo_finance_rss():
    """Yahoo Finance RSS akışını çeker"""
    url = "https://finance.yahoo.com/rss/2.0/headline?s=^GSPC,^DJI,^IXIC&region=US&lang=en-US"
    try:
        # feedparser is blocking, but it's fast. For best practice, we use to_thread.
        async with httpx.AsyncClient(timeout=10, follow_redirects=True,
                                     headers={"User-Agent": "Mozilla/5.0"}) as client:
            response = await client.get(url)
            response.raise_for_status()
        feed = await asyncio.to_thread(feedparser.parse, response.content)
        results = []
        for entry in feed.entries[:15]:
            title = entry.title
            summary = clean_html(entry.get('summary', ''))
            link = entry.link
            
            # published_parsed can be None
            if entry.get('published_parsed'):
                dt = datetime.fromtimestamp(mktime(entry.published_parsed))
            else:
                dt = datetime.now()
                
            results.append({
                "source": "YAHOO_FINANCE",
                "asset_type": "GENERAL",
                "title": title,
                "content": f"{title}. {summary}",
                "url": link,
                "published_at": dt
            })
        return results
    except Exception as e:
        logger.warning("Yahoo RSS fetch failed: %s", type(e).__name__)
        return []

async def fetch_coindesk_rss():
    """CoinDesk Crypto RSS akışını çeker"""
    url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True,
                                     headers={"User-Agent": "Mozilla/5.0"}) as client:
            response = await client.get(url)
            response.raise_for_status()
        feed = await asyncio.to_thread(feedparser.parse, response.content)
        results = []
        for entry in feed.entries[:10]:
            title = entry.title
            summary = clean_html(entry.get('summary', ''))
            link = entry.link
            
            if entry.get('published_parsed'):
                dt = datetime.fromtimestamp(mktime(entry.published_parsed))
            else:
                dt = datetime.now()
                
            results.append({
                "source": "COINDESK",
                "asset_type": "CRYPTO",
                "title": title,
                "content": f"{title}. {summary}",
                "url": link,
                "published_at": dt
            })
        return results
    except Exception as e:
        logger.warning("CoinDesk RSS fetch failed: %s", type(e).__name__)
        return []

async def process_and_save_news():
    """One collector at a time; model execution is confined to the worker process."""
    from sqlalchemy import select, text
    from sqlalchemy.dialects.postgresql import insert
    from redis.exceptions import RedisError
    from app.database import engine, redis_client
    logger = logging.getLogger(__name__)
    async with engine.connect() as lock_connection:
        locked = (await lock_connection.execute(text("SELECT pg_try_advisory_lock(81820317)"))).scalar_one()
        if not locked:
            return 0
        try:
            results = await asyncio.gather(fetch_finnhub_news(), fetch_yahoo_finance_rss(), fetch_coindesk_rss())
            unique = {item['url']: item for batch in results for item in batch if item.get('url')}
            if not unique:
                return 0
            async with AsyncSessionLocal() as session:
                existing = set((await session.execute(select(NewsItem.url).where(NewsItem.url.in_(unique)))).scalars().all())
                rows = []
                for url, item in unique.items():
                    if url in existing:
                        continue
                    sentiment = await asyncio.to_thread(analyze_sentiment, item['content'])
                    rows.append(dict(source=item['source'], asset_type=item['asset_type'],
                        title=item['title'][:250], content=item['content'], url=url,
                        published_at=item['published_at'],
                        sentiment_label=sentiment['label'] if sentiment['score'] >= .70 else 'neutral',
                        sentiment_score=sentiment['score']))
                if not rows:
                    return 0
                await session.execute(insert(NewsItem).values(rows).on_conflict_do_nothing(index_elements=['url']))
                await session.commit()
            try:
                await redis_client.incr('news:generation')
            except RedisError:
                logger.warning('News committed; cache invalidation unavailable (TTL will expire)')
            logger.info('News batch committed: %s candidates', len(rows))
            return len(rows)
        finally:
            await lock_connection.execute(text("SELECT pg_advisory_unlock(81820317)"))
