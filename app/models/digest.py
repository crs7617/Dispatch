"""Digest domain model for final Dispatch news digests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.models.news_item import NewsItem


@dataclass(frozen=True)
class Digest:
    """A clean, final digest assembled from collected and ranked stories."""

    stories: tuple[NewsItem, ...]
    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    story_limit: int = 10
    source_failures: tuple[str, ...] = ()

    @property
    def story_count(self) -> int:
        return len(self.stories)


__all__ = ["Digest"]
