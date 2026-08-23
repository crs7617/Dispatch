"""Unit tests for cross-source news deduplication."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence
from unittest import TestCase

from app.models.news_item import NewsItem, Source
from app.services.deduplication import DeduplicationService


class FakeEmbeddingProvider:
    """Deterministic embedding provider for unit tests."""

    def __init__(self, vectors_by_text: dict[str, list[float]]) -> None:
        self.vectors_by_text = vectors_by_text
        self.calls: list[list[str]] = []

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        self.calls.append(list(texts))
        return [self.vectors_by_text[text] for text in texts]


def news_item(
    title: str,
    source: Source = Source.HN,
    source_id: str = "1",
    **overrides: object,
) -> NewsItem:
    """Build a NewsItem for a deduplication test."""
    values: dict[str, object] = {
        "source": source,
        "source_id": source_id,
        "title": title,
        "url": f"https://example.com/{source_id}",
    }
    values.update(overrides)
    return NewsItem(**values)


class DeduplicationServiceTests(TestCase):
    """Verify clustering with deterministic fake embeddings."""

    def test_empty_input_returns_no_clusters(self) -> None:
        provider = FakeEmbeddingProvider({})

        result = DeduplicationService(provider).deduplicate([])

        self.assertEqual(result.clusters, ())
        self.assertEqual(provider.calls, [])

    def test_single_item_is_its_own_cluster(self) -> None:
        item = news_item("One story")
        provider = FakeEmbeddingProvider({"One story": [1.0, 0.0]})

        result = DeduplicationService(provider).deduplicate([item])

        self.assertEqual(result.clusters[0].canonical_item, item)
        self.assertEqual(result.clusters[0].items, (item,))

    def test_unrelated_items_remain_separate(self) -> None:
        first = news_item("Python release", source_id="1")
        second = news_item("Space launch", source_id="2")
        provider = FakeEmbeddingProvider(
            {"Python release": [1.0, 0.0], "Space launch": [0.0, 1.0]}
        )

        result = DeduplicationService(provider).deduplicate([first, second])

        self.assertEqual([cluster.items for cluster in result.clusters], [(first,), (second,)])

    def test_similar_and_exact_duplicate_items_are_grouped(self) -> None:
        first = news_item("Python 3.14 released", Source.RSS, "rss")
        second = news_item("Python 3.14 released", Source.HN, "hn")
        third = news_item("New Python version ships", Source.GITHUB, "github")
        provider = FakeEmbeddingProvider(
            {
                "Python 3.14 released": [1.0, 0.0],
                "New Python version ships": [0.99, 0.1],
            }
        )

        result = DeduplicationService(provider, threshold=0.9).deduplicate(
            [first, second, third]
        )

        self.assertEqual(result.clusters[0].items, (first, second, third))
        self.assertEqual(result.clusters[0].sources, (Source.RSS, Source.HN, Source.GITHUB))

    def test_threshold_controls_grouping(self) -> None:
        first = news_item("First", source_id="1")
        second = news_item("Second", source_id="2")
        vectors = {"First": [1.0, 0.0], "Second": [0.8, 0.6]}

        grouped = DeduplicationService(FakeEmbeddingProvider(vectors), threshold=0.7)
        separate = DeduplicationService(FakeEmbeddingProvider(vectors), threshold=0.9)

        self.assertEqual(len(grouped.deduplicate([first, second]).clusters), 1)
        self.assertEqual(len(separate.deduplicate([first, second]).clusters), 2)

    def test_multiple_clusters_preserve_input_cluster_order(self) -> None:
        first = news_item("First", source_id="1")
        second = news_item("Second", source_id="2")
        third = news_item("Third", source_id="3")
        provider = FakeEmbeddingProvider(
            {"First": [1.0, 0.0], "Second": [0.0, 1.0], "Third": [0.99, 0.1]}
        )

        result = DeduplicationService(provider, threshold=0.9).deduplicate(
            [first, second, third]
        )

        self.assertEqual(result.clusters[0].items, (first, third))
        self.assertEqual(result.clusters[1].items, (second,))

    def test_missing_optional_text_uses_title_and_provider_is_injected(self) -> None:
        item = news_item("Title only")
        provider = FakeEmbeddingProvider({"Title only": [1.0, 0.0]})

        DeduplicationService(provider).deduplicate([item])

        self.assertEqual(provider.calls, [["Title only"]])

    def test_earliest_published_item_is_canonical(self) -> None:
        later = news_item(
            "Same story",
            Source.HN,
            "hn",
            published_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
        earlier = news_item(
            "Same story elsewhere",
            Source.RSS,
            "rss",
            published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        provider = FakeEmbeddingProvider(
            {"Same story": [1.0, 0.0], "Same story elsewhere": [1.0, 0.0]}
        )

        result = DeduplicationService(provider).deduplicate([later, earlier])

        self.assertEqual(result.clusters[0].canonical_item, earlier)

    def test_results_are_deterministic(self) -> None:
        first = news_item("First", source_id="1")
        second = news_item("Second", source_id="2")
        provider = FakeEmbeddingProvider({"First": [1.0, 0.0], "Second": [1.0, 0.0]})
        service = DeduplicationService(provider)

        first_result = service.deduplicate([first, second])
        second_result = service.deduplicate([first, second])

        self.assertEqual(first_result, second_result)
