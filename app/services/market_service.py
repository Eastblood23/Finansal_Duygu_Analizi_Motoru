import httpx
import asyncio

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
        
        price = meta.get("regularMarketPrice", 0.0)
        prev_close = meta.get("chartPreviousClose", price)
        
        # Değişim yüzdesi
        change_pct = ((price - prev_close) / prev_close) * 100 if prev_close else 0.0
        
        # Son 30 günün kapanış fiyatları (grafik için)
        history = []
        try:
            closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
            timestamps = data["chart"]["result"][0]["timestamp"]
            # Sadece None olmayan değerleri al
            for t, c in zip(timestamps, closes):
                if c is not None:
                    history.append({"timestamp": t, "price": c})
        except (KeyError, IndexError, TypeError):
            pass
            
        return {
            "symbol": symbol_key,
            "price": price,
            "change_pct": change_pct,
            "is_up": change_pct >= 0,
            "history": history
        }
    except Exception as e:
            print(f"Piyasa verisi çekilemedi ({yahoo_symbol}): {e}")
            return {
                "symbol": symbol_key,
                "price": 0.0,
                "change_pct": 0.0,
                "is_up": True,
                "history": []
            }

async def get_all_market_data():
    tasks = [fetch_ticker_data(key, sym) for key, sym in SYMBOLS.items()]
    results = await asyncio.gather(*tasks)
    
    # Listeyi dictionary'ye çevir
    return {item["symbol"]: item for item in results}
