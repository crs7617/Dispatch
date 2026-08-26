"""Manual Telegram smoke test for sending a real Dispatch digest.

Set DISPATCH_TELEGRAM_BOT_TOKEN and DISPATCH_TELEGRAM_CHAT_ID before running:
    DISPATCH_TELEGRAM_BOT_TOKEN=... DISPATCH_TELEGRAM_CHAT_ID=... python scripts/smoke_telegram.py
"""

from __future__ import annotations

import os

from app.clients.telegram import TelegramBotClient
from app.models.digest import Digest
from app.models.news_item import NewsItem, Source
from app.services.telegram_delivery import TelegramDigestDeliveryService


def build_sample_digest() -> Digest:
    stories = (
        NewsItem(
            source=Source.HN,
            source_id="42",
            title="Python and AI agents are changing backend engineering",
            url="https://news.ycombinator.com/item?id=42",
            summary="Teams are using Python-driven AI agents to streamline backend engineering workflows.",
            content="Developers report improved automation and code review assistance.",
        ),
        NewsItem(
            source=Source.GITHUB,
            source_id="release-1",
            title="FastAPI adds new developer tooling",
            url="https://github.com/fastapi/fastapi/releases",
            summary="The new release improves developer tooling for API teams.",
            content="The update includes better developer ergonomics and workflow improvements.",
        ),
    )
    return Digest(stories=stories, story_limit=10)


def main() -> None:
    token = os.getenv("DISPATCH_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("DISPATCH_TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise SystemExit(
            "Set DISPATCH_TELEGRAM_BOT_TOKEN and DISPATCH_TELEGRAM_CHAT_ID before running this smoke test."
        )

    client = TelegramBotClient(token=token, chat_id=chat_id)
    service = TelegramDigestDeliveryService(client)
    responses = service.deliver(build_sample_digest())
    print(f"Delivered {len(responses)} Telegram message(s).")


if __name__ == "__main__":
    main()
