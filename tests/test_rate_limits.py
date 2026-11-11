"""Integration checks using Redis, with database and Gemini replaced by doubles."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import redis
from fastapi import FastAPI, Request
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import auth_routes, chatbot_routes
from app.auth import get_current_user, get_password_hash
from app.config import settings
from app.database import get_db
from app.limiter import limiter


class RateLimitTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.marker = "rate-test-" + uuid4().hex
        self.db = SimpleNamespace(execute=AsyncMock())
        self.db.execute.return_value = MagicMock()
        self.db.execute.return_value.scalar_one_or_none.return_value = None
        self.app = FastAPI()
        self.app.state.limiter = limiter
        self.app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        self.app.include_router(auth_routes.router, prefix="/api/auth")
        self.app.include_router(chatbot_routes.router, prefix="/api/chatbot")

        async def fake_db():
            yield self.db

        async def fake_user(request: Request):
            user_id = request.headers.get("X-Test-User", self.marker)
            request.state.authenticated_user_id = user_id
            return SimpleNamespace(id=user_id)

        self.app.dependency_overrides[get_db] = fake_db
        self.app.dependency_overrides[get_current_user] = fake_user

    def client(self, host=None):
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app, client=(host or self.marker, 1234)),
            base_url="http://test",
        )

    async def asyncTearDown(self):
        # Delete only keys belonging to this test; never flush the shared Redis DB.
        client = redis.Redis.from_url(settings.redis_url)
        try:
            keys = list(client.scan_iter(match=f"*{self.marker}*"))
            if keys:
                client.delete(*keys)
        finally:
            client.close()

    async def test_login_blocks_eleventh_attempt_despite_forwarded_header_changes(self):
        async with self.client() as client:
            for index in range(10):
                response = await client.post(
                    "/api/auth/login",
                    data={"username": "unknown@example.invalid", "password": "invalid"},
                    headers={"X-Forwarded-For": f"192.0.2.{index}"},
                )
                self.assertEqual(response.status_code, 401)
            response = await client.post(
                "/api/auth/login", data={"username": "unknown", "password": "invalid"}
            )
            self.assertEqual(response.status_code, 429)
        self.assertEqual(self.db.execute.await_count, 10)
        # A new HTTP connection must see the same shared counter.
        async with self.client() as client:
            response = await client.post(
                "/api/auth/login", data={"username": "unknown", "password": "invalid"}
            )
            self.assertEqual(response.status_code, 429)

    async def test_registration_blocks_sixth_request_before_database_work(self):
        self.db.execute.return_value.scalar_one_or_none.return_value = object()
        async with self.client() as client:
            for _ in range(5):
                response = await client.post(
                    "/api/auth/register", json={"email": "existing@example.invalid", "password": "invalid"}
                )
                self.assertEqual(response.status_code, 400)
            response = await client.post(
                "/api/auth/register", json={"email": "existing@example.invalid", "password": "invalid"}
            )
            self.assertEqual(response.status_code, 429)
        self.assertEqual(self.db.execute.await_count, 5)

    async def test_successful_login_and_authenticated_profile_remain_compatible(self):
        user = SimpleNamespace(
            id=123, email="test@example.invalid", first_name="Test", last_name="User",
            hashed_password=get_password_hash("test-password"),
        )
        self.db.execute.return_value.scalar_one_or_none.return_value = user
        self.app.dependency_overrides.pop(get_current_user)
        async with self.client() as client:
            response = await client.post(
                "/api/auth/login", data={"username": user.email, "password": "test-password"}
            )
            self.assertEqual(response.status_code, 200)
            token = response.json()["access_token"]
            response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["id"], user.id)

    async def test_chat_limits_user_across_ips_and_keeps_other_users_independent(self):
        with patch.object(chatbot_routes, "generate_chat_response", new_callable=AsyncMock) as generate:
            generate.return_value = "Test response"
            async with self.client() as client:
                for _ in range(10):
                    response = await client.post("/api/chatbot/chat", json={"message": "Hello"})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json(), {"reply": "Test response"})
            async with self.client(self.marker + "-other-ip") as client:
                response = await client.post("/api/chatbot/chat", json={"message": "Hello"})
                self.assertEqual(response.status_code, 429)
                response = await client.post(
                    "/api/chatbot/chat", json={"message": "Hello"},
                    headers={"X-Test-User": self.marker + "-other-user"},
                )
                self.assertEqual(response.status_code, 200)
            self.assertEqual(generate.await_count, 11)

    async def test_chat_validation_and_unavailable_response_remain_safe(self):
        from app.services.chatbot_service import ChatbotUnavailableError
        with patch.object(chatbot_routes, "generate_chat_response", new_callable=AsyncMock) as generate:
            async with self.client() as client:
                response = await client.post("/api/chatbot/chat", json={"message": " "})
                self.assertEqual(response.status_code, 400)
                response = await client.post("/api/chatbot/chat", json={"message": "a" * 4001})
                self.assertEqual(response.status_code, 422)
                generate.assert_not_awaited()
                generate.side_effect = ChatbotUnavailableError("Asistan kullanılamıyor.")
                response = await client.post("/api/chatbot/chat", json={"message": "Hello"})
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), {"detail": "Asistan kullanılamıyor."})


if __name__ == "__main__":
    unittest.main()
