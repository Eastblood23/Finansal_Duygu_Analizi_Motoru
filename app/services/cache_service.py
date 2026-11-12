"""JSON cache with local single-flight and a short distributed fill lock."""
import asyncio
import json
import time
from contextlib import asynccontextmanager
from uuid import uuid4
from app.database import redis_client

_locks = {}


class CacheBusyError(Exception):
    pass


@asynccontextmanager
async def local_lock(key):
    entry = _locks.setdefault(key, [asyncio.Lock(), 0])
    entry[1] += 1
    try:
        async with entry[0]:
            yield
    finally:
        entry[1] -= 1
        if not entry[1]:
            _locks.pop(key, None)


async def cached_json(key, factory, ttl=30):
    cached = await redis_client.get(key)
    if cached is not None:
        return json.loads(cached)
    async with local_lock(key):
        deadline = time.monotonic() + 8
        lock_key = key + ":fill"
        owner = uuid4().hex
        while True:
            cached = await redis_client.get(key)
            if cached is not None:
                return json.loads(cached)
            if await redis_client.set(lock_key, owner, nx=True, ex=15):
                try:
                    value = await factory()
                    await redis_client.setex(key, ttl, json.dumps(value, allow_nan=False))
                    return value
                finally:
                    # Atomic owner check: never delete another process's lock.
                    await redis_client.eval(
                        "if redis.call('get',KEYS[1]) == ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end",
                        1, lock_key, owner,
                    )
            if time.monotonic() >= deadline:
                raise CacheBusyError()
            await asyncio.sleep(0.05)
