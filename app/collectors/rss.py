"""Collector that normalizes RSS and Atom entries into Dispatch news items."""

from __future__ import annotations

import calendar
from datetime import datetime, timezone
from typing import Any, Mapping

import feedparser

from app.clients.rss import RSSFeedClient
from app.models.news_item import NewsItem, Source


class RSSCollector:
    """Collect valid RSS or Atom entries as normalized news items."""

    def __init__(self, client: RSSFeedClient) -> None:
        self._client = client

    def collect(self, feed_url: str, source_name: str) -> list[NewsItem]:
        """Fetch and normalize entries from one RSS or Atom feed.

        ``source_name`` identifies the feed and scopes entry IDs so that the
        same GUID from different feeds cannot collide.

        Raises:
            ValueError: If ``source_name`` is blank or feed content is invalid.
            httpx.HTTPError: If the underlying feed client cannot fetch the URL.
        """
        if not source_name.strip():
            raise ValueError("source_name must not be blank")

        parsed_feed = feedparser.parse(self._client.fetch_feed(feed_url))
        if parsed_feed.bozo:
            raise ValueError("Unable to parse RSS or Atom feed")

        items: list[NewsItem] = []
        for entry in parsed_feed.entries:
            news_item = self._to_news_item(entry, source_name)
            if news_item is not None:
                items.append(news_item)

        return items

    def _to_news_item(
        self, entry: Mapping[str, Any], source_name: str
    ) -> NewsItem | None:
        """Convert one valid parsed entry to a NewsItem, otherwise return None."""
        title = entry.get("title")
        url = entry.get("link")
        if (
            not isinstance(title, str)
            or not title.strip()
            or not isinstance(url, str)
            or not url.strip()
        ):
            return None

        entry_id = entry.get("id") or entry.get("guid") or url
        if not isinstance(entry_id, str) or not entry_id.strip():
            return None

        author = entry.get("author")
        if not isinstance(author, str):
            author_detail = entry.get("author_detail")
            author = (
                author_detail.get("name")
                if isinstance(author_detail, Mapping)
                and isinstance(author_detail.get("name"), str)
                else None
            )

        return NewsItem(
            source=Source.RSS,
            source_id=f"{source_name}:{entry_id}",
            title=title,
            url=url,
            author=author,
            published_at=self._published_at(entry),
        )

    @staticmethod
    def _published_at(entry: Mapping[str, Any]) -> datetime | None:
        """Return a UTC datetime from parsed published or updated metadata."""
        parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
        if parsed_time is None:
            return None

        try:
            return datetime.fromtimestamp(calendar.timegm(parsed_time), tz=timezone.utc)
        except (OverflowError, TypeError, ValueError):
            return None
