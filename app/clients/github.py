"""Synchronous client for GitHub's public REST API."""

from __future__ import annotations

from typing import Any

import httpx


class GitHubClient:
    """Fetch raw GitHub release data without normalizing it."""

    BASE_URL = "https://api.github.com"

    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._http_client = http_client or httpx.Client(timeout=10.0)

    def get_releases(self, repository: str) -> list[dict[str, Any]]:
        """Return raw releases for a repository.

        Raises:
            httpx.HTTPError: If the request cannot complete successfully.
            ValueError: If ``repository`` is blank or the response is malformed.
        """
        if not repository.strip():
            raise ValueError("repository must not be blank")

        response = self._http_client.get(
            f"{self.BASE_URL}/repos/{repository}/releases",
            headers={"Accept": "application/vnd.github+json"},
        )
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, list) or not all(
            isinstance(release, dict) for release in payload
        ):
            raise ValueError("Expected GitHub releases to be a list of objects")

        return payload
