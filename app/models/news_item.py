"""
app.models.news_item

MVP Pydantic model for a NewsItem in Dispatch.

This file implements the simplified, YAGNI-friendly schema you requested for the
first month of development. Keep the model intentionally small so ingestion,
storage and UI work can move forward quickly. Extra fields (embeddings,
popularity, dedup ids, raw_payload, etc.) are introduced only when we need them.

Design notes:
- id: internal stable UUID (default generated)
- source: enum identifying the source type (keeps parsing logic explicit)
- source_id: native ID from the source when available (optional)
- title, url: required core display/link fields
- published_at: optional, original publish time when available
- fetched_at: required (defaulted to now) to track ingestion time
- author, summary, content, tags: optional enrichments for UI and summarization

This model intentionally avoids heavy validation (no URL coercion, no
content extraction) to keep dependencies and friction low for the MVP.
"""
from __future__ import annotations

from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Source(str, Enum):
    """Canonical source types for initial collectors."""

    GITHUB = "github"
    HN = "hackernews"
    RSS = "rss"
    REDDIT = "reddit"
    YOUTUBE = "youtube"
    BLOG = "blog"
    OTHER = "other"


class NewsItem(BaseModel):
    """Minimal, production-minded NewsItem model for Dispatch (MVP).

    Field choices are intentionally conservative to support basic display,
    dedup/upsert by source_id, summarization and tag-based personalization.
    """

    id: UUID = Field(
        default_factory=uuid4,
        description="Internal stable UUID for the item (not the source id)",
    )

    source: Source = Field(..., description="Source type (one of Source enum)")

    source_id: Optional[str] = Field(
        None, description="Native identifier from the source (when available)"
    )

    title: str = Field(..., description="Primary headline/title")

    url: str = Field(..., description="Primary URL to the content")

    published_at: Optional[datetime] = Field(
        None,
        description=(
            "Original publication time, if provided by the source. Store in UTC."
        ),
    )

    fetched_at: datetime = Field(
        default_factory=datetime.utcnow,
        description=(
            "When Dispatch ingested this item. Default: current UTC time."
        ),
    )

    author: Optional[str] = Field(None, description="Author or poster display name")

    summary: Optional[str] = Field(
        None, description="Short summary (auto-generated or source-provided)"
    )

    content: Optional[str] = Field(
        None, description="Extracted full text or post body when available"
    )

    tags: List[str] = Field(default_factory=list, description="Topical tags")

    class Config:
        orm_mode = True
        validate_assignment = True


__all__ = ["NewsItem", "Source"]
