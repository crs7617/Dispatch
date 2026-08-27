# Dispatch

An AI-powered news aggregation pipeline that collects technical content from multiple sources, normalizes it, removes semantic duplicates, ranks it by relevance, summarizes it with an LLM, and delivers the resulting digest through Telegram.

## Architecture

![Dispatch Architecture](docs/architecture.png)

Sources → Collectors → NewsItem → Deduplication → Relevance Ranking → LLM Summarization → Digest → Telegram

Source-specific clients and collectors normalize heterogeneous external data into a shared domain model before downstream processing.

## Stack

- Python
- Pydantic
- httpx
- feedparser
- sentence-transformers
- all-MiniLM-L6-v2
- python-dotenv
- Telegram Bot API
- OpenAI-compatible LLM API
- unittest

## Setup

```bash
git clone <repo-url>
cd Dispatch
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create a `.env` file in the project root and configure the required Telegram, LLM, RSS, GitHub, timezone, and scheduling settings. Never commit `.env` or API credentials.

Run Dispatch:

```bash
python -m app.scheduler --run-now
```

Run tests:

```bash
python -m unittest discover -s tests -q
```

## Scheduling

Dispatch can be invoked manually with:

```bash
python -m app.scheduler --run-now
```

It can also be scheduled externally with Windows Task Scheduler, Linux cron/systemd timers, or macOS launchd/cron.

## Status

The current v0 pipeline works end-to-end: Collection → Deduplication → Relevance Ranking → LLM Summarization → Digest Assembly → Telegram Delivery.

## Roadmap

- [ ] Add more source adapters
- [ ] Add persistent digest history
- [ ] Improve relevance ranking
- [ ] Improve summarization and feedback
- [ ] Explore multi-user support
