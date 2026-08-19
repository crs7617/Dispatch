"""Unit tests for GitHub release collection and normalization."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import unittest

from app.collectors.github import GitHubCollector
from app.models.news_item import Source


class FakeGitHubClient:
    """In-memory substitute for GitHubClient used by collector tests."""

    def __init__(self, releases_by_repository: dict[str, list[dict[str, Any]]]) -> None:
        self.releases_by_repository = releases_by_repository
        self.requested_repositories: list[str] = []

    def get_releases(self, repository: str) -> list[dict[str, Any]]:
        self.requested_repositories.append(repository)
        return self.releases_by_repository[repository]


def release(release_id: int, **overrides: Any) -> dict[str, Any]:
    """Build a valid GitHub release payload for a test."""
    payload: dict[str, Any] = {
        "id": release_id,
        "name": f"Release {release_id}",
        "tag_name": f"v{release_id}.0.0",
        "html_url": f"https://github.com/example/project/releases/tag/v{release_id}.0.0",
        "published_at": "2024-01-02T03:04:05Z",
        "author": {"login": "octocat"},
        "body": "Release notes",
    }
    payload.update(overrides)
    return payload


class GitHubCollectorTests(unittest.TestCase):
    """Verify release filtering, ordering, and mapping without HTTP requests."""

    def collect(self, releases_by_repository: dict[str, list[dict[str, Any]]], repositories: list[str]):
        client = FakeGitHubClient(releases_by_repository)
        return GitHubCollector(client).collect(repositories), client

    def test_normal_release_maps_to_news_item(self) -> None:
        items, _ = self.collect({"example/project": [release(101)]}, ["example/project"])

        item = items[0]
        self.assertEqual(item.source, Source.GITHUB)
        self.assertEqual(item.source_id, "101")
        self.assertEqual(item.title, "Release 101")
        self.assertEqual(item.author, "octocat")
        self.assertEqual(item.content, "Release notes")
        self.assertEqual(
            item.published_at,
            datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        )
        self.assertIsNone(item.summary)
        self.assertEqual(item.tags, [])

    def test_empty_release_name_falls_back_to_tag_name(self) -> None:
        items, _ = self.collect(
            {"example/project": [release(101, name="")]}, ["example/project"]
        )

        self.assertEqual(items[0].title, "v101.0.0")

    def test_missing_optional_fields_are_allowed(self) -> None:
        items, _ = self.collect(
            {"example/project": [release(101, author=None, body=None, published_at=None)]},
            ["example/project"],
        )

        self.assertIsNone(items[0].author)
        self.assertIsNone(items[0].content)
        self.assertIsNone(items[0].published_at)

    def test_unusable_release_is_skipped(self) -> None:
        items, _ = self.collect(
            {
                "example/project": [
                    release(101, html_url=""),
                    release(202, name="", tag_name=""),
                    release(303),
                ]
            },
            ["example/project"],
        )

        self.assertEqual([item.source_id for item in items], ["303"])

    def test_repositories_and_releases_have_deterministic_order(self) -> None:
        items, client = self.collect(
            {
                "first/repo": [
                    release(101, published_at="2023-01-01T00:00:00Z"),
                    release(102, published_at="2024-01-01T00:00:00Z"),
                ],
                "second/repo": [release(201)],
            },
            ["first/repo", "second/repo"],
        )

        self.assertEqual([item.source_id for item in items], ["102", "101", "201"])
        self.assertEqual(client.requested_repositories, ["first/repo", "second/repo"])
