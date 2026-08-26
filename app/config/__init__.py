"""Shared Dispatch configuration bootstrap."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_environment() -> None:
    """Load the project's .env file before any os.getenv lookups occur."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)


load_environment()

__all__ = ["load_environment"]
