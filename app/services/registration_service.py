"""Expiring, single-use email proofs; no account exists before verification."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage
import hashlib
import hmac
import json
import secrets
import smtplib
import ssl
import threading

from fastapi import HTTPException
from app.config import settings
from app.database import redis_client

TTL_SECONDS = 600
COOLDOWN_SECONDS = 60
PREFIX = "auth:registration:"
mail_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="verification-mail")
mail_slots = threading.BoundedSemaphore(2)

# Atomic attempt accounting and consumption prevents concurrent replay and guessing.
CONSUME = """
local raw = redis.call('GET', KEYS[1])
if not raw then return nil end
local entry = cjson.decode(raw)
if entry.proof ~= ARGV[1] then
  entry.attempts = entry.attempts - 1
  if entry.attempts <= 0 then redis.call('DEL', KEYS[1])
  else redis.call('SET', KEYS[1], cjson.encode(entry), 'KEEPTTL') end
  return nil
end
redis.call('DEL', KEYS[1])
return cjson.encode(entry.user)
"""


def proof(challenge: str, code: str) -> str:
    return hmac.new(settings.jwt_secret_key.get_secret_value().encode(),
                    f"{challenge}:{code}".encode(), hashlib.sha256).hexdigest()


def require_sender():
    if not all((settings.smtp_host, settings.smtp_username,
                settings.smtp_password.get_secret_value(), settings.smtp_from_email)):
        raise HTTPException(503, "E-posta doğrulama servisi henüz hazır değil. Lütfen daha sonra deneyin.")


def send_code(email: str, code: str):
    try:
        message = EmailMessage()
        message["Subject"] = "Finansal Duygu Motoru — E-posta doğrulama"
        message["From"] = settings.smtp_from_email
        message["To"] = email
        message.set_content(
            f"Finansal Duygu Motoru kayıt doğrulama kodunuz: {code}\n\n"
            "Kod 10 dakika geçerlidir. Kodu yalnızca kayıt olduğunuz uygulamada kullanın.\n"
            "Bu kaydı siz başlatmadıysanız mesajı dikkate almayın.\n"
            "Banka veya Google şifrenizi istemiyoruz."
        )
        context = ssl.create_default_context()
        if settings.smtp_security == "ssl":
            connection = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port,
                                           timeout=5, context=context)
        else:
            connection = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5)
        with connection as server:
            if settings.smtp_security == "starttls":
                server.starttls(context=context)
            server.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            server.send_message(message)
    finally:
        # A timed-out request cannot release a slot while its SMTP thread still runs.
        mail_slots.release()


async def begin_registration(user: dict) -> dict:
    require_sender()
    cooldown = PREFIX + "cooldown:" + hashlib.sha256(user["email"].encode()).hexdigest()
    challenge = secrets.token_urlsafe(32)
    code = f"{secrets.randbelow(1000000):06d}"
    if not await redis_client.set(cooldown, "1", nx=True, ex=COOLDOWN_SECONDS):
        raise HTTPException(429, "Yeni kod istemeden önce 60 saniye bekleyin.")
    key = PREFIX + challenge
    await redis_client.set(key, json.dumps({"proof": proof(challenge, code),
                                           "attempts": 5, "user": user}), ex=TTL_SECONDS)
    if not mail_slots.acquire(blocking=False):
        await redis_client.delete(key)
        raise HTTPException(503, "E-posta servisi meşgul. Bir dakika sonra tekrar deneyin.")
    try:
        await asyncio.wait_for(asyncio.get_running_loop().run_in_executor(
            mail_pool, send_code, user["email"], code), timeout=30)
    except asyncio.CancelledError:
        await redis_client.delete(key)
        raise
    except Exception:
        await redis_client.delete(key)
        # Never expose SMTP exceptions, credentials, or verification codes in responses/logs.
        raise HTTPException(503, "Doğrulama e-postası gönderilemedi. Bir dakika sonra tekrar deneyin.") from None
    return {"challenge_id": challenge, "expires_in": TTL_SECONDS}


async def consume_registration(challenge: str, code: str) -> dict:
    raw = await redis_client.eval(CONSUME, 1, PREFIX + challenge, proof(challenge, code))
    if not raw:
        raise HTTPException(400, "Kod hatalı, süresi dolmuş veya deneme hakkı bitmiş. Yeniden kayıt başlatabilirsiniz.")
    return json.loads(raw)
