import asyncio
import math
from app.services.cache_service import cached_json

SYMBOLS = {
    "USD_TRY": "TRY=X",
    "GOLD": "GC=F",
    "BTC": "BTC-USD",
    "BIST100": "XU100.IS"
}

async def fetch_ticker_data(symbol_key: str, yahoo_symbol: str) -> dict:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}?interval=1d&range=30d"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    try:
        import urllib.request
        import json
        req = urllib.request.Request(url, headers=headers)
        
        def fetch():
            with urllib.request.urlopen(req, timeout=5) as res:
                return json.loads(res.read())
                
        data = await asyncio.to_thread(fetch)
        meta = data["chart"]["result"][0]["meta"]
        expected_currency = "TRY" if symbol_key in ("USD_TRY", "BIST100") else "USD"
        if meta.get("currency") != expected_currency:
            raise ValueError("Unexpected quote currency")
        
        price = meta.get("regularMarketPrice", 0.0)
        if not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
            raise ValueError("Invalid market price")
        prev_close = meta.get("previousClose") or meta.get("regularMarketPreviousClose")
        if not isinstance(prev_close, (int, float)) or not math.isfinite(prev_close) or prev_close <= 0:
            prev_close = None
        
        # Değişim yüzdesi
        change_pct = ((price - prev_close) / prev_close) * 100 if prev_close else None
        
        # Son 30 günün kapanış fiyatları (grafik için)
        history = []
        try:
            closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
            timestamps = data["chart"]["result"][0]["timestamp"]
            # Sadece None olmayan değerleri al
            for t, c in zip(timestamps, closes):
                if isinstance(c, (int, float)) and math.isfinite(c) and c > 0:
                    history.append({"timestamp": t, "price": c})
        except (KeyError, IndexError, TypeError):
            pass
            
        return {
            "symbol": symbol_key,
            "price": price,
            "available": True,
            "prev_close": prev_close,
            "currency": meta.get("currency"),
            "change_pct": change_pct,
            "is_up": change_pct >= 0 if change_pct is not None else None,
            "history": history
        }
    except Exception as e:
            print(f"Piyasa verisi çekilemedi ({yahoo_symbol}): {e}")
            return {
                "symbol": symbol_key,
                "price": None,
                "available": False,
                "prev_close": None,
                "currency": None,
                "change_pct": None,
                "is_up": None,
                "history": []
            }

async def _fetch_all_market_data():
    tasks = [fetch_ticker_data(key, sym) for key, sym in SYMBOLS.items()]
    results = await asyncio.gather(*tasks)
    
    # Listeyi dictionary'ye çevir
    return {item["symbol"]: item for item in results}


async def get_all_market_data():
    # Shared by ticker, portfolio and charts; one refresh across API processes.
    return await cached_json("market:all:v2", _fetch_all_market_data, ttl=60)
