"""In-memory cross-source news deduplication."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import sqrt
from typing import Protocol, Sequence

from app.models.news_item import NewsItem, Source


class EmbeddingProvider(Protocol):
    """Produces one embedding vector for each input text."""

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        """Return embeddings in the same order as ``texts``."""


@dataclass(frozen=True)
class StoryCluster:
    """A group of source items reporting the same story."""

    canonical_item: NewsItem
    items: tuple[NewsItem, ...]
    sources: tuple[Source, ...]


@dataclass(frozen=True)
class DeduplicationResult:
    """The complete set of story clusters for one deduplication run."""

    clusters: tuple[StoryCluster, ...]


class DeduplicationService:
    """Group NewsItems using injected text embeddings and cosine similarity."""

    def __init__(self, embedding_provider: EmbeddingProvider, threshold: float = 0.85) -> None:
        if not -1.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between -1.0 and 1.0")

        self._embedding_provider = embedding_provider
        self._threshold = threshold

    def deduplicate(self, items: Sequence[NewsItem]) -> DeduplicationResult:
        """Return deterministic clusters while retaining every supplied item."""
        if not items:
            return DeduplicationResult(clusters=())

        texts = [self._embedding_text(item) for item in items]
        embeddings = self._embedding_provider.embed(texts)
        if len(embeddings) != len(items):
            raise ValueError("embedding provider must return one vector per item")

        clusters: list[list[tuple[NewsItem, Sequence[float]]]] = []
        for item, embedding in zip(items, embeddings):
            for cluster in clusters:
                canonical_embedding = cluster[0][1]
                if self._cosine_similarity(embedding, canonical_embedding) >= self._threshold:
                    cluster.append((item, embedding))
                    break
            else:
                clusters.append([(item, embedding)])

        return DeduplicationResult(
            clusters=tuple(self._build_cluster(cluster) for cluster in clusters)
        )

    @staticmethod
    def _embedding_text(item: NewsItem) -> str:
        """Build a bounded text representation for one news item."""
        parts = [item.title]
        if item.summary:
            parts.append(item.summary[:1_000])
        if item.content:
            parts.append(item.content[:2_000])
        return "\n\n".join(parts)

    @classmethod
    def _build_cluster(
        cls, entries: list[tuple[NewsItem, Sequence[float]]]
    ) -> StoryCluster:
        items = tuple(item for item, _ in entries)
        canonical_item = min(items, key=cls._canonical_key)
        sources = tuple(dict.fromkeys(item.source for item in items))
        return StoryCluster(
            canonical_item=canonical_item,
            items=items,
            sources=sources,
        )

    @staticmethod
    def _canonical_key(item: NewsItem) -> tuple[int, datetime, str, str, str]:
        """Prefer the earliest published item, then use stable source identifiers."""
        published_at = item.published_at
        if published_at is None:
            published_at = datetime.max.replace(tzinfo=timezone.utc)
            has_published_at = 1
        else:
            has_published_at = 0
        return (
            has_published_at,
            published_at,
            item.source.value,
            item.source_id or "",
            str(item.id),
        )

    @staticmethod
    def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
        """Calculate cosine similarity for two embedding vectors."""
        if len(left) != len(right) or not left:
            raise ValueError("embedding vectors must be non-empty and equal length")

        dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right))
        left_norm = sqrt(sum(value * value for value in left))
        right_norm = sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            raise ValueError("embedding vectors must not be zero vectors")

        return dot_product / (left_norm * right_norm)
