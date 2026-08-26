"""Thin Telegram Bot HTTP client for Dispatch message delivery."""

from __future__ import annotations

import os
from typing import Any, Sequence

import httpx


class TelegramDeliveryError(RuntimeError):
    """Raised when Telegram rejects a delivery request or the bot configuration is invalid."""


class TelegramBotClient:
    """Synchronous client for Telegram's Bot HTTP API."""

    BASE_URL = "https://api.telegram.org"

    def __init__(
        self,
        *,
        token: str | None = None,
        chat_id: str | int | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.token = (token or os.getenv("DISPATCH_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
        self.chat_id = chat_id if chat_id is not None else (
            os.getenv("DISPATCH_TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID") or ""
        )
        if not self.token and not token and not os.getenv("DISPATCH_TELEGRAM_BOT_TOKEN") and not os.getenv("TELEGRAM_BOT_TOKEN"):
            raise ValueError("DISPATCH_TELEGRAM_BOT_TOKEN must be configured before sending Telegram messages")
        if not str(self.chat_id).strip() and chat_id is None and not os.getenv("DISPATCH_TELEGRAM_CHAT_ID") and not os.getenv("TELEGRAM_CHAT_ID"):
            raise ValueError("DISPATCH_TELEGRAM_CHAT_ID must be configured before sending Telegram messages")
        self._http_client = http_client or httpx.Client(timeout=10.0)

    def send_message(self, text: str) -> dict[str, Any]:
        """Send a single plain-text Telegram message."""
        if not self.token:
            raise ValueError("DISPATCH_TELEGRAM_BOT_TOKEN must be configured before sending Telegram messages")
        if not str(self.chat_id).strip():
            raise ValueError("DISPATCH_TELEGRAM_CHAT_ID must be configured before sending Telegram messages")
        if not text or not text.strip():
            raise ValueError("message text must not be blank")

        response = self._http_client.post(
            f"{self.BASE_URL}/bot{self.token}/sendMessage",
            json={
                "chat_id": self.chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
        )
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, dict):
            raise TelegramDeliveryError("Telegram API returned an invalid response payload")
        if not payload.get("ok"):
            description = payload.get("description") or "unknown Telegram API error"
            raise TelegramDeliveryError(f"Telegram API rejected the message: {description}")

        return payload

    def send_messages(self, texts: Sequence[str]) -> list[dict[str, Any]]:
        """Send a sequence of messages in order and return each response payload."""
        if not texts:
            return []
        return [self.send_message(text) for text in texts]


__all__ = ["TelegramBotClient", "TelegramDeliveryError"]
