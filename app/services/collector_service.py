import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import httpx
from datetime import datetime
from time import mktime
import feedparser
from bs4 import BeautifulSoup

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import NewsItem
from app.services.nlp_service import analyze_sentiment

scheduler = AsyncIOScheduler()

def clean_html(raw_html):
    if not raw_html: return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=" ", strip=True)

async def fetch_finnhub_news():
    """Finnhub API üzerinden genel piyasa haberlerini çeker"""
    if not settings.finnhub_api_key or settings.finnhub_api_key == "your_finnhub_key_here":
        return []
        
    url = f"https://finnhub.io/api/v1/news?category=general&token={settings.finnhub_api_key}"
    async with httpx.AsyncClient() as client:
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
            print(f"Finnhub API hatası: {e}")
            return []

async def fetch_yahoo_finance_rss():
    """Yahoo Finance RSS akışını çeker"""
    url = "https://finance.yahoo.com/news/rssindex"
    try:
        # feedparser is blocking, but it's fast. For best practice, we use to_thread.
        feed = await asyncio.to_thread(feedparser.parse, url)
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
        print(f"Yahoo Finance RSS hatası: {e}")
        return []

async def fetch_coindesk_rss():
    """CoinDesk Crypto RSS akışını çeker"""
    url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
    try:
        feed = await asyncio.to_thread(feedparser.parse, url)
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
        print(f"CoinDesk RSS hatası: {e}")
        return []

async def process_and_save_news():
    """Haberleri çeker, analiz eder ve veritabanına kaydeder"""
    print(f"Haber toplama işlemi başladı: {datetime.now()}")
    
    # Tüm kaynaklardan eşzamanlı veri çekme (Paralel)
    finnhub_task = fetch_finnhub_news()
    yahoo_task = fetch_yahoo_finance_rss()
    crypto_task = fetch_coindesk_rss()
    
    results = await asyncio.gather(finnhub_task, yahoo_task, crypto_task)
    
    # Gelen iç içe listeyi tek listeye düzleştir
    all_news = []
    for source_data in results:
        all_news.extend(source_data)
        
    if not all_news:
        print("Hiç haber bulunamadı.")
        return
        
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        
        saved_count = 0
        for item in all_news:
            url = item['url']
            
            # Bu haber daha önce eklendi mi?
            existing = await session.execute(select(NewsItem).where(NewsItem.url == url))
            if existing.scalar_one_or_none():
                continue
            
            # NLP Duygu Analizi
            sentiment_result = analyze_sentiment(item['content'])
            label = sentiment_result['label']
            score = sentiment_result['score']
            
            # Güvenlik Eşiği (Confidence Threshold) %70 altındaysa Nötr yap
            if score < 0.70:
                label = "neutral"
                # Orijinal skoru tutabiliriz ama sistemin nötr algıladığını bilsin
            
            new_item = NewsItem(
                source=item['source'],
                asset_type=item['asset_type'],
                title=item['title'][:250], # Güvenlik için kırp
                content=item['content'],
                url=url,
                published_at=item['published_at'],
                sentiment_label=label,
                sentiment_score=score
            )
            session.add(new_item)
            saved_count += 1
            
        await session.commit()
    print(f"Haber toplama tamamlandı. {saved_count} yeni haber eklendi.")

async def start_collector():
    """Arka plan görevlendiricisini başlatır"""
    asyncio.create_task(process_and_save_news())
    
    scheduler.add_job(
        process_and_save_news, 
        'interval', 
        minutes=settings.update_interval_minutes
    )
    scheduler.start()

async def stop_collector():
    """Arka plan görevlendiricisini durdurur"""
    scheduler.shutdown()

