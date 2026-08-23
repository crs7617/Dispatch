"""Concrete local embedding providers."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any


DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def _load_sentence_transformer(model_name: str) -> Any:
    """Load a sentence-transformers model only when it is first needed."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


class LocalSentenceEmbeddingProvider:
    """Reusable local sentence-transformers embedding provider."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        model_loader: Callable[[str], Any] = _load_sentence_transformer,
    ) -> None:
        self._model_name = model_name
        self._model_loader = model_loader
        self._model: Any | None = None

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        """Return normalized local sentence embeddings for ``texts``."""
        if not texts:
            return []

        embeddings = self._get_model().encode(
            list(texts),
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    def _get_model(self) -> Any:
        if self._model is None:
            self._model = self._model_loader(self._model_name)
        return self._model
