"""Unit tests for relevance ranking based on user/project interests."""

from __future__ import annotations

from unittest import TestCase

from app.config.personalization import UserProjectContext
from app.models.news_item import NewsItem, Source
from app.services.relevance import RelevanceRankingService


def make_item(
    title: str,
    *,
    source: Source = Source.HN,
    source_id: str = "story",
    summary: str | None = None,
    content: str | None = None,
    tags: list[str] | None = None,
    url: str | None = None,
) -> NewsItem:
    return NewsItem(
        source=source,
        source_id=source_id,
        title=title,
        url=url or f"https://example.com/{source_id}",
        summary=summary,
        content=content,
        tags=tags or [],
    )


class RelevanceRankingServiceTests(TestCase):
    """Verify relevance ranking stays deterministic and simple."""

    def setUp(self) -> None:
        self.context = UserProjectContext(
            interests=(
                "AI engineering",
                "AI agents",
                "Python",
                "FastAPI",
                "React",
                "backend engineering",
                "system design",
                "developer tools",
            )
        )

    def test_highly_relevant_story_ranks_first(self) -> None:
        starred = make_item(
            "AI agents and Python power a new FastAPI backend",
            source_id="relevant-1",
            summary="Teams build AI agents with Python and FastAPI for developer tooling.",
            tags=["AI", "python", "fastapi"],
        )
        unrelated = make_item(
            "City marathon draws record crowds",
            source_id="irrelevant-1",
            summary="A weekend race is under way with thousands of spectators.",
            tags=["sports"],
        )

        ranked = RelevanceRankingService().rank([unrelated, starred], self.context)

        self.assertEqual(ranked[0].item, starred)
        self.assertGreater(ranked[0].score, ranked[1].score)
        self.assertIn("AI agents", ranked[0].matched_terms)

    def test_unrelated_story_scores_zero(self) -> None:
        unrelated = make_item(
            "The local soccer club wins in overtime",
            source_id="irrelevant-2",
            summary="Fans celebrate a dramatic finish at the stadium.",
            tags=["sports"],
        )

        ranked = RelevanceRankingService().rank([unrelated], self.context)

        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].score, 0.0)
        self.assertEqual(ranked[0].matched_terms, ())

    def test_multiple_stories_are_deterministically_ordered(self) -> None:
        relevant_short = make_item(
            "FastAPI release improves Python API performance",
            source_id="relevant-2",
            summary="The framework adds tighter Python support with a smaller runtime footprint.",
            tags=["fastapi", "python"],
        )
        relevant_long = make_item(
            "AI agents are changing backend engineering workflows",
            source_id="relevant-3",
            summary="Teams adopt AI agents to automate backend engineering tasks.",
            tags=["ai", "backend-engineering"],
        )
        unrelated = make_item(
            "Stock market closes higher after mixed earnings",
            source_id="irrelevant-3",
            summary="Investors reacted to a day of mixed sector results.",
            tags=["finance"],
        )

        ranked = RelevanceRankingService().rank(
            [relevant_short, unrelated, relevant_long], self.context
        )

        self.assertEqual(
            [item.title for item in (entry.item for entry in ranked)],
            [
                "AI agents are changing backend engineering workflows",
                "FastAPI release improves Python API performance",
                "Stock market closes higher after mixed earnings",
            ],
        )

    def test_empty_input_returns_empty_ranked_result(self) -> None:
        self.assertEqual(RelevanceRankingService().rank([], self.context), [])

    def test_missing_content_still_ranks_using_title_and_tags(self) -> None:
        item = make_item(
            "FastAPI and Python tips for AI agent teams",
            source_id="relevant-4",
            summary=None,
            content=None,
            tags=["python", "fastapi", "ai"],
        )

        ranked = RelevanceRankingService().rank([item], self.context)

        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].item, item)
        self.assertGreaterEqual(ranked[0].score, 0.0)
