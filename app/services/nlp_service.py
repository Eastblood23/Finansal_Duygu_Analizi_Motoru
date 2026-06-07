from transformers import pipeline

# Finansal metinler için özel olarak eğitilmiş FinBERT kullanıyoruz
# Pipeline ilk çağrıldığında modeli indirecektir (Eğer inmemişse)
sentiment_pipeline = pipeline("sentiment-analysis", model="ProsusAI/finbert")

def analyze_sentiment(text: str) -> dict:
    """
    Verilen metnin duygu analizini yapar.
    Dönüş: {'label': 'positive' | 'negative' | 'neutral', 'score': 0.99}
    """
    try:
        # Maksimum token sınırını aşmamak için metni kırpıyoruz
        truncated_text = text[:512] 
        result = sentiment_pipeline(truncated_text)[0]
        
        # FinBERT zaten 'positive', 'negative', 'neutral' etiketleri döndürür
        raw_label = result['label'].lower()
        # Güvenlik amaçlı yine de eşleştirme yapıyoruz
        label = raw_label if raw_label in ["positive", "negative", "neutral"] else "neutral"
        score = float(result['score'])
        
        return {
            "label": label,
            "score": score
        }
    except Exception as e:
        print(f"NLP Analiz Hatası: {e}")
        return {
            "label": "neutral",
            "score": 0.0
        }
