"""Scheduling entry point for the Dispatch daily digest pipeline."""

from __future__ import annotations

import argparse
import logging
import os
import re
import threading
import time
from datetime import datetime, time as dt_time, timedelta, timezone, tzinfo
from typing import Any, Callable, Sequence
from zoneinfo import ZoneInfo

from app.clients.github import GitHubClient
from app.clients.hacker_news import HackerNewsClient
from app.clients.rss import RSSFeedClient
from app.clients.telegram import TelegramBotClient
from app.collectors.github import GitHubCollector
from app.collectors.hacker_news import HackerNewsCollector
from app.collectors.rss import RSSCollector
from app.config.personalization import UserProjectContext
from app.models.digest import Digest
from app.services.digest import DigestOrchestrator
from app.services.telegram_delivery import TelegramDigestDeliveryService

DEFAULT_RUN_TIME = "09:00"
DEFAULT_TIMEZONE = "UTC"


def _default_logger() -> logging.Logger:
    logger = logging.getLogger("dispatch.scheduler")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def _parse_env_list(raw_value: str | None, *, separator: str = ",") -> tuple[str, ...]:
    if not raw_value:
        return ()
    parts = re.split(rf"[{re.escape(separator)}\n;]+", raw_value)
    return tuple(part.strip() for part in parts if part and part.strip())


def _default_rss_feeds() -> tuple[tuple[str, str], ...]:
    raw_value = os.getenv("DISPATCH_RSS_FEEDS")
    if not raw_value:
        return ()

    feeds: list[tuple[str, str]] = []
    for item in re.split(r"[;\n]+", raw_value):
        value = item.strip()
        if not value:
            continue
        if "|" in value:
            url, source_name = value.split("|", 1)
        elif "," in value:
            url, source_name = value.split(",", 1)
        else:
            url, source_name = value, "rss-feed"
        feeds.append((url.strip(), source_name.strip() or "rss-feed"))
    return tuple(feeds)


def _default_repositories() -> tuple[str, ...]:
    return _parse_env_list(os.getenv("DISPATCH_GITHUB_REPOS"))


def _default_timezone() -> tzinfo:
    timezone_name = os.getenv("DISPATCH_TIMEZONE") or os.getenv("TZ") or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        return timezone.utc


def _coerce_run_time(value: str | None) -> dt_time:
    candidate = (value or os.getenv("DISPATCH_SCHEDULE_TIME") or os.getenv("DISPATCH_RUN_TIME") or DEFAULT_RUN_TIME).strip()
    try:
        if len(candidate) == 5 and candidate.count(":") == 1:
            return dt_time.fromisoformat(candidate)
        if len(candidate) == 4 and candidate.isdigit():
            return datetime.strptime(candidate, "%H%M").time()
        if candidate.count(":") == 2:
            return dt_time.fromisoformat(candidate)
    except ValueError:
        pass
    return datetime.strptime(DEFAULT_RUN_TIME, "%H:%M").time()


class DispatchScheduler:
    """Run the Digest pipeline at a configured local time without overlapping jobs."""

    def __init__(
        self,
        *,
        run_time: str | dt_time | None = None,
        timezone: str | ZoneInfo | None = None,
        orchestrator: DigestOrchestrator | None = None,
        delivery_service: TelegramDigestDeliveryService | None = None,
        logger: logging.Logger | None = None,
        rss_feeds: Sequence[tuple[str, str]] | None = None,
        repositories: Sequence[str] | None = None,
        hacker_news_limit: int = 10,
        story_limit: int = 10,
        context: UserProjectContext | None = None,
        sleep_fn: Callable[[float], None] | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._logger = logger or _default_logger()
        self._sleep_fn = sleep_fn or time.sleep
        self._now_fn = now_fn or (lambda: datetime.now(timezone=self._resolve_timezone(timezone)))
        self._timezone = self._resolve_timezone(timezone)
        self._run_time = _coerce_run_time(run_time if isinstance(run_time, str) else None)
        if isinstance(run_time, dt_time):
            self._run_time = run_time
        self._rss_feeds = tuple(rss_feeds) if rss_feeds is not None else _default_rss_feeds()
        self._repositories = tuple(repositories) if repositories is not None else _default_repositories()
        self._hacker_news_limit = hacker_news_limit
        self._context = context
        self._story_limit = story_limit
        self._lock = threading.Lock()
        self._last_run: datetime | None = None
        self._orchestrator = orchestrator
        self._delivery_service = delivery_service

    @staticmethod
    def _resolve_timezone(timezone_name: str | tzinfo | None) -> tzinfo:
        if isinstance(timezone_name, tzinfo):
            return timezone_name
        if timezone_name is not None:
            try:
                return ZoneInfo(str(timezone_name))
            except Exception:
                pass
        return _default_timezone()

    def _build_default_orchestrator(self) -> DigestOrchestrator:
        return DigestOrchestrator(
            hacker_news_collector=HackerNewsCollector(HackerNewsClient()),
            rss_collector=RSSCollector(RSSFeedClient()),
            github_collector=GitHubCollector(GitHubClient()),
            story_limit=self._story_limit,
        )

    def _build_default_delivery_service(self) -> TelegramDigestDeliveryService:
        return TelegramDigestDeliveryService(TelegramBotClient())

    @property
    def run_time(self) -> dt_time:
        return self._run_time

    @property
    def timezone(self) -> tzinfo:
        return self._timezone

    @property
    def timezone_name(self) -> str:
        return getattr(self._timezone, "key", "UTC")

    def should_run(self, now: datetime | None = None) -> bool:
        resolved_now = now or self._now_fn()
        current_local = resolved_now.astimezone(self._timezone)
        return current_local.hour == self._run_time.hour and current_local.minute == self._run_time.minute

    def next_run_at(self, now: datetime | None = None) -> datetime:
        resolved_now = (now or self._now_fn()).astimezone(self._timezone)
        target = resolved_now.replace(hour=self._run_time.hour, minute=self._run_time.minute, second=0, microsecond=0)
        if resolved_now > target:
            target += timedelta(days=1)
        return target.astimezone(self._timezone)

    def run_once(self, *, now: datetime | None = None) -> Digest | None:
        if not self._lock.acquire(blocking=False):
            self._logger.warning("Skipping scheduled Dispatch run because another execution is already in progress.")
            return None

        try:
            if self._orchestrator is None:
                self._orchestrator = self._build_default_orchestrator()
            if self._delivery_service is None:
                self._delivery_service = self._build_default_delivery_service()

            self._logger.info("Dispatch job start")
            digest = run_dispatch_pipeline(
                orchestrator=self._orchestrator,
                delivery_service=self._delivery_service,
                logger=self._logger,
                rss_feeds=self._rss_feeds,
                repositories=self._repositories,
                hacker_news_limit=self._hacker_news_limit,
                context=self._context,
                story_limit=self._story_limit,
            )
            self._last_run = now or self._now_fn()
            return digest
        except Exception:
            self._logger.exception("Unexpected failure during scheduled Dispatch execution")
            return None
        finally:
            self._lock.release()

    def run_if_due(self, *, now: datetime | None = None) -> bool:
        resolved_now = now or self._now_fn()
        if not self.should_run(resolved_now):
            return False
        self.run_once(now=resolved_now)
        return True

    def start(self, *, interval_seconds: int = 60, stop_event: threading.Event | None = None) -> None:
        event = stop_event or threading.Event()
        while not event.is_set():
            try:
                self.run_if_due()
            except Exception:
                self._logger.exception("Unexpected failure in dispatch scheduler loop")
            self._sleep_fn(max(1, interval_seconds))

    def manual_run(self) -> Digest | None:
        return self.run_once()


def run_dispatch_pipeline(
    *,
    orchestrator: DigestOrchestrator | None = None,
    delivery_service: TelegramDigestDeliveryService | None = None,
    logger: logging.Logger | None = None,
    rss_feeds: Sequence[tuple[str, str]] | None = None,
    repositories: Sequence[str] | None = None,
    hacker_news_limit: int = 10,
    context: UserProjectContext | None = None,
    story_limit: int = 10,
) -> Digest:
    """Execute the existing digest pipeline once and send the final digest to Telegram."""
    log = logger or _default_logger()
    log.info("Dispatch job start")

    effective_orchestrator = orchestrator or DigestOrchestrator(
        hacker_news_collector=HackerNewsCollector(HackerNewsClient()),
        rss_collector=RSSCollector(RSSFeedClient()),
        github_collector=GitHubCollector(GitHubClient()),
        story_limit=story_limit,
    )

    digest = effective_orchestrator.build_digest(
        hacker_news_limit=hacker_news_limit,
        rss_feeds=rss_feeds or _default_rss_feeds(),
        repositories=repositories or _default_repositories(),
        context=context or UserProjectContext.default(),
    )

    if digest.source_failures:
        log.warning("Collector failures: %s", ", ".join(digest.source_failures))

    log.info("Digest completion: %d story(s) assembled", digest.story_count)

    if delivery_service is None:
        delivery_service = TelegramDigestDeliveryService(TelegramBotClient())

    responses = delivery_service.deliver(digest)
    log.info("Telegram delivery complete: %d message(s)", len(responses))
    return digest


DailyDigestScheduler = DispatchScheduler


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Dispatch on a schedule or immediately.")
    parser.add_argument("--run-now", action="store_true", help="Execute the Dispatch pipeline immediately and exit.")
    parser.add_argument("--time", default=None, help="Local schedule time in HH:MM or HH:MM:SS format.")
    parser.add_argument("--timezone", default=None, help="IANA timezone name for the schedule, e.g. UTC or America/New_York.")
    parser.add_argument("--interval", type=int, default=60, help="Seconds to wait between schedule checks while running continuously.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    logger = _default_logger()
    scheduler = DispatchScheduler(
        run_time=args.time,
        timezone=args.timezone,
        logger=logger,
    )

    if args.run_now:
        scheduler.run_once()
        return

    logger.info("Dispatch scheduler waiting for %s in %s", scheduler.run_time.isoformat(), scheduler.timezone_name)
    scheduler.start(interval_seconds=args.interval)


if __name__ == "__main__":
    main()


__all__ = [
    "DEFAULT_RUN_TIME",
    "DEFAULT_TIMEZONE",
    "DailyDigestScheduler",
    "DispatchScheduler",
    "main",
    "run_dispatch_pipeline",
]
