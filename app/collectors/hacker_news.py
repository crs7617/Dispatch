"""Collector that normalizes Hacker News stories into Dispatch news items."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.clients.hacker_news import HackerNewsClient
from app.models.news_item import NewsItem, Source


class HackerNewsCollector:
    """Collect valid top Hacker News stories as normalized news items."""

    DISCUSSION_URL_TEMPLATE = "https://news.ycombinator.com/item?id={item_id}"

    def __init__(self, client: HackerNewsClient) -> None:
        self._client = client

    def collect(self, limit: int) -> list[NewsItem]:
        """Collect up to ``limit`` valid stories in Hacker News API order.

        Raises:
            ValueError: If ``limit`` is negative.
            httpx.HTTPError: If the underlying API client cannot complete a request.
        """
        if limit < 0:
            raise ValueError("limit must be greater than or equal to zero")

        items: list[NewsItem] = []
        for item_id in self._client.get_top_story_ids()[:limit]:
            raw_item = self._client.get_item(item_id)
            news_item = self._to_news_item(raw_item)
            if news_item is not None:
                items.append(news_item)

        return items

    def _to_news_item(self, raw_item: dict[str, Any] | None) -> NewsItem | None:
        """Convert a valid raw HN story to a NewsItem, otherwise return None."""
        if raw_item is None:
            return None
        if raw_item.get("deleted") or raw_item.get("dead"):
            return None
        if raw_item.get("type") != "story":
            return None

        item_id = raw_item.get("id")
        title = raw_item.get("title")
        timestamp = raw_item.get("time")
        if (
            type(item_id) is not int
            or not isinstance(title, str)
            or not title.strip()
            or type(timestamp) is not int
        ):
            return None

        url = raw_item.get("url")
        if not isinstance(url, str) or not url.strip():
            url = self.DISCUSSION_URL_TEMPLATE.format(item_id=item_id)

        author = raw_item.get("by")
        if not isinstance(author, str):
            author = None

        return NewsItem(
            source=Source.HN,
            source_id=str(item_id),
            title=title,
            url=url,
            author=author,
            published_at=datetime.fromtimestamp(timestamp, tz=timezone.utc),
        )
