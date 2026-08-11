"""Unit tests for the synchronous Hacker News API client."""

from __future__ import annotations

import unittest

import httpx

from app.clients.hacker_news import HackerNewsClient


class HackerNewsClientTests(unittest.TestCase):
    """Verify HTTP behavior and response-shape validation without real requests."""

    def make_client(self, handler: httpx.MockTransport) -> HackerNewsClient:
        """Build a client backed by an in-memory HTTP transport."""
        return HackerNewsClient(httpx.Client(transport=handler))

    def test_get_top_story_ids_returns_ids_in_api_order(self) -> None:
        """The client returns the API's ordered list of item IDs unchanged."""

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/v0/topstories.json")
            return httpx.Response(200, json=[101, 202, 303])

        client = self.make_client(httpx.MockTransport(handler))

        self.assertEqual(client.get_top_story_ids(), [101, 202, 303])

    def test_get_item_returns_raw_item(self) -> None:
        """The client returns a valid item object without mapping it."""
        expected_item = {"id": 101, "type": "story", "title": "Example"}

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/v0/item/101.json")
            return httpx.Response(200, json=expected_item)

        client = self.make_client(httpx.MockTransport(handler))

        self.assertEqual(client.get_item(101), expected_item)

    def test_get_item_returns_none_for_json_null(self) -> None:
        """HN JSON null is represented as None for the collector to handle."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"null")

        client = self.make_client(httpx.MockTransport(handler))

        self.assertIsNone(client.get_item(101))

    def test_http_errors_are_surfaced(self) -> None:
        """A failed HN response remains an httpx HTTPStatusError."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, request=request)

        client = self.make_client(httpx.MockTransport(handler))

        with self.assertRaises(httpx.HTTPStatusError):
            client.get_top_story_ids()

    def test_invalid_top_story_response_is_rejected(self) -> None:
        """A response that is not a list of integer IDs is invalid."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"id": 101})

        client = self.make_client(httpx.MockTransport(handler))

        with self.assertRaises(ValueError):
            client.get_top_story_ids()
