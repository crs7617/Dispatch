"""Dispatch application package bootstrap."""

from __future__ import annotations

from app.config import load_environment

load_environment()

__all__ = ["load_environment"]
