"""Unit tests for Hacker News story collection and normalization."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import unittest

from app.collectors.hacker_news import HackerNewsCollector
from app.models.news_item import Source


class FakeHackerNewsClient:
    """In-memory substitute for HackerNewsClient used by collector tests."""

    def __init__(self, top_story_ids: list[int], items: dict[int, dict[str, Any] | None]):
        self.top_story_ids = top_story_ids
        self.items = items
        self.requested_item_ids: list[int] = []

    def get_top_story_ids(self) -> list[int]:
        return self.top_story_ids

    def get_item(self, item_id: int) -> dict[str, Any] | None:
        self.requested_item_ids.append(item_id)
        return self.items[item_id]


def story(item_id: int, **overrides: Any) -> dict[str, Any]:
    """Build a valid HN story payload for a test, with optional overrides."""
    payload: dict[str, Any] = {
        "id": item_id,
        "type": "story",
        "title": f"Story {item_id}",
        "url": f"https://example.com/{item_id}",
        "by": "dispatch",
        "time": 1_700_000_000,
    }
    payload.update(overrides)
    return payload


class HackerNewsCollectorTests(unittest.TestCase):
    """Verify filtering and mapping without HTTP requests."""

    def collect(self, ids: list[int], items: dict[int, dict[str, Any] | None], limit: int):
        client = FakeHackerNewsClient(ids, items)
        return HackerNewsCollector(client).collect(limit), client

    def test_valid_story_is_mapped_to_news_item(self) -> None:
        items, _ = self.collect([101], {101: story(101)}, limit=1)

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.source, Source.HN)
        self.assertEqual(item.source_id, "101")
        self.assertEqual(item.title, "Story 101")
        self.assertEqual(item.url, "https://example.com/101")
        self.assertEqual(item.author, "dispatch")
        self.assertEqual(
            item.published_at,
            datetime.fromtimestamp(1_700_000_000, tz=timezone.utc),
        )
        self.assertIsNone(item.summary)
        self.assertIsNone(item.content)
        self.assertEqual(item.tags, [])

    def test_multiple_valid_stories_preserve_api_order(self) -> None:
        items, _ = self.collect(
            [303, 101, 202],
            {303: story(303), 101: story(101), 202: story(202)},
            limit=3,
        )

        self.assertEqual([item.source_id for item in items], ["303", "101", "202"])

    def test_limit_restricts_requested_story_ids(self) -> None:
        items, client = self.collect(
            [101, 202, 303],
            {101: story(101), 202: story(202), 303: story(303)},
            limit=2,
        )

        self.assertEqual([item.source_id for item in items], ["101", "202"])
        self.assertEqual(client.requested_item_ids, [101, 202])

    def test_deleted_dead_non_story_and_none_items_are_skipped(self) -> None:
        items, _ = self.collect(
            [101, 202, 303, 404, 505],
            {
                101: story(101, deleted=True),
                202: story(202, dead=True),
                303: story(303, type="comment"),
                404: None,
                505: story(505),
            },
            limit=5,
        )

        self.assertEqual([item.source_id for item in items], ["505"])

    def test_missing_url_uses_hacker_news_discussion_url(self) -> None:
        items, _ = self.collect([101], {101: story(101, url="")}, limit=1)

        self.assertEqual(
            items[0].url,
            "https://news.ycombinator.com/item?id=101",
        )

    def test_missing_or_malformed_required_fields_are_skipped(self) -> None:
        items, _ = self.collect(
            [101, 202, 303],
            {
                101: story(101, title=""),
                202: story(202, id="202"),
                303: story(303, time="not-a-timestamp"),
            },
            limit=3,
        )

        self.assertEqual(items, [])
