from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.database import engine, redis_client
from app.api import routes
from app.schema import initialize_schema
from app.limiter import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from sqlalchemy import text
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from limits.errors import StorageError
from sqlalchemy.exc import DBAPIError, TimeoutError as PoolTimeoutError
from app.services.cache_service import CacheBusyError
from app.middleware import RequestDeadlineMiddleware, consume_task

@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_schema()
    try:
        yield
    finally:
        if _health_task is not None and not _health_task.done():
            _health_task.cancel()
            _health_task.add_done_callback(consume_task)
        await redis_client.aclose()
        await engine.dispose()

app = FastAPI(
    title="Finansal Duygu Analizi Motoru",
    description="Altın, USD ve piyasa haberlerini toplayıp NLP ile analiz eden API",
    version="1.0.0",
    lifespan=lifespan
)
app.state.limiter = limiter
app.add_middleware(RequestDeadlineMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


async def dependency_unavailable(request, error):
    return JSONResponse(status_code=503, content={"detail": "Veri servisi geçici olarak kullanılamıyor. Lütfen tekrar deneyin."},
                        headers={"Retry-After": "2"})


for error_type in (RedisError, StorageError, DBAPIError, PoolTimeoutError, CacheBusyError, TimeoutError):
    app.add_exception_handler(error_type, dependency_unavailable)

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


_health_task = None


@app.get("/api/health", include_in_schema=False)
async def health():
    global _health_task
    async def check_dependencies():
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        await redis_client.ping()

    if _health_task is not None and not _health_task.done():
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    _health_task = asyncio.create_task(check_dependencies())
    done, _ = await asyncio.wait({_health_task}, timeout=1.5)
    if not done:
        _health_task.cancel()
        _health_task.add_done_callback(consume_task)
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    try:
        _health_task.result()
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ok"}
