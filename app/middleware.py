import asyncio
from starlette.responses import JSONResponse
from app.config import settings


def consume_task(task):
    if not task.cancelled():
        task.exception()


class RequestDeadlineMiddleware:
    """Bound response time without awaiting a stalled driver's cancellation handshake."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            return await self.app(scope, receive, send)
        path = scope["path"]
        timeout = settings.request_timeout_seconds
        if path == "/api/auth/register":
            timeout = max(timeout, 40)
        elif path.startswith("/api/chatbot/"):
            timeout = settings.gemini_timeout_seconds + 5
        elif path.startswith(("/api/market/", "/api/portfolio/", "/api/correlation/")):
            timeout = max(timeout, 10)
        expired = False
        started = False
        async def bounded_send(message):
            nonlocal started
            if not expired:
                if message["type"] == "http.response.start":
                    started = True
                await send(message)
        task = asyncio.create_task(self.app(scope, receive, bounded_send))
        try:
            done, _ = await asyncio.wait({task}, timeout=timeout)
            if done:
                return task.result()
            expired = True
            task.cancel()
            task.add_done_callback(consume_task)
            if not started:
                await JSONResponse(status_code=503, content={"detail": "İşlem zamanında tamamlanamadı. Lütfen tekrar deneyin."},
                                   headers={"Retry-After": "2"})(scope, receive, send)
        except asyncio.CancelledError:
            task.cancel()
            task.add_done_callback(consume_task)
            raise
