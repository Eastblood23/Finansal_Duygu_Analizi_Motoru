"""Dedicated news/NLP worker. No model is imported by the HTTP API."""
import asyncio
import logging
import signal
from app.config import settings
from app.database import engine, redis_client

logger = logging.getLogger(__name__)


async def run_worker(job=None):
    if job is None:
        from app.services.collector_service import process_and_save_news
        job = process_and_save_news
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows development loop.
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))

    async def heartbeat():
        while not stop.is_set():
            try:
                await redis_client.setex("collector:heartbeat", 60, "ok")
            except Exception as error:
                logger.warning("Worker heartbeat unavailable: %s", type(error).__name__)
            try:
                await asyncio.wait_for(stop.wait(), timeout=10)
            except TimeoutError:
                pass

    pulse = asyncio.create_task(heartbeat())
    try:
        while not stop.is_set():
            try:
                await job()
            except Exception as error:
                logger.error("Collector cycle failed: %s", type(error).__name__)
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.update_interval_minutes * 60)
            except TimeoutError:
                pass
    finally:
        stop.set()
        pulse.cancel()
        await asyncio.gather(pulse, return_exceptions=True)
        await redis_client.aclose()
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Provider URLs may contain credentials; suppress informational HTTP URL logging.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    asyncio.run(run_worker())
