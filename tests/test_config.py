"""Tests for the Dispatch environment bootstrap."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

import app.config as app_config
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

    def test_load_environment_falls_back_to_current_working_directory(self) -> None:
        with TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("DISPATCH_TELEGRAM_BOT_TOKEN=from-cwd\nDISPATCH_TELEGRAM_CHAT_ID=12345\n", encoding="utf-8")

            original_cwd = Path.cwd()
            original_attr = app_config.__file__
            try:
                os.chdir(tmpdir)
                app_config.__file__ = str(Path(tmpdir) / "missing" / "app" / "config" / "__init__.py")
                with mock.patch.dict(os.environ, {}, clear=True):
                    load_environment()
                    self.assertEqual(os.getenv("DISPATCH_TELEGRAM_BOT_TOKEN"), "from-cwd")
                    self.assertEqual(os.getenv("DISPATCH_TELEGRAM_CHAT_ID"), "12345")
            finally:
                app_config.__file__ = original_attr
                os.chdir(original_cwd)
