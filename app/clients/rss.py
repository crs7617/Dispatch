"""Synchronous HTTP client for RSS and Atom feeds."""

from __future__ import annotations

import httpx


class RSSFeedClient:
    """Fetch raw feed content without parsing or normalizing it."""

    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._http_client = http_client or httpx.Client(timeout=10.0)

    def fetch_feed(self, feed_url: str) -> bytes:
        """Return the successful HTTP response body for ``feed_url``.

        Raises:
            httpx.HTTPError: If the request cannot complete successfully.
        """
        response = self._http_client.get(feed_url)
        response.raise_for_status()
        return response.content
