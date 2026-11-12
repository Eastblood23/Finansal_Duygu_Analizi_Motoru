"""Real auth/router/Redis limits with an isolated in-memory database double."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import redis
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.sql.dml import Update

from app.api.auth_routes import router
from app.auth import create_access_token, get_password_hash, verify_password
from app.config import settings
from app.database import get_db
from app.limiter import limiter


class PasswordChangeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.marker = 'password-test-' + uuid4().hex
        self.user = SimpleNamespace(id=self.marker, email='owner@example.invalid', first_name='Test', last_name='User', hashed_password=get_password_hash('existing-test-password'))
        # Response model requires an integer ID; the random client address isolates limits.
        self.user.id = int(uuid4().hex[:12], 16)
        self.conflict = False
        self.db = SimpleNamespace(execute=AsyncMock(side_effect=self.execute), commit=AsyncMock(), rollback=AsyncMock())
        self.app = FastAPI()
        self.app.state.limiter = limiter
        self.app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        self.app.include_router(router, prefix='/api/auth')
        async def fake_db():
            yield self.db
        self.app.dependency_overrides[get_db] = fake_db
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app, client=(self.marker, 1234)), base_url='https://test')

    async def execute(self, statement):
        if isinstance(statement, Update):
            if self.conflict:
                return SimpleNamespace(rowcount=0)
            self.user.hashed_password = statement.compile().params['hashed_password']
            return SimpleNamespace(rowcount=1)
        result = MagicMock()
        result.scalar_one_or_none.return_value = self.user
        return result

    async def asyncTearDown(self):
        await self.client.aclose()
        connection = redis.Redis.from_url(settings.redis_url)
        try:
            keys = list(connection.scan_iter(match=f'*{self.marker}*'))
            keys += list(connection.scan_iter(match=f'*user:{self.user.id}*'))
            if keys:
                connection.delete(*keys)
        finally:
            connection.close()

    async def login(self, password='existing-test-password'):
        return await self.client.post('/api/auth/login', data={'username': self.user.email, 'password': password})

    async def change(self, token, current='existing-test-password', new='unique-new-password-for-this-app'):
        return await self.client.post('/api/auth/change-password', headers={'Authorization': f'Bearer {token}'}, json={'current_password': current, 'new_password': new})

    async def token(self):
        response = await self.login()
        self.assertEqual(response.status_code, 200)
        return response.json()['access_token']

    async def test_success_invalidates_all_previous_tokens_and_old_password(self):
        token = await self.token()
        other_token = await self.token()
        response = await self.change(token)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b'')
        self.db.commit.assert_awaited_once()
        self.assertTrue(verify_password('unique-new-password-for-this-app', self.user.hashed_password))
        for previous in (token, other_token):
            response = await self.client.get('/api/auth/me', headers={'Authorization': f'Bearer {previous}'})
            self.assertEqual(response.status_code, 401)
        self.assertEqual((await self.login()).status_code, 401)
        response = await self.login('unique-new-password-for-this-app')
        self.assertEqual(response.status_code, 200)
        response = await self.client.get('/api/auth/me', headers={'Authorization': f"Bearer {response.json()['access_token']}"})
        self.assertEqual(response.status_code, 200)

    async def test_incorrect_current_password_never_writes(self):
        token = await self.token()
        original = self.user.hashed_password
        response = await self.change(token, current='incorrect-password')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(original, self.user.hashed_password)
        self.db.commit.assert_not_awaited()

    async def test_same_short_and_oversized_passwords_rejected_without_echo(self):
        token = await self.token()
        for value in ('existing-test-password', 'short-secret', 'x' * 129):
            response = await self.change(token, new=value)
            self.assertEqual(response.status_code, 400)
            self.assertNotIn(value, response.text)
        self.db.commit.assert_not_awaited()

    async def test_concurrent_change_conflict_does_not_commit(self):
        token = await self.token()
        self.conflict = True
        self.assertEqual((await self.change(token)).status_code, 409)
        self.db.rollback.assert_awaited_once()
        self.db.commit.assert_not_awaited()

    async def test_missing_and_legacy_tokens_rejected(self):
        response = await self.client.post('/api/auth/change-password', json={'current_password': 'old', 'new_password': 'long-enough-test-password'})
        self.assertEqual(response.status_code, 401)
        legacy = create_access_token({'sub': self.user.email})
        self.assertEqual((await self.change(legacy)).status_code, 401)
        self.db.commit.assert_not_awaited()

    async def test_user_rate_limit_blocks_sixth_attempt(self):
        token = await self.token()
        for _ in range(5):
            self.assertEqual((await self.change(token, current='incorrect-password')).status_code, 400)
        self.assertEqual((await self.change(token, current='incorrect-password')).status_code, 429)
        self.db.commit.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
