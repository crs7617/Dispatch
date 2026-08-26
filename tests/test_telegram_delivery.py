"""Unit tests for Telegram digest formatting and delivery."""

from __future__ import annotations

import os
from unittest import TestCase, mock

from app.clients.telegram import TelegramBotClient, TelegramDeliveryError
from app.models.digest import Digest
from app.models.news_item import NewsItem, Source
from app.services.telegram_delivery import TelegramDigestDeliveryService, TelegramDigestFormatter


class FakeHTTPClient:
    def __init__(self, *, payload: dict[str, object] | None = None) -> None:
        self.payload = payload or {"ok": True, "result": {"message_id": 123}}
        self.calls: list[tuple[str, dict[str, object]]] = []

    def post(self, url: str, json: dict[str, object]) -> "FakeResponse":
        self.calls.append((url, json))
        return FakeResponse(self.payload)


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class TelegramDeliveryTests(TestCase):
    def make_digest(self, *, story_count: int = 2) -> Digest:
        stories = []
        for index in range(story_count):
            stories.append(
                NewsItem(
                    source=Source.HN if index % 2 == 0 else Source.GITHUB,
                    source_id=f"story-{index}",
                    title=f"Story {index}: Python and AI agents in engineering",
                    url=f"https://example.com/story-{index}",
                    summary=(
                        "Teams use Python-driven AI agents to improve engineering workflows "
                        "and reduce repetitive tasks."
                    ),
                    content="This is a grounded summary of the item text.",
                )
            )
        return Digest(stories=tuple(stories), story_limit=10)

    def test_formatting_includes_digest_title_summary_and_links(self) -> None:
        digest = self.make_digest(story_count=1)

        formatted = TelegramDigestFormatter().format_digest(digest)

        self.assertIn("Dispatch Daily Digest", formatted)
        self.assertIn("1. Story 0:", formatted)
        self.assertIn("Summary:", formatted)
        self.assertIn("Source: hackernews", formatted)
        self.assertIn("URL: https://example.com/story-0", formatted)
        self.assertIn("Why it matters:", formatted)

    def test_multiple_messages_are_created_for_large_digests(self) -> None:
        big_story = "The longest story " * 150
        digest = Digest(
            stories=(
                NewsItem(
                    source=Source.RSS,
                    source_id="big-1",
                    title=big_story,
                    url="https://example.com/big-1",
                    summary=big_story,
                    content=big_story,
                ),
                NewsItem(
                    source=Source.GITHUB,
                    source_id="big-2",
                    title=big_story,
                    url="https://example.com/big-2",
                    summary=big_story,
                    content=big_story,
                ),
            ),
            story_limit=10,
        )

        messages = TelegramDigestFormatter().split_messages(digest)

        self.assertGreater(len(messages), 1)
        self.assertTrue(all(len(message) <= 4096 for message in messages))

    def test_long_digest_is_split_without_exceeding_limits(self) -> None:
        long_entries = []
        for index in range(30):
            long_entries.append(
                NewsItem(
                    source=Source.HN,
                    source_id=f"chunk-{index}",
                    title=f"Story {index}: {'Python and AI agents ' * 20}",
                    url=f"https://example.com/chunk-{index}",
                    summary=f"{'This release matters because of Python and AI agents ' * 25}",
                    content=f"{'Detailed engineering context ' * 30}",
                )
            )

        digest = Digest(stories=tuple(long_entries), story_limit=30)
        messages = TelegramDigestFormatter().split_messages(digest)

        self.assertGreater(len(messages), 1)
        self.assertTrue(all(len(message) <= 4096 for message in messages))

    def test_api_success_is_returned(self) -> None:
        fake_http = FakeHTTPClient()
        client = TelegramBotClient(
            token="test-token",
            chat_id="-100123456",
            http_client=fake_http,
        )

        result = client.send_message("hello from Dispatch")

        self.assertTrue(result["ok"])
        self.assertEqual(fake_http.calls[0][0], "https://api.telegram.org/bottest-token/sendMessage")
        self.assertEqual(fake_http.calls[0][1]["chat_id"], "-100123456")

    def test_api_failure_raises_delivery_error(self) -> None:
        fake_http = FakeHTTPClient(payload={"ok": False, "description": "Bad Request"})
        client = TelegramBotClient(token="test-token", chat_id="123", http_client=fake_http)

        with self.assertRaisesRegex(TelegramDeliveryError, "Bad Request"):
            client.send_message("fail")

    def test_missing_configuration_raises_value_error(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "DISPATCH_TELEGRAM_BOT_TOKEN"):
                TelegramBotClient(token=None, chat_id=None)

    def test_delivery_service_sends_all_chunks(self) -> None:
        fake_http = FakeHTTPClient()
        service = TelegramDigestDeliveryService(
            TelegramBotClient(token="abc", chat_id="123", http_client=fake_http)
        )
        digest = self.make_digest(story_count=3)

        result = service.deliver(digest)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["result"]["message_id"], 123)
