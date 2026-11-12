import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


class SourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_rss_redirects_are_followed_and_entries_preserved(self):
        # Do not load the model for an HTTP/parser regression test.
        with patch.dict(sys.modules, {'app.services.nlp_service': SimpleNamespace(analyze_sentiment=None)}):
            from app.services import collector_service
        rss = b'''<rss version="2.0"><channel><title>Test</title><item>
        <title>Market update</title><link>https://example.com/news/1</link>
        <description>&lt;p&gt;Market summary&lt;/p&gt;</description>
        <pubDate>Thu, 12 Nov 2026 07:00:00 GMT</pubDate></item></channel></rss>'''
        response = SimpleNamespace(content=rss, raise_for_status=lambda: None)
        client = SimpleNamespace(get=AsyncMock(return_value=response))
        for fetch, source, asset in [
            (collector_service.fetch_yahoo_finance_rss, 'YAHOO_FINANCE', 'GENERAL'),
            (collector_service.fetch_coindesk_rss, 'COINDESK', 'CRYPTO'),
        ]:
            with self.subTest(source=source):
                with patch.object(collector_service.httpx, 'AsyncClient') as factory:
                    factory.return_value.__aenter__ = AsyncMock(return_value=client)
                    factory.return_value.__aexit__ = AsyncMock(return_value=False)
                    items = await fetch()
                    self.assertTrue(factory.call_args.kwargs['follow_redirects'])
                    self.assertEqual(factory.call_args.kwargs['timeout'], 10)
                    self.assertEqual(len(items), 1)
                    self.assertEqual(items[0]['source'], source)
                    self.assertEqual(items[0]['asset_type'], asset)
                    self.assertIn('Market summary', items[0]['content'])


if __name__ == '__main__':
    unittest.main()
