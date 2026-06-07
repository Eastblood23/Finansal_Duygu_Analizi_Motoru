import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User, PortfolioItem, NewsItem
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Configure Gemini
if settings.gemini_api_key:
    genai.configure(api_key=settings.gemini_api_key)

async def generate_chat_response(user_id: int, message: str, db: AsyncSession) -> str:
    if not settings.gemini_api_key or settings.gemini_api_key == "your_gemini_api_key_here":
        return "Sistem hatası: Gemini API anahtarı yapılandırılmamış. Lütfen .env dosyanızı kontrol edin."

    try:
        # 1. Fetch User Portfolio
        portfolio_query = await db.execute(select(PortfolioItem).filter(PortfolioItem.user_id == user_id))
        portfolio_items = portfolio_query.scalars().all()
        
        portfolio_context = "Kullanıcının portföyü boş."
        if portfolio_items:
            items_str = ", ".join([f"{item.amount} {item.symbol}" for item in portfolio_items])
            portfolio_context = f"Kullanıcının güncel portföyü: {items_str}"

        # 2. Fetch Latest News (e.g. last 10 news items with sentiment)
        news_query = await db.execute(select(NewsItem).order_by(NewsItem.published_at.desc()).limit(10))
        news_items = news_query.scalars().all()
        
        news_context = "Güncel piyasa haberi bulunamadı."
        if news_items:
            news_str = "\n".join([f"- {n.title} (Duygu: {n.sentiment_label}, Skor: {n.sentiment_score:.2f})" for n in news_items])
            news_context = f"Son piyasa haberleri ve yapay zeka duygu analizleri:\n{news_str}"

        # 3. Construct System Prompt (RAG Context)
        system_instruction = f"""
Sen profesyonel, zeki ve objektif bir finansal asistansın.
Amacın kullanıcıya portföyü ve piyasadaki en son haberler ışığında tavsiyeler vermek.

BAĞLAM BİLGİSİ (RAG):
{portfolio_context}

{news_context}

Kurallar:
- Kesin yatırım tavsiyesi ("kesin al", "sat") verme.
- YANITLARIN ÇOK KISA, NET VE DOĞRUDAN OLSUN. Asla uzun paragraflar veya destanlar yazma. Maksimum 2-3 cümle kullan.
- Gereksiz nezaket sözcüklerini ("memnuniyetle anlatayım", "dağılım şu şekildedir" vb.) atla, direkt sadede gel ve lafı uzatma.
- Kullanıcı varlıklarını soruyorsa sadece miktar ve isimlerini listeleyip kısaca durumu özetle.
"""

        # 4. Generate Response with Gemini 1.5 Flash
        model = genai.GenerativeModel('gemini-flash-latest', system_instruction=system_instruction)
        
        # We can pass the history if needed, but for now just send the message
        # Since GenerativeModel supports system_instruction directly in newer versions
        response = model.generate_content(message)
        
        return response.text
    except Exception as e:
        logger.error(f"Gemini API Error: {str(e)}")
        return "Üzgünüm, şu an piyasa verilerini analiz ederken bir sorun yaşadım. Lütfen daha sonra tekrar deneyin."
