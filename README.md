# Dispatch

Dispatch is a personal technology news digest that collects stories from multiple sources, removes duplicates, ranks them by relevance, summarizes the best items, and sends the daily digest to Telegram.

## Architecture

[ARCHITECTURE DIAGRAM]

Sources → Collect → Normalize → Deduplicate → Rank → Summarize → Telegram

## Features

- Hacker News
- RSS/Atom feeds
- GitHub releases
- Semantic deduplication
- Personalized relevance ranking
- LLM summarization
- Telegram delivery
- Scheduling

## Stack

- Python
- httpx
- feedparser
- sentence-transformers
- python-dotenv
- tzdata
- Telegram Bot API
- OpenAI-compatible LLM API

## Setup

```bash
git clone <repo-url>
cd Dispatch
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
DISPATCH_TELEGRAM_BOT_TOKEN="..."
DISPATCH_TELEGRAM_CHAT_ID="..."
DISPATCH_RSS_FEEDS="https://example.com/feed.xml|Tech Feed;https://example.org/news.xml|More News"
DISPATCH_GITHUB_REPOS="owner/repo,owner/other-repo"
DISPATCH_LLM_API_KEY="..."
DISPATCH_LLM_BASE_URL="https://api.openai.com/v1"
DISPATCH_SCHEDULE_TIME="09:00"
DISPATCH_TIMEZONE="UTC"
```

Run Dispatch:

```bash
python -m app.scheduler --run-now
```

Run tests:

```bash
python -m unittest discover -s tests -q
```

## Scheduling

Dispatch can be scheduled with the OS scheduler. Windows Task Scheduler, Linux cron/systemd, and macOS launchd/cron can all run the same command at a fixed time.

## Why Dispatch?

This project was built as a hands-on way to learn backend engineering and AI engineering by wiring together real data sources, ranking logic, summarization, and delivery into a working end-to-end system.

## Status

The pipeline runs end-to-end and the repository test suite passes.

## Future

- Add more source adapters.
- Add digest history and review workflows.
- Improve ranking and summarization tuning.
