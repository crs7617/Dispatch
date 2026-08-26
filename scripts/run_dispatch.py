"""Manual Dispatch runner used for immediate pipeline execution tests."""

from __future__ import annotations

from app.scheduler import run_dispatch_pipeline


def main() -> None:
    run_dispatch_pipeline()


if __name__ == "__main__":
    main()
