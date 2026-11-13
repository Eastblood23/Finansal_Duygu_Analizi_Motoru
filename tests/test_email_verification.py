"""Exercise real PostgreSQL/Redis, auth routes and SMTP TLS behavior without sending mail."""
import asyncio
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select

from app.api.auth_routes import router
from app.config import settings
from app.database import Base, engine, redis_client, AsyncSessionLocal
from app.limiter import limiter
from app.models import User
from app.services import registration_service as service


class EmailVerificationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.marker = uuid4().hex
        self.email = f"test-{self.marker}@example.com"
        self.password = "independent-test-password-123"
        self.deliveries = []
        self.challenges = []
        self.smtp = patch.object(service, 'send_code', side_effect=self.capture)
        self.smtp.start()
        self.app = FastAPI()
        self.app.state.limiter = limiter
        self.app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        self.app.include_router(router, prefix='/api/auth')
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app, client=(self.marker, 1234)), base_url='https://test')

    def capture(self, email, code):
        self.deliveries.append((email, code))
        service.mail_slots.release()

    async def asyncTearDown(self):
        self.smtp.stop()
        await self.client.aclose()
        for challenge in self.challenges:
            await redis_client.delete(service.PREFIX + challenge)
        # These containers contain exclusively disposable test data.
        await redis_client.aclose()
        await engine.dispose()

    async def register(self, **changes):
        payload = dict(email=self.email, password=self.password, first_name='Test', last_name='User')
        payload.update(changes)
        response = await self.client.post('/api/auth/register', json=payload)
        if response.status_code == 202:
            self.challenges.append(response.json()['challenge_id'])
        return response

    async def verify(self, challenge, code):
        return await self.client.post('/api/auth/verify-email', json=dict(challenge_id=challenge, code=code))

    async def test_no_account_or_login_until_email_verified_then_single_use(self):
        response = await self.register(email=self.email.upper())
        self.assertEqual(response.status_code, 202, response.text)
        challenge = response.json()['challenge_id']
        async with AsyncSessionLocal() as db:
            self.assertIsNone((await db.execute(select(User).where(User.email == self.email))).scalar_one_or_none())
        login = await self.client.post('/api/auth/login', data=dict(username=self.email, password=self.password))
        self.assertEqual(login.status_code, 401)
        raw = await redis_client.get(service.PREFIX + challenge)
        self.assertNotIn(self.password, raw)
        self.assertNotIn(self.deliveries[0][1], json.loads(raw)['proof'])
        self.assertEqual(self.deliveries[0][0], self.email)
        verified = await self.verify(challenge, self.deliveries[0][1])
        self.assertEqual(verified.status_code, 200, verified.text)
        token = verified.json()['access_token']
        self.assertEqual((await self.client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})).status_code, 200)
        self.assertEqual((await self.verify(challenge, self.deliveries[0][1])).status_code, 400)
        login = await self.client.post('/api/auth/login', data=dict(username=self.email.upper(), password=self.password))
        self.assertEqual(login.status_code, 200)

    async def test_five_wrong_codes_exhaust_challenge(self):
        challenge = (await self.register()).json()['challenge_id']
        actual = self.deliveries[0][1]
        wrong = '000000' if actual != '000000' else '111111'
        for _ in range(5):
            self.assertEqual((await self.verify(challenge, wrong)).status_code, 400)
        self.assertEqual((await self.verify(challenge, actual)).status_code, 400)
        self.assertFalse(await redis_client.exists(service.PREFIX + challenge))

    async def test_expired_challenge_and_concurrent_replay(self):
        challenge = (await self.register()).json()['challenge_id']
        await redis_client.pexpire(service.PREFIX + challenge, 1)
        await asyncio.sleep(0.02)
        self.assertEqual((await self.verify(challenge, self.deliveries[0][1])).status_code, 400)
        # A separate identity bypasses only the intentional per-email resend cooldown.
        response = await self.register(email=f'other-{self.marker}@example.com')
        challenge = response.json()['challenge_id']
        statuses = [r.status_code for r in await asyncio.gather(
            self.verify(challenge, self.deliveries[-1][1]), self.verify(challenge, self.deliveries[-1][1]))]
        self.assertEqual(sorted(statuses), [200, 400])

    async def test_resend_cooldown(self):
        self.assertEqual((await self.register()).status_code, 202)
        self.assertEqual((await self.register()).status_code, 429)
        self.assertEqual(len(self.deliveries), 1)

    async def test_missing_sender_fails_closed(self):
        with patch.object(settings, 'smtp_host', ''):
            self.assertEqual((await self.register()).status_code, 503)
        self.assertEqual(self.deliveries, [])

    async def test_smtp_failure_leaves_no_usable_challenge(self):
        def fail(email, code):
            service.mail_slots.release()
            raise RuntimeError('smtp-internal-secret-must-not-leak')
        with patch.object(service, 'send_code', side_effect=fail):
            response = await self.register()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('smtp-internal-secret', response.text)
        async with AsyncSessionLocal() as db:
            self.assertIsNone((await db.execute(select(User).where(User.email == self.email))).scalar_one_or_none())

    async def test_input_validation_never_echoes_secrets(self):
        response = await self.register(password='short')
        self.assertEqual(response.status_code, 400)
        response = await self.register(password={'secret': 'do-not-echo-password'})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn('do-not-echo-password', response.text)
        self.assertEqual((await self.register(email='not-an-address')).status_code, 422)
        self.assertEqual(len(self.deliveries), 0)


class SmtpTlsTests(unittest.TestCase):
    def test_ssl_and_starttls_both_validate_server_certificates(self):
        for mode, factory in [('ssl', 'SMTP_SSL'), ('starttls', 'SMTP')]:
            with patch.object(settings, 'smtp_security', mode), patch.object(service.smtplib, factory) as smtp:
                self.assertTrue(service.mail_slots.acquire(blocking=False))
                service.send_code('recipient@example.com', '123456')
                server = smtp.return_value.__enter__.return_value
                server.login.assert_called_once()
                server.send_message.assert_called_once()
                if mode == 'ssl':
                    self.assertTrue(smtp.call_args.kwargs['context'].check_hostname)
                else:
                    self.assertTrue(server.starttls.call_args.kwargs['context'].check_hostname)
                    self.assertEqual([call[0] for call in server.mock_calls][:3],
                                     ['starttls', 'login', 'send_message'])


if __name__ == '__main__':
    unittest.main()
