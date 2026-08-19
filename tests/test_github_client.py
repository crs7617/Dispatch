"""Unit tests for the GitHub REST API client."""

from __future__ import annotations

import unittest

import httpx

from app.clients.github import GitHubClient


class GitHubClientTests(unittest.TestCase):
    """Verify GitHub release fetching without real HTTP requests."""

    def test_get_releases_returns_raw_release_objects(self) -> None:
        expected_releases = [{"id": 101, "tag_name": "v1.0.0"}]

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/repos/example/project/releases")
            return httpx.Response(200, json=expected_releases)

        client = GitHubClient(httpx.Client(transport=httpx.MockTransport(handler)))

        self.assertEqual(client.get_releases("example/project"), expected_releases)

    def test_http_errors_are_surfaced(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, request=request)

        client = GitHubClient(httpx.Client(transport=httpx.MockTransport(handler)))

        with self.assertRaises(httpx.HTTPStatusError):
            client.get_releases("example/project")

    def test_malformed_response_is_rejected(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"id": 101})

        client = GitHubClient(httpx.Client(transport=httpx.MockTransport(handler)))

        with self.assertRaises(ValueError):
            client.get_releases("example/project")
