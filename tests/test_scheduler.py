"""Tests for the Dispatch scheduling boundary and manual pipeline runner."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from unittest import TestCase

from app.models.digest import Digest
from app.models.news_item import NewsItem, Source
from app.scheduler import DispatchScheduler, run_dispatch_pipeline


class FakeRuntimeOrchestrator:
    def __init__(self, digest: Digest) -> None:
        self._digest = digest
        self.calls: list[dict[str, object]] = []

    def build_digest(self, **kwargs: object) -> Digest:
        self.calls.append(dict(kwargs))
        return self._digest


class FakeDeliveryService:
    def __init__(self) -> None:
        self.deliveries: list[Digest] = []

    def deliver(self, digest: Digest) -> list[dict[str, object]]:
        self.deliveries.append(digest)
        return [{"ok": True, "message": "sent"}]


class FlakyOrchestrator:
    def __init__(self, digest: Digest) -> None:
        self._digest = digest
        self.calls = 0

    def build_digest(self, **kwargs: object) -> Digest:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("first attempt failed")
        return self._digest


class DispatchSchedulerTests(TestCase):
    def test_run_dispatch_pipeline_uses_existing_pipeline_components(self) -> None:
        digest = Digest(
            stories=(
                NewsItem(
                    source=Source.HN,
                    source_id="42",
                    title="Python and AI agents are changing backend engineering",
                    url="https://example.com/42",
                ),
            ),
            story_limit=10,
        )
        orchestrator = FakeRuntimeOrchestrator(digest)
        delivery_service = FakeDeliveryService()

        result = run_dispatch_pipeline(
            orchestrator=orchestrator,
            delivery_service=delivery_service,
            rss_feeds=(("https://example.com/feed.xml", "tech-feed"),),
            repositories=("octo/project",),
            hacker_news_limit=7,
            story_limit=10,
        )

        self.assertIs(result, digest)
        self.assertEqual(len(orchestrator.calls), 1)
        self.assertEqual(orchestrator.calls[0]["hacker_news_limit"], 7)
        self.assertEqual(len(delivery_service.deliveries), 1)
        self.assertIs(delivery_service.deliveries[0], digest)

    def test_scheduler_skips_overlap_and_continues_after_failures(self) -> None:
        digest = Digest(
            stories=(
                NewsItem(
                    source=Source.RSS,
                    source_id="feed:1",
                    title="Dispatch keeps delivering on time",
                    url="https://example.com/rss",
                ),
            ),
            story_limit=10,
        )
        scheduler = DispatchScheduler(
            run_time="09:00",
            timezone="UTC",
            orchestrator=FlakyOrchestrator(digest),
            delivery_service=FakeDeliveryService(),
            logger=logging.getLogger("dispatch.tests.scheduler"),
            now_fn=lambda: datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc),
        )

        self.assertIsNone(scheduler.run_once())
        self.assertIsNotNone(scheduler.run_once())

        scheduler._lock.acquire()
        try:
            self.assertIsNone(scheduler.run_once())
        finally:
            scheduler._lock.release()

    def test_scheduler_respects_configured_timezone_and_run_time(self) -> None:
        scheduler = DispatchScheduler(
            run_time="09:00",
            timezone="America/New_York",
            logger=logging.getLogger("dispatch.tests.timezone"),
            now_fn=lambda: datetime(2024, 1, 2, 14, 0, tzinfo=timezone.utc),
        )

        self.assertTrue(scheduler.should_run())
        self.assertEqual(scheduler.next_run_at().tzinfo.key, "America/New_York")
