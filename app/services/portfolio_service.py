"""Indicative portfolio valuation, not an accounting ledger or risk model."""
from decimal import Decimal, InvalidOperation


ASSET_TYPE_MAP = {"BTC": "CRYPTO", "GOLD": "GENERAL", "USD_TRY": "GENERAL", "EUR_TRY": "GENERAL"}


def nonnegative_decimal(value):
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and number >= 0 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def positive_price(market, symbol):
    quote = market.get(symbol) or {}
    if quote.get("available") is False:
        return None
    price = nonnegative_decimal(quote.get("price"))
    return price if price is not None and price > 0 else None


def build_portfolio_report(items, market, sentiments):
    details = []
    decimal_values = []
    known_total = Decimal(0)
    complete = True
    fx = positive_price(market, "USD_TRY")
    for item in items:
        amount = nonnegative_decimal(item.amount)
        symbol = item.symbol
        price = positive_price(market, symbol)
        value = None
        status = "ok"
        if symbol not in ASSET_TYPE_MAP:
            status = "unsupported_asset"
        elif amount is None:
            status = "invalid_amount"
        elif amount == 0:
            value = Decimal(0)
        elif symbol == "USD_TRY":
            value = amount  # Stored amount is USD, not the USD/TRY exchange rate.
        elif price is None:
            status = "price_unavailable"
        elif symbol == "EUR_TRY":
            if fx is None:
                status = "price_unavailable"
            else:
                value = amount * price / fx  # EUR/TRY divided by USD/TRY gives EUR/USD.
        else:
            value = amount * price  # GOLD: troy ounces; BTC: coins; prices in USD.
        if value is None:
            complete = False
        else:
            known_total += value
        details.append({
            "symbol": symbol, "amount": float(item.amount),
            "price": float(price) if price is not None else None,
            "value": float(value) if value is not None else None,
            "value_try": float(value * fx) if value is not None and fx is not None else None,
            "asset_type": ASSET_TYPE_MAP.get(symbol), "valuation_status": status,
            "amount_unit": {"USD_TRY": "USD", "EUR_TRY": "EUR", "GOLD": "troy_ounce", "BTC": "BTC"}.get(symbol),
        })
        decimal_values.append(value)

    weighted = Decimal(0)
    coverage = Decimal(0)
    if complete and known_total > 0:
        for detail, value in zip(details, decimal_values):
            raw_score = sentiments.get(detail["asset_type"])
            if raw_score is None:
                continue
            score = Decimal(str(raw_score))
            if not score.is_finite() or not -1 <= score <= 1:
                continue
            weight = value / known_total
            weighted += weight * score
            coverage += weight
    sentiment = float(weighted / coverage) if coverage > 0 else None
    if not items:
        report = "Portföyünüz boş."
    elif not complete:
        report = "Bazı varlıklar değerlenemediği için toplam değer ve portföy duygu skoru hesaplanamadı."
    elif known_total == 0:
        report = "Portföy değeriniz 0."
    elif sentiment is None:
        report = "Değerleme hesaplandı; son 7 günde duygu analizi için yeterli haber bulunamadı."
    else:
        mood = "olumlu" if sentiment > 0.2 else "olumsuz" if sentiment < -0.2 else "nötr"
        report = (
            f"Son 7 günün kategori haberleri {mood}; duygu skoru {sentiment:.2f}. "
            f"Haber kapsamı portföy değerinin %{float(coverage * 100):.1f}'i. "
            "Bu skor fiyat tahmini veya yatırım riski ölçümü değildir."
        )
    if any(item.symbol == "GOLD" for item in items):
        report += " Altın değeri vadeli kontrat fiyatıyla yaklaşık hesaplanır; fiziki altın alış/satış fiyatı değildir."
    if any(item.symbol == "BIST100" for item in items):
        report += " BIST100 endeksi doğrudan bir portföy varlığı olarak değerlenemez; mevcut kayıt korunmuştur."
    if items:
        report += " Kripto dışındaki haberler genel piyasa kategorisindedir; varlığa özel etkiyi ölçmez."
    return {
        "total_value_usd": float(known_total) if complete else None,
        "total_value_try": float(known_total * fx) if complete and fx is not None else None,
        "known_value_usd": float(known_total), "valuation_complete": complete,
        "sentiment_score": sentiment,
        "risk_score": sentiment,  # Compatibility alias; this is not a risk estimate.
        "sentiment_coverage": float(coverage), "report_text": report, "items": details,
    }
