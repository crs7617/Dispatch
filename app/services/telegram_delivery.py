"""Format and deliver Dispatch digests to Telegram."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from app.clients.telegram import TelegramBotClient, TelegramDeliveryError
from app.models.digest import Digest
from app.models.news_item import NewsItem


class TelegramDigestFormatter:
    """Convert a Digest into Telegram-safe text with chunk splitting."""

    MAX_MESSAGE_CHARS = 4_096

    def format_digest(self, digest: Digest) -> str:
        """Build a readable digest message without hardcoded credentials."""
        header = (
            f"Dispatch Daily Digest — {digest.generated_at.astimezone(timezone.utc):%Y-%m-%d %H:%M UTC}"
        )
        lines = [header, ""]

        if digest.source_failures:
            lines.append(f"Source issues: {', '.join(digest.source_failures)}")
            lines.append("")

        if not digest.stories:
            lines.append("No stories were available for this digest.")
            return "\n".join(lines).strip()

        for index, item in enumerate(digest.stories, start=1):
            lines.append(f"{index}. {item.title}")
            if item.summary and item.summary.strip():
                lines.append(f"Summary: {self._compact(item.summary)}")
            else:
                lines.append("Summary: Not available.")

            reason = self._why_it_matters(item)
            if reason:
                lines.append(f"Why it matters: {reason}")

            lines.append(f"Source: {item.source.value}")
            lines.append(f"URL: {item.url}")
            lines.append("")

        return "\n".join(lines).rstrip()

    def split_messages(self, digest: Digest) -> list[str]:
        """Break a digest into Telegram message chunks that stay under the size cap."""
        text = self.format_digest(digest)
        if not text:
            return []
        if len(text) <= self.MAX_MESSAGE_CHARS:
            return [text]

        chunks: list[str] = []
        current_lines: list[str] = []
        current_length = 0

        for line in text.splitlines():
            prospective = "\n".join(current_lines + [line])
            if current_lines and len(prospective) > self.MAX_MESSAGE_CHARS:
                chunks.append("\n".join(current_lines).rstrip())
                current_lines = [line]
                current_length = len(line)
            else:
                current_lines.append(line)
                current_length = len("\n".join(current_lines))

        if current_lines:
            chunks.append("\n".join(current_lines).rstrip())

        results: list[str] = []
        for chunk in chunks:
            if len(chunk) <= self.MAX_MESSAGE_CHARS:
                results.append(chunk)
                continue
            for start in range(0, len(chunk), self.MAX_MESSAGE_CHARS):
                results.append(chunk[start : start + self.MAX_MESSAGE_CHARS])

        return [message for message in results if message]

    @staticmethod
    def _compact(value: str) -> str:
        return " ".join(value.replace("\r", " ").replace("\n", " ").split())

    @staticmethod
    def _why_it_matters(item: NewsItem) -> str:
        """Return a direct, evidence-backed explanation when available."""
        summary = item.summary or item.content or item.title
        if not summary:
            return ""
        clean = TelegramDigestFormatter._compact(summary)
        if len(clean) > 180:
            clean = f"{clean[:177].rstrip()}..."
        return clean


class TelegramDigestDeliveryService:
    """Send a completed Digest to Telegram in one or more messages."""

    def __init__(
        self,
        client: TelegramBotClient,
        formatter: TelegramDigestFormatter | None = None,
    ) -> None:
        self._client = client
        self._formatter = formatter or TelegramDigestFormatter()

    def deliver(self, digest: Digest) -> list[dict[str, Any]]:
        """Send the digest in Telegram-sized chunks and return response payloads."""
        texts = self._formatter.split_messages(digest)
        if not texts:
            return []
        return self._client.send_messages(texts)

    def format_digest(self, digest: Digest) -> str:
        return self._formatter.format_digest(digest)


__all__ = ["TelegramDigestDeliveryService", "TelegramDigestFormatter", "TelegramDeliveryError"]
