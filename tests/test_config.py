"""Tests for the Dispatch environment bootstrap."""

from __future__ import annotations

import os
from pathlib import Path
from unittest import TestCase, mock

from app.config import load_environment


class EnvironmentBootstrapTests(TestCase):
    def test_load_environment_reads_project_dotenv(self) -> None:
        env_path = Path(__file__).resolve().parents[1] / ".env"
        if not env_path.exists():
            self.skipTest("project .env is not present")

        with mock.patch.dict(os.environ, {}, clear=True):
            load_environment()
            self.assertTrue(os.getenv("DISPATCH_TELEGRAM_BOT_TOKEN"))
            self.assertTrue(os.getenv("DISPATCH_TELEGRAM_CHAT_ID"))
