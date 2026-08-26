# Dispatch

Dispatch is a simple daily AI-powered tech news digest that collects stories, deduplicates them, ranks the results by relevance, summarizes the best items, assembles a digest, and sends it to Telegram.

## Manual run

Use the same pipeline immediately without waiting for the scheduled job:

```bash
python scripts/run_dispatch.py
```

The script executes the same Dispatch pipeline as the scheduler:

- collect
- deduplicate
- relevance ranking
- summarization
- digest assembly
- Telegram delivery

Environment variables needed by the real pipeline:

```bash
export DISPATCH_TELEGRAM_BOT_TOKEN="..."
export DISPATCH_TELEGRAM_CHAT_ID="..."
export DISPATCH_RSS_FEEDS="https://example.com/feed.xml|tech-feed;https://example.org/news.xml|more-news"
export DISPATCH_GITHUB_REPOS="octo/project,fastapi/fastapi"
export DISPATCH_SCHEDULE_TIME="09:00"
export DISPATCH_TIMEZONE="UTC"
```

## Scheduled run

Run the scheduler loop in the configured timezone and time:

```bash
DISPATCH_TELEGRAM_BOT_TOKEN="..." \
DISPATCH_TELEGRAM_CHAT_ID="..." \
DISPATCH_SCHEDULE_TIME="09:00" \
DISPATCH_TIMEZONE="UTC" \
python -m app.scheduler
```

To trigger the schedule immediately for a test run without waiting for the next time window:

```bash
python -m app.scheduler --run-now
```

The scheduler uses a daily local time and a timezone-aware check to avoid overlaps. Failed broadcasts are logged but do not stop future runs.
