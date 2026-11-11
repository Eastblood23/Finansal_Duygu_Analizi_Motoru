"""Read-only verification of the built frontend and its reverse proxy."""
import argparse
import asyncio
import re

import httpx


async def check(base_url):
    async with httpx.AsyncClient(base_url=base_url, timeout=45) as client:
        index = await client.get("/")
        assert index.status_code == 200
        assert "/@vite/client" not in index.text
        assert index.headers["x-content-type-options"] == "nosniff"
        assert index.headers["x-frame-options"] == "DENY"
        assert "no-cache" in index.headers["cache-control"]
        asset_path = re.search(r'src="(/assets/[^\"]+\.js)"', index.text).group(1)
        asset = await client.get(asset_path)
        assert asset.status_code == 200
        assert "localhost:8000" not in asset.text
        assert "max-age=31536000" in asset.headers["cache-control"]
        assert (await client.get("/assets/nonexistent.js")).status_code == 404
        assert (await client.get("/client-side-route")).status_code == 200
        assert (await client.get("/api/health")).json() == {"status": "ok"}
        for path in ("/api/sentiment/latest?limit=1", "/api/market/ticker", "/api/correlation/BTC"):
            response = await client.get(path)
            assert response.status_code == 200, (path, response.status_code)
        missing = await client.get("/api/nonexistent")
        assert missing.status_code == 404
        assert "application/json" in missing.headers["content-type"]
    print("PASS: production assets, cache/security headers, SPA routing and API proxy")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:5173")
    args = parser.parse_args()
    asyncio.run(check(args.url))
