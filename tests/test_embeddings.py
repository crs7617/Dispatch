"""Unit tests for the local sentence embedding provider."""

from __future__ import annotations

import builtins
from typing import Any
from unittest import TestCase, mock

from app.services.embeddings import LocalSentenceEmbeddingProvider, _load_sentence_transformer


class FakeEncodedEmbeddings:
    """Array-like test object returned by a fake sentence-transformers model."""

    def __init__(self, values: list[list[float]]) -> None:
        self._values = values

    def tolist(self) -> list[list[float]]:
        return self._values


class FakeSentenceTransformer:
    """Records encode calls without loading model weights."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def encode(self, texts: list[str], **kwargs: Any) -> FakeEncodedEmbeddings:
        self.calls.append((texts, kwargs))
        return FakeEncodedEmbeddings([[float(index), 1.0] for index in range(len(texts))])


class LocalSentenceEmbeddingProviderTests(TestCase):
    """Verify provider behavior without downloading a real model."""

    def test_empty_input_does_not_load_model(self) -> None:
        loader_calls: list[str] = []
        provider = LocalSentenceEmbeddingProvider(
            model_loader=lambda model_name: loader_calls.append(model_name)
        )

        self.assertEqual(provider.embed([]), [])
        self.assertEqual(loader_calls, [])

    def test_provider_loads_once_and_returns_embedding_lists(self) -> None:
        model = FakeSentenceTransformer()
        loader_calls: list[str] = []

        def loader(model_name: str) -> FakeSentenceTransformer:
            loader_calls.append(model_name)
            return model

        provider = LocalSentenceEmbeddingProvider(
            model_name="test-model", model_loader=loader
        )

        self.assertEqual(provider.embed(["first", "second"]), [[0.0, 1.0], [1.0, 1.0]])
        self.assertEqual(provider.embed(["third"]), [[0.0, 1.0]])
        self.assertEqual(loader_calls, ["test-model"])
        self.assertEqual(
            model.calls,
            [
                (
                    ["first", "second"],
                    {"convert_to_numpy": True, "normalize_embeddings": True},
                ),
                (
                    ["third"],
                    {"convert_to_numpy": True, "normalize_embeddings": True},
                ),
            ],
        )

    def test_missing_sentence_transformers_includes_install_hint(self) -> None:
        real_import = builtins.__import__

        def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "sentence_transformers":
                raise ModuleNotFoundError("No module named 'sentence_transformers'")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaisesRegex(
                ModuleNotFoundError,
                r"python -m pip install sentence-transformers",
            ):
                _load_sentence_transformer("test-model")
