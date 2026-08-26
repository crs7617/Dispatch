"""Unit tests for grounded news summarization."""

from __future__ import annotations

import json
from unittest import TestCase, mock

import httpx

from app.models.news_item import NewsItem, Source
from app.services.summarization import (
    OpenAICompatibleLLMProvider,
    SummarizationService,
)


class FakeLLMProvider:
    """Deterministic provider for summary tests."""

    def __init__(self, summary: str = "A concise summary.") -> None:
        self.summary = summary
        self.calls: list[str] = []

    def summarize(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.summary


class SummarizationServiceTests(TestCase):
    """Verify grounded summarization behavior and provider integration."""

    def test_normal_article_is_summarized_and_stored(self) -> None:
        item = NewsItem(
            source=Source.HN,
            source_id="42",
            title="Python 3.14 is released",
            url="https://example.com/python-3-14",
            content="Python 3.14 adds a faster parser and better typing support.",
        )
        provider = FakeLLMProvider("This release improves parsing and typing support.")

        result = SummarizationService(provider).summarize(item)

        self.assertIs(result, item)
        self.assertEqual(item.summary, "This release improves parsing and typing support.")
        self.assertIn("Python 3.14 is released", provider.calls[0])
        self.assertIn("better typing support", provider.calls[0])

    def test_missing_content_uses_title_and_metadata(self) -> None:
        item = NewsItem(
            source=Source.RSS,
            source_id="feed:1",
            title="New release candidate",
            url="https://example.com/release-candidate",
            author="Ada",
        )
        provider = FakeLLMProvider("This item announces a new release candidate.")

        SummarizationService(provider).summarize(item)

        prompt = provider.calls[0]
        self.assertIn("Title: New release candidate", prompt)
        self.assertIn("Return a brief, factual summary", prompt)
        self.assertNotIn("Content:", prompt)

    def test_empty_input_raises_value_error(self) -> None:
        item = NewsItem(
            source=Source.GITHUB,
            source_id="empty",
            title="   ",
            url="https://example.com/empty",
            content="  ",
        )

        with self.assertRaisesRegex(ValueError, "NewsItem must contain title or source text"):
            SummarizationService(FakeLLMProvider()).summarize(item)

    def test_provider_failure_is_propagated(self) -> None:
        class FailingProvider:
            def summarize(self, prompt: str) -> str:
                raise RuntimeError("LLM outage")

        item = NewsItem(
            source=Source.HN,
            source_id="99",
            title="A title",
            url="https://example.com/99",
            content="Some content.",
        )

        with self.assertRaisesRegex(RuntimeError, "LLM outage"):
            SummarizationService(FailingProvider()).summarize(item)

    def test_summary_is_grounded_in_available_input(self) -> None:
        item = NewsItem(
            source=Source.GITHUB,
            source_id="release-1",
            title="Release 1.0",
            url="https://example.com/release-1",
            content="Release 1.0 adds search and removes the old dashboard.",
        )
        provider = FakeLLMProvider("This release adds search and removes the old dashboard.")

        SummarizationService(provider).summarize(item)

        prompt = provider.calls[0]
        self.assertIn("Release 1.0 adds search and removes the old dashboard", prompt)
        self.assertNotIn("a complete rewrite", prompt)
        self.assertNotIn("new AI features", prompt)

    def test_environment_provider_reads_configuration(self) -> None:
        class FakeHTTPClient:
            def __init__(self) -> None:
                self.calls: list[tuple[str, dict[str, object]]] = []

            def post(self, url: str, headers: dict[str, str], json: dict[str, object]) -> object:
                self.calls.append((url, json))
                return FakeResponse({
                    "choices": [
                        {"message": {"content": "Grounded summary from the mock environment provider."}}
                    ]
                })

        class FakeResponse:
            def __init__(self, payload: dict[str, object]) -> None:
                self._payload = payload

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return self._payload

        fake_http = FakeHTTPClient()
        with mock.patch.dict(
            "os.environ",
            {
                "DISPATCH_LLM_API_KEY": "test-key",
                "DISPATCH_LLM_BASE_URL": "https://example.com/api",
                "DISPATCH_LLM_MODEL": "test-model",
            },
            clear=False,
        ):
            provider = OpenAICompatibleLLMProvider(http_client=fake_http)
            summary = provider.summarize("Summarize this article")

        self.assertEqual(summary, "Grounded summary from the mock environment provider.")
        self.assertEqual(fake_http.calls[0][0], "https://example.com/api/chat/completions")
        self.assertEqual(fake_http.calls[0][1]["model"], "test-model")
        self.assertEqual(fake_http.calls[0][1]["messages"][0]["content"], "Summarize this article")
