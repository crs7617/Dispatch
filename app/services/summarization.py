"""Grounded summarization for dispatch news items."""

from __future__ import annotations

import os
import re
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
        "You are a grounded news summarizer. Base every sentence on the supplied "
        "source material only. Do not invent facts, numbers, dates, motives, "
        "consequences, or context. Keep the output concise and useful for a "
        "Telegram news digest."
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
            "Return a brief, factual summary and a separate Why it matters explanation.\n"
            "Return exactly two labeled lines:\n"
            "Summary: 1-3 concise sentences grounded only in the source. Avoid repeating the title.\n"
            "Why it matters: Give only additional context or significance supported by the source. "
            "Never simply repeat the Summary. If the source does not provide enough context, say: "
            "'The source does not provide enough context to explain why this matters.'\n\n"
            "Do not invent facts, do not repeat the same sentence in both sections, and do not echo the prompt."
        )

    @staticmethod
    def _normalize_summary(raw_summary: str) -> str:
        """Trim whitespace and reject empty or placeholder responses."""
        summary = (raw_summary or "").strip()
        if not summary:
            raise ValueError("LLM provider returned an empty summary")

        summary = re.sub(r"(?is)^\s*summary\s*:\s*", "", summary)
        if re.search(r"(?is)\bwhy it matters\s*:", summary):
            summary = re.split(r"(?is)\bwhy it matters\s*:", summary, maxsplit=1)[0].strip()
        summary = summary.strip(" -\t\r\n")
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
        raw_key = api_key if api_key is not None else os.getenv("DISPATCH_LLM_API_KEY")
        self.api_key = raw_key.strip() if isinstance(raw_key, str) else raw_key
        base_url_value = base_url if base_url is not None else os.getenv("DISPATCH_LLM_BASE_URL")
        self.base_url = (base_url_value or "https://api.openai.com/v1").rstrip("/")
        model_name_value = model_name if model_name is not None else os.getenv("DISPATCH_LLM_MODEL")
        self.model_name = model_name_value or "gpt-4o-mini"
        self._http_client = http_client or httpx.Client(timeout=10.0)

    @staticmethod
    def _extract_text(value: Any) -> str | None:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, str):
                    item_text = item.strip()
                    if item_text:
                        parts.append(item_text)
                elif isinstance(item, dict):
                    text = OpenAICompatibleLLMProvider._extract_text(item.get("text"))
                    if text:
                        parts.append(text)
                    else:
                        nested = OpenAICompatibleLLMProvider._extract_text(item.get("content"))
                        if nested:
                            parts.append(nested)
            combined = " ".join(parts).strip()
            return combined or None
        if isinstance(value, dict):
            for key in ("text", "content"):
                extracted = OpenAICompatibleLLMProvider._extract_text(value.get(key))
                if extracted:
                    return extracted
            nested_parts = value.get("parts")
            if nested_parts is not None:
                return OpenAICompatibleLLMProvider._extract_text(nested_parts)
        return None

    @staticmethod
    def _clean_generated_summary(raw_summary: str, *, prompt: str | None = None) -> str:
        """Normalize model output and reject prompt echoes."""
        summary = (raw_summary or "").strip()
        if not summary:
            raise ValueError("LLM provider returned an empty summary")

        content = summary
        if re.search(r"(?is)\bwhy it matters\s*:", content):
            content = re.split(r"(?is)\bwhy it matters\s*:", content, maxsplit=1)[0].strip()
        content = re.sub(r"(?is)^\s*summary\s*:\s*", "", content).strip(" -\t\r\n")

        if not content:
            raise ValueError("LLM provider returned an empty summary")
        if prompt and prompt.strip() and content == prompt.strip():
            raise ValueError("LLM provider returned the prompt instead of a summary")
        return content

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
        content = self._extract_text(message)
        if not content:
            raise ValueError("LLM provider returned an empty summary")

        return self._clean_generated_summary(content, prompt=prompt)


__all__ = [
    "LLMProvider",
    "OpenAICompatibleLLMProvider",
    "SummarizationService",
]
