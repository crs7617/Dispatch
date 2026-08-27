"""Shared Dispatch configuration bootstrap."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def _candidate_env_paths() -> list[Path]:
    """Return the most likely project .env locations for local and unattended launches."""
    candidates: list[Path] = []
    seen: set[Path] = set()

    for base in (Path.cwd(), Path(__file__).resolve().parents[2]):
        for candidate in (base, *base.parents):
            normalized = candidate.resolve()
            if normalized in seen:
                continue
            seen.add(normalized)
            candidates.append(normalized / ".env")

    return candidates


def load_environment() -> None:
    """Load the project's .env file before any os.getenv lookups occur."""
    for env_path in _candidate_env_paths():
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)


load_environment()

__all__ = ["load_environment"]
