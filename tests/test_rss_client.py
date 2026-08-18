"""Unit tests for the RSS feed HTTP client."""

from __future__ import annotations

import unittest

import httpx

from app.clients.rss import RSSFeedClient


class RSSFeedClientTests(unittest.TestCase):
    """Verify feed fetching without real HTTP requests."""

    def test_fetch_feed_returns_response_bytes(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(str(request.url), "https://example.com/feed.xml")
            return httpx.Response(200, content=b"<rss />")

        client = RSSFeedClient(httpx.Client(transport=httpx.MockTransport(handler)))

        self.assertEqual(client.fetch_feed("https://example.com/feed.xml"), b"<rss />")

    def test_fetch_feed_surfaces_http_errors(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, request=request)

        client = RSSFeedClient(httpx.Client(transport=httpx.MockTransport(handler)))

        with self.assertRaises(httpx.HTTPStatusError):
            client.fetch_feed("https://example.com/feed.xml")
