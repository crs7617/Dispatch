"""Grounded summarization for dispatch news items."""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

import httpx

from app.models.news_item import NewsItem


class LLMProvider(Protocol):
    """Abstract provider that returns a grounded summary for a prompt."""

    def summarize(self, prompt: str) -> str:
        """Return a textual summary for the supplied prompt."""


class SummarizationService:
    """Summarize a NewsItem using an injected LLM provider."""

    SYSTEM_PROMPT = (
        "You are a grounded news summarizer. Summarize only the facts explicitly "
        "present in the supplied source material. Do not invent facts, dates, "
        "quotes, releases, numbers, or claims. If the item is brief or sparse, "
        "say so plainly without adding unsupported details."
    )

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def summarize(self, item: NewsItem) -> NewsItem:
        """Generate a grounded summary and write it back to ``item.summary``."""
        prompt = self._build_prompt(item)
        if not prompt.strip():
            raise ValueError("NewsItem must contain title or source text to summarize")

        summary = self._provider.summarize(prompt)
        normalized = self._normalize_summary(summary)
        item.summary = normalized
        return item

    def summarize_item(self, item: NewsItem) -> NewsItem:
        """Alias kept for clarity when callers pass a single item."""
        return self.summarize(item)

    def generate_summary(self, item: NewsItem) -> str:
        """Generate and return the summary text without a separate item mutation."""
        return self.summarize(item).summary or ""

    def _build_prompt(self, item: NewsItem) -> str:
        """Collect only the item fields that can support a grounded summary."""
        sections: list[str] = []

        title = (item.title or "").strip()
        if title:
            sections.append(f"Title: {title}")

        if item.summary and item.summary.strip():
            sections.append(f"Existing summary: {item.summary.strip()}")

        if item.content and item.content.strip():
            sections.append(f"Content:\n{item.content.strip()}")

        if not sections:
            return ""

        return (
            f"{self.SYSTEM_PROMPT}\n\n"
            "Source material:\n"
            f"{chr(10).join(sections)}\n\n"
            "Return a brief, factual summary in 1-3 sentences."
        )

    @staticmethod
    def _normalize_summary(raw_summary: str) -> str:
        """Trim whitespace and reject empty or placeholder responses."""
        summary = (raw_summary or "").strip()
        if not summary:
            raise ValueError("LLM provider returned an empty summary")
        return summary


class OpenAICompatibleLLMProvider:
    """A thin, env-configurable OpenAI-compatible chat completion provider."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("DISPATCH_LLM_API_KEY")
        self.base_url = (base_url or os.getenv("DISPATCH_LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.model_name = model_name or os.getenv("DISPATCH_LLM_MODEL") or "gpt-4o-mini"
        self._http_client = http_client or httpx.Client(timeout=10.0)

    def summarize(self, prompt: str) -> str:
        """Ask an OpenAI-compatible endpoint for a grounded summary."""
        if not self.api_key:
            raise ValueError("DISPATCH_LLM_API_KEY must be set before using the LLM provider")

        response = self._http_client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model_name,
                "messages": [
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
            },
        )
        response.raise_for_status()

        payload = response.json()
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("LLM provider returned no choices")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("LLM provider returned an invalid choice")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("LLM provider returned no message payload")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("LLM provider returned an empty summary")

        return content.strip()


__all__ = [
    "LLMProvider",
    "OpenAICompatibleLLMProvider",
    "SummarizationService",
]
