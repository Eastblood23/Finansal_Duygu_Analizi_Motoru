"""Run ONLY against a disposable stack: deliberately consumes login rate limits."""
import argparse
import asyncio

import httpx


async def check(base_url, mode):
    async with httpx.AsyncClient(base_url=base_url, timeout=15) as client:
        async def login(ip):
            return await client.post(
                '/api/auth/login',
                data={'username': 'proxy-check@example.invalid', 'password': 'synthetic'},
                headers={
                    'X-Forwarded-For': f'192.0.2.66, {ip}',
                    'X-Forwarded-Proto': 'https',
                },
            )

        if mode == 'trusted':
            for ip in ('198.51.100.101', '198.51.100.102'):
                for _ in range(10):
                    response = await login(ip)
                    assert response.status_code == 401, response.status_code
                response = await login(ip)
                assert response.status_code == 429, response.status_code
            print('PASS: trusted proxy preserves separate client limits and selects the last untrusted IP')
        else:
            for n in range(10):
                response = await login(f'203.0.113.{n + 1}')
                assert response.status_code == 401, response.status_code
            response = await login('203.0.113.200')
            assert response.status_code == 429, response.status_code
            print('PASS: untrusted peer cannot bypass login limits by changing forwarded headers')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://frontend')
    parser.add_argument('--mode', required=True, choices=['trusted', 'untrusted'])
    args = parser.parse_args()
    asyncio.run(check(args.url, args.mode))
