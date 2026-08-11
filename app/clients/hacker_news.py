"""Synchronous client for the public Hacker News API."""

from __future__ import annotations

from typing import Any

import httpx


class HackerNewsClient:
    """Fetch raw data from the Hacker News API.

    This class only handles HTTP communication and basic response-shape
    validation. Filtering and conversion to ``NewsItem`` belong in a collector.
    """

    BASE_URL = "https://hacker-news.firebaseio.com/v0"

    def __init__(self, http_client: httpx.Client | None = None) -> None:
        """Create a client, optionally using an injected httpx client."""
        self._http_client = http_client or httpx.Client(timeout=10.0)

    def get_top_story_ids(self) -> list[int]:
        """Return the top-story item IDs in the order provided by Hacker News.

        Raises:
            httpx.HTTPError: If the request cannot complete successfully.
            ValueError: If the API response is not a list of integer IDs.
        """
        response = self._http_client.get(f"{self.BASE_URL}/topstories.json")
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, list) or not all(
            type(item_id) is int for item_id in payload
        ):
            raise ValueError("Expected Hacker News top stories to be a list of IDs")

        return payload

    def get_item(self, item_id: int) -> dict[str, Any] | None:
        """Return the raw API item for ``item_id``, or ``None`` for JSON null.

        Raises:
            httpx.HTTPError: If the request cannot complete successfully.
            ValueError: If the API response is neither an object nor null.
        """
        response = self._http_client.get(f"{self.BASE_URL}/item/{item_id}.json")
        response.raise_for_status()

        payload = response.json()
        if payload is None:
            return None
        if not isinstance(payload, dict):
            raise ValueError("Expected Hacker News item to be an object or null")

        return payload
