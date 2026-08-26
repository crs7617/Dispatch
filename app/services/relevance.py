"""Deterministic relevance scoring for Dispatch news items."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Protocol, Sequence

from app.config.personalization import UserProjectContext
from app.models.news_item import NewsItem
from app.services.deduplication import EmbeddingProvider


@dataclass(frozen=True)
class RelevanceScore:
    """Normalized relevance result for one item against a user/project context."""

    score: float
    matched_terms: tuple[str, ...]


@dataclass(frozen=True)
class RankedNewsItem:
    """A NewsItem paired with its deterministic relevance score."""

    item: NewsItem
    score: float
    matched_terms: tuple[str, ...]


class RelevanceStrategy(Protocol):
    """Strategy interface for scoring a NewsItem against a user context."""

    def score(self, item: NewsItem, context: UserProjectContext) -> RelevanceScore:
        """Return the item score and matched terms for the supplied context."""


class KeywordRelevanceStrategy:
    """Lightweight keyword strategy with optional embedding enhancement."""

    def __init__(self, embedding_provider: EmbeddingProvider | None = None) -> None:
        self._embedding_provider = embedding_provider

    def score(self, item: NewsItem, context: UserProjectContext) -> RelevanceScore:
        """Compute a deterministic score using explicit interest overlap."""
        if not context.normalized():
            return RelevanceScore(score=0.0, matched_terms=())

        text = self._item_text(item)
        if not text:
            return RelevanceScore(score=0.0, matched_terms=())

        matched_terms: list[str] = []
        for interest in context.normalized():
            normalized_interest = interest.casefold()
            if normalized_interest in text:
                matched_terms.append(interest)

        score = 0.0
        if matched_terms:
            score = float(len(matched_terms) * 10.0)
            for interest in context.normalized():
                normalized_interest = interest.casefold()
                if normalized_interest in text:
                    score += self._term_weight(interest, text)

            if self._embedding_provider is not None:
                score += self._embedding_bonus(item, context)

        return RelevanceScore(score=score, matched_terms=tuple(matched_terms))

    def _embedding_bonus(self, item: NewsItem, context: UserProjectContext) -> float:
        """Use the shared embedding abstraction when a provider is available."""
        text = self._item_text(item)
        context_text = " ".join(context.normalized())
        if not text or not context_text:
            return 0.0

        try:
            embeddings = self._embedding_provider.embed([text, context_text])
        except (TypeError, ValueError, AttributeError):
            return 0.0

        if len(embeddings) != 2:
            return 0.0

        left = embeddings[0]
        right = embeddings[1]
        if not left or not right or len(left) != len(right):
            return 0.0

        dot_product = sum(a * b for a, b in zip(left, right))
        left_norm = sqrt(sum(value * value for value in left))
        right_norm = sqrt(sum(value * value for value in right))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0

        similarity = dot_product / (left_norm * right_norm)
        return max(0.0, similarity)

    @staticmethod
    def _term_weight(term: str, text: str) -> float:
        """Give a small preference to exact matches and multi-word phrases."""
        normalized_term = term.casefold()
        if normalized_term in text:
            if " " in normalized_term:
                return 2.0
            return 1.5
        return 0.0

    @staticmethod
    def _item_text(item: NewsItem) -> str:
        """Build a single text block from the item metadata most useful for ranking."""
        parts = [item.title]
        if item.summary:
            parts.append(item.summary)
        if item.content:
            parts.append(item.content)
        if item.tags:
            parts.append(" ".join(item.tags))
        return " ".join(part for part in parts if part and part.strip()).casefold()


class RelevanceRankingService:
    """Rank news items in deterministic order based on a user/project context."""

    def __init__(
        self,
        strategy: RelevanceStrategy | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._strategy = strategy or KeywordRelevanceStrategy(embedding_provider=embedding_provider)

    def rank(
        self,
        items: Sequence[NewsItem],
        context: UserProjectContext | Sequence[str] | None = None,
    ) -> list[RankedNewsItem]:
        """Return items sorted from most relevant to least relevant."""
        if not items:
            return []

        normalized_context = self._coerce_context(context)
        ranked = []
        for item in items:
            result = self._strategy.score(item, normalized_context)
            ranked.append(
                RankedNewsItem(
                    item=item,
                    score=result.score,
                    matched_terms=result.matched_terms,
                )
            )

        ranked.sort(
            key=lambda ranked_item: (
                -ranked_item.score,
                ranked_item.item.title.casefold(),
                ranked_item.item.url,
            )
        )
        return ranked

    def score(self, item: NewsItem, context: UserProjectContext | Sequence[str] | None = None) -> float:
        """Return the raw relevance score for a single item."""
        return self._strategy.score(item, self._coerce_context(context)).score

    @staticmethod
    def _coerce_context(
        context: UserProjectContext | Sequence[str] | None,
    ) -> UserProjectContext:
        """Accept either a single context object or a simple sequence of interest strings."""
        if context is None:
            return UserProjectContext.default()
        if isinstance(context, UserProjectContext):
            return context
        return UserProjectContext(interests=tuple(str(item).strip() for item in context if str(item).strip()))


RelevanceService = RelevanceRankingService
PersonalizationService = RelevanceRankingService

__all__ = [
    "KeywordRelevanceStrategy",
    "PersonalizationService",
    "RankedNewsItem",
    "RelevanceRankingService",
    "RelevanceScore",
    "RelevanceService",
    "RelevanceStrategy",
]
