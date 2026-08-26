"""Unit tests for digest orchestration across collection, deduplication, ranking and summary."""

from __future__ import annotations

from unittest import TestCase

from app.config.personalization import UserProjectContext
from app.models.digest import Digest
from app.models.news_item import NewsItem, Source
from app.services.deduplication import DeduplicationService
from app.services.digest import DigestOrchestrator
from app.services.relevance import RelevanceRankingService
from app.services.summarization import SummarizationService


class FakeEmbeddingProvider:
    def __init__(self, vectors_by_text: dict[str, list[float]]) -> None:
        self.vectors_by_text = vectors_by_text

    def embed(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for text in texts:
            if text in self.vectors_by_text:
                results.append(self.vectors_by_text[text])
            else:
                title = text.split("\n\n", 1)[0]
                results.append(self.vectors_by_text.get(title, [1.0, 0.0]))
        return results


class FakeCollector:
    def __init__(self, items: list[NewsItem] | None = None, *, exc: Exception | None = None) -> None:
        self._items = items or []
        self._exc = exc

    def collect(self, *args: object, **kwargs: object) -> list[NewsItem]:
        if self._exc is not None:
            raise self._exc
        return list(self._items)


class FakeSummaryProvider:
    def __init__(self, summary: str = "A grounded summary.") -> None:
        self.summary = summary
        self.calls: list[str] = []

    def summarize(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.summary


class DigestOrchestratorTests(TestCase):
    def test_build_digest_assembles_and_summarizes(self) -> None:
        hn_item = NewsItem(
            source=Source.HN,
            source_id="10",
            title="AI agents accelerate backend engineering with Python",
            url="https://example.com/hn",
            content="Teams are using AI agents and Python to automate backend engineering tasks.",
        )
        rss_item = NewsItem(
            source=Source.RSS,
            source_id="feed:20",
            title="FastAPI release brings better Python support",
            url="https://example.com/rss",
            content="The new FastAPI release targets Python developers and API work.",
        )
        github_item = NewsItem(
            source=Source.GITHUB,
            source_id="30",
            title="Cloud workload tooling",
            url="https://example.com/github",
            content="New cloud tooling helps with developer ops workflows.",
        )

        orchestrator = DigestOrchestrator(
            hacker_news_collector=FakeCollector([hn_item]),
            rss_collector=FakeCollector([rss_item]),
            github_collector=FakeCollector([github_item]),
            deduplication_service=DeduplicationService(
                FakeEmbeddingProvider(
                    {
                        hn_item.title: [1.0, 0.0],
                        rss_item.title: [0.99, 0.1],
                        github_item.title: [0.0, 1.0],
                    }
                ),
                threshold=0.85,
            ),
            relevance_service=RelevanceRankingService(),
            summarization_service=SummarizationService(FakeSummaryProvider("A concise digest summary.")),
            story_limit=10,
        )

        digest = orchestrator.build_digest(
            hacker_news_limit=3,
            rss_feeds=(("https://example.com/feed.xml", "tech-feed"),),
            repositories=("octo/project",),
            context=UserProjectContext(
                interests=("AI engineering", "AI agents", "Python", "FastAPI")
            ),
        )

        self.assertIsInstance(digest, Digest)
        self.assertEqual(digest.story_count, 2)
        self.assertEqual(digest.stories[0].summary, "A concise digest summary.")
        self.assertTrue(all(item.url for item in digest.stories))
        self.assertEqual(digest.source_failures, ())

    def test_partial_collector_failure_keeps_other_sources(self) -> None:
        working_hn = NewsItem(
            source=Source.HN,
            source_id="100",
            title="AI engineering trends in Python",
            url="https://example.com/100",
            content="Teams are using Python to build AI engineering tools.",
        )

        orchestrator = DigestOrchestrator(
            hacker_news_collector=FakeCollector([working_hn]),
            rss_collector=FakeCollector(exc=RuntimeError("RSS outage")),
            github_collector=FakeCollector(),
            deduplication_service=DeduplicationService(
                FakeEmbeddingProvider({working_hn.title: [1.0, 0.0]}),
            ),
            relevance_service=RelevanceRankingService(),
            summarization_service=SummarizationService(FakeSummaryProvider("Recovered summary.")),
        )

        digest = orchestrator.build_digest(
            rss_feeds=(("https://example.com/bad.xml", "broken"),),
            repositories=(),
            context=UserProjectContext(interests=("AI engineering", "Python")),
        )

        self.assertEqual(digest.story_count, 1)
        self.assertEqual(digest.stories[0].title, working_hn.title)
        self.assertIn("rss:broken", digest.source_failures)

    def test_empty_results_produce_empty_digest(self) -> None:
        orchestrator = DigestOrchestrator(
            hacker_news_collector=FakeCollector(),
            rss_collector=FakeCollector(),
            github_collector=FakeCollector(),
            deduplication_service=DeduplicationService(FakeEmbeddingProvider({})),
            relevance_service=RelevanceRankingService(),
            summarization_service=SummarizationService(FakeSummaryProvider()),
        )

        digest = orchestrator.build_digest(
            rss_feeds=(),
            repositories=(),
            context=UserProjectContext(interests=("Python",)),
        )

        self.assertEqual(digest.stories, ())
        self.assertEqual(digest.story_count, 0)
        self.assertEqual(digest.source_failures, ())

    def test_duplicate_stories_are_removed(self) -> None:
        duplicate = NewsItem(
            source=Source.HN,
            source_id="42",
            title="Python and AI agents are changing developer workflows",
            url="https://example.com/42",
            content="Many teams are adopting Python-based AI agents.",
        )
        same_story = NewsItem(
            source=Source.RSS,
            source_id="feed:42",
            title="Python and AI agents are changing developer workflows",
            url="https://example.com/42-alt",
            content="Many teams are adopting Python-based AI agents.",
        )

        orchestrator = DigestOrchestrator(
            hacker_news_collector=FakeCollector([duplicate]),
            rss_collector=FakeCollector([same_story]),
            github_collector=FakeCollector(),
            deduplication_service=DeduplicationService(
                FakeEmbeddingProvider(
                    {
                        duplicate.title: [1.0, 0.0],
                        same_story.title: [1.0, 0.0],
                    }
                ),
                threshold=0.99,
            ),
            relevance_service=RelevanceRankingService(),
            summarization_service=SummarizationService(FakeSummaryProvider("Deduped summary.")),
        )

        digest = orchestrator.build_digest(
            rss_feeds=(("https://example.com/feed.xml", "tech-feed"),),
            repositories=(),
            context=UserProjectContext(interests=("AI agents", "Python")),
        )

        self.assertEqual(digest.story_count, 1)
        self.assertEqual(digest.stories[0].source_id, duplicate.source_id)

    def test_ranking_and_story_limit_are_applied(self) -> None:
        first = NewsItem(
            source=Source.HN,
            source_id="1",
            title="Python frameworks for AI agents",
            url="https://example.com/1",
            content="AI agents rely on Python frameworks and backend engineering patterns.",
        )
        second = NewsItem(
            source=Source.RSS,
            source_id="2",
            title="A new bike-sharing app launches",
            url="https://example.com/2",
            content="A city bike-sharing startup opened to the public.",
        )
        third = NewsItem(
            source=Source.GITHUB,
            source_id="3",
            title="Developer tooling for React teams",
            url="https://example.com/3",
            content="A React-focused team adds tooling for developer workflows.",
        )

        orchestrator = DigestOrchestrator(
            hacker_news_collector=FakeCollector([first]),
            rss_collector=FakeCollector([second]),
            github_collector=FakeCollector([third]),
            deduplication_service=DeduplicationService(
                FakeEmbeddingProvider(
                    {
                        first.title: [1.0, 0.0],
                        second.title: [0.0, 1.0],
                        third.title: [0.8, 0.6],
                    }
                ),
                threshold=0.7,
            ),
            relevance_service=RelevanceRankingService(),
            summarization_service=SummarizationService(FakeSummaryProvider("Summary.")),
            story_limit=2,
        )

        digest = orchestrator.build_digest(
            hacker_news_limit=5,
            rss_feeds=(("https://example.com/feed.xml", "city-feed"),),
            repositories=("acme/tooling",),
            context=UserProjectContext(interests=("AI engineering", "Python", "React")),
        )

        self.assertEqual(digest.story_limit, 2)
        self.assertEqual(digest.story_count, 2)
        self.assertEqual(digest.stories[0].title, third.title)
        self.assertEqual(digest.stories[1].title, second.title)
