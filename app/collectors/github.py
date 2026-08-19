"""Collector that normalizes GitHub releases into Dispatch news items."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from app.clients.github import GitHubClient
from app.models.news_item import NewsItem, Source


class GitHubCollector:
    """Collect repository releases as normalized news items."""

    def __init__(self, client: GitHubClient) -> None:
        self._client = client

    def collect(self, repositories: Sequence[str]) -> list[NewsItem]:
        """Collect releases in repository order and newest-first within each one.

        Releases without a publication timestamp are placed after dated releases,
        while keeping their API order relative to one another.
        """
        items: list[NewsItem] = []
        for repository in repositories:
            releases = self._client.get_releases(repository)
            for release in sorted(releases, key=self._release_sort_key, reverse=True):
                news_item = self._to_news_item(release)
                if news_item is not None:
                    items.append(news_item)

        return items

    def _release_sort_key(self, release: dict[str, Any]) -> datetime:
        """Return a timestamp used to order releases newest first."""
        return self._parse_timestamp(release.get("published_at")) or datetime.min.replace(
            tzinfo=timezone.utc
        )

    def _to_news_item(self, release: dict[str, Any]) -> NewsItem | None:
        """Convert a valid raw GitHub release to NewsItem, otherwise return None."""
        release_id = release.get("id")
        release_name = release.get("name")
        tag_name = release.get("tag_name")
        title = release_name if isinstance(release_name, str) and release_name.strip() else tag_name
        url = release.get("html_url")

        if (
            type(release_id) is not int
            or not isinstance(title, str)
            or not title.strip()
            or not isinstance(url, str)
            or not url.strip()
        ):
            return None

        author_data = release.get("author")
        author = (
            author_data.get("login")
            if isinstance(author_data, dict)
            and isinstance(author_data.get("login"), str)
            else None
        )
        body = release.get("body")

        return NewsItem(
            source=Source.GITHUB,
            source_id=str(release_id),
            title=title,
            url=url,
            author=author,
            content=body if isinstance(body, str) else None,
            published_at=self._parse_timestamp(release.get("published_at")),
        )

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        """Convert a GitHub ISO 8601 timestamp to a UTC-aware datetime."""
        if not isinstance(value, str):
            return None

        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

        if timestamp.tzinfo is None:
            return None
        return timestamp.astimezone(timezone.utc)
