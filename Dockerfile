FROM python:3.11-slim

# Çalışma dizinini ayarla
WORKDIR /app

# Gerekli sistem kütüphanelerini kur (psycopg2/asyncpg vb. derlemeleri için gerekebilir)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Gereksinimleri kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Proje dosyalarını kopyala
COPY . .

# FastAPI'nin çalışacağı port
EXPOSE 8000

# Uygulamayı başlat
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
