from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import engine, Base, redis_client
from app.api import routes
from app.services.collector_service import start_collector, stop_collector
from app.limiter import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Veritabanı tablolarını oluştur
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Arka plan veri toplayıcısını başlat
    await start_collector()
    yield
    # Kapatılırken kaynakları temizle
    await stop_collector()
    await redis_client.aclose()
    await engine.dispose()

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Finansal Duygu Analizi Motoru",
    description="Altın, USD ve piyasa haberlerini toplayıp NLP ile analiz eden API",
    version="1.0.0",
    lifespan=lifespan
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE"],
    allow_headers=["*"],
)

from app.api import auth_routes, watchlist_routes, correlation_routes, portfolio_routes, chatbot_routes

app.include_router(routes.router, prefix="/api", tags=["Sentiment API"])
app.include_router(auth_routes.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(watchlist_routes.router, prefix="/api/watchlist", tags=["Watchlist"])
app.include_router(correlation_routes.router, prefix="/api/correlation", tags=["Correlation"])
app.include_router(portfolio_routes.router, prefix="/api/portfolio", tags=["Portfolio"])
app.include_router(chatbot_routes.router, prefix="/api/chatbot", tags=["Chatbot"])

@app.get("/")
async def root():
    return {"message": "Finansal Duygu Analizi Motoru çalışıyor. API dökümantasyonu için /docs sayfasına gidin."}
