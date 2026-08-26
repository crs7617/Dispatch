"""Simple, editable project/user context for relevance scoring."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

DEFAULT_INTERESTS = [
    "AI engineering",
    "AI agents",
    "Python",
    "FastAPI",
    "React",
    "backend engineering",
    "system design",
    "developer tools",
    "cloud/devops",
]


@dataclass(frozen=True)
class UserProjectContext:
    """Small configuration object used to rank news items by importance to a user."""

    interests: tuple[str, ...] = field(default_factory=lambda: tuple(DEFAULT_INTERESTS))

    @classmethod
    def default(cls) -> "UserProjectContext":
        """Return the default project context shipped with Dispatch."""
        return cls(interests=tuple(DEFAULT_INTERESTS))

    @classmethod
    def from_file(cls, path: str | Path | None = None) -> "UserProjectContext":
        """Load a JSON configuration file, falling back to the built-in defaults."""
        config_path = Path(path) if path else Path(__file__).with_name("user_context.json")
        if not config_path.exists():
            return cls.default()

        with config_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        interests = payload.get("interests", DEFAULT_INTERESTS)
        if not isinstance(interests, list) or not interests:
            return cls.default()

        normalized = tuple(str(item).strip() for item in interests if str(item).strip())
        return cls(interests=normalized or cls.default().interests)

    def normalized(self) -> tuple[str, ...]:
        """Return a non-empty, trimmed tuple of interest phrases."""
        return tuple(item.strip() for item in self.interests if item and item.strip())

    def keywords(self) -> tuple[str, ...]:
        """Flatten multi-word interests into single-word keywords for lightweight matching."""
        keywords: list[str] = []
        for interest in self.normalized():
            tokens = [token for token in interest.lower().replace("/", " ").split() if token]
            keywords.extend(tokens)
        return tuple(dict.fromkeys(keywords))


ProjectContext = UserProjectContext
UserContext = UserProjectContext

__all__ = [
    "DEFAULT_INTERESTS",
    "ProjectContext",
    "UserContext",
    "UserProjectContext",
]
