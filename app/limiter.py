from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request
from app.config import settings


def authenticated_user_key(request: Request) -> str:
    user_id = getattr(request.state, "authenticated_user_id", None)
    if user_id is not None:
        return f"user:{user_id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
    key_prefix="finans:rate-limit",
    strategy="moving-window",
    swallow_errors=False,
    in_memory_fallback_enabled=False,
    storage_options={"socket_connect_timeout": 2, "socket_timeout": 2},
)
