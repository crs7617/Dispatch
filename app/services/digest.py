"""Assemble a final Dispatch digest from collectors, deduplication, and ranking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from app.config.personalization import UserProjectContext
from app.models.digest import Digest
from app.models.news_item import NewsItem
from app.services.deduplication import DeduplicationService
from app.services.embeddings import LocalSentenceEmbeddingProvider
from app.services.relevance import RelevanceRankingService
from app.services.summarization import OpenAICompatibleLLMProvider, SummarizationService


class DigestOrchestrator:
    """Collect, deduplicate, rank, and summarize Dispatch stories into a final digest."""

    def __init__(
        self,
        *,
        hacker_news_collector: Any | None = None,
        rss_collector: Any | None = None,
        github_collector: Any | None = None,
        deduplication_service: DeduplicationService | None = None,
        relevance_service: RelevanceRankingService | None = None,
        summarization_service: SummarizationService | None = None,
        story_limit: int = 10,
    ) -> None:
        self._hacker_news_collector = hacker_news_collector
        self._rss_collector = rss_collector
        self._github_collector = github_collector
        self._deduplication_service = deduplication_service or DeduplicationService(
            embedding_provider=LocalSentenceEmbeddingProvider()
        )
        self._relevance_service = relevance_service or RelevanceRankingService()
        self._summarization_service = summarization_service or SummarizationService(
            provider=OpenAICompatibleLLMProvider()
        )
        self._story_limit = story_limit

    def build_digest(
        self,
        *,
        hacker_news_limit: int = 10,
        rss_feeds: Sequence[tuple[str, str]] = (),
        repositories: Sequence[str] = (),
        context: UserProjectContext | None = None,
    ) -> Digest:
        """Arrange all collection sources into a final digest while tolerating partial failures."""
        if self._story_limit < 0:
            raise ValueError("story_limit must be greater than or equal to zero")

        collected_items: list[NewsItem] = []
        failures: list[str] = []

        if self._hacker_news_collector is not None:
            try:
                collected_items.extend(self._hacker_news_collector.collect(hacker_news_limit))
            except Exception:
                failures.append("hacker_news")

        for feed_url, source_name in rss_feeds:
            if self._rss_collector is None:
                continue
            try:
                collected_items.extend(self._rss_collector.collect(feed_url, source_name))
            except Exception:
                failures.append(f"rss:{source_name}")

        if self._github_collector is not None:
            try:
                collected_items.extend(self._github_collector.collect(repositories))
            except Exception:
                failures.append("github")

        if not collected_items:
            return Digest(
                stories=(),
                generated_at=datetime.now(timezone.utc),
                story_limit=self._story_limit,
                source_failures=tuple(failures),
            )

        deduped = self._deduplication_service.deduplicate(collected_items)
        unique_items = [cluster.canonical_item for cluster in deduped.clusters]
        ranked = self._relevance_service.rank(unique_items, context or UserProjectContext.default())

        final_stories: list[NewsItem] = []
        for ranked_item in ranked[: self._story_limit]:
            item = ranked_item.item
            try:
                item = self._summarization_service.summarize(item)
            except (TypeError, ValueError, RuntimeError):
                pass
            final_stories.append(item)

        return Digest(
            stories=tuple(final_stories),
            generated_at=datetime.now(timezone.utc),
            story_limit=self._story_limit,
            source_failures=tuple(failures),
        )


__all__ = ["DigestOrchestrator"]
